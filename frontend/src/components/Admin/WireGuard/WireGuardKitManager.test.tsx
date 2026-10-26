// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardKitManager} from "./WireGuardKitManager";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

vi.mock("../../../services/WireGuard/wireguard.service", () => ({
    wireguardService: {listKits: vi.fn(), enrollKit: vi.fn()},
}));
vi.mock("../../../hooks/useClipboard", () => ({useClipboard: () => ({copy: vi.fn()})}));

describe("kit enrollment", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(wireguardService.listKits).mockResolvedValue([]);
    });
    afterEach(cleanup);

    it("registers only public device material and forgets the one-time token when acknowledged", async () => {
        const kit = {id: "factory-01", device_id: "pi-01", equipment_subnet: "172.30.0.0/24",
            peer_public_key: "public-key", authorized_instructors: ["teacher@example.edu", "other@example.edu"], enabled: true};
        vi.mocked(wireguardService.enrollKit).mockResolvedValue({kit, enrollment_token: "one-time-secret"});
        render(<WireGuardKitManager />);
        await screen.findByText("No kits have been registered.");
        fireEvent.change(screen.getByLabelText(/Kit ID/), {target: {value: kit.id}});
        fireEvent.change(screen.getByLabelText(/Pi device identity/), {target: {value: kit.device_id}});
        fireEvent.change(screen.getByLabelText(/Equipment IPv4 subnet/), {target: {value: kit.equipment_subnet}});
        fireEvent.change(screen.getByLabelText(/Pi WireGuard public key/), {target: {value: kit.peer_public_key}});
        fireEvent.change(screen.getByLabelText(/Authorized instructor emails/), {target: {value: "teacher@example.edu,\nother@example.edu"}});
        fireEvent.click(screen.getByRole("button", {name: "Register kit"}));
        const {enabled, ...request} = kit;
        await waitFor(() => expect(wireguardService.enrollKit).toHaveBeenCalledWith(request));
        expect(await screen.findByLabelText("One-time enrollment token")).toHaveValue("one-time-secret");
        expect(screen.getByRole("button", {name: "Register kit"})).toBeDisabled();
        fireEvent.click(screen.getByRole("button", {name: "I saved the token"}));
        expect(screen.queryByDisplayValue("one-time-secret")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Register kit"})).toBeEnabled();
    });
});
