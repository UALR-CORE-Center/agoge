// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {MemoryRouter} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {nestedService} from "../../../../../services/Server/nested.service";
import NestedImageWizard from "./NestedImageWizard";

vi.mock("../../../../../services/Server/nested.service", () => ({
    nestedService: {list_machine_types: vi.fn()},
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
});
