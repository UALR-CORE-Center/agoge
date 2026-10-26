// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardKitSelector} from "./WireGuardKitSelector";
import {wireguardService} from "../../../services/WireGuard/wireguard.service";

vi.mock("../../../services/WireGuard/wireguard.service", () => ({wireguardService: {listKits: vi.fn()}}));
const kit = {id: "factory-01", device_id: "pi-01", equipment_subnet: "172.30.0.0/24",
    peer_public_key: "public", authorized_instructors: ["teacher@example.edu"], enabled: true};

describe("authorized factory kit selection", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("offers only enabled, unassigned kits from the authorized API inventory", async () => {
        vi.mocked(wireguardService.listKits).mockResolvedValue([
            kit, {...kit, id: "busy", assigned_unit_id: "anotherlab"}, {...kit, id: "disabled", enabled: false},
        ]);
        const change = vi.fn();
        const availability = vi.fn();
        render(<WireGuardKitSelector open value="" onChange={change} onAvailabilityChange={availability} />);
        await waitFor(() => expect(availability).toHaveBeenLastCalledWith(true));
        fireEvent.mouseDown(screen.getByRole("combobox"));
        expect(screen.getByRole("option", {name: /factory-01/})).toBeInTheDocument();
        expect(screen.queryByRole("option", {name: /busy|disabled/})).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("option", {name: /factory-01/}));
        expect(change).toHaveBeenCalledWith("factory-01");
    });

    it("clears a previously selected kit when it is no longer available", async () => {
        vi.mocked(wireguardService.listKits).mockResolvedValue([{...kit, assigned_unit_id: "anotherlab"}]);
        const change = vi.fn();
        const availability = vi.fn();
        render(<WireGuardKitSelector open value="factory-01" onChange={change} onAvailabilityChange={availability} />);
        expect(await screen.findByText(/No available kits/)).toBeInTheDocument();
        expect(change).toHaveBeenCalledWith("");
        expect(availability).toHaveBeenLastCalledWith(false);
        expect(screen.getByRole("combobox")).toHaveAttribute("aria-disabled", "true");
    });

    it("fails closed with the API's actionable error and permits retry", async () => {
        vi.mocked(wireguardService.listKits).mockRejectedValueOnce(new Error("Authorization expired."))
            .mockResolvedValueOnce([kit]);
        const availability = vi.fn();
        render(<WireGuardKitSelector open value="" onChange={vi.fn()} onAvailabilityChange={availability} />);
        expect(await screen.findByRole("alert")).toHaveTextContent("Authorization expired.");
        expect(availability).toHaveBeenLastCalledWith(false);
        fireEvent.click(screen.getByRole("button", {name: "Retry"}));
        await waitFor(() => expect(availability).toHaveBeenLastCalledWith(true));
    });

    it("does not request enrollment data while the dialog is closed", () => {
        render(<WireGuardKitSelector open={false} value="" onChange={vi.fn()} onAvailabilityChange={vi.fn()} />);
        expect(wireguardService.listKits).not.toHaveBeenCalled();
    });
});
