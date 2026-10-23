// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";
import "@testing-library/jest-dom/vitest";
import {WireGuardLabStatus} from "./WireGuardLabStatus";
import {WireGuardEndpoint, WireGuardLease} from "../../../services/Unit/unit.model";

const endpoint: WireGuardEndpoint = {id: "10000", hostname: "wg10000.example.edu.",
    server_name: "gateway", port: 51820, status: "active"};
const lease: WireGuardLease = {unit_id: "abcdefghij", kit_id: "legacy-peer", device_id: "device-01", endpoint_id: "10000",
    equipment_subnet: "172.30.0.0/24", student_subnets: ["10.20.0.0/24"], gateway_public_key: "public",
    peer_public_key: "peer-public", gateway_address: "10.254.254.1/30", peer_address: "10.254.254.2/32",
    expires: Date.now() / 1000 + 3600, status: "reserved", service_ready: true, tunnel_ready: true,
    health_timestamp: Date.now() / 1000, latest_handshake: Date.now() / 1000};

describe("remote lab telemetry", () => {
    afterEach(cleanup);

    it("shows selected remote peer, its configured private LAN and recent handshake", () => {
        render(<WireGuardLabStatus endpoint={endpoint} lease={{...lease, remote_peer_id: "remote-lab-01",
            remote_network_cidr: "192.168.40.0/24"}} />);
        expect(screen.getByText("remote-lab-01")).toBeInTheDocument();
        expect(screen.getByText("Remote LAN: 192.168.40.0/24")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel connected")).toBeInTheDocument();
        expect(screen.getByText(/Last remote peer handshake:/)).toBeInTheDocument();
    });

    it("reads legacy enrollment records while refusing stale telemetry", () => {
        render(<WireGuardLabStatus endpoint={endpoint} lease={{...lease, health_timestamp: Date.now() / 1000 - 121}} />);
        expect(screen.getByText("legacy-peer")).toBeInTheDocument();
        expect(screen.getByText("Remote LAN: 172.30.0.0/24")).toBeInTheDocument();
        expect(screen.getByText("Gateway service not ready")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel not connected")).toBeInTheDocument();
    });
});
