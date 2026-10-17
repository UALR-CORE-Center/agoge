import {
    NestedGuest,
    NestedImageCreateRequest,
    NestedInstallMethod,
    NestedOsCatalogEntry,
} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {catalogEntry, isWindows, NESTED_PARENT_OVERHEAD_MB, requiresProductKey} from "./guestRules";
import {effectiveDiskSize, nestedMinDiskSize, NestedWizardState} from "./nestedWizardState";

// Mirrors common/constants/nested.py.
export const NESTED_CONSOLE_BASE_PORT = 5901;
export const NESTED_BUILD_MAX_MINUTES = 240;

export interface NestedExposure {
    guest: string;
    nic: number;
    network: string;
    ip: string | null;
}

export interface NestedConsole {
    guest: string;
    port: number;
}

// NestedHostValidator.derive: alias slots follow guest order, then NIC order. The list index is the slot.
export const deriveExposures = (guests: NestedGuest[]): NestedExposure[] =>
    guests.flatMap(guest => guest.nics.flatMap((nic, index) =>
        nic.expose ? [{guest: guest.name, nic: index, network: nic.network, ip: nic.ip}] : []));

// NestedHostValidator.derive: console ports follow guest order among guests with a console.
export const deriveConsoles = (guests: NestedGuest[]): NestedConsole[] =>
    guests.filter(guest => guest.console).map((guest, slot) => ({guest: guest.name, port: NESTED_CONSOLE_BASE_PORT + slot}));

// A slot can only change by reordering guests, so an exposure can pass a neighbour only on another guest.
// Two exposures on one guest keep their NIC order, which also fixes the interface order inside the guest.
export const canMoveExposure = (exposures: NestedExposure[], index: number, delta: -1 | 1): boolean => {
    const target = index + delta;
    return target >= 0 && target < exposures.length && exposures[target].guest !== exposures[index].guest;
};

// Moves the exposure's guest just past the guest of the neighbouring exposure. All of that guest's
// exposures move together, and console ports, which also follow guest order, move with them.
export const moveExposure = (
    guests: NestedGuest[],
    exposures: NestedExposure[],
    index: number,
    delta: -1 | 1,
): NestedGuest[] => {
    if (!canMoveExposure(exposures, index, delta)) {
        return guests;
    }
    const moving = guests.find(guest => guest.name === exposures[index].guest);
    if (!moving) {
        return guests;
    }
    const rest = guests.filter(guest => guest !== moving);
    const anchor = rest.findIndex(guest => guest.name === exposures[index + delta].guest);
    if (anchor < 0) {
        return guests;
    }
    const position = delta < 0 ? anchor : anchor + 1;
    return [...rest.slice(0, position), moving, ...rest.slice(position)];
};

export interface CapacityMeter {
    label: string;
    used: number;
    available: number;
    unit: string;
}

const meter = (label: string, used: number, available: number, unit: string): CapacityMeter =>
    ({label, used, available, unit});

// The checks of NestedHostValidator._validate_capacity and min_disk_size, as used/available pairs.
export const capacityMeters = (state: NestedWizardState, machineTypes: ServerMachineTypes[]): CapacityMeter[] => {
    const memory = state.guests.reduce((total, guest) => total + guest.memory_mb, 0) + NESTED_PARENT_OVERHEAD_MB;
    const vcpus = state.guests.reduce((total, guest) => total + guest.vcpus, 0);
    const meters: CapacityMeter[] = [];
    const roles: [string, string][] = [["Build", state.build_machine_type], ["Lab", state.machine_type]];
    for (const [role, name] of roles) {
        const type = machineTypes.find(candidate => candidate.name === name);
        if (!type) {
            continue;
        }
        meters.push(meter(`${role} RAM (${name})`, memory, type.memory_mb, "MB"));
        meters.push(meter(`${role} vCPU (${name})`, vcpus, 2 * type.guest_cpus, "vCPU"));
    }
    meters.push(meter("Disk", nestedMinDiskSize(state.guests), effectiveDiskSize(state), "GB"));
    return meters;
};

export const meterPercent = (value: CapacityMeter): number =>
    value.available > 0 ? Math.min(100, Math.round(100 * value.used / value.available)) : 100;

