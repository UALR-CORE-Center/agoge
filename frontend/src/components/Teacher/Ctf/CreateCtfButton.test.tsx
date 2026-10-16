// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CreateCtfButton from "./CreateCtfButton";

let ctfEnabled = true;
vi.mock("../../../hooks/useCtfEnabled", () => ({
    useCtfEnabled: () => ({ctfEnabled, loading: false}),
}));
vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {create: vi.fn()},
}));

const renderButton = (isExpired = false) => render(
    <MemoryRouter initialEntries={["/teacher/unit/unitunitab"]}>
        <Routes>
            <Route path="/teacher/unit/:build_id" element={<CreateCtfButton buildId="unitunitab" isExpired={isExpired} />} />
            <Route path={`${URL_TEACHER_CTF_EVENT}/:ctf_id`} element={<div>dashboard page</div>} />
        </Routes>
    </MemoryRouter>
);

describe("CreateCtfButton", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        ctfEnabled = true;
    });
    afterEach(cleanup);

    it("creates the event from the unit and navigates to its dashboard", async () => {
        vi.mocked(ctfService.create).mockResolvedValue({build_id: "neweventab", exists: null});
        renderButton();

        fireEvent.click(screen.getByRole("button", {name: "Create CTF Event"}));

        expect(await screen.findByText("dashboard page")).toBeInTheDocument();
        expect(ctfService.create).toHaveBeenCalledWith({unit_id: "unitunitab"});
        expect(ctfService.create).toHaveBeenCalledTimes(1);
    });

    it("shows the API's reason and stays on the unit when creation fails", async () => {
        vi.mocked(ctfService.create).mockRejectedValue(new HttpError(409, "Workout abc is already on an active CTF board"));
        renderButton();

        fireEvent.click(screen.getByRole("button", {name: "Create CTF Event"}));

        expect(await screen.findByText("409: Workout abc is already on an active CTF board")).toBeInTheDocument();
        expect(screen.queryByText("dashboard page")).not.toBeInTheDocument();
        // A failure re-enables the button so the game master can retry after fixing the cause.
        expect(screen.getByRole("button", {name: "Create CTF Event"})).toBeEnabled();
    });

    it("is disabled on an expired unit", () => {
        renderButton(true);

        const button = screen.getByRole("button", {name: "Create CTF Event"});
        expect(button).toBeDisabled();
        fireEvent.click(button);
        expect(ctfService.create).not.toHaveBeenCalled();
    });

    it("renders nothing when CTF is disabled for the deployment", () => {
        ctfEnabled = false;
        renderButton();

        expect(screen.queryByRole("button", {name: "Create CTF Event"})).not.toBeInTheDocument();
    });
});
