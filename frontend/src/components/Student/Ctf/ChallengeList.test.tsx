// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfChallenge, CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import ChallengeList, {PUBLIC_SCOREBOARD_POLL_INTERVAL_MS} from "./ChallengeList";

const showModal = vi.fn();
vi.mock("mui-modal-provider", () => ({useModal: () => ({showModal})}));
vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfBoardService: {takeHint: vi.fn(), getPublicScoreboard: vi.fn()},
}));

const WORKOUT_ID = "workoutaaa";

const CHALLENGE = (overrides: Partial<CtfChallenge>): CtfChallenge => ({
    flag_id: "web1",
    category: "web",
    points: 100,
    solved: false,
    solved_at: null,
    hint_available: true,
    hint_cost: 25,
    hint: null,
    ...overrides,
});

const BOARD = (overrides: Partial<CtfStudentBoardResponse> = {}): CtfStudentBoardResponse => ({
    enrolled: true,
    ctf_id: "eventevent",
    name: "Spring CTF",
    description: null,
    rules_url: null,
    state_name: "RUNNING",
    remaining_seconds: 600,
    flag_format: null,
    score: 75,
    challenges: [
        CHALLENGE({}),
        CHALLENGE({flag_id: "pwn1", category: null, points: 200, solved: true, solved_at: 1, hint_available: false, hint_cost: 0}),
        CHALLENGE({flag_id: "crypto1", category: "crypto", hint: "Look at the padding.", hint_cost: 10}),
    ],
    public_scoreboard_enabled: false,
    ...overrides,
});

const renderList = (board: CtfStudentBoardResponse = BOARD(), onChanged = vi.fn()) => {
    const view = render(<ChallengeList workoutId={WORKOUT_ID} board={board} onChanged={onChanged} />);
    return {onChanged, view};
};

const flush = () => act(async () => {
    await Promise.resolve();
});

// The page stays aria-hidden until the dialog's exit transition ends, so role queries must wait for it.
const dialogClosed = () => waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

const rowFor = (flagId: string) => screen.getByRole("rowheader", {name: flagId}).closest("tr") as HTMLElement;

