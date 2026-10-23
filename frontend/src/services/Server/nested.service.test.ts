import axios from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NestedImageCreateRequest } from "./nested.model";
import { nestedService } from "./nested.service";

vi.mock("axios", async (importOriginal) => {
    const actual = await importOriginal<typeof import("axios")>();
    return {
        default: {
            get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(),
            isAxiosError: actual.default.isAxiosError, isCancel: actual.default.isCancel, Cancel: actual.default.Cancel,
        },
    };
});
vi.mock("../../components/AgogeAuth/Firebase/firebaseConfig", () => ({
    auth: { currentUser: { getIdToken: vi.fn().mockResolvedValue("test-token") } },
}));
vi.mock("../../utilities/apiClient", () => ({ apiUrl: (endpoint: string) => endpoint }));

const authHeaders = { headers: { "Content-Type": "application/json", Authorization: "Bearer test-token" } };

const media = {
    id: "m1",
    filename: "kali.qcow2",
    format: "qcow2",
    size_bytes: 4,
    gcs_path: "gs://p_nested-media/media/m1/kali.qcow2",
    sha256: null,
    os_id: "kali-2025",
    uploaded_by: "t@example.edu",
    uploaded_at: "2026-10-17T00:00:00Z",
    complete: true,
};

const signed = {
    media_id: "m1",
    upload_url: "https://storage.googleapis.com/p_nested-media/media/m1/kali.qcow2?X-Goog-Signature=abc",
    upload_headers: { "x-goog-resumable": "start", "x-goog-content-length-range": "0,21474836480" },
    expires_in: 3600,
};

const session = "https://storage.googleapis.com/upload/session-123";

const createRequest = (): NestedImageCreateRequest => ({
    server_name: "range-host",
    description: "Two guests",
    labels: [],
    machine_type: "n2-standard-4",
    disk_size: null,
    username: "agoge",
    ssh_key: "ssh-ed25519 AAAA",
    nested: {
        parent_os: "debian-12",
        build_machine_type: "n2-standard-8",
        networks: [{
            name: "lan", cidr: "10.10.0.0/24", mode: "nat", parent_address: "10.10.0.1",
            dhcp: true, dhcp_start: null, dhcp_end: null,
        }],
        guests: [{
            name: "kali", os_id: "kali-2025", media_id: null, vcpus: 2, memory_mb: 4096, disk_gb: 40,
            nics: [{ network: "lan", ip: null, expose: false }],
            admin_username: "kali", admin_password: "pw", packages: [], post_install_script: null,
            console: true, autostart: true, start_order: 0, start_delay_seconds: 0,
        }],
    },
    product_keys: {},
});

const file = () => new File(["abcd"], "kali.qcow2");

describe("nested service", () => {
    beforeEach(() => vi.clearAllMocks());

    it("lists nested-capable machine types with nested=true", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [{ id: "1", name: "n2-standard-8" }] } } });
        expect(await nestedService.list_machine_types()).toEqual([{ id: "1", name: "n2-standard-8" }]);
        expect(axios.get).toHaveBeenCalledWith("compute/images/machine-types/", { ...authHeaders, params: { nested: true } });
    });

    it("lists the OS catalog through the transformer", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [{
            id: "kali-2025", display_name: "Kali", family: "linux", group: "kali", version: "2025",
            install_method: "cloud_image", media_formats: ["qcow2"], license_note: "", osinfo: "debian12",
            agent: true, net_config: "networkd", min_memory_mb: 1024, default_memory_mb: 4096,
            min_disk_gb: 20, default_disk_gb: 40,
        }] } } });
        const [entry] = await nestedService.list_catalog();
        expect(axios.get).toHaveBeenCalledWith("compute/images/nested/catalog/", { ...authHeaders, params: null });
        expect(entry).toMatchObject({ id: "kali-2025", media_url: null, requires_upload: false, is_enabled: true });
    });

    it("posts the create request without derived fields and returns the build id", async () => {
        vi.mocked(axios.post).mockResolvedValue({ data: { data: { build_id: "range-host" } } });
        const request = createRequest();
        // A spec copied from an existing image carries fields the API refuses on create.
        const nested = { ...request.nested, exposures: [["kali", 0]], console_ports: { kali: 5901 } };

        expect(await nestedService.create({ ...request, nested, product_keys: { kali: " " } }))
            .toEqual({ build_id: "range-host" });
        expect(axios.post).toHaveBeenCalledWith("compute/images/nested/", createRequest(), authHeaders);
    });

    it("gets the build status for an encoded image name and drops the finalize nonce", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: {
            phase: "building", guests: { kali: "installing" }, guest_addresses: { kali: { "0": "192.168.100.10" } },
            finalize_nonce: "secret",
        } } });
        const status = await nestedService.get_build_status("range host");
        expect(axios.get).toHaveBeenCalledWith("compute/images/range%20host/nested-build/", { ...authHeaders, params: null });
        expect(status).toEqual({
            phase: "building", guests: { kali: "installing" }, guest_addresses: { kali: { "0": "192.168.100.10" } }, message: null,
            heartbeat_at: null, started_at: null, updated_at: null,
        });
    });

    it("requests a signed upload, sending os_id only when set", async () => {
        vi.mocked(axios.post).mockResolvedValue({ data: { data: signed } });
        expect(await nestedService.create_media({ filename: "a.iso", size_bytes: 9, os_id: "win11" })).toEqual(signed);
        expect(axios.post).toHaveBeenLastCalledWith(
            "compute/images/nested/media/", { filename: "a.iso", size_bytes: 9, os_id: "win11" }, authHeaders
        );
        await nestedService.create_media({ filename: "a.iso", size_bytes: 9, os_id: null });
        expect(axios.post).toHaveBeenLastCalledWith("compute/images/nested/media/", { filename: "a.iso", size_bytes: 9 }, authHeaders);
    });

    it("lists, completes and deletes media", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [media] } } });
        expect(await nestedService.list_media()).toEqual([media]);
        expect(axios.get).toHaveBeenCalledWith("compute/images/nested/media/", { ...authHeaders, params: null });

        vi.mocked(axios.put).mockResolvedValue({ data: { data: media } });
        expect(await nestedService.complete_media("m1")).toEqual(media);
        expect(axios.put).toHaveBeenCalledWith("compute/images/nested/media/m1/", {}, authHeaders);

        vi.mocked(axios.delete).mockResolvedValue({ data: { data: { build_id: "m1" } } });
        expect(await nestedService.delete_media("m1")).toEqual({ build_id: "m1" });
        expect(axios.delete).toHaveBeenCalledWith("compute/images/nested/media/m1/", authHeaders);
    });
});

