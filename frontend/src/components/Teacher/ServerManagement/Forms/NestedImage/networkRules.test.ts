import {describe, expect, it} from "vitest";
import {NestedGuest, NestedNetwork} from "../../../../../services/Server/nested.model";
import {defaultNestedNetwork} from "./nestedWizardState";
import {
    guestsOnNetwork,
    nextNestedNetwork,
    parseCidr,
    parseIpv4,
    renameNetworkInGuests,
    validateNetworks,
} from "./networkRules";

const network = (patch: Partial<NestedNetwork> = {}): NestedNetwork => ({...defaultNestedNetwork(), ...patch});

const isolated = (name: string, base: string): NestedNetwork => ({
    name,
    cidr: `${base}.0/24`,
    mode: "isolated",
    parent_address: `${base}.1`,
    dhcp: true,
    dhcp_start: `${base}.100`,
    dhcp_end: `${base}.199`,
});

const guest = (name: string, networks: string[]): NestedGuest => ({
    name,
    os_id: "debian-12",
    media_id: null,
    vcpus: 1,
    memory_mb: 2048,
    disk_gb: 20,
    nics: networks.map(networkName => ({network: networkName, ip: null, expose: false})),
    admin_username: "admin",
    admin_password: "Passw0rd!",
    packages: [],
    post_install_script: null,
    console: true,
    autostart: true,
    start_order: 0,
    start_delay_seconds: 0,
});

describe("parseIpv4 and parseCidr", () => {
    it("parses dotted quads and rejects malformed or leading-zero octets", () => {
        expect(parseIpv4("192.168.100.1")).toBe(0xC0A86401);
        expect(parseIpv4("255.255.255.255")).toBe(0xFFFFFFFF);
        ["192.168.100", "192.168.100.256", "192.168.01.1", "a.b.c.d", "1.2.3.4.5", ""].forEach(value =>
            expect(parseIpv4(value)).toBeNull());
    });

    it("accepts only strict network addresses", () => {
        expect(parseCidr("10.1.0.0/16")).toEqual({network: 0x0A010000, prefix: 16, broadcast: 0x0A01FFFF});
        // Host bits set, as Python's ip_network(strict=True) rejects.
        expect(parseCidr("192.168.100.1/24")).toBeNull();
        expect(parseCidr("192.168.100.0/33")).toBeNull();
        expect(parseCidr("192.168.100.0")).toBeNull();
    });
});