describe("ChallengeList", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("lists category, points and solved state for each challenge in a labelled section", () => {
        renderList();

        expect(screen.getByRole("region", {name: "Challenges"}).tagName).toBe("SECTION");
        expect(within(rowFor("web1")).getByText("web")).toBeTruthy();
        expect(within(rowFor("web1")).getByText("100")).toBeTruthy();
        expect(within(rowFor("web1")).getByText("Unsolved")).toBeTruthy();
        // A flag with no category falls back to a neutral label.
        expect(within(rowFor("pwn1")).getByText("General")).toBeTruthy();
        expect(within(rowFor("pwn1")).getByText("Solved")).toBeTruthy();
        expect(screen.getByText("75")).toBeTruthy();
    });

    it("never shows a host or path column", () => {
        renderList();
        const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
        expect(headers).toEqual(["Challenge", "Category", "Points", "Status", "Hint"]);
    });

    it("shows a taken hint's text, 'No hint' when there is none, and a button with the cost otherwise", () => {
        renderList();

        expect(within(rowFor("crypto1")).getByText("Look at the padding.")).toBeTruthy();
        expect(within(rowFor("crypto1")).queryByRole("button")).toBeNull();
        expect(within(rowFor("pwn1")).getByText("No hint")).toBeTruthy();
        expect(within(rowFor("web1")).getByRole("button", {name: /Take hint for web1 \(costs 25 points\)/})).toBeTruthy();
    });

    it("disables the hint button when the event is not running", () => {
        renderList(BOARD({state_name: "PAUSED"}));
        expect((within(rowFor("web1")).getByRole("button") as HTMLButtonElement).disabled).toBe(true);
    });

    it("confirms with the cost before taking a hint, then shows it and refreshes the board", async () => {
        vi.mocked(ctfBoardService.takeHint).mockResolvedValue(
            {flag_id: "web1", hint: "Check robots.txt.", hint_cost: 25, score: 50}
        );
        const {onChanged} = renderList();

        fireEvent.click(within(rowFor("web1")).getByRole("button"));
        const dialog = screen.getByRole("dialog");
        expect(within(dialog).getByText(/deducts 25 points from your team's score/)).toBeTruthy();
        expect(ctfBoardService.takeHint).not.toHaveBeenCalled();

        await act(async () => {
            fireEvent.click(within(dialog).getByRole("button", {name: "Take hint"}));
        });

        expect(ctfBoardService.takeHint).toHaveBeenCalledWith(WORKOUT_ID, "web1");
        await dialogClosed();
        expect(within(rowFor("web1")).getByText("Check robots.txt.")).toBeTruthy();
        expect(onChanged).toHaveBeenCalledTimes(1);
        expect(showModal).not.toHaveBeenCalled();
    });

    it("says a free hint is free", () => {
        renderList(BOARD({challenges: [CHALLENGE({hint_cost: 0})]}));
        fireEvent.click(screen.getByRole("button", {name: /Take hint for web1/}));
        expect(within(screen.getByRole("dialog")).getByText(/This hint is free/)).toBeTruthy();
    });

    it("cancelling the dialog takes no hint", () => {
        renderList();
        fireEvent.click(within(rowFor("web1")).getByRole("button"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Cancel"}));
        expect(ctfBoardService.takeHint).not.toHaveBeenCalled();
    });

    it("shows the server's message for a 409 and a generic error otherwise, refreshing either way", async () => {
        vi.mocked(ctfBoardService.takeHint).mockRejectedValueOnce(new HttpError(409, "Hints are closed."));
        const {onChanged} = renderList();

        fireEvent.click(within(rowFor("web1")).getByRole("button"));
        await act(async () => {
            fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Take hint"}));
        });
        expect(showModal).toHaveBeenLastCalledWith(SimpleSnackbar, {message: "Hints are closed.", severity: "warning"});
        await dialogClosed();
        expect(within(rowFor("web1")).getByRole("button")).toBeTruthy();

        vi.mocked(ctfBoardService.takeHint).mockRejectedValueOnce(new HttpError(500, "Internal detail"));
        fireEvent.click(within(rowFor("web1")).getByRole("button"));
        await act(async () => {
            fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Take hint"}));
        });
        expect(showModal).toHaveBeenLastCalledWith(
            SimpleSnackbar, {message: "The hint could not be loaded. Try again.", severity: "error"}
        );
        expect(onChanged).toHaveBeenCalledTimes(2);
    });

    it("says so when no challenges are listed", () => {
        renderList(BOARD({challenges: []}));
        expect(screen.getByText("No challenges are available yet.")).toBeTruthy();
        expect(screen.queryByRole("table")).toBeNull();
    });

    it("makes no scoreboard request and shows no standings when the public scoreboard is off", async () => {
        renderList();
        await flush();
        expect(ctfBoardService.getPublicScoreboard).not.toHaveBeenCalled();
        expect(screen.queryByRole("region", {name: "Standings"})).toBeNull();
    });

    it("shows the standings with the caller's row highlighted when the public scoreboard is on", async () => {
        vi.mocked(ctfBoardService.getPublicScoreboard).mockResolvedValue([
            {rank: 1, team_label: "Team 2", score: 300, solve_count: 2, is_you: false},
            {rank: 2, team_label: "Team 1", score: 75, solve_count: 1, is_you: true},
        ]);
        renderList(BOARD({public_scoreboard_enabled: true}));
        await flush();

        expect(ctfBoardService.getPublicScoreboard).toHaveBeenCalledWith(WORKOUT_ID);
        const standings = screen.getByRole("region", {name: "Standings"});
        const you = within(standings).getByText("Team 1").closest("tr") as HTMLElement;
        const other = within(standings).getByText("Team 2").closest("tr") as HTMLElement;
        expect(you.getAttribute("aria-current")).toBe("true");
        expect(you.className).toMatch(/Mui-selected/);
        expect(within(you).getByText("(you)")).toBeTruthy();
        expect(other.getAttribute("aria-current")).toBeNull();
        expect(other.className).not.toMatch(/Mui-selected/);
    });

    it("polls the standings every 30 s", async () => {
        vi.useFakeTimers();
        vi.mocked(ctfBoardService.getPublicScoreboard).mockResolvedValue([]);
        renderList(BOARD({public_scoreboard_enabled: true}));
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });
        expect(ctfBoardService.getPublicScoreboard).toHaveBeenCalledTimes(1);

        await act(async () => {
            await vi.advanceTimersByTimeAsync(PUBLIC_SCOREBOARD_POLL_INTERVAL_MS);
        });
        expect(ctfBoardService.getPublicScoreboard).toHaveBeenCalledTimes(2);
        expect(screen.getByText("No standings yet.")).toBeTruthy();
    });

    it("drops the standings when the board says the public scoreboard was turned off", async () => {
        vi.mocked(ctfBoardService.getPublicScoreboard).mockResolvedValue([
            {rank: 1, team_label: "Team 1", score: 75, solve_count: 1, is_you: true},
        ]);
        const {view} = renderList(BOARD({public_scoreboard_enabled: true}));
        await flush();
        expect(screen.getByRole("region", {name: "Standings"})).toBeTruthy();

        view.rerender(<ChallengeList workoutId={WORKOUT_ID} board={BOARD()} onChanged={vi.fn()} />);
        await flush();
        expect(screen.queryByRole("region", {name: "Standings"})).toBeNull();
    });
    it.each([
        ["a 404", new HttpError(404, "Not found")],
        ["a server error", new HttpError(500, "Internal detail")],
    ])("says the standings are unavailable when the first read fails with %s", async (_, error) => {
        vi.mocked(ctfBoardService.getPublicScoreboard).mockRejectedValue(error);
        renderList(BOARD({public_scoreboard_enabled: true}));
        await flush();

        const standings = screen.getByRole("region", {name: "Standings"});
        expect(within(standings).getByText("The standings are unavailable right now.")).toBeTruthy();
        expect(within(standings).queryByText("Loading standings…")).toBeNull();
    });

    it("keeps the last good standings when a later read fails", async () => {
        vi.useFakeTimers();
        vi.mocked(ctfBoardService.getPublicScoreboard)
            .mockResolvedValueOnce([{rank: 1, team_label: "Team 1", score: 75, solve_count: 1, is_you: true}])
            .mockRejectedValueOnce(new HttpError(500, "Internal detail"));
        renderList(BOARD({public_scoreboard_enabled: true}));
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(PUBLIC_SCOREBOARD_POLL_INTERVAL_MS);
        });

        expect(ctfBoardService.getPublicScoreboard).toHaveBeenCalledTimes(2);
        expect(screen.getByText("Team 1")).toBeTruthy();
        expect(screen.queryByText("The standings are unavailable right now.")).toBeNull();
    });
});
