import {NestedGuest, NestedNetwork, NestedParentOs} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {catalogEntry, GuestRuleContext, NESTED_MEDIA_MAX_BYTES, validateGuests} from "./guestRules";
import {validateNetworks} from "./networkRules";

// Mirrors common/constants/nested.py; the API applies the same disk rule (NestedHostValidator.min_disk_size).
export const NESTED_PARENT_BASE_DISK_GB = 20;
export const NESTED_BUILD_SCRATCH_GB = 12;
export const NESTED_MAX_DISK_GB = 1000;
export const NESTED_DEFAULT_BUILD_MACHINE_TYPE = "n2-standard-8";
export const NESTED_PARENT_OS_OPTIONS: {value: NestedParentOs; label: string}[] = [
    {value: "debian-12", label: "Debian 12 (bookworm)"},
    {value: "debian-13", label: "Debian 13 (trixie)"},
];

export enum NestedWizardSteps {
    Host = "Host",
    Networks = "Networks",
    Guests = "Guests",
    Access = "Access",
    Review = "Review",
}

export const NESTED_WIZARD_STEPS: NestedWizardSteps[] = Object.values(NestedWizardSteps);

export interface NestedWizardState {
    server_name: string;
    description: string;
    labels: string[];
    parent_os: NestedParentOs;
    build_machine_type: string;
    // What lab servers built from the image default to.
    machine_type: string;
    // null = the computed minimum; the instructor may only raise it.
    disk_size: number | null;
    username: string;
    ssh_key: string;
    networks: NestedNetwork[];
    guests: NestedGuest[];
    // guest -> product key; sent once with the create request and never persisted.
    product_keys: Record<string, string>;
}

export type HostField =
    'server_name' | 'description' | 'parent_os' | 'build_machine_type' | 'machine_type' |
    'disk_size' | 'username' | 'ssh_key';

export type StepErrors = Partial<Record<string, string>>;

export const defaultNestedNetwork = (): NestedNetwork => ({
    name: "lab",
    cidr: "192.168.100.0/24",
    mode: "nat",
    parent_address: "192.168.100.1",
    dhcp: true,
    dhcp_start: "192.168.100.100",
    dhcp_end: "192.168.100.199",
});

export const initialNestedWizardState = (): NestedWizardState => ({
    server_name: "",
    description: "",
    labels: [],
    parent_os: "debian-12",
    build_machine_type: NESTED_DEFAULT_BUILD_MACHINE_TYPE,
    machine_type: "",
    disk_size: null,
    username: "",
    ssh_key: "",
    networks: [defaultNestedNetwork()],
    guests: [],
    product_keys: {},
});

const GIB = 1024 ** 3;

// NestedHostValidator.media_sizes: bytes of each distinct medium, keyed the way builder.sh fetch_media caches it,
// so guests sharing a medium count it once. A size the wizard cannot know reserves the upload limit, as the API does.
export const nestedMediaSizes = (guests: NestedGuest[], context: GuestRuleContext): Record<string, number> => {
    const sizes: Record<string, number> = {};
    for (const guest of guests) {
        // nested_manifest._media_source: a guest's media_id wins over the entry's media_url.
        if (guest.media_id) {
            const medium = context.media.find(item => item.id === guest.media_id);
            sizes[medium?.sha256 || `upload-${guest.media_id}`] = medium ? medium.size_bytes : NESTED_MEDIA_MAX_BYTES;
        } else {
            const entry = catalogEntry(context.catalog, guest.os_id);
            sizes[entry?.media_sha256 || guest.os_id] = entry?.media_size_bytes || NESTED_MEDIA_MAX_BYTES;
        }
    }
    return sizes;
};

// NestedHostValidator.min_disk_size: every medium stays cached on the parent disk until finalize, so each is
// reserved on top of the scratch space.
export const nestedMinDiskSize = (guests: NestedGuest[], context: GuestRuleContext): number => {
    const mediaGb = Object.values(nestedMediaSizes(guests, context))
        .reduce((total, size) => total + Math.ceil(size / GIB), 0);
    return NESTED_PARENT_BASE_DISK_GB + guests.reduce((total, guest) => total + guest.disk_gb, 0)
        + NESTED_BUILD_SCRATCH_GB + mediaGb;
};

export const effectiveDiskSize = (state: NestedWizardState, context: GuestRuleContext): number =>
    state.disk_size ?? nestedMinDiskSize(state.guests, context);

// ComputeImage._validate_new_name: 54 characters leaves room for the longest snapshot suffix.
const SERVER_NAME_PATTERN = /^[a-z](?:[a-z0-9-]{0,52}[a-z0-9])?$/;
const RESERVED_SERVER_NAMES = ["agoge", "google", "nested"];
// ComputeImage._validate_username.
const USERNAME_PATTERN = /^[a-zA-Z0-9_]([a-zA-Z0-9_.-]{0,18}[a-zA-Z0-9_]?)?$/;
const SSH_KEY_PATTERN = /^(ssh-[a-z0-9-]+|ecdsa-sha2-[a-z0-9-]+|sk-[a-z0-9@.-]+) [A-Za-z0-9+/=]+( .*)?$/;