describe("nested media upload", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(axios.post).mockImplementation(async (url: string) =>
            url === signed.upload_url ? { headers: { location: session } } : { data: { data: signed } }
        );
        vi.mocked(axios.put).mockImplementation(async (url: string) =>
            url === session ? {} : { data: { data: media } }
        );
        vi.mocked(axios.delete).mockResolvedValue({ data: { data: { build_id: "m1" } } });
    });

    it("starts the session with only the signed headers, sends the bytes, then completes", async () => {
        const onProgress = vi.fn();
        const upload = file();
        expect(await nestedService.upload_media(upload, { osId: "kali-2025", onProgress })).toEqual(media);

        expect(axios.post).toHaveBeenNthCalledWith(
            1, "compute/images/nested/media/", { filename: "kali.qcow2", size_bytes: 4, os_id: "kali-2025" }, authHeaders
        );
        // No Authorization header goes to Cloud Storage: the signature covers exactly upload_headers.
        expect(axios.post).toHaveBeenNthCalledWith(2, signed.upload_url, null, { headers: signed.upload_headers, signal: undefined });
        expect(axios.put).toHaveBeenNthCalledWith(1, session, upload, expect.objectContaining({ signal: undefined }));
        expect(axios.put).toHaveBeenNthCalledWith(2, "compute/images/nested/media/m1/", {}, authHeaders);

        const { onUploadProgress } = vi.mocked(axios.put).mock.calls[0][2] as { onUploadProgress: (e: object) => void };
        onUploadProgress({ loaded: 2 });
        expect(onProgress).toHaveBeenCalledWith(2, 4);
        expect(axios.delete).not.toHaveBeenCalled();
    });

    it("deletes the record when Cloud Storage refuses the session", async () => {
        vi.mocked(axios.post).mockImplementation(async (url: string) => {
            if (url === signed.upload_url) {
                throw Object.assign(new Error("forbidden"), { isAxiosError: true, response: { status: 403 } });
            }
            return { data: { data: signed } };
        });
        await expect(nestedService.upload_media(file())).rejects.toMatchObject({
            status: 403, message: expect.stringContaining("starting the upload"),
        });
        expect(axios.delete).toHaveBeenCalledWith("compute/images/nested/media/m1/", authHeaders);
        expect(axios.put).not.toHaveBeenCalled();
    });

    it("fails with a CORS hint when the session URI is hidden", async () => {
        vi.mocked(axios.post).mockImplementation(async (url: string) =>
            url === signed.upload_url ? { headers: {} } : { data: { data: signed } }
        );
        await expect(nestedService.upload_media(file())).rejects.toMatchObject({
            status: 502, message: expect.stringContaining("CORS"),
        });
        expect(axios.delete).toHaveBeenCalledTimes(1);
    });

    it("deletes the record when sending the bytes fails, and keeps the original error if cleanup fails", async () => {
        vi.mocked(axios.put).mockRejectedValue(Object.assign(new Error("reset"), { isAxiosError: true, response: { status: 410 } }));
        vi.mocked(axios.delete).mockRejectedValue(new Error("cleanup failed"));
        await expect(nestedService.upload_media(file())).rejects.toMatchObject({
            status: 410, message: expect.stringContaining("sending the file"),
        });
        expect(axios.delete).toHaveBeenCalledTimes(1);
    });

    it("reports a cancelled upload", async () => {
        vi.mocked(axios.put).mockRejectedValue(new axios.Cancel("aborted"));
        await expect(nestedService.upload_media(file())).rejects.toMatchObject({ status: 499 });
        expect(axios.delete).toHaveBeenCalledTimes(1);
    });

    it("keeps the uploaded bytes when the completion check fails", async () => {
        vi.mocked(axios.put).mockImplementation(async (url: string) => {
            if (url === session) {
                return {};
            }
            throw { response: { status: 503, data: { detail: "Cloud Storage is unavailable." } } };
        });
        await expect(nestedService.upload_media(file())).rejects.toMatchObject({
            status: 503, message: "Cloud Storage is unavailable.",
        });
        expect(axios.delete).not.toHaveBeenCalled();
    });
});
