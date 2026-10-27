// @vitest-environment jsdom
import React from "react";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import "@testing-library/jest-dom/vitest";
import {UnitInfoCard} from "./UnitInfoCard";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

const {copy} = vi.hoisted(() => ({copy: vi.fn()}));
vi.mock("../../../hooks/useClipboard", () => ({useClipboard: () => ({copy})}));
vi.mock("../../../services/WireGuard/wireguard.service", () => ({wireguardService: {
    getLabRemoteSettings: vi.fn(), listRemotePeers: vi.fn(), saveLabRemoteSettings: vi.fn(),
}}));

const endpoint = {id: "10000", connection_id: "test-dev-787001:abcdefghij",
    hostname: "wg10000.test-dev-787001.example.edu.", port: 51820, status: "reserved"};
const data = {summary: {name: "Remote lab", teacher_instructions_url: null}, wireguard_endpoint: endpoint};

describe("instructor remote lab connection details", () => {
    afterEach(cleanup);
    beforeEach(() => vi.clearAllMocks());

    it("shows and copies a stable connection ID alongside its current gateway DNS", () => {
        render(<UnitInfoCard data={data} />);
        expect(screen.getByText("test-dev-787001:abcdefghij")).toBeInTheDocument();
        expect(screen.getByText("Gateway number: 10000")).toBeInTheDocument();
        expect(screen.getByText("wg10000.test-dev-787001.example.edu:51820")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Copy remote lab connection ID"}));
        expect(copy).toHaveBeenLastCalledWith("test-dev-787001:abcdefghij");
        fireEvent.click(screen.getByRole("button", {name: "Copy gateway DNS and port"}));
        expect(copy).toHaveBeenLastCalledWith("wg10000.test-dev-787001.example.edu:51820");
    });

    it("keeps identity visible while stopped without presenting the tunnel as connected", () => {
        render(<UnitInfoCard data={{...data, wireguard_lease: {kit_id: "remote-lab-01", device_id: "peer-01",
            equipment_subnet: "172.30.0.0/24", student_subnets: [], service_ready: true,
            tunnel_ready: true, health_timestamp: Date.now() / 1000, status: "reserved"}}} />);
        expect(screen.getByText("test-dev-787001:abcdefghij")).toBeInTheDocument();
        expect(screen.getByText("Gateway unavailable")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel status unknown")).toBeInTheDocument();
    });

    it("does not use the recycled gateway number as a substitute connection ID", () => {
        render(<UnitInfoCard data={{...data, wireguard_endpoint: {...endpoint, connection_id: null}}} />);
        expect(screen.getByRole("button", {name: "Copy remote lab connection ID"})).toBeDisabled();
        expect(screen.getByText("Pending")).toBeInTheDocument();
    });

    it("opens saved-lab settings and refreshes the instructor page after saving", async () => {
        const peer = {id: "remote-lab-01", device_id: "pi-01", remote_network_cidr: "172.30.0.0/24",
            peer_public_key: "public", authorized_instructors: ["teacher@example.edu"], enabled: true, assigned_unit_id: "abcdefghij"};
        const settings = {unit_id: "abcdefghij", remote_peer_id: peer.id, remote_network_cidr: peer.remote_network_cidr,
            remote_peer: peer, can_edit: true, configuration_status: "saved"};
        vi.mocked(wireguardService.getLabRemoteSettings).mockResolvedValue(settings);
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([peer]);
        vi.mocked(wireguardService.saveLabRemoteSettings).mockResolvedValue(settings);
        const refresh = vi.fn().mockResolvedValue(undefined);
        render(<UnitInfoCard onRemoteLabSettingsSaved={refresh} data={{...data, id: "abcdefghij",
            wireguard_lease: {kit_id: peer.id, device_id: peer.device_id, equipment_subnet: peer.remote_network_cidr,
                student_subnets: [], status: "reserved", service_ready: false, tunnel_ready: false}}} />);
        expect(wireguardService.getLabRemoteSettings).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", {name: "Edit remote lab settings"}));
        await screen.findByLabelText(/Remote LAN for this lab/);
        fireEvent.click(screen.getByRole("button", {name: "Save remote lab settings"}));
        await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
        expect(await screen.findByText(/Remote lab settings saved/)).toBeInTheDocument();
    });
});
