import {describe, expect, it} from "vitest";
import {NestedGuest, NestedMedia, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {
    dropProductKey,
    generatePassword,
    GuestsInput,
    mediaFormat,
    newGuest,
    nextGuestName,
    osChipLabels,
    renameProductKey,
    usableMedia,
    validateGuests,
    validateMediaFile,
} from "./guestRules";
import {defaultNestedNetwork} from "./nestedWizardState";

const entry = (overrides: Partial<NestedOsCatalogEntry>): NestedOsCatalogEntry => ({
    id: "debian-12", display_name: "Debian 12", family: "linux", group: "linux", version: "12",
    install_method: "cloud_image", media_url: "https://example.test/debian.qcow2", media_sha256: null,
    media_size_bytes: null,
    media_formats: ["qcow2"], requires_upload: false, license_note: "Free software.", eval_days: null,
    osinfo: "debian12", firmware: "bios", disk_bus: "virtio", nic_model: "virtio", video: "virtio",
    virtio_win_version: null, agent: true, net_config: "networkd", unattend_template: null,
    windows_image_index: null, default_username: "debian", min_memory_mb: 512, default_memory_mb: 2048,
    min_disk_gb: 4, default_disk_gb: 20, default_vcpus: 2, is_enabled: true,
    ...overrides,
});

const debian = entry({});
const server2019 = entry({
    id: "windows-server-2019", display_name: "Windows Server 2019", family: "windows", group: "windows_server",
    install_method: "unattended_iso", media_url: null, media_formats: ["iso"], requires_upload: true,
    eval_days: null, default_username: "Administrator", min_memory_mb: 2048, min_disk_gb: 32,
});
const server2025Eval = entry({...server2019, id: "windows-server-2025-eval", eval_days: 180, display_name: "Server 2025 (eval)"});
const appliance = entry({
    id: "pfsense", display_name: "pfSense", family: "appliance", group: "appliance",
    install_method: "manual_iso", agent: false, requires_upload: true, media_formats: ["iso"],
});
const catalog = [debian, server2019, server2025Eval, appliance];

const media = (overrides: Partial<NestedMedia>): NestedMedia => ({
    id: "m1", filename: "server2019.iso", format: "iso", size_bytes: 5e9, gcs_path: "gs://b/media/m1/server2019.iso",
    sha256: null, os_id: "windows-server-2019", uploaded_by: "gm@example.test", uploaded_at: "2026-10-17T00:00:00Z",
    complete: true, ...overrides,
});

const guest = (overrides: Partial<NestedGuest> = {}): NestedGuest => ({
    name: "kali", os_id: "debian-12", media_id: null, vcpus: 2, memory_mb: 2048, disk_gb: 20,
    nics: [{network: "lab", ip: null, expose: false}], admin_username: "student", admin_password: "Passw0rd!",
    packages: [], post_install_script: null, console: true, autostart: true, start_order: 0, start_delay_seconds: 0,
    ...overrides,
});

const machineTypes: ServerMachineTypes[] = [
    {id: "1", name: "n2-standard-8", description: "", is_shared_core: false, memory_mb: 32768, guest_cpus: 8},
    {id: "2", name: "n1-standard-2", description: "", is_shared_core: false, memory_mb: 7680, guest_cpus: 2},
];

const input = (guests: NestedGuest[], overrides: Partial<GuestsInput> = {}): GuestsInput => ({
    guests, networks: [defaultNestedNetwork()], product_keys: {},
    build_machine_type: "n2-standard-8", machine_type: "n2-standard-8", ...overrides,
});

const check = (guests: NestedGuest[], overrides: Partial<GuestsInput> = {}, library: NestedMedia[] = []) =>
    validateGuests(input(guests, overrides), {catalog, media: library}, machineTypes);

describe("guestRules", () => {
    it("accepts a valid guest and requires at least one", () => {
        expect(check([guest()])).toEqual({});
        expect(check([])).toEqual({guests: "Add at least one guest."});
    });

    it("checks the name pattern, uniqueness, and an unknown or disabled OS", () => {
        expect(check([guest({name: "Kali"})])["guests.0.name"]).toMatch(/lowercase/);
        expect(check([guest(), guest()])["guests.1.name"]).toBe("Another guest already uses this name.");
        expect(check([guest({os_id: "gone"})])["guests.0.os_id"]).toMatch(/not in the catalog/);
        const disabled = validateGuests(input([guest()]), {catalog: [{...debian, is_enabled: false}], media: []}, []);
        expect(disabled["guests.0.os_id"]).toBeDefined();
    });

    it("applies the catalog minimums and the model limits to vCPU, memory, and disk", () => {
        expect(check([guest({memory_mb: 511})])["guests.0.memory_mb"]).toBe("Use 512 to 32768 MB.");
        expect(check([guest({disk_gb: 3})])["guests.0.disk_gb"]).toBe("Use 4 to 500 GB.");
        expect(check([guest({vcpus: 9})])["guests.0.vcpus"]).toBeDefined();
        expect(check([guest({vcpus: NaN})])["guests.0.vcpus"]).toBeDefined();
        expect(check([guest({start_order: 100})])["guests.0.start_order"]).toBeDefined();
        expect(check([guest({start_delay_seconds: 601})])["guests.0.start_delay_seconds"]).toBeDefined();
    });

    it("checks the admin username, password length, and Windows complexity", () => {
        expect(check([guest({admin_username: "1admin"})])["guests.0.admin_username"]).toBeDefined();
        expect(check([guest({admin_password: "short"})])["guests.0.admin_password"]).toMatch(/at least 8/);
        // Linux needs only the length.
        expect(check([guest({admin_password: "alllowercase"})])["guests.0.admin_password"]).toBeUndefined();
        const windows = guest({name: "dc01", os_id: "windows-server-2025-eval", media_id: "m1", disk_gb: 40, admin_password: "alllowercase1"});
        expect(check([windows], {}, [media({os_id: null})])["guests.0.admin_password"]).toMatch(/three of/);
        expect(check([{...windows, admin_password: "Lower1case"}], {}, [media({os_id: null})])).toEqual({});
    });

    it("needs a product key for retail Windows but not for evaluation media", () => {
        const retail = guest({name: "dc01", os_id: "windows-server-2019", media_id: "m1", disk_gb: 40});
        expect(check([retail], {}, [media({})])["guests.0.product_key"]).toMatch(/product key/);
        expect(check([retail], {product_keys: {dc01: "abcde-12345"}}, [media({})])["guests.0.product_key"]).toBeDefined();
        expect(check([retail], {product_keys: {dc01: "ABCDE-12345-FGHIJ-67890-KLMNO"}}, [media({})])).toEqual({});
        const evaluation = {...retail, os_id: "windows-server-2025-eval"};
        expect(check([evaluation], {}, [media({os_id: null})])["guests.0.product_key"]).toBeUndefined();
    });

    it("blocks a requires_upload guest without completed media in an accepted format", () => {
        const dc = guest({name: "dc01", os_id: "windows-server-2019", disk_gb: 40});
        const keys = {product_keys: {dc01: "ABCDE-12345-FGHIJ-67890-KLMNO"}};
        expect(check([dc], keys)["guests.0.media_id"]).toMatch(/needs uploaded media/);
        expect(check([{...dc, media_id: "m1"}], keys, [media({complete: false})])["guests.0.media_id"]).toMatch(/not complete/);
        expect(check([{...dc, media_id: "m1"}], keys, [])["guests.0.media_id"]).toMatch(/not complete/);
        expect(check([{...dc, media_id: "m1"}], keys, [media({format: "qcow2"})])["guests.0.media_id"]).toMatch(/not qcow2/);
        expect(check([{...dc, media_id: "m1"}], keys, [media({})])).toEqual({});
    });

    it("allows packages only on Linux cloud images, with valid names", () => {
        expect(check([guest({packages: ["nmap", "python3-pip"]})])).toEqual({});
        expect(check([guest({packages: ["Bad Name"]})])["guests.0.packages"]).toBe("Bad Name is not a valid package name.");
        const fw = guest({name: "fw", os_id: "pfsense", media_id: "m2", packages: ["nmap"]});
        expect(check([fw], {}, [media({id: "m2", os_id: "pfsense"})])["guests.0.packages"]).toMatch(/only supported/);
    });

    it("checks NIC networks, static addresses, exposure, and duplicates across guests", () => {
        const nic = (ip: string | null, expose = false, network = "lab") => [{network, ip, expose}];
        expect(check([guest({nics: nic(null, false, "gone")})])["guests.0.nics.0.network"]).toBe("Choose a network.");
        expect(check([guest({nics: nic(null, true)})])["guests.0.nics.0.expose"]).toMatch(/static IP/);
        expect(check([guest({nics: nic("")})])["guests.0.nics.0.ip"]).toMatch(/IPv4/);
        expect(check([guest({nics: nic("10.0.0.5")})])["guests.0.nics.0.ip"]).toMatch(/inside 192.168.100.0\/24/);
        expect(check([guest({nics: nic("192.168.100.255")})])["guests.0.nics.0.ip"]).toMatch(/host address/);
        expect(check([guest({nics: nic("192.168.100.1")})])["guests.0.nics.0.ip"]).toMatch(/parent's address/);
        expect(check([guest({nics: nic("192.168.100.150")})])["guests.0.nics.0.ip"]).toMatch(/DHCP range/);
        expect(check([guest({nics: nic("192.168.100.10", true)})])).toEqual({});
        const two = [guest({nics: nic("192.168.100.10")}), guest({name: "ws01", nics: nic("192.168.100.10")})];
        expect(check(two)["guests.1.nics.0.ip"]).toBe("192.168.100.10 is already used by kali.");
        expect(check([guest({nics: []})])["guests.0.nics"]).toBeDefined();
    });

    it("caps exposures at eight across all guests", () => {
        const guests = [0, 1, 2].map(n => guest({
            name: `g${n}x`,
            nics: [0, 1, 2].map(i => ({network: "lab", ip: `192.168.100.${10 + n * 3 + i}`, expose: true})),
        }));
        const errors = check(guests);
        // Nine exposed NICs: the ninth (guest 2, NIC 2) is the one over the limit.
        expect(errors["guests.2.nics.2.expose"]).toMatch(/At most 8/);
        expect(errors["guests.2.nics.1.expose"]).toBeUndefined();
    });

    it("checks the guests' memory and vCPUs against both machine types", () => {
        const big = [guest({memory_mb: 4096, vcpus: 4}), guest({name: "ws01", memory_mb: 2048})];
        expect(check(big)).toEqual({});
        expect(check(big, {machine_type: "n1-standard-2"}).guests).toMatch(/n1-standard-2 has 7680 MB.*8192 MB/);
        expect(check([guest({vcpus: 5})], {machine_type: "n1-standard-2"}).guests).toMatch(/at most 4 guest vCPUs/);
    });

    it("builds a new guest from catalog defaults with a unique name and a complex password", () => {
        const first = newGuest(server2019, [], [defaultNestedNetwork()]);
        expect(first).toMatchObject({
            name: "winsrv", os_id: "windows-server-2019", memory_mb: 2048, disk_gb: 32, vcpus: 2,
            admin_username: "Administrator", nics: [{network: "lab", ip: null, expose: false}], start_order: 0,
        });
        expect(nextGuestName([first], server2019)).toBe("winsrv-2");
        expect(newGuest(debian, [first], []).start_order).toBe(1);
        for (let run = 0; run < 20; run++) {
            const password = generatePassword();
            expect(password).toHaveLength(16);
            expect(password).toMatch(/[A-Z]/);
            expect(password).toMatch(/[a-z]/);
            expect(password).toMatch(/[0-9]/);
            expect(password).toMatch(/[^A-Za-z0-9]/);
        }
    });

    it("pre-checks media files and filters the library", () => {
        expect(mediaFormat("disk.img.xz")).toBe("img.xz");
        expect(mediaFormat("OPNsense-26.7-nano-amd64.img.bz2")).toBe("img.bz2");
        expect(mediaFormat("pfSense-CE-2.7.2-RELEASE-amd64.iso.gz")).toBe("iso.gz");
        expect(mediaFormat("README")).toBeNull();
        expect(validateMediaFile({name: "ws2019.iso", size: 5e9}, server2019)).toBe("");
        expect(validateMediaFile({name: "ws2019.qcow2", size: 5e9}, server2019)).toMatch(/accepts iso/);
        expect(validateMediaFile({name: ".hidden.iso", size: 5e9}, server2019)).toMatch(/Rename/);
        expect(validateMediaFile({name: "big.iso", size: 21474836481}, server2019)).toMatch(/20 GiB/);
        const library = [
            media({}), media({id: "m2", os_id: null}), media({id: "m3", complete: false}),
            media({id: "m4", os_id: "pfsense"}), media({id: "m5", format: "qcow2", os_id: null}),
        ];
        expect(usableMedia(library, server2019).map(item => item.id)).toEqual(["m1", "m2"]);
    });

    it("labels the picker chips and carries product keys through renames and removals", () => {
        expect(osChipLabels(debian)).toEqual(["Auto install"]);
        expect(osChipLabels(server2025Eval)).toEqual(["Auto install", "Upload required", "Eval 180 days"]);
        expect(osChipLabels(appliance)).toEqual(["Manual install", "Upload required", "No agent"]);
        expect(renameProductKey({dc01: "K"}, "dc01", "dc02")).toEqual({dc02: "K"});
        expect(renameProductKey({dc01: "K"}, "ws01", "ws02")).toEqual({dc01: "K"});
        expect(dropProductKey({dc01: "K", ws01: "L"}, "dc01")).toEqual({ws01: "L"});
    });
});
