import {AgogeImage} from "../../../../../services/Server/image.model";
import {
    NestedBuildPhase,
    NestedBuildStatus,
    NestedGuestStatus,
    NestedHostSpec,
    NestedOsCatalogEntry,
} from "../../../../../services/Server/nested.model";

type ChipColor = 'default' | 'info' | 'success' | 'warning' | 'error';

// Mirrors common/constants/nested.py: NESTED_FINALIZE_TIMEOUT_SECONDS + 900.
export const NESTED_FINALIZE_STALE_SECONDS = 360 + 900;

// The phases in which the parent is still working; the list polls GET …/nested-build/ only for these.
export const NESTED_ACTIVE_PHASES: NestedBuildPhase[] = ['queued', 'provisioning', 'building', 'finalizing'];

const PHASE_LABELS: Record<NestedBuildPhase, {label: string, color: ChipColor}> = {
    queued: {label: 'Queued', color: 'default'},
    provisioning: {label: 'Provisioning', color: 'info'},
    building: {label: 'Building guests', color: 'info'},
    ready: {label: 'Guests ready', color: 'success'},
    finalizing: {label: 'Finalizing', color: 'info'},
    finalized: {label: 'Finalized', color: 'success'},
    failed: {label: 'Build failed', color: 'error'},
};

const GUEST_STATUS_LABELS: Record<NestedGuestStatus, {label: string, color: ChipColor}> = {
    pending: {label: 'Pending', color: 'default'},
    downloading: {label: 'Downloading', color: 'info'},
    installing: {label: 'Installing', color: 'info'},
    post_install: {label: 'Post-install', color: 'info'},
    manual: {label: 'Manual install', color: 'warning'},
    ready: {label: 'Ready', color: 'success'},
    failed: {label: 'Failed', color: 'error'},
};

export const nestedPhaseLabel = (phase: NestedBuildPhase) => PHASE_LABELS[phase] ?? {label: phase, color: 'default'};

export const nestedGuestStatusLabel = (status: NestedGuestStatus) =>
    GUEST_STATUS_LABELS[status] ?? {label: status, color: 'default'};

const timeOf = (value: string | null | undefined): number | null => {
    if (!value) {
        return null;
    }
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
};

// is_stale_finalize: a `finalizing` phase no live invocation still owns. The API then lets Check In
// finalize again, so the button must not stay disabled. A missing updated_at counts as stale, as there.
export const isStaleFinalize = (build: NestedBuildStatus | null | undefined, now: number = Date.now()): boolean => {
    if (build?.phase !== 'finalizing') {
        return false;
    }
    const updated = timeOf(build.updated_at);
    return updated === null || now - updated > NESTED_FINALIZE_STALE_SECONDS * 1000;
};

export const isNestedBuildActive = (build: NestedBuildStatus | null | undefined, now: number = Date.now()): boolean =>
    !!build && NESTED_ACTIVE_PHASES.includes(build.phase) && !isStaleFinalize(build, now);

// Check In is refused (409) while the parent is still provisioning, building or finalizing. A queued
// build has no guests yet, so imaging it would publish an empty host.
export const isNestedCheckInBlocked = (image: AgogeImage, now: number = Date.now()): boolean =>
    !!image.nested && isNestedBuildActive(image.nested_build, now);

// The list record and the polled status can each be the fresher one: the poll refreshes guest attributes,
// but after a later Check In the list shows `finalizing` while the last poll still says `ready`.
export const latestBuildStatus = (
    listed: NestedBuildStatus | null | undefined,
    polled: NestedBuildStatus | null | undefined,
): NestedBuildStatus | null => {
    if (!polled) {
        return listed ?? null;
    }
    if (!listed) {
        return polled;
    }
    return (timeOf(polled.updated_at) ?? 0) >= (timeOf(listed.updated_at) ?? 0) ? polled : listed;
};

export const withPolledBuildStatus = (image: AgogeImage, polled: Record<string, NestedBuildStatus>): AgogeImage => {
    if (!image.nested || !polled[image.name]) {
        return image;
    }
    return {...image, nested_build: latestBuildStatus(image.nested_build, polled[image.name])};
};

