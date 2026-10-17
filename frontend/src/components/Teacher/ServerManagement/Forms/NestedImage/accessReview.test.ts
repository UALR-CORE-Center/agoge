import {describe, expect, it} from "vitest";
import {NestedGuest, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {toNestedImageCreateRequest} from "../../../../../utilities/transformers/nested.transform";
import {
    canMoveExposure,
    capacityMeters,
    deriveConsoles,
    deriveExposures,
    estimateBuildMinutes,
    meterPercent,
    moveExposure,
    reviewWarnings,
    toCreateRequest,
} from "./accessReview";
import {defaultNestedNetwork, initialNestedWizardState, NestedWizardState} from "./nestedWizardState";

const entry = (overrides: Partial<NestedOsCatalogEntry>): NestedOsCatalogEntry => ({
    id: "ubuntu-24.04", display_name: "Ubuntu 24.04", family: "linux", group: "linux", version: "24.04",
    install_method: "cloud_image", media_url: "https://example.test/noble.img", media_sha256: null,
    media_formats: ["qcow2"], requires_upload: false, license_note: "Free software.", eval_days: null,
    osinfo: "ubuntu24.04", firmware: "bios", disk_bus: "virtio", nic_model: "virtio", video: "virtio",
    virtio_win_version: null, agent: true, net_config: "netplan", unattend_template: null,
    windows_image_index: null, default_username: null, min_memory_mb: 512, default_memory_mb: 2048,
    min_disk_gb: 4, default_disk_gb: 20, default_vcpus: 2, is_enabled: true,
    ...overrides,
});

const ubuntu = entry({});
const kali = entry({id: "kali-rolling", display_name: "Kali Rolling", group: "kali"});
const server2022 = entry({
    id: "win-server-2022-eval", display_name: "Windows Server 2022 Evaluation", family: "windows",
    group: "windows_server", install_method: "unattended_iso", media_formats: ["iso"], eval_days: 180,
    net_config: "windows", unattend_template: "autounattend",
});
const retail10 = entry({
    id: "windows-10", display_name: "Windows 10", family: "windows", group: "windows_client",
    install_method: "unattended_iso", media_url: null, media_formats: ["iso"], requires_upload: true,
});
const pfsense = entry({
    id: "pfsense", display_name: "pfSense", family: "appliance", group: "appliance", install_method: "manual_iso",
    agent: false, media_formats: ["iso"],
});
const catalog = [ubuntu, kali, server2022, retail10, pfsense];

const guest = (name: string, osId: string, overrides: Partial<NestedGuest> = {}): NestedGuest => ({
    name, os_id: osId, media_id: null, vcpus: 2, memory_mb: 4096, disk_gb: 40,
    nics: [{network: "lab", ip: null, expose: false}], admin_username: "agoge", admin_password: "Str0ng-Passw0rd",
    packages: [], post_install_script: null, console: true, autostart: true, start_order: 0, start_delay_seconds: 0,
    ...overrides,
});

// SC-35: Kali + Ubuntu 24.04 + Windows Server 2022 Evaluation on two networks.
const sc35 = (): NestedWizardState => ({
    ...initialNestedWizardState(),
    server_name: "ad-lab-host",
    description: "  AD lab  ",
    labels: ["ctf"],
    machine_type: "n2-standard-4",
    username: "gm",
    ssh_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0 gm@laptop",
    networks: [
        defaultNestedNetwork(),
        {name: "dmz", cidr: "10.10.0.0/24", mode: "isolated", parent_address: null, dhcp: false, dhcp_start: null, dhcp_end: null},
    ],
    guests: [
        guest("kali", "kali-rolling", {nics: [{network: "lab", ip: "192.168.100.10", expose: true}]}),
        guest("web", "ubuntu-24.04", {nics: [
            {network: "lab", ip: "192.168.100.20", expose: true},
            {network: "dmz", ip: "10.10.0.20", expose: true},
        ]}),
        guest("dc", "win-server-2022-eval", {console: false, nics: [{network: "dmz", ip: "10.10.0.10", expose: true}]}),
    ],
    // A key left behind for an evaluation guest, and one for a guest that was removed.
    product_keys: {dc: "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE", gone: "FFFFF-GGGGG-HHHHH-IIIII-JJJJJ"},
});

describe("deriveExposures and deriveConsoles", () => {
    it("follow guest order, then NIC order, like NestedHostValidator.derive", () => {
        const state = sc35();
        expect(deriveExposures(state.guests).map(({guest, nic}) => [guest, nic])).toEqual([
            ["kali", 0], ["web", 0], ["web", 1], ["dc", 0],
        ]);
        // dc has no console, so it takes no port and the numbering stays dense.
        expect(deriveConsoles(state.guests)).toEqual([{guest: "kali", port: 5901}, {guest: "web", port: 5902}]);
    });
});

describe("moveExposure", () => {
    it("moves the whole guest past the neighbouring guest's exposure", () => {
        const state = sc35();
        const exposures = deriveExposures(state.guests);
        const moved = moveExposure(state.guests, exposures, 3, -1);
        expect(moved.map(item => item.name)).toEqual(["kali", "dc", "web"]);
        expect(deriveExposures(moved).map(({guest, nic}) => [guest, nic])).toEqual([
            ["kali", 0], ["dc", 0], ["web", 0], ["web", 1],
        ]);
        const down = moveExposure(state.guests, exposures, 0, 1);
        expect(down.map(item => item.name)).toEqual(["web", "kali", "dc"]);
    });

    it("refuses to swap two NICs of one guest or to leave the list", () => {
        const state = sc35();
        const exposures = deriveExposures(state.guests);
        expect(canMoveExposure(exposures, 1, 1)).toBe(false);
        expect(canMoveExposure(exposures, 2, -1)).toBe(false);
        expect(canMoveExposure(exposures, 0, -1)).toBe(false);
        expect(canMoveExposure(exposures, 3, 1)).toBe(false);
        expect(moveExposure(state.guests, exposures, 1, 1)).toBe(state.guests);
    });

    it("leaves unexposed guests where they are relative to each other", () => {
        const guests = [
            guest("a", "ubuntu-24.04", {nics: [{network: "lab", ip: "192.168.100.10", expose: true}]}),
            guest("quiet", "ubuntu-24.04"),
            guest("b", "ubuntu-24.04", {nics: [{network: "lab", ip: "192.168.100.11", expose: true}]}),
        ];
        const moved = moveExposure(guests, deriveExposures(guests), 1, -1);
        expect(moved.map(item => item.name)).toEqual(["b", "a", "quiet"]);
    });
});

describe("capacityMeters", () => {
    it("compares RAM and vCPU with both machine types and the disk with its minimum", () => {
        const state = sc35();
        const machineTypes = [
            {id: "1", name: "n2-standard-8", description: "", is_shared_core: false, memory_mb: 32768, guest_cpus: 8},
            {id: "2", name: "n2-standard-4", description: "", is_shared_core: false, memory_mb: 16384, guest_cpus: 4},
        ];
        const meters = capacityMeters({...state, disk_size: 200}, machineTypes);
        expect(meters.map(item => [item.label, item.used, item.available])).toEqual([
            ["Build RAM (n2-standard-8)", 3 * 4096 + 2048, 32768],
            ["Build vCPU (n2-standard-8)", 6, 16],
            ["Lab RAM (n2-standard-4)", 3 * 4096 + 2048, 16384],
            ["Lab vCPU (n2-standard-4)", 6, 8],
            ["Disk", 20 + 3 * 40 + 12, 200],
        ]);
        expect(meterPercent(meters[2])).toBe(88);
        expect(meterPercent({label: "x", used: 30, available: 10, unit: "GB"})).toBe(100);
    });

    it("skips a machine type the list does not have", () => {
        expect(capacityMeters(sc35(), []).map(item => item.label)).toEqual(["Disk"]);
    });
});

describe("estimateBuildMinutes", () => {
    it("runs two installs at a time in start_order", () => {
        // Parent 10, then kali (10) and web (10) side by side, then dc (30) in the first free slot: 10 + 40.
        expect(estimateBuildMinutes(sc35().guests, catalog)).toBe(50);
        // The Windows install first keeps one slot busy while both Linux guests run in the other.
        const windowsFirst = sc35().guests.map(item => ({...item, start_order: item.name === "dc" ? 0 : 1}));
        expect(estimateBuildMinutes(windowsFirst, catalog)).toBe(40);
    });
});

describe("reviewWarnings", () => {
    it("names evaluation expiry, manual installs, agentless guests and uploaded Windows media", () => {
        const state: NestedWizardState = {
            ...sc35(),
            guests: [
                guest("dc", "win-server-2022-eval"),
                guest("fw", "pfsense", {console: false, post_install_script: "echo hi"}),
                guest("desk", "windows-10", {media_id: "m1"}),
            ],
        };
        const messages = reviewWarnings(state, catalog, {m1: "win10.iso"}).map(item => item.message);
        expect(messages).toEqual([
            expect.stringMatching(/^dc: .*expires 180 days after install/),
            expect.stringMatching(/^fw: pfSense is a manual install, but its console is off/),
            expect.stringMatching(/^fw: .*offline driver.*post-install script will not run/),
            expect.stringMatching(/^desk: .*uploaded media \(win10\.iso\)/),
        ]);
    });

    it("warns when the estimate passes the build limit", () => {
        const slow = Array.from({length: 8}, (_, index) => guest(`w${index}`, "win-server-2022-eval"));
        const warnings = reviewWarnings({...sc35(), guests: slow}, catalog, {});
        expect(warnings.filter(item => item.guest === null)).toEqual([]);
        const slower = [...slow, ...slow.map(item => ({...item, name: `${item.name}x`}))];
        expect(reviewWarnings({...sc35(), guests: slower}, catalog, {}).at(-1)?.message).toMatch(/250 minutes.*240-minute limit/);
    });
});

describe("toCreateRequest", () => {
    it("builds the create body from the SC-35 wizard state", () => {
        const state = sc35();
        const body = toNestedImageCreateRequest(toCreateRequest(state, catalog));
        expect(body).toEqual({
            server_name: "ad-lab-host",
            description: "AD lab",
            labels: ["ctf"],
            machine_type: "n2-standard-4",
            disk_size: null,
            username: "gm",
            ssh_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0 gm@laptop",
            nested: {
                parent_os: "debian-12",
                build_machine_type: "n2-standard-8",
                networks: state.networks,
                guests: state.guests,
            },
            // Neither key is needed: dc is an evaluation and gone does not exist.
            product_keys: {},
        });
        // Exposures, console ports and VNC passwords are the API's to derive.
        expect(Object.keys(body.nested)).not.toContain("exposures");
    });

    it("sends the key of a retail Windows guest", () => {
        const state = {...sc35(), guests: [guest("desk", "windows-10", {media_id: "m1"})], product_keys: {desk: "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}};
        expect(toCreateRequest(state, catalog).product_keys).toEqual({desk: "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"});
    });
});
