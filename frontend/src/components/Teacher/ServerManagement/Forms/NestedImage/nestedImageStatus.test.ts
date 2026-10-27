import {describe, expect, it} from "vitest";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {NestedBuildStatus, NestedGuest, NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {transformToAgogeImage} from "../../../../../utilities/transformers/image.transform";
import {
    isNestedBuildActive,
    isNestedCheckInBlocked,
    isStaleFinalize,
    latestBuildStatus,
    NESTED_FINALIZE_STALE_SECONDS,
    nestedGuestDetails,
    nestedTunnels,
    prunePolledBuilds,
    withPolledBuildStatus,
} from "./nestedImageStatus";

const NOW = Date.parse("2026-10-17T12:00:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

const build = (overrides: Partial<NestedBuildStatus> = {}): NestedBuildStatus => ({
    phase: "building", guests: {}, message: null, heartbeat_at: null, started_at: null, updated_at: ago(10),
    ...overrides,
});

const guest = (name: string, osId: string, nics: NestedGuest["nics"], overrides: Partial<NestedGuest> = {}): NestedGuest => ({
    name, os_id: osId, media_id: null, vcpus: 2, memory_mb: 4096, disk_gb: 40, nics,
    admin_username: "admin", admin_password: `${name}-pw`, packages: [], post_install_script: null,
    console: true, autostart: true, start_order: 0, start_delay_seconds: 0, ...overrides,
});

// SC-35 shape: a DC exposed on slot 0, a Linux box exposed on slots 1 and 2, a workstation with no exposure.
const spec = (): NestedHostSpec => ({
    parent_os: "debian-12",
    build_machine_type: "n2-standard-8",
    networks: [],
    guests: [
        guest("dc01", "server-2022", [{network: "lab", ip: "192.168.100.10", expose: true}]),
        guest("web01", "ubuntu-24.04", [
            {network: "lab", ip: "192.168.100.20", expose: true},
            {network: "dmz", ip: "10.0.0.5", expose: true},
        ], {console: false}),
        guest("ws01", "win10", [{network: "lab", ip: null, expose: false}]),
    ],
    exposures: [["dc01", 0], ["web01", 0], ["web01", 1]],
    console_ports: {ws01: 5902, dc01: 5901},
    vnc_passwords: {dc01: "vncdc001", ws01: "vncws001"},
});

const catalogEntry = (id: string, family: NestedOsCatalogEntry["family"]) =>
    ({id, family} as NestedOsCatalogEntry);
const catalog = [catalogEntry("server-2022", "windows"), catalogEntry("ubuntu-24.04", "linux")];

const image = (overrides: Partial<AgogeImage> = {}): AgogeImage =>
    ({name: "adlab", nested: spec(), nested_build: build(), ...overrides} as AgogeImage);

describe("nested build activity", () => {
    it("treats queued, provisioning, building and a live finalizing as active", () => {
        for (const phase of ["queued", "provisioning", "building", "finalizing"] as const) {
            expect(isNestedBuildActive(build({phase}), NOW)).toBe(true);
        }
        for (const phase of ["ready", "finalized", "failed"] as const) {
            expect(isNestedBuildActive(build({phase}), NOW)).toBe(false);
        }
        expect(isNestedBuildActive(null, NOW)).toBe(false);
    });

    it("mirrors is_stale_finalize, so a stranded finalize re-enables Check In", () => {
        const fresh = build({phase: "finalizing", updated_at: ago(NESTED_FINALIZE_STALE_SECONDS - 5)});
        const stale = build({phase: "finalizing", updated_at: ago(NESTED_FINALIZE_STALE_SECONDS + 5)});
        expect(isStaleFinalize(fresh, NOW)).toBe(false);
        expect(isStaleFinalize(stale, NOW)).toBe(true);
        // A missing updated_at is stale there too, or the record could never leave finalizing.
        expect(isStaleFinalize(build({phase: "finalizing", updated_at: null}), NOW)).toBe(true);
        expect(isStaleFinalize(build({phase: "building", updated_at: null}), NOW)).toBe(false);
        expect(isNestedCheckInBlocked(image({nested_build: fresh}), NOW)).toBe(true);
        expect(isNestedCheckInBlocked(image({nested_build: stale}), NOW)).toBe(false);
    });

    it("blocks Check In only for nested images with an active build", () => {
        expect(isNestedCheckInBlocked(image(), NOW)).toBe(true);
        expect(isNestedCheckInBlocked(image({nested_build: build({phase: "ready"})}), NOW)).toBe(false);
        expect(isNestedCheckInBlocked(image({nested: null}), NOW)).toBe(false);
    });
});

describe("merging polled build status", () => {
    it("keeps whichever status was updated last", () => {
        const listed = build({phase: "finalizing", updated_at: ago(5)});
        const polled = build({phase: "ready", updated_at: ago(60)});
        // After Check In the list moves to finalizing while the last poll still says ready.
        expect(latestBuildStatus(listed, polled)).toBe(listed);
        expect(latestBuildStatus(polled, listed)).toBe(listed);
        expect(latestBuildStatus(null, polled)).toBe(polled);
        expect(latestBuildStatus(listed, undefined)).toBe(listed);
    });

    it("applies a poll only to the nested image it belongs to", () => {
        const polled = build({phase: "ready", updated_at: ago(1)});
        expect(withPolledBuildStatus(image(), {adlab: polled}).nested_build).toBe(polled);
        const standard = image({name: "plain", nested: null, nested_build: null});
        expect(withPolledBuildStatus(standard, {plain: polled})).toBe(standard);
        const other = image();
        expect(withPolledBuildStatus(other, {elsewhere: polled})).toBe(other);
    });
});

describe("prunePolledBuilds", () => {
    it("drops a settled poll once the list catches up, so a re-created record shows", () => {
        const polledReady = build({phase: "ready", updated_at: ago(30)});
        // Re-created as queued: the fresh record has no updated_at and must not lose to the old poll.
        const requeued = image({nested_build: build({phase: "queued", updated_at: null})});
        expect(prunePolledBuilds([requeued], {adlab: polledReady}, NOW)).toEqual({});
        const caughtUp = image({nested_build: build({phase: "ready", updated_at: ago(30)})});
        expect(prunePolledBuilds([caughtUp], {adlab: polledReady}, NOW)).toEqual({});
    });

    it("keeps a poll that is still active or newer than the list, and drops deleted images", () => {
        const polled = {adlab: build({phase: "building", updated_at: ago(1)})};
        expect(prunePolledBuilds([image()], polled, NOW)).toBe(polled);
        const newerReady = {adlab: build({phase: "ready", updated_at: ago(1)})};
        const behind = image({nested_build: build({phase: "building", updated_at: ago(60)})});
        expect(prunePolledBuilds([behind], newerReady, NOW)).toBe(newerReady);
        expect(prunePolledBuilds([], polled, NOW)).toEqual({});
    });
});

describe("nestedGuestDetails", () => {
    it("lists each guest with status, IPs, alias slots, credentials and console", () => {
        const details = nestedGuestDetails(spec(), build({guests: {dc01: "ready", web01: "installing"}}));
        expect(details.map(item => item.name)).toEqual(["dc01", "web01", "ws01"]);
        expect(details[0]).toEqual({
            name: "dc01", os_id: "server-2022", status: "ready",
            ips: [{network: "lab", ip: "192.168.100.10"}], alias_slots: [0],
            admin_username: "admin", admin_password: "dc01-pw", console_port: 5901, vnc_password: "vncdc001",
        });
        expect(details[1]).toMatchObject({status: "installing", alias_slots: [1, 2], console_port: null, vnc_password: null});
        // No status reported yet means the guest has not started.
        expect(details[2]).toMatchObject({status: "pending", ips: [{network: "lab", ip: null}], alias_slots: [], console_port: 5902});
    });
});

describe("nestedTunnels", () => {
    // lab has a parent address, so the parent can route to it; dmz is a bare layer-2 segment.
    const routed = (): NestedHostSpec => ({
        ...spec(),
        networks: [
            {name: "lab", cidr: "192.168.100.0/24", mode: "nat", parent_address: "192.168.100.1", dhcp: true,
                dhcp_start: "192.168.100.100", dhcp_end: "192.168.100.199"},
            {name: "dmz", cidr: "10.0.0.0/24", mode: "isolated", parent_address: null, dhcp: false,
                dhcp_start: null, dhcp_end: null},
        ],
    });
    const withWindows10 = [...catalog, catalogEntry("win10", "windows")];

    it("builds a console tunnel per port, RDP per Windows guest and SSH per Linux guest, exposed or not", () => {
        const addresses = {ws01: {"0": "192.168.100.166"}};
        const tunnels = nestedTunnels(routed(), "agoge@adlab.example.test", withWindows10, addresses);
        expect(tunnels.map(item => item.command)).toEqual([
            "ssh -L 5901:localhost:5901 agoge@adlab.example.test",
            "ssh -L 5902:localhost:5902 agoge@adlab.example.test",
            "ssh -L 13389:192.168.100.10:3389 agoge@adlab.example.test",
            "ssh -L 2223:192.168.100.20:22 agoge@adlab.example.test",
            // ws01 is DHCP and not exposed: its tunnel uses the lease the builder reported.
            "ssh -L 13391:192.168.100.166:3389 agoge@adlab.example.test",
        ]);
        expect(tunnels.map(item => [item.guest, item.kind, item.local_port])).toEqual([
            ["dc01", "console", 5901], ["ws01", "console", 5902], ["dc01", "rdp", 13389],
            ["web01", "ssh", 2223], ["ws01", "rdp", 13391],
        ]);
        // PuTTY's Tunnels page takes the forward's far end on its own.
        expect(tunnels.map(item => item.destination)).toEqual([
            "localhost:5901", "localhost:5902", "192.168.100.10:3389", "192.168.100.20:22", "192.168.100.166:3389",
        ]);
    });

    it("skips a DHCP guest until its address is reported, and a NIC the parent cannot route to", () => {
        const noLab = routed();
        noLab.guests[1] = {...noLab.guests[1], nics: [{network: "dmz", ip: "10.0.0.5", expose: true}]};
        const tunnels = nestedTunnels(noLab, "agoge@host", withWindows10).filter(item => item.kind !== "console");
        expect(tunnels.map(item => item.guest)).toEqual(["dc01"]);
    });

    it("offers only consoles for a guest whose family is unknown or an appliance", () => {
        const appliance = [catalogEntry("server-2022", "appliance")];
        for (const entries of [[], appliance]) {
            const tunnels = nestedTunnels(routed(), "agoge@host", entries).filter(item => item.guest === "dc01");
            expect(tunnels.map(item => item.kind)).toEqual(["console"]);
        }
    });
});

describe("transformToAgogeImage", () => {
    it("keeps nested and nested_build, minus the finalize nonce", () => {
        const result = transformToAgogeImage({
            name: "adlab",
            nested: spec(),
            nested_build: {...build({phase: "ready"}), finalize_nonce: "secret"},
        });
        expect(result.nested?.exposures).toEqual([["dc01", 0], ["web01", 0], ["web01", 1]]);
        expect(result.nested?.console_ports).toEqual({ws01: 5902, dc01: 5901});
        expect(result.nested_build?.phase).toBe("ready");
        expect(result.nested_build).not.toHaveProperty("finalize_nonce");
    });

    it("leaves a standard image without nested fields", () => {
        const result = transformToAgogeImage({name: "plain"});
        expect(result.nested).toBeNull();
        expect(result.nested_build).toBeNull();
    });
});
