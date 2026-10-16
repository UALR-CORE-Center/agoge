// @vitest-environment jsdom
import {act, cleanup, render, screen} from "@testing-library/react";
import React from "react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import {workoutService} from "../../../services/Workout/workout.service";
import StudentWorkout from "../Workout";
import {BOARD_POLL_INTERVAL_MS} from "./useCtfBoard";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfBoardService: {getBoard: vi.fn()},
}));
vi.mock("../../../services/Workout/workout.service", () => ({
    workoutService: {get_full: vi.fn()},
}));
vi.mock("../../../hooks/userIp", () => ({useUserIp: () => null}));
// The page's children have their own data fetching; only the two polls are under test here.
vi.mock("../../Common/Timer", () => ({default: () => null}));
vi.mock("../../Common/InfoCard/InfoCard", () => ({InfoCard: () => null}));
vi.mock("../ConfigureAccess", () => ({ConfigureAccess: () => null}));
vi.mock("../WorkoutTable", () => ({default: () => null}));
vi.mock("../WorkoutAssessment", () => ({default: () => null}));

const WORKOUT_ID = "workoutaaa";

const BOARD = (enrolled: boolean): CtfStudentBoardResponse => ({
    enrolled,
    ctf_id: enrolled ? "eventevent" : null,
    name: enrolled ? "Spring CTF" : null,
    description: null,
    rules_url: null,
    state_name: enrolled ? "RUNNING" : null,
    remaining_seconds: null,
    flag_format: null,
    score: null,
    challenges: [],
    public_scoreboard_enabled: false,
});

const page = () => (
    <MemoryRouter initialEntries={[`/student/workout/${WORKOUT_ID}`]}>
        <Routes>
            <Route path="/student/workout/:build_id" element={<StudentWorkout />} />
        </Routes>
    </MemoryRouter>
);

const advance = (ms: number) => act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
});

describe("StudentWorkout CTF polling", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        // One server keeps the page's own workout poll at its 3.5 s cadence.
        vi.mocked(workoutService.get_full).mockResolvedValue({
            workout: {state: "RUNNING", student_external_ip_addresses: []},
            servers: [{}],
        } as never);
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("polls the board every 15 s on its own cadence while the workout poll runs every 3.5 s", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(BOARD(true));
        render(page());
        await advance(0);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
        expect(ctfBoardService.getBoard).toHaveBeenCalledWith(WORKOUT_ID);

        const workoutReads = vi.mocked(workoutService.get_full).mock.calls.length;
        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
        // Four 3.5 s workout ticks fit in 15 s; the board poll did not ride on them.
        expect(vi.mocked(workoutService.get_full).mock.calls.length - workoutReads).toBeGreaterThanOrEqual(4);
    });

    it("makes one CTF request and no more when the workout is not enrolled", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(BOARD(false));
        render(page());
        // Separate acts let React commit between ticks, as it would in a browser.
        for (let i = 0; i < 4; i++) {
            await advance(BOARD_POLL_INTERVAL_MS);
        }

        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
        expect(vi.mocked(workoutService.get_full).mock.calls.length).toBeGreaterThan(4);
    });

    it("shows the CTF banner in the session aside for an enrolled workout", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(BOARD(true));
        render(page());
        await advance(0);

        const aside = screen.getByRole("complementary", {name: "Workout session controls"});
        const banner = screen.getByRole("region", {name: "Spring CTF"});
        expect(aside.contains(banner)).toBe(true);
        // The banner sits at the top of the aside, above the session controls (TimerBox).
        expect(aside.firstElementChild).toBe(banner);
    });

    it("renders no CTF banner when the workout is not enrolled", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(BOARD(false));
        render(page());
        await advance(0);

        expect(screen.queryByRole("region", {name: "Spring CTF"})).toBeNull();
        expect(screen.queryByText("Time remaining")).toBeNull();
    });
});
