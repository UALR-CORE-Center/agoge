// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {MemoryRouter} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {CtfEventSummary, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfEventList from "./CtfEventList";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {list: vi.fn()},
}));
vi.mock("./CreateCtfDialog", () => ({
    default: ({open, onClose}: {open: boolean; onClose: () => void}) =>
        open ? <div role="dialog" aria-label="New CTF dialog"><button onClick={onClose}>close dialog</button></div> : null,
}));

const summary = (id: string, name: string, state: number): CtfEventSummary => ({
    id,
    name,
    unit_id: "unitunitab",
    state,
    state_name: Object.keys(CtfStates).find(key => CtfStates[key as keyof typeof CtfStates] === state) ?? "",
    board_count: 3,
    creation_timestamp: 1790000000,
    starts_at: null,
    ends_at: null,
});

const renderList = () => render(<MemoryRouter><CtfEventList /></MemoryRouter>);

describe("CtfEventList", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(ctfService.list).mockResolvedValue([
            summary("runningaaa", "Spring Qualifier", CtfStates.RUNNING),
            summary("brokenbbbb", "Broken Event", CtfStates.BROKEN),
            summary("archivedcc", "Fall Final", CtfStates.ARCHIVED),
        ]);
    });
    afterEach(cleanup);

    it("shows non-archived events on the Active tab, each linking to its dashboard", async () => {
        renderList();

        const link = await screen.findByRole("link", {name: `Link to ${URL_TEACHER_CTF_EVENT}/runningaaa`});
        expect(link).toHaveAttribute("href", `${URL_TEACHER_CTF_EVENT}/runningaaa`);
        expect(screen.getByText("Spring Qualifier")).toBeInTheDocument();
        // BROKEN still needs the game master, so it stays on the Active tab.
        expect(screen.getByText("Broken Event")).toBeInTheDocument();
        expect(screen.queryByText("Fall Final")).not.toBeInTheDocument();
        expect(ctfService.list).toHaveBeenCalledTimes(1);
    });

    it("shows only archived events on the Archived tab", async () => {
        renderList();
        await screen.findByText("Spring Qualifier");

        fireEvent.click(screen.getByRole("tab", {name: "Archived"}));

        expect(await screen.findByText("Fall Final")).toBeInTheDocument();
        expect(screen.queryByText("Spring Qualifier")).not.toBeInTheDocument();
        expect(screen.queryByText("Broken Event")).not.toBeInTheDocument();
    });

    it("shows an empty-tab message when there are no events", async () => {
        vi.mocked(ctfService.list).mockResolvedValue([]);
        renderList();

        expect(await screen.findByText("No active CTF events")).toBeInTheDocument();
    });

    it("shows the error instead of failing silently when the list cannot load", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.list).mockRejectedValue(new HttpError(503, "Service unavailable."));
        renderList();

        expect(await screen.findByRole("alert")).toHaveTextContent("503: Service unavailable.");
        expect(screen.getByText("No active CTF events")).toBeInTheDocument();
    });

    it("opens the New CTF dialog from the button and closes it again", async () => {
        renderList();
        await screen.findByText("Spring Qualifier");
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: "New CTF"}));
        expect(screen.getByRole("dialog", {name: "New CTF dialog"})).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: "close dialog"}));
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
});
