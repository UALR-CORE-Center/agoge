// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardLabSettingsDialog} from "./WireGuardLabSettingsDialog";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

vi.mock("../../../services/WireGuard/wireguard.service", () => ({wireguardService: {
    getLabRemoteSettings: vi.fn(), listRemotePeers: vi.fn(), saveLabRemoteSettings: vi.fn(),
}}));

const assigned = {id: "remote-lab-01", name: "Pump station", device_id: "pi-01", remote_network_cidr: "192.168.50.0/24",
    peer_public_key: "public", authorized_instructors: ["teacher@example.edu"], enabled: true, assigned_unit_id: "abcdefghij"};
const other = {...assigned, id: "remote-lab-02", name: "Factory", remote_network_cidr: "172.30.0.0/24", assigned_unit_id: null};
const settings = {unit_id: "abcdefghij", remote_peer_id: assigned.id, remote_network_cidr: "192.168.55.0/24",
    remote_peer: assigned, can_edit: true, blocked_reason: null, configuration_status: "current"};

describe("built remote lab settings", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(wireguardService.getLabRemoteSettings).mockResolvedValue(settings);
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([assigned, other,
            {...other, id: "busy", assigned_unit_id: "anotherlab"}, {...other, id: "disabled", enabled: false}]);
    });
    afterEach(cleanup);

    it("preserves a per-lab LAN override, allows an available peer, and saves before refreshing", async () => {
        const saved = {...settings, remote_peer_id: other.id, remote_network_cidr: "172.31.0.0/24", remote_peer: other,
            configuration_status: "saved"};
        vi.mocked(wireguardService.saveLabRemoteSettings).mockResolvedValue(saved);
        const refreshed = vi.fn().mockResolvedValue(undefined);
        const close = vi.fn();
        render(<WireGuardLabSettingsDialog open unitId="abcdefghij" onClose={close} onSaved={refreshed} />);
        const network = await screen.findByLabelText(/Remote LAN for this lab/);
        expect(network).toHaveValue("192.168.55.0/24");
        fireEvent.mouseDown(screen.getByRole("combobox", {name: "Remote lab"}));
        expect(screen.getByRole("option", {name: /Pump station/})).toBeInTheDocument();
        expect(screen.queryByRole("option", {name: /busy|disabled/})).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("option", {name: /Factory/}));
        expect(network).toHaveValue("172.30.0.0/24");
        fireEvent.change(network, {target: {value: "172.31.0.0/24"}});
        fireEvent.click(screen.getByRole("button", {name: "Save remote lab settings"}));
        await waitFor(() => expect(wireguardService.saveLabRemoteSettings).toHaveBeenCalledWith("abcdefghij", {
            remote_peer_id: "remote-lab-02", remote_network_cidr: "172.31.0.0/24",
        }));
        await waitFor(() => expect(refreshed).toHaveBeenCalledWith(saved));
        expect(close).toHaveBeenCalledOnce();
    });

    it("disables editing while the API reports active students or gateway", async () => {
        vi.mocked(wireguardService.getLabRemoteSettings).mockResolvedValue({...settings, can_edit: false,
            blocked_reason: "Stop the active student workouts and gateway first."});
        render(<WireGuardLabSettingsDialog open unitId="abcdefghij" onClose={vi.fn()} onSaved={vi.fn()} />);
        expect(await screen.findByText("Stop the active student workouts and gateway first.")).toBeInTheDocument();
        expect(screen.getByLabelText(/Remote LAN for this lab/)).toBeDisabled();
        expect(screen.getByRole("button", {name: "Save remote lab settings"})).toBeDisabled();
        fireEvent.submit(screen.getByRole("button", {name: "Save remote lab settings"}).closest("form")!);
        expect(wireguardService.saveLabRemoteSettings).not.toHaveBeenCalled();
    });

    it("retains edits and shows a conflict returned during save", async () => {
        vi.mocked(wireguardService.saveLabRemoteSettings).mockRejectedValue(new Error("A student started while settings were open. Stop all students and retry."));
        const close = vi.fn();
        render(<WireGuardLabSettingsDialog open unitId="abcdefghij" onClose={close} onSaved={vi.fn()} />);
        const network = await screen.findByLabelText(/Remote LAN for this lab/);
        fireEvent.change(network, {target: {value: "192.168.60.0/24"}});
        fireEvent.click(screen.getByRole("button", {name: "Save remote lab settings"}));
        expect(await screen.findByText(/A student started while settings were open/)).toBeInTheDocument();
        expect(network).toHaveValue("192.168.60.0/24");
        expect(close).not.toHaveBeenCalled();
    });

    it("does not request settings while closed", () => {
        render(<WireGuardLabSettingsDialog open={false} unitId="abcdefghij" onClose={vi.fn()} onSaved={vi.fn()} />);
        expect(wireguardService.getLabRemoteSettings).not.toHaveBeenCalled();
        expect(wireguardService.listRemotePeers).not.toHaveBeenCalled();
    });
});
