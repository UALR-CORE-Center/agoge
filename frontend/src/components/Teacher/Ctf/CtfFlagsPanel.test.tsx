// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfFlagBoardStatus, CtfFlagRow, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfFlagsPanel, {flagProblems, REPLANT_STATES, selectedServers} from "./CtfFlagsPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getFlags: vi.fn(), replant: vi.fn()},
}));

const CTF_ID = "eventevent";

const board = (overrides: Partial<CtfFlagBoardStatus> = {}): CtfFlagBoardStatus => ({
    workout_id: "boardaaaaa",
    team_name: "Red",
    plant_status: "planted",
    planted_at: 1_800_000_000,
    plant_error: null,
    solved: false,
    ...overrides,
});

const flag = (overrides: Partial<CtfFlagRow> = {}): CtfFlagRow => ({
    flag_id: "web-1",
    server: "web",
    slot: 1,
    category: "web",
    location_type: "file",
    points: 100,
    decoy: false,
    boards: [board()],
    ...overrides,
});

const FLAGS: CtfFlagRow[] = [
    flag(),
    flag({
        flag_id: "db-1",
        server: "db",
        points: 250,
        decoy: true,
        boards: [
            board({plant_status: "failed", plant_error: "guest attribute timeout"}),
            board({workout_id: "boardbbbbb", team_name: "Blue", plant_status: "stale", planted_at: null}),
        ],
    }),
];

const renderPanel = (state: number = CtfStates.RUNNING) => render(
    <ThemeProvider theme={darkTheme}>
        <CtfFlagsPanel ctfId={CTF_ID} state={state} active={true} />
    </ThemeProvider>
);

const rowFor = async (flagId: string) => {
    const cell = await screen.findByRole("gridcell", {name: flagId});
    return cell.closest('[role="row"]') as HTMLElement;
};

describe("flagProblems", () => {
    it("counts failed and stale boards and is null when every board is fine", () => {
        expect(flagProblems([board(), board({plant_status: "pending"})])).toBeNull();
        expect(flagProblems([board({plant_status: "failed"}), board({plant_status: "stale"}), board({plant_status: "stale"})]))
            .toBe("1 failed, 2 stale");
    });
});

describe("selectedServers", () => {
    it("is the de-duplicated union of the selected rows' servers in row order, ignoring unknown ids", () => {
        const rows = [flag(), flag({flag_id: "db-1", server: "db"}), flag({flag_id: "web-2", server: "web", slot: 2})];
        expect(selectedServers(rows, ["web-2", "db-1", "web-1", "gone"])).toEqual(["web", "db"]);
        expect(selectedServers(rows, [])).toEqual([]);
    });
});

const checkRow = async (flagId: string) => {
    const row = await rowFor(flagId);
    fireEvent.click(within(row).getByRole("checkbox"));
};

