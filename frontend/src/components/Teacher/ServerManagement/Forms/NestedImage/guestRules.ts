import {
    NestedGuest,
    NestedGuestNic,
    NestedMedia,
    NestedMediaFormat,
    NestedNetwork,
    NestedOsCatalogEntry,
    NestedOsGroup,
} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {parseCidr, parseIpv4} from "./networkRules";

// Client versions of NestedHostValidator._validate_guests/_validate_nics/_validate_credentials/_validate_capacity
// (api/core/compute/nested/validator.py) and the NestedGuestModel field limits. The API still enforces them.
export const NESTED_MAX_GUESTS = 8;
export const NESTED_MAX_NICS = 4;
export const NESTED_MAX_EXPOSURES = 8;
export const NESTED_MAX_PACKAGES = 50;
export const NESTED_PARENT_OVERHEAD_MB = 2048;
export const NESTED_MEDIA_MAX_BYTES = 21474836480;
export const GUEST_LIMITS = {
    vcpus: {min: 1, max: 8},
    memory_mb: {min: 256, max: 32768},
    disk_gb: {min: 2, max: 500},
    start_order: {min: 0, max: 99},
    start_delay_seconds: {min: 0, max: 600},
};
const MAX_SCRIPT_LENGTH = 65536;
const MIN_PASSWORD_LENGTH = 8;
// common/models/agoge.py SLUG15.
const GUEST_NAME_PATTERN = /^[a-z][a-z0-9-]{0,13}[a-z0-9]$/;
const ADMIN_USERNAME_PATTERN = /^[a-zA-Z][a-zA-Z0-9_.-]{0,19}$/;
const PRODUCT_KEY_PATTERN = /^([A-Z0-9]{5}-){4}[A-Z0-9]{5}$/;
const PACKAGE_PATTERN = /^[a-z0-9][a-z0-9+.-]{0,63}$/;
// NestedMediaCreateRequest.filename; a 422 on it carries no readable message, so check it before the POST.
const MEDIA_FILENAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._ ()+-]{0,199}$/;
// api/core/compute/nested/media.py media_format: longest first, so "disk.img.xz" is img.xz.
const MEDIA_FORMATS: NestedMediaFormat[] = (
    ['qcow2', 'raw', 'img.xz', 'img.bz2', 'tar.xz', 'iso', 'iso.gz', 'vmdk', 'vhd', 'vhdx', 'ova', 'zip', '7z'] as NestedMediaFormat[]
).sort((a, b) => b.length - a.length);

export interface GuestRuleContext {
    catalog: NestedOsCatalogEntry[];
    media: NestedMedia[];
}

export const guestErrorKey = (index: number, field: keyof NestedGuest | 'product_key'): string =>
    `guests.${index}.${field}`;

export const nicErrorKey = (guestIndex: number, nicIndex: number, field: keyof NestedGuestNic): string =>
    `guests.${guestIndex}.nics.${nicIndex}.${field}`;

export const catalogEntry = (catalog: NestedOsCatalogEntry[], osId: string): NestedOsCatalogEntry | undefined =>
    catalog.find(entry => entry.id === osId && entry.is_enabled);

export const isWindows = (entry: NestedOsCatalogEntry): boolean => entry.family === 'windows';

export const supportsPackages = (entry: NestedOsCatalogEntry): boolean =>
    entry.install_method === 'cloud_image' && entry.family === 'linux';

// Retail Windows installs need a key; evaluation media installs without one.
export const requiresProductKey = (entry: NestedOsCatalogEntry): boolean =>
    isWindows(entry) && entry.install_method === 'unattended_iso' && entry.eval_days === null;

export const mediaFormat = (filename: string): NestedMediaFormat | null => {
    const lower = filename.toLowerCase();
    return MEDIA_FORMATS.find(format => lower.endsWith(`.${format}`)) ?? null;
};

// Why a file cannot be uploaded for this entry, or "" when it can.
export const validateMediaFile = (file: {name: string; size: number}, entry: NestedOsCatalogEntry): string => {
    if (!MEDIA_FILENAME_PATTERN.test(file.name)) {
        return "Rename the file: use letters, numbers, spaces, and . _ ( ) + -, starting with a letter or number.";
    }
    const format = mediaFormat(file.name);
    if (!format || !entry.media_formats.includes(format)) {
        return `${entry.display_name} accepts ${entry.media_formats.join(", ")} media.`;
    }
    if (file.size > NESTED_MEDIA_MAX_BYTES) {
        return "The file is larger than the 20 GiB limit.";
    }
    return "";
};