// Drops polled entries the list no longer needs: the image is gone, or its build has settled and the list
// record (which the poll's refresh also writes) has caught up. Otherwise a stale polled `ready` would
// mask a later record, e.g. one re-created as `queued` with no updated_at, and polling would never resume.
export const prunePolledBuilds = (
    images: AgogeImage[],
    polled: Record<string, NestedBuildStatus>,
    now: number = Date.now(),
): Record<string, NestedBuildStatus> => {
    const next: Record<string, NestedBuildStatus> = {};
    for (const image of images) {
        const entry = polled[image.name];
        if (!entry || !image.nested) {
            continue;
        }
        const listed = image.nested_build;
        const listedTime = timeOf(listed?.updated_at);
        const caughtUp = !listed || listedTime === null || listedTime >= (timeOf(entry.updated_at) ?? 0);
        if (isNestedBuildActive(latestBuildStatus(listed, entry), now) || !caughtUp) {
            next[image.name] = entry;
        }
    }
    return Object.keys(next).length === Object.keys(polled).length ? polled : next;
};

export interface NestedGuestDetail {
    name: string;
    os_id: string;
    status: NestedGuestStatus;
    ips: {network: string, ip: string | null}[];
    alias_slots: number[];
    admin_username: string;
    admin_password: string;
    console_port: number | null;
    vnc_password: string | null;
}

export const nestedGuestDetails = (spec: NestedHostSpec, build: NestedBuildStatus | null | undefined): NestedGuestDetail[] =>
    spec.guests.map(guest => ({
        name: guest.name,
        os_id: guest.os_id,
        status: build?.guests[guest.name] ?? 'pending',
        ips: guest.nics.map(nic => ({network: nic.network, ip: nic.ip})),
        alias_slots: spec.exposures.flatMap(([name], slot) => name === guest.name ? [slot] : []),
        admin_username: guest.admin_username,
        admin_password: guest.admin_password,
        console_port: spec.console_ports[guest.name] ?? null,
        vnc_password: spec.vnc_passwords[guest.name] ?? null,
    }));

export interface NestedTunnel {
    guest: string;
    kind: 'console' | 'rdp' | 'ssh';
    // Where the client connects once the tunnel is up.
    local_port: number;
    // host:port the parent forwards to, as PuTTY's Tunnels page asks for it.
    destination: string;
    command: string;
}

const RDP_PORT = 3389;
const SSH_PORT = 22;
// Local ends for guest tunnels, offset per guest so several can be open at once. 2222 keeps clear of a
// local sshd on 22, and 13389 of a local RDP service on 3389.
const LOCAL_RDP_BASE = 13389;
const LOCAL_SSH_BASE = 2222;

// null when the catalog cannot say (it failed to load, or the entry was removed since the build).
export const guestFamily = (osId: string, catalog: NestedOsCatalogEntry[]): NestedOsCatalogEntry['family'] | null =>
    catalog.find(item => item.id === osId)?.family ?? null;

// The guest's first address the parent can route to: a NIC on a network the parent has an address on, at its
// static IP or the address the builder reported (a DHCP lease).
const reachableAddress = (
    spec: NestedHostSpec,
    guest: NestedHostSpec['guests'][number],
    addresses: Record<string, string>,
): string | null => {
    for (const [index, nic] of guest.nics.entries()) {
        const network = spec.networks.find(item => item.name === nic.network);
        const ip = nic.ip || addresses[String(index)];
        if (network?.parent_address && ip) {
            return ip;
        }
    }
    return null;
};

// Template servers have no alias IPs, so guests are reached through the parent: a console on its VNC port
// on the parent, a Windows guest on RDP 3389 and a Linux guest on SSH 22 at its address. An appliance has
// only its console, and a guest whose family is unknown (the catalog is still loading) gets no guess.
export const nestedTunnels = (
    spec: NestedHostSpec,
    target: string,
    catalog: NestedOsCatalogEntry[],
    guestAddresses: Record<string, Record<string, string>> = {},
): NestedTunnel[] => {
    const consoles: NestedTunnel[] = Object.entries(spec.console_ports)
        .sort(([, a], [, b]) => a - b)
        .map(([guest, port]) => ({
            guest,
            kind: 'console',
            local_port: port,
            destination: `localhost:${port}`,
            command: `ssh -L ${port}:localhost:${port} ${target}`,
        }));
    const guests: NestedTunnel[] = spec.guests.flatMap((guest, index) => {
        const family = guestFamily(guest.os_id, catalog);
        const ip = reachableAddress(spec, guest, guestAddresses[guest.name] ?? {});
        if ((family !== 'windows' && family !== 'linux') || !ip) {
            return [];
        }
        const kind = family === 'windows' ? 'rdp' : 'ssh';
        const localPort = (kind === 'rdp' ? LOCAL_RDP_BASE : LOCAL_SSH_BASE) + index;
        const remotePort = kind === 'rdp' ? RDP_PORT : SSH_PORT;
        const destination = `${ip}:${remotePort}`;
        return [{guest: guest.name, kind, local_port: localPort, destination, command: `ssh -L ${localPort}:${destination} ${target}`}];
    });
    return [...consoles, ...guests];
};
