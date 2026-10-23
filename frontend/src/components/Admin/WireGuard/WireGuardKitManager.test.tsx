// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardRemotePeerManager} from "./WireGuardKitManager";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

vi.mock("../../../services/WireGuard/wireguard.service", () => ({
    wireguardService: {listRemotePeers: vi.fn(), enrollRemotePeer: vi.fn()},
}));
vi.mock("../../../hooks/useClipboard", () => ({useClipboard: () => ({copy: vi.fn()})}));

describe("remote peer enrollment", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([]);
    });
    afterEach(cleanup);

    it("registers only public device material and forgets the one-time token when acknowledged", async () => {
        const peer = {id: "remote-lab-01", device_id: "pi-01", remote_network_cidr: "172.30.0.0/24",
            peer_public_key: "public-key", authorized_instructors: ["teacher@example.edu", "other@example.edu"], enabled: true};
        vi.mocked(wireguardService.enrollRemotePeer).mockResolvedValue({remote_peer: peer, enrollment_token: "one-time-secret"});
        render(<WireGuardRemotePeerManager />);
        await screen.findByText("No remote peers have been registered.");
        fireEvent.change(screen.getByLabelText(/Remote peer ID/), {target: {value: peer.id}});
        fireEvent.change(screen.getByLabelText(/Remote device identity/), {target: {value: peer.device_id}});
        fireEvent.change(screen.getByLabelText(/Remote LAN \(IPv4 CIDR\)/), {target: {value: peer.remote_network_cidr}});
        fireEvent.change(screen.getByLabelText(/Remote peer WireGuard public key/), {target: {value: peer.peer_public_key}});
        fireEvent.change(screen.getByLabelText(/Authorized instructor emails/), {target: {value: "teacher@example.edu,\nother@example.edu"}});
        fireEvent.click(screen.getByRole("button", {name: "Register remote peer"}));
        const {enabled, ...request} = peer;
        await waitFor(() => expect(wireguardService.enrollRemotePeer).toHaveBeenCalledWith(request));
        expect(await screen.findByLabelText("One-time enrollment token")).toHaveValue("one-time-secret");
        expect(screen.getByText("Remote LAN (IPv4 CIDR): 172.30.0.0/24")).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Register remote peer"})).toBeDisabled();
        fireEvent.click(screen.getByRole("button", {name: "I saved the token"}));
        expect(screen.queryByDisplayValue("one-time-secret")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Register remote peer"})).toBeEnabled();
    });

    it("keeps a rejected remote LAN editable and presents the server's validation message", async () => {
        vi.mocked(wireguardService.enrollRemotePeer).mockRejectedValue(new Error("Remote LAN must be a private IPv4 CIDR."));
        render(<WireGuardRemotePeerManager />);
        await screen.findByText("No remote peers have been registered.");
        fireEvent.change(screen.getByLabelText(/Remote peer ID/), {target: {value: "remote-lab-01"}});
        fireEvent.change(screen.getByLabelText(/Remote device identity/), {target: {value: "router-01"}});
        fireEvent.change(screen.getByLabelText(/Remote LAN \(IPv4 CIDR\)/), {target: {value: "8.8.8.0/24"}});
        fireEvent.change(screen.getByLabelText(/Remote peer WireGuard public key/), {target: {value: "public-key"}});
        fireEvent.change(screen.getByLabelText(/Authorized instructor emails/), {target: {value: "teacher@example.edu"}});
        fireEvent.click(screen.getByRole("button", {name: "Register remote peer"}));
        expect(await screen.findByRole("alert")).toHaveTextContent("Remote LAN must be a private IPv4 CIDR.");
        expect(screen.getByLabelText(/Remote LAN \(IPv4 CIDR\)/)).toHaveValue("8.8.8.0/24");
        expect(screen.queryByLabelText("One-time enrollment token")).not.toBeInTheDocument();
    });
});
