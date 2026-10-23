// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WorkoutModal} from "./WorkoutModal";
import {wireguardService} from "../../../../services/WireGuard/wireguard.service";

vi.mock("../../../../services/WireGuard/wireguard.service", () => ({wireguardService: {listRemotePeers: vi.fn()}}));
vi.mock("../../../../services/User/user.service", () => ({userService: {
    get: vi.fn().mockResolvedValue({}), get_courses: vi.fn().mockResolvedValue({}),
}}));
vi.mock("../../../../services/Server/image.service", () => ({imageService: {list: vi.fn().mockResolvedValue([
    {image: "image-kali-linux-2023", name: "student-kali-record", status: 0, architecture: "X86_64",
        human_interaction: [{display: true, protocol: "rdp", username: "student", password: "test-image-credential"}]},
])}}));
vi.mock("../TagChips", () => ({TagChip: () => null}));
vi.mock("@mui/x-date-pickers", () => ({LocalizationProvider: ({children}: {children: React.ReactNode}) => children}));
vi.mock("@mui/x-date-pickers/DateTimePicker", () => ({DateTimePicker: () => <span>Expiration date</span>}));

const peer = {id: "remote-lab-01", device_id: "pi-01", remote_network_cidr: "172.30.0.0/24",
    peer_public_key: "public", authorized_instructors: ["teacher@example.edu"], enabled: true};
const specification = {id: "managed-wireguard", managed_wireguard: true,
    summary: {name: "WireGuard Remote Lab"}, servers: [{wireguard_gateway: true}]};

describe("WireGuard build flow", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(wireguardService.listRemotePeers).mockResolvedValue([peer]);
    });
    afterEach(cleanup);

    it("blocks submission until an authorized remote peer is selected, then includes its id", async () => {
        const submit = vi.fn();
        render(<WorkoutModal open user={null} onClose={vi.fn()} onSubmit={submit} selectedRow={specification} />);
        const button = screen.getByRole("button", {name: "Build Lab"});
        expect(button).toBeDisabled();
        fireEvent.submit(button.closest("form")!);
        expect(submit).not.toHaveBeenCalled();
        await waitFor(() => expect(screen.getByRole("combobox", {name: /Remote peer/})).not.toHaveAttribute("aria-disabled", "true"));
        fireEvent.mouseDown(screen.getByRole("combobox", {name: /Remote peer/}));
        fireEvent.click(screen.getByRole("option", {name: /remote-lab-01/}));
        expect(button).toBeEnabled();
        fireEvent.click(button);
        expect(submit).toHaveBeenCalledWith(expect.objectContaining({remote_peer_id: "remote-lab-01", build_count: 1,
            student_image: "student-kali-record"}));
        expect(screen.queryByLabelText("Build with LMS")).not.toBeInTheDocument();
    });

    it("leaves ordinary catalog builds independent of remote peer enrollment", async () => {
        const submit = vi.fn();
        render(<WorkoutModal open user={null} onClose={vi.fn()} onSubmit={submit}
            selectedRow={{id: "ordinary", summary: {name: "Linux basics"}, servers: []}} />);
        const button = screen.getByRole("button", {name: "Build Lab"});
        expect(button).toBeEnabled();
        fireEvent.click(button);
        await waitFor(() => expect(submit).toHaveBeenCalled());
        expect(submit.mock.calls[0][0]).not.toHaveProperty("remote_peer_id");
        expect(submit.mock.calls[0][0]).not.toHaveProperty("kit_id");
        expect(wireguardService.listRemotePeers).not.toHaveBeenCalled();
    });
});
