// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {act, cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfBoardStatus, CtfStates, CtfSubmission, VERDICTS} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfSubmissionLogPanel, {
    SUBMISSIONS_POLL_INTERVAL_MS,
    SUBMISSIONS_ROW_CAP,
    VERDICT_LABELS,
    newestFirst,
} from "./CtfSubmissionLogPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getSubmissions: vi.fn()},
}));

const CTF_ID = "eventevent";
const NOW = 1_800_000_000;

const board = (workout_id: string, team_name: string): CtfBoardStatus => ({
    workout_id, team_name, arm_status: "armed", arm_error: null, plant_failed_count: 0, plant_stale_count: 0,
});

const BOARDS = [board("boardaaaaa", "Red"), board("boardbbbbb", "Blue")];

const submission = (overrides: Partial<CtfSubmission> = {}): CtfSubmission => ({
    id: "sub-1",
    ctf_id: CTF_ID,
    workout_id: "boardaaaaa",
    flag_id: "web-1",
    submitted_digest: "digest",
    verdict: "incorrect",
    matched_workout_id: null,
    points_awarded: 0,
    submitted_at: NOW - 300,
    origin_ip: "10.0.0.5",
    ...overrides,
});

// Deliberately not newest first, so the panel's own ordering is what the tests see.
const SUBMISSIONS: CtfSubmission[] = [
    submission({id: "sub-1", verdict: "correct", points_awarded: 100, submitted_at: NOW - 900}),
    submission({id: "sub-3", verdict: "cross_submission", matched_workout_id: "boardbbbbb", submitted_at: NOW - 60}),
    submission({id: "sub-2", workout_id: "boardbbbbb", flag_id: null, verdict: "incorrect", origin_ip: null, submitted_at: NOW - 300}),
];

interface PanelProps {
    state?: number;
    active?: boolean;
    boards?: CtfBoardStatus[];
}

const panel = ({state = CtfStates.RUNNING, active = true, boards = BOARDS}: PanelProps = {}) => (
    <ThemeProvider theme={darkTheme}>
        <CtfSubmissionLogPanel ctfId={CTF_ID} state={state} boards={boards} active={active} />
    </ThemeProvider>
);

// Let the awaited getSubmissions promise settle and React flush the resulting state.
const flush = () => act(async () => {
    await Promise.resolve();
});

const rowCells = () => screen.getAllByRole("row").slice(1)
    .map(r => within(r).getAllByRole("gridcell").map(c => c.textContent));

const verdictOrder = () => rowCells().map(cells => cells[3]);

const chooseVerdict = async (label: string) => {
    fireEvent.mouseDown(screen.getByRole("combobox", {name: "Verdict"}));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name: label}));
    await flush();
};

