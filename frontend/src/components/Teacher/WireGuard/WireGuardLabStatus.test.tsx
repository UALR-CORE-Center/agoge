// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";
import "@testing-library/jest-dom/vitest";
import {WireGuardLabStatus} from "./WireGuardLabStatus";
import {WireGuardEndpoint, WireGuardLease} from "../../../services/Unit/unit.model";
import {WorkoutStates} from "../../../types/AgogeStates";

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
        expect(screen.getByText("Gateway running")).toBeInTheDocument();
        expect(screen.getByText("Gateway service status unknown")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel status unknown")).toBeInTheDocument();
        expect(screen.queryByText(/Wait for gateway configuration/)).not.toBeInTheDocument();
    });

    it("shows a running gateway without any guest callback or peer handshake", () => {
        render(<WireGuardLabStatus endpoint={endpoint} lease={{...lease, service_ready: false,
            tunnel_ready: false, health_timestamp: null, latest_handshake: 0}} />);
        expect(screen.getByText("Gateway running")).toBeInTheDocument();
        expect(screen.getByText("Gateway service status unknown")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel status unknown")).toBeInTheDocument();
        expect(screen.getByText(/remote peer connection is optional for lab completion/)).toBeInTheDocument();
        expect(screen.queryByText("Gateway service not ready")).not.toBeInTheDocument();
    });

    it("shows a completed idle lab as stopped without requiring telemetry", () => {
        render(<WireGuardLabStatus unitState={WorkoutStates.READY} endpoint={{...endpoint, status: "reserved"}}
            lease={{...lease, service_ready: false, tunnel_ready: false, health_timestamp: null, latest_handshake: 0}} />);
        expect(screen.getByText("Gateway stopped (idle)")).toBeInTheDocument();
        expect(screen.getByText(/The lab is built and its gateway is stopped while idle/)).toBeInTheDocument();
        expect(screen.getByText(/first student start starts the gateway; the last student stop stops it/)).toBeInTheDocument();
        expect(screen.queryByText("Gateway unavailable")).not.toBeInTheDocument();
    });

    it.each([WorkoutStates.BUILDING_SERVERS, WorkoutStates.STARTING, WorkoutStates.EXPIRED])(
        "does not infer idle completion from a reserved endpoint while state is %s", state => {
            render(<WireGuardLabStatus unitState={state} endpoint={{...endpoint, status: "reserved"}} lease={lease} />);
            expect(screen.queryByText("Gateway stopped (idle)")).not.toBeInTheDocument();
        });

    it.each([
        {endpoint: {...endpoint, status: "reserved" as const}, lease},
        {endpoint, lease: {...lease, status: "released"}},
        {endpoint, lease: {...lease, expires: Date.now() / 1000 - 1}},
    ])("does not show inactive gateways as running despite a recent health report", value => {
        render(<WireGuardLabStatus endpoint={value.endpoint} lease={value.lease as WireGuardLease} />);
        expect(screen.getByText("Gateway unavailable")).toBeInTheDocument();
        expect(screen.queryByText("Gateway running")).not.toBeInTheDocument();
        expect(screen.queryByText("Remote tunnel connected")).not.toBeInTheDocument();
    });
});
