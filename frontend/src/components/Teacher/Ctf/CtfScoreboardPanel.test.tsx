// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {act, cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfScoreboardRow, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfScoreboardPanel, {SCOREBOARD_POLL_INTERVAL_MS} from "./CtfScoreboardPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getScoreboard: vi.fn(), adjustScore: vi.fn()},
}));

const CTF_ID = "eventevent";
const NOW = 1_800_000_000;

const row = (overrides: Partial<CtfScoreboardRow> = {}): CtfScoreboardRow => ({
    rank: 1,
    workout_id: "boardaaaaa",
    team_name: "Red",
    score: 300,
    solve_count: 3,
    decoy_count: 0,
    last_solve_at: NOW - 120,
    ...overrides,
});

// Ranked as the API returns them; the tie at rank 2 is broken by the earlier last solve.
const ROWS: CtfScoreboardRow[] = [
    row(),
    row({rank: 2, workout_id: "boardbbbbb", team_name: "Blue", score: 200, solve_count: 2, decoy_count: 1, last_solve_at: NOW - 600}),
    row({rank: 3, workout_id: "boardccccc", team_name: "Green", score: 200, solve_count: 2, last_solve_at: NOW - 300}),
    row({rank: 4, workout_id: "boardddddd", team_name: "Gold", score: 0, solve_count: 0, last_solve_at: null}),
];

interface PanelProps {
    state?: number;
    frozenAt?: number | null;
    active?: boolean;
}

const panel = ({state = CtfStates.RUNNING, frozenAt = null, active = true}: PanelProps = {}) => (
    <ThemeProvider theme={darkTheme}>
        <CtfScoreboardPanel ctfId={CTF_ID} state={state} scoreboardFrozenAt={frozenAt} active={active} />
    </ThemeProvider>
);

// Let the awaited getScoreboard promise settle and React flush the resulting state.
const flush = () => act(async () => {
    await Promise.resolve();
});

const teamOrder = () => screen.getAllByRole("row").slice(1)
    .map(r => within(r).getAllByRole("gridcell")[1].textContent);