describe("CtfFlagsPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(ctfService.getFlags).mockResolvedValue(FLAGS);
    });

    afterEach(() => {
        cleanup();
    });

    it("renders flag id, server, slot, points, decoy and per-board plant status", async () => {
        renderPanel();
        const row = await rowFor("db-1");
        const cells = within(row);
        expect(cells.getByRole("gridcell", {name: "db"})).toBeInTheDocument();
        expect(cells.getByRole("gridcell", {name: "250"})).toBeInTheDocument();
        expect(cells.getByRole("gridcell", {name: "Yes"})).toBeInTheDocument();
        expect(cells.getByText("Red: failed")).toBeInTheDocument();
        expect(cells.getByText("Blue: stale")).toBeInTheDocument();
        expect(ctfService.getFlags).toHaveBeenCalledWith(CTF_ID);
    });

    it("shows a warning icon and text only on rows with failed or stale boards", async () => {
        renderPanel();
        const bad = await rowFor("db-1");
        expect(within(bad).getByText("1 failed, 1 stale")).toBeInTheDocument();
        expect(within(bad).getByTestId("WarningAmberIcon")).toBeInTheDocument();

        const good = await rowFor("web-1");
        expect(within(good).getByText("OK")).toBeInTheDocument();
        expect(within(good).queryByTestId("WarningAmberIcon")).not.toBeInTheDocument();
    });

    it("replants the row's server on every board after confirmation, then re-reads the flags", async () => {
        vi.mocked(ctfService.replant).mockResolvedValue({messages: 2});
        renderPanel();
        fireEvent.click(await screen.findByRole("button", {name: "Replant db for flag db-1"}));

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toHaveTextContent("Plant every flag on db again, on every board.");
        fireEvent.click(within(dialog).getByRole("button", {name: "Replant"}));

        await waitFor(() => expect(ctfService.replant).toHaveBeenCalledWith(CTF_ID, {servers: ["db"]}));
        expect(await screen.findByText("Replant of db started (2 plant requests).")).toBeInTheDocument();
        await waitFor(() => expect(ctfService.getFlags).toHaveBeenCalledTimes(2));
    });

    it("does not replant when the dialog is cancelled", async () => {
        renderPanel();
        fireEvent.click(await screen.findByRole("button", {name: "Replant web for flag web-1"}));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Cancel"}));
        expect(ctfService.replant).not.toHaveBeenCalled();
    });

    it("shows the API error when the replant is refused", async () => {
        vi.mocked(ctfService.replant).mockRejectedValue(new HttpError(409, "Event is not armed"));
        renderPanel();
        fireEvent.click(await screen.findByRole("button", {name: "Replant web for flag web-1"}));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Replant"}));
        expect(await screen.findByText("409: Event is not armed")).toBeInTheDocument();
    });

    it("enables Replant only in the states the API accepts", async () => {
        // Written out independently of REPLANT_STATES so a drift from the PRD's route table fails here.
        expect([...REPLANT_STATES].sort()).toEqual(
            [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN].sort()
        );
        for (const state of Object.values(CtfStates)) {
            const {unmount} = renderPanel(state);
            const button = await screen.findByRole("button", {name: "Replant web for flag web-1"});
            if (REPLANT_STATES.includes(state)) {
                expect(button).toBeEnabled();
            } else {
                expect(button).toBeDisabled();
            }
            unmount();
        }
    });

    it("shows an error alert when the flags cannot be read", async () => {
        vi.mocked(ctfService.getFlags).mockRejectedValue(new HttpError(500, "boom"));
        renderPanel();
        expect(await screen.findByText("500: boom")).toBeInTheDocument();
    });

    it("replants the union of the selected flags' servers with one scoped PUT, then clears the selection", async () => {
        vi.mocked(ctfService.replant).mockResolvedValue({messages: 4});
        renderPanel();
        const bulk = await screen.findByRole("button", {name: "Replant selected"});
        expect(bulk).toBeDisabled();

        await checkRow("web-1");
        await checkRow("db-1");
        fireEvent.click(screen.getByRole("button", {name: "Replant selected (2)"}));

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toHaveTextContent("Replant 2 servers");
        expect(dialog).toHaveTextContent("Plant every flag on web, db again, on every board.");
        fireEvent.click(within(dialog).getByRole("button", {name: "Replant"}));

        await waitFor(() => expect(ctfService.replant).toHaveBeenCalledTimes(1));
        expect(ctfService.replant).toHaveBeenCalledWith(CTF_ID, {servers: ["web", "db"]});
        expect(await screen.findByText("Replant of web, db started (4 plant requests).")).toBeInTheDocument();
        // findByRole: the closing dialog keeps the grid aria-hidden until its exit transition ends.
        expect(await screen.findByRole("button", {name: "Replant selected"})).toBeDisabled();
    });

    it("sends a server once when several selected flags live on it", async () => {
        vi.mocked(ctfService.getFlags).mockResolvedValue([flag(), flag({flag_id: "web-2", slot: 2})]);
        vi.mocked(ctfService.replant).mockResolvedValue({messages: 1});
        renderPanel();
        await checkRow("web-1");
        await checkRow("web-2");
        fireEvent.click(screen.getByRole("button", {name: "Replant selected (1)"}));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Replant"}));
        await waitFor(() => expect(ctfService.replant).toHaveBeenCalledWith(CTF_ID, {servers: ["web"]}));
    });

    it("keeps bulk replant disabled with a selection when the event state refuses replants", async () => {
        renderPanel(CtfStates.ENDED);
        await checkRow("web-1");
        expect(screen.getByRole("button", {name: "Replant selected (1)"})).toBeDisabled();
    });
});
