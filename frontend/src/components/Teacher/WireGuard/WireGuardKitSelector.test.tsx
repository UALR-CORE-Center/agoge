// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardRemotePeerSelector} from "./WireGuardKitSelector";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

vi.mock("../../../services/WireGuard/wireguard.service", () => ({wireguardService: {listRemotePeers: vi.fn()}}));
const peer = {id: "remote-lab-01", device_id: "pi-01", remote_network_cidr: "172.30.0.0/24",
    peer_public_key: "public", authorized_instructors: ["teacher@example.edu"], enabled: true};

describe("authorized remote lab selection", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("offers only enabled, unassigned remote peers from the authorized API inventory", async () => {
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([
            peer, {...peer, id: "busy", assigned_unit_id: "anotherlab"}, {...peer, id: "disabled", enabled: false},
        ]);
        const change = vi.fn();
        const availability = vi.fn();
        const Selection = () => {
            const [value, setValue] = React.useState("");
            return <WireGuardRemotePeerSelector open value={value} onChange={id => {
                change(id);
                setValue(id);
            }} onAvailabilityChange={availability} />;
        };
        render(<Selection />);
        await waitFor(() => expect(availability).toHaveBeenLastCalledWith(true));
        fireEvent.mouseDown(screen.getByRole("combobox"));
        expect(screen.getByRole("option", {name: /remote-lab-01/})).toBeInTheDocument();
        expect(screen.queryByRole("option", {name: /busy|disabled/})).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("option", {name: /remote-lab-01/}));
        expect(change).toHaveBeenCalledWith("remote-lab-01");
        expect(screen.getByText(/Remote LAN \(IPv4 CIDR\): 172\.30\.0\.0\/24/)).toBeInTheDocument();
    });

    it("clears a previously selected remote peer when it is no longer available", async () => {
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([{...peer, assigned_unit_id: "anotherlab"}]);
        const change = vi.fn();
        const availability = vi.fn();
        render(<WireGuardRemotePeerSelector open value="remote-lab-01" onChange={change} onAvailabilityChange={availability} />);
        expect(await screen.findByText(/No available remote peers/)).toBeInTheDocument();
        expect(change).toHaveBeenCalledWith("");
        expect(availability).toHaveBeenLastCalledWith(false);
        expect(screen.getByRole("combobox")).toHaveAttribute("aria-disabled", "true");
    });

    it("fails closed with the API's actionable error and permits retry", async () => {
        vi.mocked(wireguardService.listRemotePeers).mockRejectedValueOnce(new Error("Authorization expired."))
            .mockResolvedValueOnce([peer]);
        const availability = vi.fn();
        render(<WireGuardRemotePeerSelector open value="" onChange={vi.fn()} onAvailabilityChange={availability} />);
        expect(await screen.findByRole("alert")).toHaveTextContent("Authorization expired.");
        expect(availability).toHaveBeenLastCalledWith(false);
        fireEvent.click(screen.getByRole("button", {name: "Retry"}));
        await waitFor(() => expect(availability).toHaveBeenLastCalledWith(true));
    });

    it("does not request enrollment data while the dialog is closed", () => {
        render(<WireGuardRemotePeerSelector open={false} value="" onChange={vi.fn()} onAvailabilityChange={vi.fn()} />);
        expect(wireguardService.listRemotePeers).not.toHaveBeenCalled();
    });
});