// Rough minutes per install, from the reference build of 2026-10-17 (Working Notes 14–23): a cloud image
// is customized and booted in minutes, Windows Setup plus virtio drivers takes the longest, and a manual
// install only boots the ISO; the instructor's console work happens after the build.
const INSTALL_MINUTES: Record<NestedInstallMethod, number> = {
    cloud_image: 10,
    disk_image: 15,
    unattended_iso: 30,
    manual_iso: 5,
};
// Provisioning the parent and installing libvirt, before the first guest starts.
const PARENT_SETUP_MINUTES = 10;
// The builder installs at most two guests at a time.
const PARALLEL_INSTALLS = 2;

// Schedules the installs in start_order onto two slots and returns the finishing time, rounded up to 5.
export const estimateBuildMinutes = (guests: NestedGuest[], catalog: NestedOsCatalogEntry[]): number => {
    const slots = Array<number>(PARALLEL_INSTALLS).fill(0);
    [...guests]
        .sort((a, b) => a.start_order - b.start_order)
        .forEach(guest => {
            const entry = catalogEntry(catalog, guest.os_id);
            const minutes = INSTALL_MINUTES[entry?.install_method ?? 'unattended_iso'];
            const slot = slots.indexOf(Math.min(...slots));
            slots[slot] += minutes;
        });
    const total = PARENT_SETUP_MINUTES + Math.max(...slots);
    return Math.ceil(total / 5) * 5;
};

export interface ReviewWarning {
    guest: string | null;
    message: string;
}

export const reviewWarnings = (
    state: NestedWizardState,
    catalog: NestedOsCatalogEntry[],
    mediaNames: Record<string, string>,
): ReviewWarning[] => {
    const warnings: ReviewWarning[] = [];
    state.guests.forEach(guest => {
        const entry = catalogEntry(catalog, guest.os_id);
        if (!entry) {
            return;
        }
        const add = (message: string) => warnings.push({guest: guest.name, message: `${guest.name}: ${message}`});
        if (entry.eval_days !== null) {
            add(`${entry.display_name} is an evaluation that expires ${entry.eval_days} days after install. ` +
                `Rearm it with slmgr /rearm or rebuild the image before then.`);
        }
        if (entry.install_method === 'manual_iso') {
            add(guest.console
                ? `${entry.display_name} is a manual install. Finish it in the console before Check In.`
                : `${entry.display_name} is a manual install, but its console is off, so there is no way to install it.`);
        }
        if (!entry.agent) {
            add(`${entry.display_name} has no guest agent, so CTF flags use the offline driver (written while the ` +
                `guest is shut off)${guest.post_install_script ? " and its post-install script will not run" : ""}.`);
        }
        if (isWindows(entry) && entry.requires_upload) {
            const media = guest.media_id ? mediaNames[guest.media_id] ?? guest.media_id : "no media";
            add(`${entry.display_name} installs from your uploaded media (${media}). ` +
                `Agoge never downloads or redistributes this Windows media.`);
        }
    });
    const minutes = estimateBuildMinutes(state.guests, catalog);
    if (minutes > NESTED_BUILD_MAX_MINUTES) {
        warnings.push({
            guest: null,
            message: `The estimated build of ${minutes} minutes is over the ${NESTED_BUILD_MAX_MINUTES}-minute limit, ` +
                `after which the build is failed. Use fewer or smaller guests.`,
        });
    }
    return warnings;
};

// Builds the create request from wizard state. Product keys are sent only for guests that need one,
// because the API refuses a key for a guest that does not exist and the builder has no use for others.
export const toCreateRequest = (
    state: NestedWizardState,
    catalog: NestedOsCatalogEntry[],
): NestedImageCreateRequest => {
    const needsKey = new Set(state.guests
        .filter(guest => {
            const entry = catalogEntry(catalog, guest.os_id);
            return entry !== undefined && requiresProductKey(entry);
        })
        .map(guest => guest.name));
    return {
        server_name: state.server_name,
        description: state.description.trim(),
        labels: [...state.labels],
        machine_type: state.machine_type,
        disk_size: state.disk_size,
        username: state.username,
        ssh_key: state.ssh_key,
        nested: {
            parent_os: state.parent_os,
            build_machine_type: state.build_machine_type,
            networks: state.networks,
            guests: state.guests,
        },
        product_keys: Object.fromEntries(Object.entries(state.product_keys).filter(([guest]) => needsKey.has(guest))),
    };
};