// Completed uploads in a format the entry accepts, uploaded for this OS or for none in particular.
export const usableMedia = (media: NestedMedia[], entry: NestedOsCatalogEntry): NestedMedia[] =>
    media.filter(item => item.complete && entry.media_formats.includes(item.format)
        && (item.os_id === null || item.os_id === entry.id));

const meetsWindowsComplexity = (password: string): boolean => {
    const classes = [/[A-Z]/, /[a-z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(pattern => pattern.test(password)).length;
    return password.length >= MIN_PASSWORD_LENGTH && classes >= 3;
};

// Symbols limited to ones that survive XML, shells and URLs unescaped.
const PASSWORD_ALPHABETS = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789", "!#%+-=?@^_"];

const randomIndex = (size: number): number => {
    const value = new Uint32Array(1);
    crypto.getRandomValues(value);
    return value[0] % size;
};

// 16 characters with every class present, so it meets the Windows complexity rule.
export const generatePassword = (length = 16): string => {
    const all = PASSWORD_ALPHABETS.join("");
    const chars = PASSWORD_ALPHABETS.map(alphabet => alphabet[randomIndex(alphabet.length)]);
    while (chars.length < length) {
        chars.push(all[randomIndex(all.length)]);
    }
    for (let index = chars.length - 1; index > 0; index--) {
        const swap = randomIndex(index + 1);
        [chars[index], chars[swap]] = [chars[swap], chars[index]];
    }
    return chars.join("");
};

const GUEST_NAME_BASES: Record<NestedOsGroup, string> = {
    kali: "kali",
    linux: "linux",
    windows_client: "win",
    windows_server: "winsrv",
    appliance: "appliance",
};

// A free SLUG15 name based on the catalog entry's group, e.g. kali, kali-2, winsrv.
export const nextGuestName = (guests: NestedGuest[], entry: NestedOsCatalogEntry): string => {
    const base = GUEST_NAME_BASES[entry.group] ?? "guest";
    const names = new Set(guests.map(guest => guest.name));
    if (!names.has(base)) {
        return base;
    }
    let suffix = 2;
    while (names.has(`${base}-${suffix}`)) {
        suffix++;
    }
    return `${base}-${suffix}`;
};

export const newGuest = (
    entry: NestedOsCatalogEntry,
    guests: NestedGuest[],
    networks: NestedNetwork[],
): NestedGuest => ({
    name: nextGuestName(guests, entry),
    os_id: entry.id,
    media_id: null,
    vcpus: entry.default_vcpus,
    memory_mb: Math.max(entry.default_memory_mb, entry.min_memory_mb),
    disk_gb: Math.max(entry.default_disk_gb, entry.min_disk_gb),
    nics: [{network: networks[0]?.name ?? "", ip: null, expose: false}],
    admin_username: entry.default_username ?? (isWindows(entry) ? "Administrator" : "labadmin"),
    admin_password: generatePassword(),
    packages: [],
    post_install_script: null,
    console: true,
    autostart: true,
    start_order: guests.length,
    start_delay_seconds: 0,
});

const inRange = (value: number, limits: {min: number; max: number}): boolean =>
    Number.isInteger(value) && value >= limits.min && value <= limits.max;

const validateGuest = (
    guest: NestedGuest,
    index: number,
    entry: NestedOsCatalogEntry | undefined,
    productKey: string,
    context: GuestRuleContext,
    set: (key: string, message: string) => void,
) => {
    const key = (field: keyof NestedGuest | 'product_key') => guestErrorKey(index, field);
    if (!GUEST_NAME_PATTERN.test(guest.name)) {
        set(key("name"), "Use 2–15 lowercase letters, numbers, or hyphens, starting with a letter.");
    }
    if (!entry) {
        set(key("os_id"), "This OS is not in the catalog any more; remove the guest and add it again.");
    }
    const minMemory = Math.max(GUEST_LIMITS.memory_mb.min, entry?.min_memory_mb ?? 0);
    const minDisk = Math.max(GUEST_LIMITS.disk_gb.min, entry?.min_disk_gb ?? 0);
    if (!inRange(guest.vcpus, GUEST_LIMITS.vcpus)) {
        set(key("vcpus"), `Use ${GUEST_LIMITS.vcpus.min} to ${GUEST_LIMITS.vcpus.max} vCPUs.`);
    }
    if (!inRange(guest.memory_mb, {min: minMemory, max: GUEST_LIMITS.memory_mb.max})) {
        set(key("memory_mb"), `Use ${minMemory} to ${GUEST_LIMITS.memory_mb.max} MB.`);
    }
    if (!inRange(guest.disk_gb, {min: minDisk, max: GUEST_LIMITS.disk_gb.max})) {
        set(key("disk_gb"), `Use ${minDisk} to ${GUEST_LIMITS.disk_gb.max} GB.`);
    }
    if (!ADMIN_USERNAME_PATTERN.test(guest.admin_username)) {
        set(key("admin_username"), "Use up to 20 letters, numbers, underscores, dots, or hyphens, starting with a letter.");
    }
    if (guest.admin_password.length < MIN_PASSWORD_LENGTH) {
        set(key("admin_password"), `Use at least ${MIN_PASSWORD_LENGTH} characters.`);
    } else if (entry && isWindows(entry) && !meetsWindowsComplexity(guest.admin_password)) {
        set(key("admin_password"), "Windows needs three of: uppercase, lowercase, digits, symbols.");
    }
    if (entry && requiresProductKey(entry) && !PRODUCT_KEY_PATTERN.test(productKey.trim())) {
        set(key("product_key"), `${entry.display_name} needs a product key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX.`);
    }
    if (entry?.requires_upload) {
        const media = guest.media_id ? context.media.find(item => item.id === guest.media_id) : undefined;
        if (!guest.media_id) {
            set(key("media_id"), `${entry.display_name} needs uploaded media. Upload it or pick it from the library.`);
        } else if (!media || !media.complete) {
            set(key("media_id"), "That upload is not complete. Retry it or choose other media.");
        } else if (!entry.media_formats.includes(media.format)) {
            set(key("media_id"), `${entry.display_name} accepts ${entry.media_formats.join(", ")} media, not ${media.format}.`);
        }
    }
    if (guest.packages.length > 0 && entry && !supportsPackages(entry)) {
        set(key("packages"), "Packages are only supported for Linux cloud images.");
    } else if (guest.packages.length > NESTED_MAX_PACKAGES) {
        set(key("packages"), `Use at most ${NESTED_MAX_PACKAGES} packages.`);
    } else {
        const bad = guest.packages.find(name => !PACKAGE_PATTERN.test(name));
        if (bad !== undefined) {
            set(key("packages"), `${bad} is not a valid package name.`);
        }
    }
    if ((guest.post_install_script ?? "").length > MAX_SCRIPT_LENGTH) {
        set(key("post_install_script"), "The script is longer than 64 KB.");
    }
    if (!inRange(guest.start_order, GUEST_LIMITS.start_order)) {
        set(key("start_order"), `Use ${GUEST_LIMITS.start_order.min} to ${GUEST_LIMITS.start_order.max}.`);
    }
    if (!inRange(guest.start_delay_seconds, GUEST_LIMITS.start_delay_seconds)) {
        set(key("start_delay_seconds"), `Use ${GUEST_LIMITS.start_delay_seconds.min} to ${GUEST_LIMITS.start_delay_seconds.max} seconds.`);
    }
    if (guest.nics.length === 0 || guest.nics.length > NESTED_MAX_NICS) {
        set(key("nics"), `Give the guest 1 to ${NESTED_MAX_NICS} NICs.`);
    }
};

const validateNics = (
    guests: NestedGuest[],
    networks: NestedNetwork[],
    set: (key: string, message: string) => void,
) => {
    const staticIps = new Map<number, string>();
    let exposed = 0;
    guests.forEach((guest, guestIndex) => guest.nics.forEach((nic, nicIndex) => {
        const key = (field: keyof NestedGuestNic) => nicErrorKey(guestIndex, nicIndex, field);
        const network = networks.find(candidate => candidate.name === nic.network);
        if (!network) {
            set(key("network"), "Choose a network.");
        }
        if (nic.expose) {
            exposed++;
            if (nic.ip === null) {
                set(key("expose"), "An exposed NIC needs a static IP.");
            } else if (exposed > NESTED_MAX_EXPOSURES) {
                set(key("expose"), `At most ${NESTED_MAX_EXPOSURES} NICs may be exposed.`);
            }
        }
        if (nic.ip === null || !network) {
            return;
        }
        const address = parseIpv4(nic.ip.trim());
        const cidr = parseCidr(network.cidr);
        if (address === null) {
            set(key("ip"), "Enter an IPv4 address, or choose DHCP.");
            return;
        }
        if (cidr && (address <= cidr.network || address >= cidr.broadcast)) {
            set(key("ip"), `Use a host address inside ${network.cidr}.`);
            return;
        }
        if (staticIps.has(address)) {
            set(key("ip"), `${nic.ip} is already used by ${staticIps.get(address)}.`);
            return;
        }
        if (network.parent_address && address === parseIpv4(network.parent_address)) {
            set(key("ip"), `${nic.ip} is the parent's address on ${network.name}.`);
            return;
        }
        const dhcpStart = parseIpv4(network.dhcp_start ?? "");
        const dhcpEnd = parseIpv4(network.dhcp_end ?? "");
        if (network.dhcp && dhcpStart !== null && dhcpEnd !== null && dhcpStart <= address && address <= dhcpEnd) {
            set(key("ip"), `${nic.ip} is inside the DHCP range of ${network.name}.`);
            return;
        }
        staticIps.set(address, guest.name);
    }));
};

// The API checks both machine types; the build type is usually the bigger one, so name whichever fails first.
const validateCapacity = (
    guests: NestedGuest[],
    machineTypeNames: string[],
    machineTypes: ServerMachineTypes[],
): string => {
    const memory = guests.reduce((total, guest) => total + guest.memory_mb, 0) + NESTED_PARENT_OVERHEAD_MB;
    const vcpus = guests.reduce((total, guest) => total + guest.vcpus, 0);
    for (const name of machineTypeNames) {
        const type = machineTypes.find(candidate => candidate.name === name);
        if (!type) {
            continue;
        }
        if (memory > type.memory_mb) {
            return `${name} has ${type.memory_mb} MB, but the guests plus ${NESTED_PARENT_OVERHEAD_MB} MB parent overhead need ${memory} MB.`;
        }
        if (vcpus > 2 * type.guest_cpus) {
            return `${name} allows at most ${2 * type.guest_cpus} guest vCPUs; the guests ask for ${vcpus}.`;
        }
    }
    return "";
};

export interface GuestsInput {
    guests: NestedGuest[];
    networks: NestedNetwork[];
    product_keys: Record<string, string>;
    build_machine_type: string;
    machine_type: string;
}

// Errors keyed by guestErrorKey / nicErrorKey, plus `guests` for the list as a whole. One message per field.
export const validateGuests = (
    input: GuestsInput,
    context: GuestRuleContext,
    machineTypes: ServerMachineTypes[],
): Record<string, string> => {
    const errors: Record<string, string> = {};
    const set = (key: string, message: string) => {
        if (!errors[key]) {
            errors[key] = message;
        }
    };
    const {guests, networks} = input;
    if (guests.length === 0) {
        set("guests", "Add at least one guest.");
    } else if (guests.length > NESTED_MAX_GUESTS) {
        set("guests", `Use at most ${NESTED_MAX_GUESTS} guests.`);
    }
    const seen = new Set<string>();
    guests.forEach((guest, index) => {
        if (seen.has(guest.name)) {
            set(guestErrorKey(index, "name"), "Another guest already uses this name.");
        }
        seen.add(guest.name);
        validateGuest(
            guest, index, catalogEntry(context.catalog, guest.os_id), input.product_keys[guest.name] ?? "", context, set,
        );
    });
    validateNics(guests, networks, set);
    const capacity = validateCapacity(guests, [input.build_machine_type, input.machine_type], machineTypes);
    if (capacity) {
        set("guests", capacity);
    }
    return errors;
};

// Product keys are keyed by guest name, so renames and removals carry them along.
export const renameProductKey = (
    productKeys: Record<string, string>,
    oldName: string,
    newName: string,
): Record<string, string> => {
    if (oldName === newName || !(oldName in productKeys)) {
        return productKeys;
    }
    const {[oldName]: key, ...rest} = productKeys;
    return {...rest, [newName]: key};
};

export const dropProductKey = (productKeys: Record<string, string>, name: string): Record<string, string> =>
    Object.fromEntries(Object.entries(productKeys).filter(([guest]) => guest !== name));

// The picker's chips: how the OS gets installed, whether media must be uploaded, evaluation limits, no agent.
export const osChipLabels = (entry: NestedOsCatalogEntry): string[] => {
    const labels = [entry.install_method === 'manual_iso' ? "Manual install" : "Auto install"];
    if (entry.requires_upload) {
        labels.push("Upload required");
    }
    if (entry.eval_days !== null) {
        labels.push(`Eval ${entry.eval_days} days`);
    }
    if (!entry.agent) {
        labels.push("No agent");
    }
    return labels;
};