export const validateNestedServerName = (name: string): string => {
    if (!SERVER_NAME_PATTERN.test(name)) {
        return "Use 1–54 lowercase letters, numbers, or hyphens. Start with a letter and end with a letter or number.";
    }
    if (name.startsWith("image-") || RESERVED_SERVER_NAMES.includes(name)) {
        return "Choose a name without the image- prefix; agoge, google, and nested are reserved.";
    }
    return "";
};

const validateMachineType = (value: string, machineTypes: ServerMachineTypes[], label: string): string => {
    if (!value) {
        return `Choose a ${label}.`;
    }
    // The list comes from ?nested=true, so anything outside it is not nested-capable (a fixed N1/N2/N4 set).
    if (machineTypes.length > 0 && !machineTypes.some(type => type.name === value)) {
        return `${value} is not available for nested images; choose an N1, N2, or N4 standard type.`;
    }
    return "";
};

export const validateHostStep = (
    state: NestedWizardState,
    machineTypes: ServerMachineTypes[],
    context: GuestRuleContext,
): StepErrors => {
    const errors: StepErrors = {};
    const nameError = validateNestedServerName(state.server_name);
    if (nameError) {
        errors.server_name = nameError;
    }
    const description = state.description.trim();
    if (!description) {
        errors.description = "Enter a description.";
    } else if (description.length > 200) {
        errors.description = "Use at most 200 characters.";
    }
    if (!NESTED_PARENT_OS_OPTIONS.some(option => option.value === state.parent_os)) {
        errors.parent_os = "Choose a parent OS.";
    }
    const buildError = validateMachineType(state.build_machine_type, machineTypes, "build machine type");
    if (buildError) {
        errors.build_machine_type = buildError;
    }
    const labError = validateMachineType(state.machine_type, machineTypes, "lab machine type");
    if (labError) {
        errors.machine_type = labError;
    }
    if (state.disk_size !== null) {
        const minimum = nestedMinDiskSize(state.guests, context);
        if (!Number.isInteger(state.disk_size) || state.disk_size < minimum || state.disk_size > NESTED_MAX_DISK_GB) {
            errors.disk_size = `Use a whole number from ${minimum} to ${NESTED_MAX_DISK_GB} GB.`;
        }
    }
    if (!USERNAME_PATTERN.test(state.username.trim())) {
        errors.username = "Use up to 20 letters, numbers, underscores, dots, or hyphens, starting with a letter, number, or underscore.";
    }
    const sshKey = state.ssh_key.trim();
    if (!sshKey) {
        errors.ssh_key = "Paste the public key for the parent's user.";
    } else if (!SSH_KEY_PATTERN.test(sshKey)) {
        errors.ssh_key = "Paste an OpenSSH public key, e.g. ssh-ed25519 AAAA… user@host.";
    }
    return errors;
};

export const validateNetworksStep = (state: NestedWizardState): StepErrors => validateNetworks(state.networks);

export const EMPTY_GUEST_CONTEXT: GuestRuleContext = {catalog: [], media: []};

// Guest rules need the OS catalog and the media library; with them still loading, every guest reads as
// "not in the catalog", which keeps Next from passing a step it cannot check yet.
export const validateGuestsStep = (
    state: NestedWizardState,
    machineTypes: ServerMachineTypes[],
    context: GuestRuleContext,
): StepErrors => validateGuests(state, context, machineTypes);

export const validateStep = (
    step: NestedWizardSteps,
    state: NestedWizardState,
    machineTypes: ServerMachineTypes[],
    context: GuestRuleContext = EMPTY_GUEST_CONTEXT,
): StepErrors => {
    switch (step) {
        case NestedWizardSteps.Host:
            return validateHostStep(state, machineTypes, context);
        case NestedWizardSteps.Networks:
            return validateNetworksStep(state);
        case NestedWizardSteps.Guests:
            return validateGuestsStep(state, machineTypes, context);
        case NestedWizardSteps.Access:
            return {};
        case NestedWizardSteps.Review: {
            const invalid = firstInvalidStep(NESTED_WIZARD_STEPS.length - 1, state, machineTypes, context);
            return invalid === null ? {} : {review: `Fix the ${NESTED_WIZARD_STEPS[invalid]} step first.`};
        }
    }
};

export const hasErrors = (errors: StepErrors): boolean => Object.keys(errors).length > 0;

// The first step before `before` whose rules fail, or null.
export const firstInvalidStep = (
    before: number,
    state: NestedWizardState,
    machineTypes: ServerMachineTypes[],
    context: GuestRuleContext = EMPTY_GUEST_CONTEXT,
): number | null => {
    for (let index = 0; index < before; index++) {
        if (hasErrors(validateStep(NESTED_WIZARD_STEPS[index], state, machineTypes, context))) {
            return index;
        }
    }
    return null;
};

// Non-linear, but forward only through valid steps: going back is always allowed, and going forward
// lands on the first invalid step before the target. That step may lie behind the current one (adding a guest
// raises the minimum disk size, which can invalidate the Host step), so the instructor is taken to its errors.
export const resolveNavigation = (
    from: number,
    to: number,
    state: NestedWizardState,
    machineTypes: ServerMachineTypes[],
    context: GuestRuleContext = EMPTY_GUEST_CONTEXT,
): number => {
    if (to <= from) {
        return to;
    }
    return firstInvalidStep(to, state, machineTypes, context) ?? to;
};
