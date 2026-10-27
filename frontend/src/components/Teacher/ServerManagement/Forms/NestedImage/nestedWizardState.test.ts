import {describe, expect, it} from "vitest";
import {NestedGuest, NestedMedia, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {
    effectiveDiskSize,
    initialNestedWizardState,
    NestedWizardState,
    NestedWizardSteps,
    nestedMediaSizes,
    nestedMinDiskSize,
    resolveNavigation,
    validateHostStep,
    validateNestedServerName,
    validateStep,
} from "./nestedWizardState";

const machineTypes: ServerMachineTypes[] = [
    {id: "1", name: "n2-standard-8", description: "", is_shared_core: false, memory_mb: 32768, guest_cpus: 8},
    {id: "2", name: "n1-standard-4", description: "", is_shared_core: false, memory_mb: 15360, guest_cpus: 4},
];

const guest = (name: string, disk_gb: number): NestedGuest => ({
    name,
    os_id: "debian-12",
    media_id: null,
    vcpus: 1,
    memory_mb: 2048,
    disk_gb,
    nics: [{network: "lab", ip: null, expose: false}],
    admin_username: "student",
    admin_password: "Passw0rd!",
    packages: [],
    post_install_script: null,
    console: true,
    autostart: true,
    start_order: 0,
    start_delay_seconds: 0,
});

const debian = {
    id: "debian-12", display_name: "Debian 12", family: "linux", group: "linux", install_method: "cloud_image",
    requires_upload: false, media_formats: ["qcow2"], eval_days: null, agent: true, is_enabled: true,
    min_memory_mb: 512, min_disk_gb: 4, media_sha256: "deb-sha", media_size_bytes: 400 * 1024 ** 2,
} as NestedOsCatalogEntry;

const GIB = 1024 ** 3;
const context = {catalog: [debian], media: []};

const upload = (id: string, size_bytes: number, sha256: string | null): NestedMedia => ({
    id, filename: `${id}.iso`, format: "iso", size_bytes, gcs_path: `nested-media/${id}`, sha256, os_id: null,
    uploaded_by: "gm@example.test", uploaded_at: "2026-10-17T00:00:00Z", complete: true,
});

const validHost = (overrides: Partial<NestedWizardState> = {}): NestedWizardState => ({
    ...initialNestedWizardState(),
    server_name: "ad-lab-host",
    description: "Domain controller and two clients",
    machine_type: "n1-standard-4",
    username: "gm",
    ssh_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl gm@laptop",
    ...overrides,
});

describe("nestedWizardState", () => {
    it("starts with the lab NAT network, no guests, and the default build machine type", () => {
        const state = initialNestedWizardState();
        expect(state.networks).toEqual([{
            name: "lab", cidr: "192.168.100.0/24", mode: "nat", parent_address: "192.168.100.1",
            dhcp: true, dhcp_start: "192.168.100.100", dhcp_end: "192.168.100.199",
        }]);
        expect(state.guests).toEqual([]);
        expect(state.build_machine_type).toBe("n2-standard-8");
        expect(state.disk_size).toBeNull();
    });

    it("computes the minimum disk as parent base + guest disks + build scratch + install media", () => {
        expect(nestedMinDiskSize([], context)).toBe(32);
        // Both guests use the 400 MiB Debian image, cached once and rounded up to 1 GiB.
        expect(nestedMinDiskSize([guest("kali", 40), guest("dc", 60)], context)).toBe(133);
        // An unset size shows the minimum; a chosen size wins.
        expect(effectiveDiskSize(validHost({guests: [guest("kali", 40)]}), context)).toBe(73);
        expect(effectiveDiskSize(validHost({disk_size: 200}), context)).toBe(200);
    });

    it("sizes media the way NestedHostValidator.media_sizes keys builder.sh's cache", () => {
        const withMedia = (name: string, media_id: string | null, os_id = "debian-12"): NestedGuest =>
            ({...guest(name, 10), os_id, media_id});
        const media = [upload("iso-a", GIB, "sha-a"), upload("iso-b", GIB + 1, null), upload("iso-c", 5, "sha-a")];
        expect(nestedMediaSizes([
            // Debian is downloadable, but a guest's media_id wins over the entry's media_url.
            withMedia("a", "iso-a"),
            // Same sha256 as iso-a: one cached file, so the later size replaces it under one key.
            withMedia("c", "iso-c"),
            // No sha256 yet: keyed by the upload id.
            withMedia("b", "iso-b"),
            // An upload record that is gone reserves the upload limit.
            withMedia("gone", "deleted"),
            // No media_id: the entry's own medium, keyed by its sha256.
            withMedia("d", null),
        ], {catalog: [debian], media})).toEqual({
            "sha-a": 5,
            "upload-iso-b": GIB + 1,
            "upload-deleted": 20 * GIB,
            "deb-sha": 400 * 1024 ** 2,
        });
        // Partial GiBs round up per medium: 1 GiB + (1 GiB + 1 byte) = 3 GB.
        expect(nestedMinDiskSize([withMedia("a", "iso-a"), withMedia("b", "iso-b")], {catalog: [], media}))
            .toBe(32 + 20 + 3);
    });

    it("reserves the upload limit for an entry with no recorded size or no catalog match", () => {
        const unsized = {...debian, id: "old-sync", media_sha256: null, media_size_bytes: null};
        const guests = [{...guest("old", 10), os_id: "old-sync"}, {...guest("lost", 10), os_id: "not-loaded"}];
        expect(nestedMediaSizes(guests, {catalog: [unsized], media: []}))
            .toEqual({"old-sync": 20 * GIB, "not-loaded": 20 * GIB});
        expect(nestedMinDiskSize(guests, {catalog: [unsized], media: []})).toBe(20 + 20 + 12 + 40);
    });

    it("accepts a complete Host step", () => {
        expect(validateHostStep(validHost(), machineTypes, context)).toEqual({});
    });

    it("flags every empty required Host field", () => {
        const errors = validateHostStep({...initialNestedWizardState(), build_machine_type: ""}, machineTypes, context);
        expect(Object.keys(errors).sort()).toEqual(
            ["build_machine_type", "description", "machine_type", "server_name", "ssh_key", "username"]
        );
    });

    it.each([
        ["Upper", true],
        ["ends-with-", true],
        ["1starts-with-digit", true],
        ["a".repeat(55), true],
        ["image-foo", true],
        ["nested", true],
        ["agoge", true],
        ["google", true],
        ["a".repeat(54), false],
        ["x", false],
        ["lab-host-2", false],
    ])("server name %s is rejected: %s", (name, rejected) => {
        expect(!!validateNestedServerName(name)).toBe(rejected);
    });

    it("rejects a description over 200 characters", () => {
        expect(validateHostStep(validHost({description: "d".repeat(201)}), machineTypes, context).description)
            .toMatch(/200/);
    });

    it("rejects a machine type outside the nested-capable list", () => {
        const errors = validateHostStep(validHost({machine_type: "e2-standard-8"}), machineTypes, context);
        expect(errors.machine_type).toMatch(/N1 or N2/);
        // While the list has not loaded, a chosen value is not second-guessed.
        expect(validateHostStep(validHost({machine_type: "e2-standard-8"}), [], context).machine_type).toBeUndefined();
    });

    it("lets the disk size go up from the computed minimum but not below it or above 1000 GB", () => {
        const guests = [guest("kali", 40)];
        expect(validateHostStep(validHost({guests, disk_size: 73}), machineTypes, context).disk_size).toBeUndefined();
        expect(validateHostStep(validHost({guests, disk_size: 500}), machineTypes, context).disk_size).toBeUndefined();
        expect(validateHostStep(validHost({guests, disk_size: 72}), machineTypes, context).disk_size).toMatch(/73 to 1000/);
        // Without the 1 GB media reservation, 72 would pass here and get a 400 from the API.
        expect(validateHostStep(validHost({guests, disk_size: 1001}), machineTypes, context).disk_size).toBeDefined();
        expect(validateHostStep(validHost({guests, disk_size: 80.5}), machineTypes, context).disk_size).toBeDefined();
    });

    it("applies the API's username rule and requires an OpenSSH public key", () => {
        expect(validateHostStep(validHost({username: "bad user"}), machineTypes, context).username).toBeDefined();
        expect(validateHostStep(validHost({username: "u".repeat(21)}), machineTypes, context).username).toBeDefined();
        expect(validateHostStep(validHost({ssh_key: "not a key"}), machineTypes, context).ssh_key).toBeDefined();
        expect(validateHostStep(validHost({ssh_key: "ssh-rsa AAAAB3NzaC1yc2E="}), machineTypes, context).ssh_key)
            .toBeUndefined();
    });

    it("requires a network and a guest, and Review names the first broken step", () => {
        expect(validateStep(NestedWizardSteps.Networks, validHost({networks: []}), machineTypes)).toEqual(
            {networks: "Add at least one network."}
        );
        expect(validateStep(NestedWizardSteps.Guests, validHost(), machineTypes)).toEqual(
            {guests: "Add at least one guest."}
        );
        expect(validateStep(NestedWizardSteps.Review, validHost(), machineTypes).review).toMatch(/Guests/);
        expect(validateStep(NestedWizardSteps.Review, validHost({server_name: ""}), machineTypes).review)
            .toMatch(/Host/);
        // Guest rules need the catalog: without it every guest reads as an unknown OS.
        const guests = [guest("kali", 40)];
        expect(validateStep(NestedWizardSteps.Review, validHost({guests}), machineTypes).review).toMatch(/Guests/);
        expect(validateStep(NestedWizardSteps.Review, validHost({guests}), machineTypes, {catalog: [debian], media: []}))
            .toEqual({});
    });

    it("moves back freely and forward only through valid steps", () => {
        const empty = initialNestedWizardState();
        // Host (0) invalid: forward goes nowhere.
        expect(resolveNavigation(0, 1, empty, machineTypes)).toBe(0);
        expect(resolveNavigation(0, 4, empty, machineTypes)).toBe(0);
        // Host valid, no guests: jumping to Review stops at Guests (2).
        expect(resolveNavigation(0, 4, validHost(), machineTypes)).toBe(2);
        expect(resolveNavigation(0, 2, validHost(), machineTypes)).toBe(2);
        // Back is always allowed, even from a broken state.
        expect(resolveNavigation(3, 1, empty, machineTypes)).toBe(1);
        // A guest change that breaks the Host disk size sends a forward move back to Host.
        const broken = validHost({guests: [guest("kali", 40)], disk_size: 40});
        expect(resolveNavigation(3, 4, broken, machineTypes)).toBe(0);
    });
});
