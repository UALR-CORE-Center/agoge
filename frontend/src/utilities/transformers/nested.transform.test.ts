import { describe, expect, it } from "vitest";
import { NestedHostSpec, NestedImageCreateRequest } from "../../services/Server/nested.model";
import {
    toNestedImageCreateRequest,
    transformToNestedBuildStatus,
    transformToNestedHostSpec,
    transformToNestedMedia,
    transformToNestedMediaUpload,
    transformToNestedOsCatalogEntry,
} from "./nested.transform";

const storedSpec: NestedHostSpec = {
    parent_os: "debian-13",
    build_machine_type: "n2-standard-16",
    networks: [
        { name: "dmz", cidr: "10.20.0.0/24", mode: "nat", parent_address: "10.20.0.1", dhcp: true, dhcp_start: "10.20.0.100", dhcp_end: "10.20.0.200" },
        { name: "core", cidr: "10.30.0.0/29", mode: "isolated", parent_address: null, dhcp: false, dhcp_start: null, dhcp_end: null },
    ],
    guests: [
        {
            name: "dc01", os_id: "win2022-eval", media_id: null, vcpus: 4, memory_mb: 8192, disk_gb: 80,
            nics: [{ network: "core", ip: "10.30.0.2", expose: false }],
            admin_username: "Administrator", admin_password: "P@ssw0rd!", packages: [],
            post_install_script: "Install-WindowsFeature AD-Domain-Services", console: true,
            autostart: true, start_order: 0, start_delay_seconds: 0,
        },
        {
            name: "web", os_id: "custom-appliance", media_id: "m1", vcpus: 1, memory_mb: 1024, disk_gb: 10,
            nics: [{ network: "dmz", ip: null, expose: true }, { network: "core", ip: "10.30.0.3", expose: false }],
            admin_username: "admin", admin_password: "pw", packages: ["nginx"], post_install_script: null,
            console: false, autostart: false, start_order: 5, start_delay_seconds: 60,
        },
    ],
    exposures: [["web", 0]],
    console_ports: { dc01: 5901 },
    vnc_passwords: { dc01: "abcdefgh" },
};

const request = (nested: NestedImageCreateRequest["nested"]): NestedImageCreateRequest => ({
    server_name: " range-host ",
    description: "AD range",
    labels: ["ad"],
    machine_type: "n2-standard-8",
    disk_size: 200,
    username: "agoge",
    ssh_key: "ssh-ed25519 AAAA\n",
    nested,
    product_keys: { dc01: " AAAAA-BBBBB ", web: "" },
});

describe("nested transformers", () => {
    it("round-trips a stored host spec through a create request", () => {
        const loaded = transformToNestedHostSpec(structuredClone(storedSpec));
        expect(loaded).toEqual(storedSpec);

        const body = toNestedImageCreateRequest(request(loaded));
        const { parent_os, build_machine_type, networks, guests } = storedSpec;
        const clientFields = { parent_os, build_machine_type, networks, guests };
        // The derived fields never leave the client; everything else survives unchanged.
        expect(body.nested).toStrictEqual(clientFields);

        expect(transformToNestedHostSpec(body.nested)).toEqual({
            ...clientFields, exposures: [], console_ports: {}, vnc_passwords: {},
        });
    });

    it("trims identity fields and drops blank product keys", () => {
        const body = toNestedImageCreateRequest(request(storedSpec));
        expect(body).toMatchObject({
            server_name: "range-host", username: "agoge", ssh_key: "ssh-ed25519 AAAA",
            disk_size: 200, product_keys: { dc01: "AAAAA-BBBBB" },
        });
        expect(toNestedImageCreateRequest({ ...request(storedSpec), disk_size: undefined as unknown as null }).disk_size).toBeNull();
    });

    it("fills model defaults on a sparse stored spec", () => {
        const spec = transformToNestedHostSpec({
            networks: [{ name: "lan", cidr: "10.0.0.0/24", mode: "nat" } as NestedHostSpec["networks"][0]],
            guests: [{ name: "kali", os_id: "kali", nics: [{ network: "lan" }], admin_username: "kali" } as unknown as NestedHostSpec["guests"][0]],
        });
        expect(spec).toMatchObject({ parent_os: "debian-12", build_machine_type: "n2-standard-8", exposures: [] });
        expect(spec.networks[0]).toEqual({
            name: "lan", cidr: "10.0.0.0/24", mode: "nat", parent_address: null, dhcp: true, dhcp_start: null, dhcp_end: null,
        });
        expect(spec.guests[0]).toMatchObject({
            vcpus: 1, memory_mb: 2048, disk_gb: 20, media_id: null, admin_password: "", packages: [],
            console: true, autostart: true, start_order: 0, start_delay_seconds: 0,
            nics: [{ network: "lan", ip: null, expose: false }],
        });
    });

    it("defaults a missing build status to queued", () => {
        expect(transformToNestedBuildStatus(null)).toEqual({
            phase: "queued", guests: {}, message: null, heartbeat_at: null, started_at: null, updated_at: null,
        });
    });

    it("normalizes catalog, media and upload responses", () => {
        const entry = transformToNestedOsCatalogEntry({
            id: "win11-eval", display_name: "Windows 11", family: "windows", group: "windows_client", version: "24H2",
            install_method: "unattended_iso", media_formats: ["iso"], requires_upload: true, license_note: "90-day eval",
            osinfo: "win11", agent: true, net_config: "windows", min_memory_mb: 4096, default_memory_mb: 8192,
            min_disk_gb: 64, default_disk_gb: 80, is_enabled: false, firmware: "uefi",
        } as Parameters<typeof transformToNestedOsCatalogEntry>[0]);
        expect(entry).toMatchObject({
            media_url: null, media_size_bytes: null, eval_days: null, firmware: "uefi", disk_bus: "virtio", video: "vga",
            unattend_template: null, default_vcpus: 1, is_enabled: false, requires_upload: true,
        });

        // A downloaded entry keeps its size: the wizard reserves it on the parent disk.
        expect(transformToNestedOsCatalogEntry({
            id: "debian-12", display_name: "Debian 12", family: "linux", group: "linux", version: "12",
            install_method: "cloud_image", media_url: "https://example.test/debian.qcow2", media_sha256: "abc",
            media_size_bytes: 400000000, media_formats: ["qcow2"], osinfo: "debian12", net_config: "networkd",
            min_memory_mb: 512, default_memory_mb: 2048, min_disk_gb: 4, default_disk_gb: 20,
        } as Parameters<typeof transformToNestedOsCatalogEntry>[0])).toMatchObject({media_size_bytes: 400000000});

        expect(transformToNestedMedia({
            id: "m1", filename: "a.iso", format: "iso", size_bytes: 1, gcs_path: "gs://b/media/m1/a.iso",
            uploaded_by: "t@example.edu", uploaded_at: "2026-10-17T00:00:00Z",
        } as Parameters<typeof transformToNestedMedia>[0])).toMatchObject({ sha256: null, os_id: null, complete: false });

        const headers = { "x-goog-resumable": "start" };
        const upload = transformToNestedMediaUpload({ media_id: "m1", upload_url: "https://u", upload_headers: headers, expires_in: 60 });
        expect(upload.upload_headers).toEqual(headers);
        expect(upload.upload_headers).not.toBe(headers);
    });
});
