import {NestedGuest, NestedNetwork} from "../../../../../services/Server/nested.model";

// Client versions of NestedHostValidator._validate_networks (api/core/compute/nested/validator.py). The API
// still enforces them; these keep the instructor on the Networks step instead of failing at submit.
export const NESTED_MAX_NETWORKS = 8;
const MIN_PREFIX = 16;
const MAX_PREFIX = 29;
// common/models/agoge.py SLUG15.
const NETWORK_NAME_PATTERN = /^[a-z][a-z0-9-]{0,13}[a-z0-9]$/;

export interface Ipv4Cidr {
    network: number;
    prefix: number;
    broadcast: number;
}

const RFC1918: Ipv4Cidr[] = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"].map(cidr => parseCidr(cidr)!);
// Link-local carries the metadata server; 192.168.122.0/24 is libvirt's default network on the parent.
const RESERVED: Ipv4Cidr[] = ["169.254.0.0/16", "192.168.122.0/24"].map(cidr => parseCidr(cidr)!);

// Dotted quad to an unsigned 32-bit number, or null. Leading zeros are rejected, as Python's ipaddress does.
export function parseIpv4(value: string): number | null {
    const parts = value.split(".");
    if (parts.length !== 4 || !parts.every(part => /^(0|[1-9][0-9]{0,2})$/.test(part) && Number(part) <= 255)) {
        return null;
    }
    return parts.reduce((total, part) => total * 256 + Number(part), 0);
}

export const formatIpv4 = (address: number): string =>
    [24, 16, 8, 0].map(shift => Math.floor(address / 2 ** shift) % 256).join(".");

// A strict network address in CIDR form (host bits zero), or null. Prefix limits are checked separately.
export function parseCidr(value: string): Ipv4Cidr | null {
    const match = /^([0-9.]+)\/([0-9]{1,2})$/.exec(value.trim());
    if (!match) {
        return null;
    }
    const address = parseIpv4(match[1]);
    const prefix = Number(match[2]);
    if (address === null || prefix > 32) {
        return null;
    }
    const size = 2 ** (32 - prefix);
    if (address % size !== 0) {
        return null;
    }
    return {network: address, prefix, broadcast: address + size - 1};
}

const contains = (cidr: Ipv4Cidr, address: number): boolean => cidr.network <= address && address <= cidr.broadcast;

export const cidrsOverlap = (a: Ipv4Cidr, b: Ipv4Cidr): boolean =>
    a.network <= b.broadcast && b.network <= a.broadcast;

const cidrText = (cidr: Ipv4Cidr): string => `${formatIpv4(cidr.network)}/${cidr.prefix}`;

export const networkErrorKey = (index: number, field: keyof NestedNetwork): string => `networks.${index}.${field}`;

type AddressField = 'parent_address' | 'dhcp_start' | 'dhcp_end';
const ADDRESS_LABELS: Record<AddressField, string> = {
    parent_address: "Parent address",
    dhcp_start: "DHCP start",
    dhcp_end: "DHCP end",
};

