import {describe, expect, it, vi} from "vitest";

import {NestedGuest, NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {missingImageGuests} from "../../../Ctf/CtfSpecEditor";
import {
    fillAliasIps,
    mergeNestedConnections,
    nestedConnections,
    nestedCtfGuests,
    nestedMachineTypes,
    networkCidr,
    splitAliases,
} from "./nestedServer";

// CtfSpecEditor imports the CTF service, whose client initializes Firebase at import
vi.mock("../../../../../services/Ctf/ctf.service", () => ({ctfService: {}}));

const entry = (id: string, family: NestedOsCatalogEntry['family'], agent: boolean) =>
    ({id, display_name: id, family, agent} as NestedOsCatalogEntry);

const CATALOG = [
    entry('win2019', 'windows', true),
    entry('ubuntu-24.04', 'linux', true),
    entry('kali', 'linux', false),
    entry('pfsense', 'appliance', false),
];

const guest = (name: string, os_id: string, console = true): NestedGuest => ({
    name, os_id, console, admin_username: `${name}-admin`, admin_password: `${name}-pw`,
} as NestedGuest);

// The SC-35 shape: an exposed Windows DC, an exposed Linux web server, and a console-only Kali box
const NESTED: NestedHostSpec = {
    guests: [guest('dc', 'win2019'), guest('web', 'ubuntu-24.04'), guest('kali', 'kali'), guest('fw', 'pfsense', false)],
    exposures: [['dc', 0], ['web', 0]],
    console_ports: {dc: 5901, web: 5902, kali: 5903},
    vnc_passwords: {dc: 'dcvncpw1', web: 'webvncpw', kali: 'kalivnc1'},
} as unknown as NestedHostSpec;

describe('fillAliasIps', () => {
    it('takes the lowest free addresses in slot order, skipping GCP-reserved and used ones', () => {
        expect(fillAliasIps('10.1.1.0/24', 3, [], ['10.1.1.2', '10.1.1.4'])).toEqual(['10.1.1.3', '10.1.1.5', '10.1.1.6']);
    });

    it('keeps a valid existing alias in its slot and refills invalid or conflicting ones', () => {
        // slot 0 is kept; slot 1 is outside the subnet; slot 2 collides with another server's address
        expect(fillAliasIps('10.1.1.0/24', 3, ['10.1.1.50', '192.168.0.9', '10.1.1.10'], ['10.1.1.10/32']))
            .toEqual(['10.1.1.50', '10.1.1.2', '10.1.1.3']);
    });

    it('drops aliases past the slot count', () => {
        expect(fillAliasIps('10.1.1.0/24', 1, ['10.1.1.20', '10.1.1.21'], [])).toEqual(['10.1.1.20']);
    });

    it('returns null when the subnet is unknown, malformed or too small', () => {
        expect(fillAliasIps(null, 1, [], [])).toBeNull();
        expect(fillAliasIps('10.1.1.5/24', 1, [], [])).toBeNull();
        // a /29 has .2–.5 usable once the network, gateway, second-to-last and broadcast are reserved
        expect(fillAliasIps('10.1.1.0/29', 4, [], [])).toEqual(['10.1.1.2', '10.1.1.3', '10.1.1.4', '10.1.1.5']);
        expect(fillAliasIps('10.1.1.0/29', 5, [], [])).toBeNull();
    });

    it('fills nothing for an image with no exposures', () => {
        expect(fillAliasIps('10.1.1.0/24', 0, ['10.1.1.9'], [])).toEqual([]);
    });
});

describe('nestedConnections', () => {
    it('makes RDP for an exposed Windows guest, SSH for an exposed Linux guest, and VNC otherwise', () => {
        expect(nestedConnections(NESTED, CATALOG)).toEqual([
            {protocol: 'rdp', username: 'dc-admin', password: 'dc-pw', alias_index: 0, nested_guest: 'dc'},
            {protocol: 'ssh', username: 'web-admin', password: 'web-pw', alias_index: 1, nested_guest: 'web'},
            {protocol: 'vnc', password: 'kalivnc1', port: 5903, nested_guest: 'kali'},
        ]);
    });

    it('falls back to the console when the catalog does not know an exposed guest', () => {
        expect(nestedConnections(NESTED, [])).toEqual([
            {protocol: 'vnc', password: 'dcvncpw1', port: 5901, nested_guest: 'dc'},
            {protocol: 'vnc', password: 'webvncpw', port: 5902, nested_guest: 'web'},
            {protocol: 'vnc', password: 'kalivnc1', port: 5903, nested_guest: 'kali'},
        ]);
    });

    it('replaces earlier guest connections and keeps the parent\'s own', () => {
        const parent = {protocol: 'ssh', username: 'root'};
        const stale = {protocol: 'vnc', port: 5909, nested_guest: 'old'};
        const generated = nestedConnections(NESTED, CATALOG);
        expect(mergeNestedConnections([parent, stale], generated)).toEqual([parent, ...generated]);
    });
});

describe('nestedCtfGuests', () => {
    it('pre-fills domain from the guest name and driver from the catalog agent, skipping appliances', () => {
        expect(nestedCtfGuests('hv', NESTED, CATALOG)).toEqual([
            {name: 'dc', server: 'hv', domain: 'dc', operating_system: 'windows', driver: 'qemu-agent'},
            {name: 'web', server: 'hv', domain: 'web', operating_system: 'linux', driver: 'qemu-agent'},
            {name: 'kali', server: 'hv', domain: 'kali', operating_system: 'linux', driver: 'offline'},
        ]);
        expect(nestedCtfGuests('hv', NESTED, [])).toEqual([]);
    });

    it('offers only guests not yet declared, up to eight per server', () => {
        const imageGuests = nestedCtfGuests('hv', NESTED, CATALOG);
        expect(missingImageGuests([imageGuests[0]], imageGuests)).toEqual(imageGuests.slice(1));
        const seven = Array.from({length: 7}, (_, i) => ({...imageGuests[0], name: `g${i}`}));
        expect(missingImageGuests(seven, imageGuests)).toEqual([imageGuests[0]]);
    });
});

describe('form helpers', () => {
    it('hides E2 and other non-N1/N2 machine types', () => {
        const types = ['e2-medium', 'n1-standard-4', 'n2-standard-8', 'n2d-standard-4'].map(id => ({id}));
        expect(nestedMachineTypes(types as never).map(type => type.id)).toEqual(['n1-standard-4', 'n2-standard-8']);
    });

    it('reads the network subnet and the comma-joined alias field', () => {
        const networks = [{name: 'lan', subnets: [{name: 'other', ip_subnet: '10.9.0.0/24'}, {name: 'default', ip_subnet: '10.1.1.0/24'}]}];
        expect(networkCidr(networks, 'lan')).toBe('10.1.1.0/24');
        expect(networkCidr(networks, 'missing')).toBeNull();
        expect(splitAliases(' 10.1.1.2, 10.1.1.3,')).toEqual(['10.1.1.2', '10.1.1.3']);
        expect(splitAliases(['10.1.1.2'])).toEqual(['10.1.1.2']);
        expect(splitAliases(undefined)).toEqual([]);
    });
});