describe("CtfSubmissionLogPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        vi.setSystemTime(NOW * 1000);
        vi.mocked(ctfService.getSubmissions).mockResolvedValue(SUBMISSIONS);
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("sorts submissions newest first", () => {
        expect(newestFirst(SUBMISSIONS).map(s => s.id)).toEqual(["sub-3", "sub-2", "sub-1"]);
    });

    it("renders newest first with team names, and the matched team only on a cross-team submission", async () => {
        render(panel());
        await flush();

        expect(ctfService.getSubmissions).toHaveBeenCalledWith(CTF_ID, undefined);
        expect(rowCells()).toEqual([
            [new Date((NOW - 60) * 1000).toLocaleString(), "Red", "web-1", "Cross-team submission", "Blue", "0", "10.0.0.5"],
            [new Date((NOW - 300) * 1000).toLocaleString(), "Blue", "", "Incorrect", "", "0", ""],
            [new Date((NOW - 900) * 1000).toLocaleString(), "Red", "web-1", "Correct", "", "100", "10.0.0.5"],
        ]);
    });

    it("shows no matched team when a non-cross verdict carries a matched workout id", async () => {
        vi.mocked(ctfService.getSubmissions).mockResolvedValue([
            submission({verdict: "incorrect", matched_workout_id: "boardbbbbb"}),
        ]);
        render(panel());
        await flush();
        expect(rowCells()[0][4]).toBe("");
    });

    it("falls back to the workout id for a board the state poll does not list", async () => {
        vi.mocked(ctfService.getSubmissions).mockResolvedValue([
            submission({workout_id: "boardzzzzz", verdict: "cross_submission", matched_workout_id: "boardyyyyy"}),
        ]);
        render(panel({boards: []}));
        await flush();
        expect(rowCells()[0][1]).toBe("boardzzzzz");
        expect(rowCells()[0][4]).toBe("boardyyyyy");
    });

    it("offers every verdict as a filter and re-reads with it at once", async () => {
        render(panel());
        await flush();

        fireEvent.mouseDown(screen.getByRole("combobox", {name: "Verdict"}));
        const options = within(screen.getByRole("listbox")).getAllByRole("option").map(o => o.textContent);
        expect(options).toEqual(["All verdicts", ...VERDICTS.map(v => VERDICT_LABELS[v])]);
        fireEvent.keyDown(screen.getByRole("listbox"), {key: "Escape"});

        vi.mocked(ctfService.getSubmissions).mockResolvedValue([SUBMISSIONS[1]]);
        await chooseVerdict("Cross-team submission");
        expect(ctfService.getSubmissions).toHaveBeenLastCalledWith(CTF_ID, "cross_submission");
        expect(verdictOrder()).toEqual(["Cross-team submission"]);

        // The filter sticks across polls.
        await act(async () => {
            vi.advanceTimersByTime(SUBMISSIONS_POLL_INTERVAL_MS);
        });
        await flush();
        expect(ctfService.getSubmissions).toHaveBeenLastCalledWith(CTF_ID, "cross_submission");

        vi.mocked(ctfService.getSubmissions).mockResolvedValue([]);
        await chooseVerdict("Rate limited");
        expect(screen.getByText("No submissions with this verdict")).toBeInTheDocument();

        vi.mocked(ctfService.getSubmissions).mockResolvedValue(SUBMISSIONS);
        await chooseVerdict("All verdicts");
        expect(ctfService.getSubmissions).toHaveBeenLastCalledWith(CTF_ID, undefined);
        expect(verdictOrder()).toEqual(["Cross-team submission", "Incorrect", "Correct"]);
    });

    it("drops a response for a filter the user has already changed", async () => {
        let resolveStale: (rows: CtfSubmission[]) => void = () => undefined;
        render(panel());
        await flush();

        vi.mocked(ctfService.getSubmissions)
            .mockImplementationOnce(() => new Promise(resolve => {
                resolveStale = resolve;
            }))
            .mockResolvedValueOnce([SUBMISSIONS[0]]);
        await chooseVerdict("Cross-team submission");
        await chooseVerdict("Correct");
        expect(verdictOrder()).toEqual(["Correct"]);

        await act(async () => {
            resolveStale([SUBMISSIONS[1]]);
        });
        await flush();
        expect(verdictOrder()).toEqual(["Correct"]);
    });

    it("re-reads every 15 s while active and not while hidden", async () => {
        const {rerender} = render(panel({active: false}));
        await act(async () => {
            vi.advanceTimersByTime(SUBMISSIONS_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getSubmissions).not.toHaveBeenCalled();

        rerender(panel());
        await flush();
        expect(ctfService.getSubmissions).toHaveBeenCalledTimes(1);
        await act(async () => {
            vi.advanceTimersByTime(SUBMISSIONS_POLL_INTERVAL_MS - 1);
        });
        expect(ctfService.getSubmissions).toHaveBeenCalledTimes(1);
        await act(async () => {
            vi.advanceTimersByTime(1);
        });
        await flush();
        expect(ctfService.getSubmissions).toHaveBeenCalledTimes(2);
    });

    it("reads an archived event once and stops polling", async () => {
        render(panel({state: CtfStates.ARCHIVED}));
        await flush();
        expect(ctfService.getSubmissions).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(SUBMISSIONS_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getSubmissions).toHaveBeenCalledTimes(1);
    });

    it("says when the log is capped at the API's row limit", async () => {
        const full = Array.from({length: SUBMISSIONS_ROW_CAP}, (_, i) => submission({id: `sub-${i}`, submitted_at: NOW - i}));
        vi.mocked(ctfService.getSubmissions).mockResolvedValue(full);
        render(panel());
        await flush();
        expect(screen.getByText(/Showing the newest 500 submissions/)).toBeInTheDocument();
    });

    it("shows a load error and clears it on the next successful poll", async () => {
        vi.mocked(ctfService.getSubmissions).mockRejectedValue(new HttpError(500, "boom"));
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        render(panel());
        await flush();
        expect(screen.getByText("500: boom")).toBeInTheDocument();

        vi.mocked(ctfService.getSubmissions).mockResolvedValue(SUBMISSIONS);
        await act(async () => {
            vi.advanceTimersByTime(SUBMISSIONS_POLL_INTERVAL_MS);
        });
        await flush();
        expect(screen.queryByText("500: boom")).not.toBeInTheDocument();
        expect(verdictOrder()).toEqual(["Cross-team submission", "Incorrect", "Correct"]);
    });
});
