// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {MemoryRouter} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_TEACHER_SERVERS} from "../../../../../router/urls";
import {nestedService} from "../../../../../services/Server/nested.service";
import NestedImageWizard from "./NestedImageWizard";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (importOriginal) => ({
    ...await importOriginal<typeof import("react-router-dom")>(),
    useNavigate: () => navigate,
}));
vi.mock("../../../../../services/Server/nested.service", () => ({
    nestedService: {
        list_machine_types: vi.fn(), list_catalog: vi.fn(), list_media: vi.fn(), upload_media: vi.fn(), create: vi.fn(),
    },
}));

const machineTypes = [
    {id: "1", name: "n2-standard-8", description: "", is_shared_core: false, memory_mb: 32768, guest_cpus: 8},
    {id: "2", name: "n1-standard-4", description: "", is_shared_core: false, memory_mb: 15360, guest_cpus: 4},
];

const renderWizard = () => render(<MemoryRouter><NestedImageWizard /></MemoryRouter>);

const heading = () => screen.getByRole("heading", {level: 2});

const chooseOption = (labelText: RegExp, option: RegExp) => {
    fireEvent.mouseDown(screen.getByRole("combobox", {name: labelText}));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name: option}));
};

const fillHost = () => {
    fireEvent.change(screen.getByRole("textbox", {name: /Server Name/}), {target: {value: "ad-lab-host"}});
    fireEvent.change(screen.getByRole("textbox", {name: /Description/}), {target: {value: "AD lab"}});
    chooseOption(/Lab machine type/, /n1-standard-4/);
    fireEvent.change(screen.getByRole("textbox", {name: /Username/}), {target: {value: "gm"}});
    fireEvent.change(screen.getByRole("textbox", {name: /SSH Public Key/}), {
        target: {value: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0 gm@laptop"},
    });
};

describe("NestedImageWizard", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(nestedService.list_machine_types).mockResolvedValue(machineTypes);
        vi.mocked(nestedService.list_catalog).mockResolvedValue([]);
        vi.mocked(nestedService.list_media).mockResolvedValue([]);
    });
    afterEach(cleanup);

    it("loads nested machine types and pre-selects the default build type", async () => {
        renderWizard();

        expect(await screen.findByRole("combobox", {name: /Build machine type/})).toHaveTextContent("n2-standard-8");
        expect(nestedService.list_machine_types).toHaveBeenCalledTimes(1);
        expect(heading()).toHaveTextContent("Host");
        // The minimum with no guests yet: 20 GB parent + 12 GB scratch.
        expect(screen.getByRole("spinbutton", {name: /Disk Size/})).toHaveValue(32);
    });

    it("keeps an invalid Host step and shows its errors only after Next", async () => {
        renderWizard();
        await screen.findByText(/n2-standard-8/);

        expect(screen.queryByText("Choose a lab machine type.")).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));

        expect(heading()).toHaveTextContent("Host");
        expect(screen.getByLabelText("Host has errors")).toBeInTheDocument();
        expect(screen.getByText("Choose a lab machine type.")).toBeInTheDocument();
        expect(screen.getByText("Enter a description.")).toBeInTheDocument();
    });

    it("clears a default build type the project does not offer", async () => {
        vi.mocked(nestedService.list_machine_types).mockResolvedValue([machineTypes[1]]);
        renderWizard();
        // The spinner goes away once the list has loaded.
        await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());

        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(await screen.findByText("Choose a build machine type.")).toBeInTheDocument();
    });

    it("blocks a step-button jump past an invalid step and allows going back", async () => {
        renderWizard();
        await screen.findByText(/n2-standard-8/);

        fireEvent.click(screen.getByRole("button", {name: "Review"}));
        expect(heading()).toHaveTextContent("Host");

        fillHost();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Networks");
        expect(screen.getByRole("textbox", {name: /CIDR/})).toHaveValue("192.168.100.0/24");

        // No guests yet, so a jump to Review stops on Guests with its error.
        fireEvent.click(screen.getByRole("button", {name: "Review"}));
        expect(heading()).toHaveTextContent("Guests");
        expect(screen.getByText("Add at least one guest.")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: "Back"}));
        expect(heading()).toHaveTextContent("Networks");
        fireEvent.click(screen.getByRole("button", {name: "Host"}));
        expect(screen.getByRole("textbox", {name: /Server Name/})).toHaveValue("ad-lab-host");
    });

    it("lets the disk size be raised but flags a value under the minimum", async () => {
        renderWizard();
        await screen.findByText(/n2-standard-8/);
        fillHost();

        const disk = screen.getByRole("spinbutton", {name: /Disk Size/});
        fireEvent.change(disk, {target: {value: "20"}});
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Host");
        expect(screen.getByText("Use a whole number from 32 to 1000 GB.")).toBeInTheDocument();

        // Clearing the field keeps it empty while typing; it shows the minimum again on blur.
        fireEvent.change(disk, {target: {value: ""}});
        expect(disk).toHaveValue(null);
        fireEvent.blur(disk);
        expect(disk).toHaveValue(32);

        fireEvent.change(disk, {target: {value: "120"}});
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Networks");
    });

    it("reports a machine-type load failure, leaving nothing to choose for the lab type", async () => {
        vi.mocked(nestedService.list_machine_types).mockRejectedValue(new Error("boom"));
        renderWizard();

        expect(await screen.findByText("Could not load machine types: boom")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Host");
        expect(screen.getByText("Choose a lab machine type.")).toBeInTheDocument();
    });

    it("edits networks, flags an overlap after Next, and draws the topology", async () => {
        renderWizard();
        await screen.findByText(/n2-standard-8/);
        fillHost();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Networks");
        // The pre-filled network is the only one, so it cannot be removed.
        expect(screen.getByRole("button", {name: "Remove network 1"})).toBeDisabled();

        fireEvent.click(screen.getByRole("button", {name: /Add network/}));
        const second = within(screen.getByRole("region", {name: "Network 2"}));
        expect(second.getByRole("textbox", {name: /Name/})).toHaveValue("net2");
        expect(second.getByRole("textbox", {name: /CIDR/})).toHaveValue("192.168.101.0/24");
        expect(screen.getAllByTestId("topology-rail")).toHaveLength(2);
        expect(screen.getByRole("img", {name: /2 network\(s\), 0 guest\(s\)/})).toBeInTheDocument();

        fireEvent.change(second.getByRole("textbox", {name: /CIDR/}), {target: {value: "192.168.100.128/25"}});
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Networks");
        expect(screen.getByLabelText("Networks has errors")).toBeInTheDocument();
        expect(second.getByText("Overlaps network lab (192.168.100.0/24).")).toBeInTheDocument();

        // Turning DHCP off hides the range fields; a range that starts after it ends is then not checked.
        fireEvent.change(second.getByRole("textbox", {name: /CIDR/}), {target: {value: "10.0.0.0/24"}});
        expect(second.getByText("Parent address is outside 10.0.0.0/24.")).toBeInTheDocument();
        fireEvent.change(second.getByRole("textbox", {name: /Parent address/}), {target: {value: ""}});
        fireEvent.click(second.getByRole("checkbox", {name: "DHCP"}));
        expect(second.queryByRole("textbox", {name: /DHCP start/})).not.toBeInTheDocument();
        expect(second.getByText("DHCP start is outside 10.0.0.0/24.")).toBeInTheDocument();
        fireEvent.click(second.getByRole("checkbox", {name: "DHCP"}));
        fireEvent.change(second.getByRole("textbox", {name: /DHCP start/}), {target: {value: "10.0.0.100"}});
        fireEvent.change(second.getByRole("textbox", {name: /DHCP end/}), {target: {value: "10.0.0.199"}});
        expect(second.getByText(/^DHCP needs a parent address/)).toBeInTheDocument();
        fireEvent.change(second.getByRole("textbox", {name: /Parent address/}), {target: {value: "10.0.0.1"}});

        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Guests");

        fireEvent.click(screen.getByRole("button", {name: "Back"}));
        fireEvent.click(screen.getByRole("button", {name: "Remove network 2"}));
        expect(screen.queryByRole("region", {name: "Network 2"})).not.toBeInTheDocument();
    });

    it("adds a guest through the OS picker and blocks Next until required media is uploaded", async () => {
        const server2019 = {
            id: "windows-server-2019", display_name: "Windows Server 2019", family: "windows", group: "windows_server",
            version: "2019", install_method: "unattended_iso", media_url: null, media_sha256: null, media_formats: ["iso"],
            media_size_bytes: null,
            requires_upload: true, license_note: "Bring your own volume license.", eval_days: null, osinfo: "win2k19",
            firmware: "uefi", disk_bus: "sata", nic_model: "e1000e", video: "qxl", virtio_win_version: null, agent: true,
            net_config: "windows", unattend_template: "autounattend", windows_image_index: 2,
            default_username: "Administrator", min_memory_mb: 2048, default_memory_mb: 4096, min_disk_gb: 32,
            default_disk_gb: 40, default_vcpus: 2, is_enabled: true,
        } as const;
        const kali = {...server2019, id: "kali-rolling", display_name: "Kali Rolling", version: "2026.3", family: "linux", group: "kali",
            install_method: "cloud_image", requires_upload: false, license_note: "Free software.", agent: true} as const;
        vi.mocked(nestedService.list_catalog).mockResolvedValue([kali, server2019].map(entry => ({...entry, media_formats: [...entry.media_formats]})));
        const uploaded = {
            id: "m1", filename: "ws2019.iso", format: "iso" as const, size_bytes: 4, gcs_path: "gs://b/media/m1/ws2019.iso",
            sha256: null, os_id: "windows-server-2019", uploaded_by: "gm", uploaded_at: "2026-10-17T00:00:00Z", complete: true,
        };
        let finishUpload: (value: typeof uploaded) => void = () => undefined;
        vi.mocked(nestedService.upload_media).mockImplementation((_file, options) => {
            options?.onProgress?.(2, 4);
            return new Promise(resolve => {
                finishUpload = resolve;
            });
        });
        renderWizard();
        await screen.findByText(/n2-standard-8/);
        fillHost();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Guests");

        fireEvent.click(screen.getByRole("button", {name: /Add guest/}));
        const dialog = within(await screen.findByRole("dialog"));
        expect(dialog.getByText("Windows Server")).toBeInTheDocument();
        expect(dialog.getByText("Kali")).toBeInTheDocument();
        fireEvent.change(dialog.getByRole("textbox", {name: /Search/}), {target: {value: "2019"}});
        expect(dialog.queryByText("Kali Rolling")).not.toBeInTheDocument();
        expect(dialog.getByRole("button", {name: "Add guest"})).toBeDisabled();
        fireEvent.click(dialog.getByText("Windows Server 2019"));
        // The license note is on screen before the choice is confirmed.
        expect(dialog.getByLabelText("License note")).toHaveTextContent("Bring your own volume license.");
        expect(dialog.getByText("Upload required")).toBeInTheDocument();
        fireEvent.click(dialog.getByRole("button", {name: "Add guest"}));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

        const section = within(screen.getByRole("region", {name: "Guest 1"}));
        expect(section.getByRole("textbox", {name: /^Name/})).toHaveValue("winsrv");
        expect(section.getByRole("spinbutton", {name: /Disk \(GB\)/})).toHaveValue(40);
        expect(section.getByRole("textbox", {name: /Admin username/})).toHaveValue("Administrator");
        fireEvent.change(section.getByRole("textbox", {name: /Product key/}), {target: {value: "abcde-12345-fghij-67890-klmno"}});

        // No media yet: Next stays on Guests and names the missing upload.
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Guests");
        expect(section.getByText(/needs uploaded media/)).toBeInTheDocument();

        const file = new File(["abcd"], "ws2019.iso");
        fireEvent.change(screen.getByTestId("nested-guest-winsrv-media-file"), {target: {files: [file]}});
        expect(await section.findByLabelText("Upload progress")).toHaveAttribute("aria-valuenow", "50");
        // An edit made while the upload runs survives its completion.
        fireEvent.change(section.getByRole("spinbutton", {name: /Disk \(GB\)/}), {target: {value: "60"}});
        finishUpload(uploaded);
        await waitFor(() => expect(section.queryByText(/needs uploaded media/)).not.toBeInTheDocument());
        expect(nestedService.upload_media).toHaveBeenCalledWith(file, expect.objectContaining({osId: "windows-server-2019"}));
        expect(section.getByRole("combobox", {name: /Media/})).toHaveTextContent("ws2019.iso");
        expect(section.getByRole("spinbutton", {name: /Disk \(GB\)/})).toHaveValue(60);

        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        expect(heading()).toHaveTextContent("Access");
    });

    it("rejects a media file in the wrong format before uploading", async () => {
        const appliance = {
            id: "pfsense", display_name: "pfSense", family: "appliance", group: "appliance", version: "2.7",
            install_method: "manual_iso", media_url: null, media_sha256: null, media_size_bytes: null, media_formats: ["iso"],
            requires_upload: true, license_note: "", eval_days: null, osinfo: "freebsd14.0", firmware: "bios",
            disk_bus: "virtio", nic_model: "virtio", video: "vga", virtio_win_version: null, agent: false,
            net_config: "none", unattend_template: null, windows_image_index: null, default_username: null,
            min_memory_mb: 1024, default_memory_mb: 1024, min_disk_gb: 8, default_disk_gb: 8, default_vcpus: 1,
            is_enabled: true,
        } as const;
        vi.mocked(nestedService.list_catalog).mockResolvedValue([{...appliance, media_formats: ["iso"]}]);
        renderWizard();
        await screen.findByText(/n2-standard-8/);
        fillHost();
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        fireEvent.click(screen.getByRole("button", {name: "Next"}));
        fireEvent.click(screen.getByRole("button", {name: /Add guest/}));
        const dialog = within(await screen.findByRole("dialog"));
        fireEvent.click(dialog.getByText("pfSense"));
        expect(dialog.getByText("No agent")).toBeInTheDocument();
        expect(dialog.getByText("Manual install")).toBeInTheDocument();
        fireEvent.click(dialog.getByRole("button", {name: "Add guest"}));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

        fireEvent.change(screen.getByTestId("nested-guest-appliance-media-file"), {
            target: {files: [new File(["abcd"], "pfsense.img")]},
        });
        expect(await screen.findByText("pfSense accepts iso media.")).toBeInTheDocument();
        expect(nestedService.upload_media).not.toHaveBeenCalled();
    });

    describe("Access, Review and submit", () => {
        const kali = {
            id: "kali-rolling", display_name: "Kali Rolling", family: "linux", group: "kali", version: "2026.3",
            install_method: "cloud_image", media_url: "https://kali.test/kali.qcow2", media_sha256: null,
            media_size_bytes: 3 * 1024 ** 3, media_formats: ["qcow2"], requires_upload: false, license_note: "Free software.", eval_days: null,
            osinfo: "debian12", firmware: "bios", disk_bus: "virtio", nic_model: "virtio", video: "virtio",
            virtio_win_version: null, agent: true, net_config: "ifupdown", unattend_template: null,
            windows_image_index: null, default_username: "kali", min_memory_mb: 1024, default_memory_mb: 2048,
            min_disk_gb: 10, default_disk_gb: 20, default_vcpus: 2, is_enabled: true,
        } as const;

        const addExposedKali = async (index: number, ip: string) => {
            fireEvent.click(screen.getByRole("button", {name: /Add guest/}));
            const dialog = within(await screen.findByRole("dialog"));
            fireEvent.click(dialog.getByText("Kali Rolling"));
            fireEvent.click(dialog.getByRole("button", {name: "Add guest"}));
            await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
            const section = within(screen.getByRole("region", {name: `Guest ${index}`}));
            fireEvent.mouseDown(section.getByRole("combobox", {name: /Addressing/}));
            fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name: "Static"}));
            fireEvent.change(section.getByRole("textbox", {name: /IP address/}), {target: {value: ip}});
            fireEvent.click(section.getByRole("checkbox", {name: "Expose"}));
        };

        const toReview = async () => {
            vi.mocked(nestedService.list_catalog).mockResolvedValue([{...kali, media_formats: [...kali.media_formats]}]);
            renderWizard();
            await screen.findByText(/n2-standard-8/);
            fillHost();
            fireEvent.click(screen.getByRole("button", {name: "Next"}));
            fireEvent.click(screen.getByRole("button", {name: "Next"}));
            await addExposedKali(1, "192.168.100.10");
            await addExposedKali(2, "192.168.100.11");
            fireEvent.click(screen.getByRole("button", {name: "Next"}));
            expect(heading()).toHaveTextContent("Access");
        };

        it("reorders alias slots, reviews the host, and posts the request built from wizard state", async () => {
            vi.mocked(nestedService.create).mockResolvedValue({build_id: "abcdefghij"});
            await toReview();

            const slots = within(screen.getByRole("table", {name: "Exposure slots"}));
            const guestsInOrder = () => slots.getAllByRole("row").slice(1).map(row => within(row).getAllByRole("cell")[1].textContent);
            expect(guestsInOrder()).toEqual(["kali", "kali-2"]);
            expect(screen.getByRole("button", {name: "Move kali NIC 0 up"})).toBeDisabled();
            fireEvent.click(screen.getByRole("button", {name: "Move kali-2 NIC 0 up"}));
            expect(guestsInOrder()).toEqual(["kali-2", "kali"]);
            // Console ports follow the same guest order.
            const ports = within(screen.getByRole("table", {name: "Console ports"})).getAllByRole("row").slice(1)
                .map(row => row.textContent);
            expect(ports).toEqual(["kali-25901", "kali5902"]);
            expect(screen.getByText(/need 2 alias IPs on NIC 0/)).toBeInTheDocument();

            fireEvent.click(screen.getByRole("button", {name: "Next"}));
            expect(heading()).toHaveTextContent("Review");
            expect(screen.getByLabelText("Estimated build time")).toHaveTextContent("about 20 minutes");
            // 20 parent + 2 x 20 guest + 12 scratch + 3 for the Kali image both guests share.
            expect(screen.getByText(/75 GB disk/)).toBeInTheDocument();
            expect(screen.getByRole("progressbar", {name: "Lab RAM (n1-standard-4)"})).toHaveAttribute("aria-valuenow", "40");
            const credentials = within(screen.getByRole("table", {name: "Guest credentials"}));
            expect(credentials.getAllByText("••••••••")).toHaveLength(2);
            fireEvent.click(screen.getByRole("checkbox", {name: "Show passwords"}));
            expect(credentials.queryByText("••••••••")).not.toBeInTheDocument();

            fireEvent.click(screen.getByRole("button", {name: "Create image"}));
            await waitFor(() => expect(navigate).toHaveBeenCalledWith(URL_TEACHER_SERVERS));
            const request = vi.mocked(nestedService.create).mock.calls[0][0];
            expect(request).toMatchObject({
                server_name: "ad-lab-host",
                description: "AD lab",
                machine_type: "n1-standard-4",
                disk_size: null,
                username: "gm",
                product_keys: {},
            });
            expect(request.nested.build_machine_type).toBe("n2-standard-8");
            expect(request.nested.networks.map(network => network.name)).toEqual(["lab"]);
            // The reorder on Access is the guest order the API derives alias slots from.
            expect(request.nested.guests.map(guest => [guest.name, guest.nics])).toEqual([
                ["kali-2", [{network: "lab", ip: "192.168.100.11", expose: true}]],
                ["kali", [{network: "lab", ip: "192.168.100.10", expose: true}]],
            ]);
            expect(request.nested).not.toHaveProperty("exposures");
        });

        it("keeps the wizard and shows the API's refusal when create fails", async () => {
            vi.mocked(nestedService.create).mockRejectedValue(new Error("Guest kali: the name is taken."));
            await toReview();
            fireEvent.click(screen.getByRole("button", {name: "Next"}));
            fireEvent.click(screen.getByRole("button", {name: "Create image"}));

            expect(await screen.findByText("Guest kali: the name is taken.")).toBeInTheDocument();
            expect(heading()).toHaveTextContent("Review");
            expect(navigate).not.toHaveBeenCalled();
            expect(screen.getByRole("button", {name: "Create image"})).toBeEnabled();
        });
    });
});
