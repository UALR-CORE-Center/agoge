// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {WireGuardStudentImageSelector} from "./WireGuardStudentImageSelector";
import {imageService} from "../../../services/Server/image.service";

vi.mock("../../../services/Server/image.service", () => ({imageService: {list: vi.fn()}}));
const image = {image: "image-kali-linux-2023", name: "student-kali-record", status: 0, architecture: "X86_64",
    human_interaction: [{display: true, protocol: "rdp", username: "student", password: "image-credential"}]};

describe("student image selection", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("excludes checked-out, missing, ARM, and inaccessible workstation images", async () => {
        vi.mocked(imageService.list).mockResolvedValue([
            image, {...image, name: "checked-out", status: 1}, {...image, name: "arm-image", architecture: "ARM64"},
            {...image, name: "missing", image_exists: false}, {...image, name: "no-login", human_interaction: []},
            {...image, name: "key-only", human_interaction: [{display: true, protocol: "ssh", username: "student", ssh_key: "key-only"}]},
            {...image, name: "unsupported-protocol", human_interaction: [{display: true, protocol: "telnet", username: "student", password: "credential"}]},
        ] as any);
        const available = vi.fn();
        const change = vi.fn();
        render(<WireGuardStudentImageSelector open value="" onChange={change} onAvailabilityChange={available} />);
        await waitFor(() => expect(available).toHaveBeenLastCalledWith(true));
        expect(change).toHaveBeenCalledWith("student-kali-record");
        fireEvent.mouseDown(screen.getByRole("combobox"));
        expect(screen.getAllByRole("option")).toHaveLength(1);
        expect(screen.getByRole("option", {name: "student-kali-record"})).toBeInTheDocument();
    });

    it("requires an explicit image choice when the conventional Kali image is unavailable", async () => {
        vi.mocked(imageService.list).mockResolvedValue([{...image, name: "custom-student-record", image: "projects/shared/global/images/custom-student-source"}] as any);
        const change = vi.fn();
        render(<WireGuardStudentImageSelector open value="" onChange={change} onAvailabilityChange={vi.fn()} />);
        await waitFor(() => expect(change).toHaveBeenCalledWith(""));
        fireEvent.mouseDown(screen.getByRole("combobox"));
        fireEvent.click(screen.getByRole("option", {name: "custom-student-record"}));
        expect(change).toHaveBeenLastCalledWith("custom-student-record");
    });

    it("selects the conventional Agoge record even when its Compute image source differs", async () => {
        vi.mocked(imageService.list).mockResolvedValue([{...image, name: "image-kali-linux-2023",
            image: "projects/shared/global/images/kali-snapshot-2027"}] as any);
        const change = vi.fn();
        render(<WireGuardStudentImageSelector open value="" onChange={change} onAvailabilityChange={vi.fn()} />);
        await waitFor(() => expect(change).toHaveBeenCalledWith("image-kali-linux-2023"));
    });
});
