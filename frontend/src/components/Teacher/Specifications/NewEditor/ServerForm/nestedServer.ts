import {CtfNestedGuestSpec} from "../../../../../services/Ctf/ctf.model";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {HumanInteraction, Network} from "../../../../../services/Specification/specification.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {formatIpv4, parseCidr, parseIpv4} from "../../../ServerManagement/Forms/NestedImage/networkRules";

export type NestedImage = AgogeImage & { nested: NestedHostSpec };

export const isNestedImage = (image?: AgogeImage | null): image is NestedImage => !!image?.nested;

// Nested virtualization needs N1/N2 (NESTED_MACHINE_FAMILIES); the API rejects E2 on a nested server
export const nestedMachineTypes = (machineTypes: ServerMachineTypes[]): ServerMachineTypes[] =>
    machineTypes.filter(type => /^n[12]-/i.test(type.id));

// The subnet render() writes is `default`, so prefer it; older specs may name their only subnet otherwise
export const networkCidr = (networks: Network[], networkName: string): string | null => {
    const subnets = networks.find(network => network.name === networkName)?.subnets || [];
    return (subnets.find(subnet => subnet.name === 'default') || subnets[0])?.ip_subnet ?? null;
};

export const splitAliases = (value: unknown): string[] => {
    const raw = Array.isArray(value) ? value.join(',') : String(value ?? '');
    return raw.replace(/\s/g, '').split(',').filter(Boolean);
};

/**
 * One alias per exposure slot, in slot order: alias i is where the runtime DNATs exposed guest i. An existing
 * alias in the subnet and not used elsewhere keeps its slot; the rest take the lowest free addresses. GCP
 * reserves the network, gateway (.1), second-to-last and broadcast addresses. null when the subnet is unknown
 * or too small.
 */
export const fillAliasIps = (
    cidr: string | null,
    count: number,
    existing: string[],
    taken: string[],
): string[] | null => {
    const subnet = cidr ? parseCidr(cidr.trim()) : null;
    if (!subnet) {
        return null;
    }
    const usable = (ip: number) => ip >= subnet.network + 2 && ip <= subnet.broadcast - 2;
    const used = new Set(taken.map(ip => parseIpv4(ip.split('/')[0])).filter((ip): ip is number => ip !== null));
    const result: (number | null)[] = [];
    for (let slot = 0; slot < count; slot++) {
        const ip = slot < existing.length ? parseIpv4(existing[slot].split('/')[0]) : null;
        const keep = ip !== null && usable(ip) && !used.has(ip);
        result.push(keep ? ip : null);
        if (keep) {
            used.add(ip);
        }
    }
    let next = subnet.network + 2;
    for (let slot = 0; slot < count; slot++) {
        if (result[slot] !== null) {
            continue;
        }
        while (next <= subnet.broadcast - 2 && used.has(next)) {
            next++;
        }
        if (next > subnet.broadcast - 2) {
            return null;
        }
        result[slot] = next;
        used.add(next);
    }
    return result.map(ip => formatIpv4(ip as number));
};

/**
 * Guacamole connections for a nested image's exposed guests, in guest order: a Windows guest gets RDP and a
 * Linux guest SSH, both on its alias slot with the guest's admin credentials. An exposed guest the catalog does
 * not know is never guessed at: it gets only its console, VNC to the console port on the parent. Guests that are
 * not exposed get nothing, so students reach them only from inside the lab. All are `display` so DisplayProxy
 * registers them with Guacamole.
 */
export const nestedConnections = (nested: NestedHostSpec, catalog: NestedOsCatalogEntry[]): HumanInteraction[] =>
    nested.guests.flatMap((guest): HumanInteraction[] => {
        const slot = nested.exposures.findIndex(([name]) => name === guest.name);
        if (slot < 0) {
            return [];
        }
        const family = catalog.find(entry => entry.id === guest.os_id)?.family ?? null;
        if (family === 'windows' || family === 'linux') {
            return [{
                display: true,
                protocol: family === 'windows' ? 'rdp' : 'ssh',
                username: guest.admin_username,
                password: guest.admin_password,
                alias_index: slot,
                nested_guest: guest.name,
            }];
        }
        const port = nested.console_ports[guest.name];
        if (port === undefined) {
            return [];
        }
        return [{
            display: true,
            protocol: 'vnc',
            password: nested.vnc_passwords[guest.name],
            port,
            nested_guest: guest.name,
        }];
    });

/**
 * The connections a student is shown for a server. When any is `display` (proxied through Guacamole), only those:
 * a nested host's own login is hidden behind its exposed guests. Otherwise all, as before, for direct-connect
 * servers, except on a nested host (NIC 0 alias IPs), which then shows none.
 */
export const directConnection = (interactions: HumanInteraction[] | null | undefined): HumanInteraction | undefined =>
    // Mirrors direct_connect_slot in nested_scripts.py: the guest the host forwards outside SSH to
    (interactions ?? []).find(interaction =>
        interaction.display && interaction.protocol === 'ssh' && interaction.alias_index != null);

export const studentConnections = (
    interactions: HumanInteraction[] | null | undefined,
    nestedHost = false,
): HumanInteraction[] => {
    const all = interactions ?? [];
    const displayed = all.filter(interaction => interaction.display);
    // A nested host's undisplayed connection is its own login: never a student's, even with no guest connections
    return displayed.length || nestedHost ? displayed : all;
};

// "Add connections" replaces the guest connections it made before and keeps the parent's own
export const mergeNestedConnections = (
    current: HumanInteraction[],
    generated: HumanInteraction[],
): HumanInteraction[] => [...current.filter(connection => !connection.nested_guest), ...generated];

/**
 * CTF nested guests pre-filled from a server's nested image: the libvirt domain is the guest name (the builder
 * names domains after guests), and the driver follows the catalog's `agent`. Appliances, and guests the catalog
 * does not know, take no flags, so they are left for the instructor.
 */
export const nestedCtfGuests = (
    server: string,
    nested: NestedHostSpec,
    catalog: NestedOsCatalogEntry[],
): CtfNestedGuestSpec[] =>
    nested.guests.flatMap((guest): CtfNestedGuestSpec[] => {
        const entry = catalog.find(item => item.id === guest.os_id);
        if (!entry || (entry.family !== 'windows' && entry.family !== 'linux')) {
            return [];
        }
        return [{
            name: guest.name,
            server,
            domain: guest.name,
            operating_system: entry.family,
            driver: entry.agent ? 'qemu-agent' : 'offline',
        }];
    });