// Errors keyed by networkErrorKey, plus `networks` for the list as a whole. One message per field.
export const validateNetworks = (networks: NestedNetwork[]): Record<string, string> => {
    const errors: Record<string, string> = {};
    const set = (key: string, message: string) => {
        if (!errors[key]) {
            errors[key] = message;
        }
    };
    if (networks.length === 0) {
        set("networks", "Add at least one network.");
    } else if (networks.length > NESTED_MAX_NETWORKS) {
        set("networks", `Use at most ${NESTED_MAX_NETWORKS} networks.`);
    }

    const parsed: (Ipv4Cidr | null)[] = [];
    networks.forEach((network, index) => {
        const key = (field: keyof NestedNetwork) => networkErrorKey(index, field);
        if (!NETWORK_NAME_PATTERN.test(network.name)) {
            set(key("name"), "Use 2–15 lowercase letters, numbers, or hyphens, starting with a letter.");
        } else if (networks.findIndex(other => other.name === network.name) !== index) {
            set(key("name"), `Another network is already named ${network.name}.`);
        }

        const cidr = parseCidr(network.cidr);
        parsed.push(null);
        if (!cidr) {
            set(key("cidr"), "Enter a network address in CIDR form, e.g. 192.168.100.0/24.");
        } else if (!RFC1918.some(range => range.prefix <= cidr.prefix && contains(range, cidr.network))) {
            set(key("cidr"), "Use a private range: 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16.");
        } else if (cidr.prefix < MIN_PREFIX || cidr.prefix > MAX_PREFIX) {
            set(key("cidr"), `The prefix must be /${MIN_PREFIX} to /${MAX_PREFIX}.`);
        } else {
            const reserved = RESERVED.find(range => cidrsOverlap(cidr, range));
            const otherIndex = parsed.findIndex(other => other !== null && cidrsOverlap(cidr, other));
            if (reserved) {
                set(key("cidr"), `Overlaps the reserved range ${cidrText(reserved)}.`);
            } else if (otherIndex >= 0) {
                set(key("cidr"), `Overlaps network ${networks[otherIndex].name || otherIndex + 1} (${networks[otherIndex].cidr}).`);
            } else {
                parsed[index] = cidr;
            }
        }

        // Addresses are checked against the range only once the range itself is valid.
        const addresses: Partial<Record<AddressField, number>> = {};
        (Object.keys(ADDRESS_LABELS) as AddressField[]).forEach(field => {
            const value = network[field];
            if (!value) {
                return;
            }
            const address = parseIpv4(value);
            if (address === null) {
                set(key(field), `${ADDRESS_LABELS[field]} is not an IP address.`);
            } else if (parsed[index] && !contains(parsed[index]!, address)) {
                set(key(field), `${ADDRESS_LABELS[field]} is outside ${network.cidr}.`);
            } else if (parsed[index] && (address === parsed[index]!.network || address === parsed[index]!.broadcast)) {
                set(key(field), `${ADDRESS_LABELS[field]} is the network or broadcast address.`);
            } else {
                addresses[field] = address;
            }
        });

        if (network.mode === "nat" && !network.parent_address) {
            set(key("parent_address"), "NAT needs a parent address; the parent routes the network to the internet.");
        }
        if (network.dhcp) {
            if (!network.parent_address) {
                set(key("parent_address"), "DHCP needs a parent address; the parent serves it.");
            }
            if (!network.dhcp_start) {
                set(key("dhcp_start"), "Enter the first DHCP address.");
            }
            if (!network.dhcp_end) {
                set(key("dhcp_end"), "Enter the last DHCP address.");
            }
            const {parent_address: parent, dhcp_start: start, dhcp_end: end} = addresses;
            if (start !== undefined && end !== undefined) {
                if (start > end) {
                    set(key("dhcp_end"), "The DHCP range must not end before it starts.");
                } else if (parent !== undefined && start <= parent && parent <= end) {
                    set(key("parent_address"), "The DHCP range must exclude the parent address.");
                }
            }
        }
    });
    return errors;
};

// The default for a new network: the first free /24 under 192.168.0.0/16, isolated, served by the parent at .1.
export const nextNestedNetwork = (networks: NestedNetwork[]): NestedNetwork => {
    const names = new Set(networks.map(network => network.name));
    let suffix = networks.length + 1;
    while (names.has(`net${suffix}`)) {
        suffix++;
    }
    const taken = networks.map(network => parseCidr(network.cidr)).filter((cidr): cidr is Ipv4Cidr => cidr !== null);
    let third = 101;
    for (; third < 255; third++) {
        const candidate = parseCidr(`192.168.${third}.0/24`)!;
        if (![...taken, ...RESERVED].some(other => cidrsOverlap(candidate, other))) {
            break;
        }
    }
    const base = `192.168.${third}`;
    return {
        name: `net${suffix}`,
        cidr: `${base}.0/24`,
        mode: "isolated",
        parent_address: `${base}.1`,
        dhcp: true,
        dhcp_start: `${base}.100`,
        dhcp_end: `${base}.199`,
    };
};

// Guest NICs refer to networks by name, so a rename carries them along. Skipped while the old name is shared,
// since then there is no telling which network the NICs meant.
export const renameNetworkInGuests = (
    guests: NestedGuest[],
    networks: NestedNetwork[],
    oldName: string,
    newName: string,
): NestedGuest[] => {
    if (oldName === newName || networks.filter(network => network.name === oldName).length !== 1) {
        return guests;
    }
    return guests.map(guest => guest.nics.some(nic => nic.network === oldName)
        ? {...guest, nics: guest.nics.map(nic => nic.network === oldName ? {...nic, network: newName} : nic)}
        : guest);
};

export const guestsOnNetwork = (guests: NestedGuest[], name: string): string[] =>
    guests.filter(guest => guest.nics.some(nic => nic.network === name)).map(guest => guest.name);