describe("CtfScoreboardPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        vi.setSystemTime(NOW * 1000);
        vi.mocked(ctfService.getScoreboard).mockResolvedValue(ROWS);
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("renders the boards in the API's rank order with score, solves, decoys and last solve", async () => {
        render(panel());
        await flush();

        expect(ctfService.getScoreboard).toHaveBeenCalledWith(CTF_ID);
        expect(teamOrder()).toEqual(["Red", "Blue", "Green", "Gold"]);
        const blue = screen.getByRole("gridcell", {name: "Blue"}).closest('[role="row"]') as HTMLElement;
        const cells = within(blue).getAllByRole("gridcell").map(c => c.textContent);
        expect(cells.slice(0, 5)).toEqual(["2", "Blue", "200", "2", "1"]);
        expect(cells[5]).toBe(new Date((NOW - 600) * 1000).toLocaleString());
        const gold = screen.getByRole("gridcell", {name: "Gold"}).closest('[role="row"]') as HTMLElement;
        expect(within(gold).getByRole("gridcell", {name: "No solves"})).toBeInTheDocument();
    });

    it("re-reads the scoreboard every 30 s while active", async () => {
        render(panel());
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(SCOREBOARD_POLL_INTERVAL_MS - 1);
        });
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);

        vi.mocked(ctfService.getScoreboard).mockResolvedValue([row({team_name: "Blue", workout_id: "boardbbbbb", score: 500})]);
        await act(async () => {
            vi.advanceTimersByTime(1);
        });
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(2);
        expect(teamOrder()).toEqual(["Blue"]);
    });

    it("does not read while its tab is hidden", async () => {
        render(panel({active: false}));
        await act(async () => {
            vi.advanceTimersByTime(SCOREBOARD_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getScoreboard).not.toHaveBeenCalled();
    });

    it("reads an archived event once and stops polling", async () => {
        render(panel({state: CtfStates.ARCHIVED}));
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(SCOREBOARD_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);
    });

    it("shows the frozen banner with the freeze time only while frozen", async () => {
        const {rerender} = render(panel());
        await flush();
        expect(screen.queryByText(/has been frozen/)).not.toBeInTheDocument();

        rerender(panel({frozenAt: NOW - 60}));
        const banner = screen.getByText(/has been frozen/);
        expect(banner).toHaveTextContent(new Date((NOW - 60) * 1000).toLocaleString());
        // The instructor ranking ignores the freeze, so the banner must not suggest these rows are frozen.
        expect(banner).toHaveTextContent(/still counts every solve/);

        rerender(panel({frozenAt: null}));
        expect(screen.queryByText(/has been frozen/)).not.toBeInTheDocument();
    });

    it("shows a load error and clears it on the next successful poll", async () => {
        vi.mocked(ctfService.getScoreboard).mockRejectedValue(new HttpError(500, "boom"));
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        render(panel());
        await flush();
        expect(screen.getByText("500: boom")).toBeInTheDocument();

        vi.mocked(ctfService.getScoreboard).mockResolvedValue(ROWS);
        await act(async () => {
            vi.advanceTimersByTime(SCOREBOARD_POLL_INTERVAL_MS);
        });
        await flush();
        expect(screen.queryByText("500: boom")).not.toBeInTheDocument();
        expect(teamOrder()).toEqual(["Red", "Blue", "Green", "Gold"]);
    });

    describe("Adjust score", () => {
        const openDialog = async (team: string) => {
            render(panel());
            await flush();
            fireEvent.click(screen.getByRole("button", {name: `Adjust score for ${team}`}));
            return screen.getByRole("dialog", {name: `Adjust score for ${team}`});
        };

        it("sends the signed delta and trimmed reason for that board, then re-reads the scoreboard", async () => {
            vi.mocked(ctfService.adjustScore).mockResolvedValue({workout_id: "boardbbbbb", score: 150});
            const dialog = await openDialog("Blue");
            fireEvent.change(within(dialog).getByLabelText(/^Points/), {target: {value: "-50"}});
            fireEvent.change(within(dialog).getByLabelText(/^Reason/), {target: {value: "  late start  "}});
            fireEvent.click(within(dialog).getByRole("button", {name: "Adjust"}));
            await flush();

            expect(ctfService.adjustScore).toHaveBeenCalledWith(CTF_ID, "boardbbbbb", {delta: -50, reason: "late start"});
            expect(ctfService.getScoreboard).toHaveBeenCalledTimes(2);
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        });

        it("needs a non-zero delta within +/-10000 and a reason", async () => {
            const dialog = await openDialog("Red");
            const submit = within(dialog).getByRole("button", {name: "Adjust"});
            expect(submit).toBeDisabled();
            fireEvent.change(within(dialog).getByLabelText(/^Reason/), {target: {value: "bonus"}});
            expect(submit).toBeDisabled();
            fireEvent.change(within(dialog).getByLabelText(/^Points/), {target: {value: "10001"}});
            expect(submit).toBeDisabled();
            fireEvent.change(within(dialog).getByLabelText(/^Points/), {target: {value: "25"}});
            expect(submit).toBeEnabled();
        });

        it("keeps the dialog open with the API error when the adjustment is refused", async () => {
            vi.mocked(ctfService.adjustScore).mockRejectedValue(new HttpError(400, "The reason must not contain a flag value."));
            vi.spyOn(console, "error").mockImplementation(() => undefined);
            const dialog = await openDialog("Red");
            fireEvent.change(within(dialog).getByLabelText(/^Points/), {target: {value: "10"}});
            fireEvent.change(within(dialog).getByLabelText(/^Reason/), {target: {value: "agoge{x}"}});
            fireEvent.click(within(dialog).getByRole("button", {name: "Adjust"}));
            await flush();

            expect(within(dialog).getByText("400: The reason must not contain a flag value.")).toBeInTheDocument();
        });

        it("disables Adjust on an archived event", async () => {
            render(panel({state: CtfStates.ARCHIVED}));
            await flush();
            expect(screen.getByRole("button", {name: "Adjust score for Red"})).toBeDisabled();
        });
    });
});