describe("validateNetworks", () => {
    it("accepts the pre-filled lab network and a second isolated one", () => {
        expect(validateNetworks([network(), isolated("dmz", "10.20.30")])).toEqual({});
    });

    it("accepts an isolated pure layer-2 segment with no parent address and no DHCP", () => {
        expect(validateNetworks([network(), {
            ...isolated("wire", "10.9.9"), parent_address: null, dhcp: false, dhcp_start: null, dhcp_end: null,
        }])).toEqual({});
    });

    it("requires one to eight networks", () => {
        expect(validateNetworks([])).toEqual({networks: "Add at least one network."});
        const nine = Array.from({length: 9}, (_, index) => isolated(`net${index}`, `10.0.${index}`));
        expect(validateNetworks(nine).networks).toBe("Use at most 8 networks.");
    });

    it("rejects bad and duplicate names", () => {
        const errors = validateNetworks([network(), network({name: "Lab_1", cidr: "10.0.0.0/24"}),
            isolated("lab", "10.0.1")]);
        expect(errors["networks.1.name"]).toMatch(/lowercase letters/);
        expect(errors["networks.2.name"]).toBe("Another network is already named lab.");
        expect(errors["networks.0.name"]).toBeUndefined();
    });

    it("rejects malformed, public, and out-of-bounds prefix ranges", () => {
        const errors = validateNetworks([
            network({cidr: "192.168.100.5/24"}),
            isolated("pub", "8.8.8"),
            {...isolated("big", "10.0.0"), cidr: "10.0.0.0/8"},
            {...isolated("tiny", "10.1.0"), cidr: "10.1.0.0/30"},
        ]);
        expect(errors["networks.0.cidr"]).toMatch(/CIDR form/);
        expect(errors["networks.1.cidr"]).toMatch(/private range/);
        expect(errors["networks.2.cidr"]).toBe("The prefix must be /16 to /29.");
        expect(errors["networks.3.cidr"]).toBe("The prefix must be /16 to /29.");
    });

    it("rejects a range that overlaps another network or a reserved range", () => {
        const errors = validateNetworks([
            network(),
            {...isolated("wide", "192.168.0"), cidr: "192.168.0.0/16"},
            isolated("virbr", "192.168.122"),
            {...isolated("meta", "10.0.0"), cidr: "172.16.0.0/16"},
        ]);
        // The later network is the one flagged, as in the API.
        expect(errors["networks.1.cidr"]).toBe("Overlaps the reserved range 192.168.122.0/24.");
        expect(errors["networks.2.cidr"]).toBe("Overlaps the reserved range 192.168.122.0/24.");
        expect(errors["networks.0.cidr"]).toBeUndefined();
        expect(errors["networks.3.cidr"]).toBeUndefined();

        const pair = validateNetworks([network(), {...isolated("sub", "192.168.100"), cidr: "192.168.100.128/25"}]);
        expect(pair["networks.1.cidr"]).toBe("Overlaps network lab (192.168.100.0/24).");
    });

    it("checks that addresses are in range and are not the network or broadcast address", () => {
        const errors = validateNetworks([network({
            parent_address: "192.168.101.1",
            dhcp_start: "192.168.100.0",
            dhcp_end: "192.168.100.255",
        })]);
        expect(errors["networks.0.parent_address"]).toBe("Parent address is outside 192.168.100.0/24.");
        expect(errors["networks.0.dhcp_start"]).toBe("DHCP start is the network or broadcast address.");
        expect(errors["networks.0.dhcp_end"]).toBe("DHCP end is the network or broadcast address.");
        expect(validateNetworks([network({parent_address: "192.168.100.x"})])["networks.0.parent_address"])
            .toBe("Parent address is not an IP address.");
    });

    it("requires a parent address for NAT and for DHCP", () => {
        expect(validateNetworks([network({parent_address: null})])["networks.0.parent_address"])
            .toMatch(/^NAT needs a parent address/);
        expect(validateNetworks([{...isolated("iso", "10.0.0"), parent_address: null}])["networks.0.parent_address"])
            .toMatch(/^DHCP needs a parent address/);
    });

    it("requires an ordered DHCP range that excludes the parent", () => {
        expect(validateNetworks([network({dhcp_start: null, dhcp_end: ""})])).toEqual({
            "networks.0.dhcp_start": "Enter the first DHCP address.",
            "networks.0.dhcp_end": "Enter the last DHCP address.",
        });
        expect(validateNetworks([network({dhcp_start: "192.168.100.200", dhcp_end: "192.168.100.100"})]))
            .toEqual({"networks.0.dhcp_end": "The DHCP range must not end before it starts."});
        expect(validateNetworks([network({parent_address: "192.168.100.150"})]))
            .toEqual({"networks.0.parent_address": "The DHCP range must exclude the parent address."});
        // A one-address range is allowed.
        expect(validateNetworks([network({dhcp_start: "192.168.100.10", dhcp_end: "192.168.100.10"})])).toEqual({});
    });

    it("still checks range addresses kept while DHCP is off, since the API does", () => {
        expect(validateNetworks([network({dhcp: false, dhcp_start: "10.0.0.5"})]))
            .toEqual({"networks.0.dhcp_start": "DHCP start is outside 192.168.100.0/24."});
        expect(validateNetworks([network({dhcp: false, dhcp_start: "192.168.100.200", dhcp_end: "192.168.100.100"})]))
            .toEqual({});
    });
});

describe("network helpers", () => {
    it("suggests a new network on the first free /24 that is valid as-is", () => {
        const second = nextNestedNetwork([network()]);
        expect(second).toMatchObject({name: "net2", cidr: "192.168.101.0/24", mode: "isolated"});
        const taken = [network(), second, isolated("net3", "192.168.102")];
        const fourth = nextNestedNetwork(taken);
        expect(fourth.name).toBe("net4");
        expect(fourth.cidr).toBe("192.168.103.0/24");
        expect(validateNetworks([...taken, fourth])).toEqual({});
    });

    it("skips the reserved libvirt range when suggesting", () => {
        const used = Array.from({length: 21}, (_, index) => isolated(`n${index}x`, `192.168.${101 + index}`));
        expect(nextNestedNetwork(used).cidr).toBe("192.168.123.0/24");
    });

    it("carries guest NICs through a rename unless the old name is shared", () => {
        const guests = [guest("dc01", ["lab", "dmz"]), guest("kali", ["dmz"])];
        const renamed = renameNetworkInGuests(guests, [network(), isolated("dmz", "10.0.0")], "lab", "corp");
        expect(renamed[0].nics.map(nic => nic.network)).toEqual(["corp", "dmz"]);
        expect(renamed[1]).toBe(guests[1]);

        const shared = [network(), isolated("lab", "10.0.0")];
        expect(renameNetworkInGuests(guests, shared, "lab", "corp")).toBe(guests);
        expect(guestsOnNetwork(guests, "dmz")).toEqual(["dc01", "kali"]);
    });
});
