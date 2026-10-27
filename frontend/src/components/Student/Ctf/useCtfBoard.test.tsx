// @vitest-environment jsdom
import {act, cleanup, renderHook} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import {BOARD_POLL_INTERVAL_MS, useCtfBoard} from "./useCtfBoard";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfBoardService: {getBoard: vi.fn()},
}));

const WORKOUT_ID = "workoutaaa";

const NOT_ENROLLED: CtfStudentBoardResponse = {
    enrolled: false,
    ctf_id: null,
    name: null,
    description: null,
    rules_url: null,
    state_name: null,
    remaining_seconds: null,
    flag_format: null,
    score: null,
    challenges: [],
    public_scoreboard_enabled: false,
};

const ENROLLED: CtfStudentBoardResponse = {
    ...NOT_ENROLLED,
    enrolled: true,
    ctf_id: "eventevent",
    name: "Spring CTF",
    state_name: "RUNNING",
    remaining_seconds: 3600,
    flag_format: "agoge{...}",
    score: 100,
};

// Let the awaited getBoard promise settle and React flush the resulting state.
const flush = () => act(async () => {
    await Promise.resolve();
});

const advance = (ms: number) => act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
});

describe("useCtfBoard", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("reads the board once on mount and makes no further request when not enrolled", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(NOT_ENROLLED);
        const {result} = renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();

        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
        expect(ctfBoardService.getBoard).toHaveBeenCalledWith(WORKOUT_ID);
        expect(result.current.board).toBeNull();

        await advance(BOARD_POLL_INTERVAL_MS * 4);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
    });

    it("makes no further request even when ticks fire before React commits the not-enrolled answer", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(NOT_ENROLLED);
        renderHook(() => useCtfBoard(WORKOUT_ID));
        // One act: usePolling keeps its scheduled timers firing with no re-render in between.
        await advance(BOARD_POLL_INTERVAL_MS * 4);

        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
    });

    it("polls every 15 s when enrolled and exposes the latest board", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(ENROLLED);
        const {result} = renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();

        expect(BOARD_POLL_INTERVAL_MS).toBe(15000);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);
        expect(result.current.board?.name).toBe("Spring CTF");

        await advance(BOARD_POLL_INTERVAL_MS - 1);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(1);

        vi.mocked(ctfBoardService.getBoard).mockResolvedValue({...ENROLLED, score: 250});
        await advance(1);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
        expect(result.current.board?.score).toBe(250);

        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(3);
    });

    it("stops polling once an enrolled board reports it is no longer enrolled", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValueOnce(ENROLLED).mockResolvedValue(NOT_ENROLLED);
        const {result} = renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();
        expect(result.current.board).not.toBeNull();

        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
        expect(result.current.board).toBeNull();

        await advance(BOARD_POLL_INTERVAL_MS * 3);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
    });

    it("keeps the last board and keeps polling after a failed read", async () => {
        vi.mocked(ctfBoardService.getBoard)
            .mockResolvedValueOnce(ENROLLED)
            .mockRejectedValueOnce(new HttpError(500, "boom"))
            .mockResolvedValue({...ENROLLED, score: 300});
        const {result} = renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();

        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
        expect(result.current.board?.score).toBe(100);

        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(3);
        expect(result.current.board?.score).toBe(300);
    });

    it("retries after a failed first read, since an error does not mean not enrolled", async () => {
        vi.mocked(ctfBoardService.getBoard)
            .mockRejectedValueOnce(new HttpError(503, "unavailable"))
            .mockResolvedValue(NOT_ENROLLED);
        renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();

        await advance(BOARD_POLL_INTERVAL_MS);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);

        await advance(BOARD_POLL_INTERVAL_MS * 3);
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
    });

    it("refresh reads the board on demand", async () => {
        vi.mocked(ctfBoardService.getBoard).mockResolvedValue(ENROLLED);
        const {result} = renderHook(() => useCtfBoard(WORKOUT_ID));
        await flush();

        vi.mocked(ctfBoardService.getBoard).mockResolvedValue({...ENROLLED, score: 500});
        await act(async () => {
            await result.current.refresh();
        });
        expect(ctfBoardService.getBoard).toHaveBeenCalledTimes(2);
        expect(result.current.board?.score).toBe(500);
    });
});
