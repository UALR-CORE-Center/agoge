// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStudentBoardResponse, CtfSubmitResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import FlagSubmitCard, {FLAG_MAX_LENGTH} from "./FlagSubmitCard";

const showModal = vi.fn();
vi.mock("mui-modal-provider", () => ({useModal: () => ({showModal})}));
vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfBoardService: {submitFlag: vi.fn()},
}));

const WORKOUT_ID = "workoutaaa";

const BOARD: CtfStudentBoardResponse = {
    enrolled: true,
    ctf_id: "eventevent",
    name: "Spring CTF",
    description: null,
    rules_url: null,
    state_name: "RUNNING",
    remaining_seconds: 600,
    flag_format: "agoge{<challenge>_<20 hex>}",
    score: 0,
    challenges: [],
    public_scoreboard_enabled: false,
};

const RESULT = (overrides: Partial<CtfSubmitResponse>): CtfSubmitResponse => ({
    verdict: "correct",
    correct: true,
    points_awarded: 100,
    message: "Correct! Flag accepted.",
    ...overrides,
});

const renderCard = (board: CtfStudentBoardResponse = BOARD, onSubmitted = vi.fn()) => {
    render(<FlagSubmitCard workoutId={WORKOUT_ID} board={board} onSubmitted={onSubmitted} />);
    return onSubmitted;
};

const field = () => screen.getByLabelText("Flag") as HTMLInputElement;

const submit = async (value: string) => {
    fireEvent.change(field(), {target: {value}});
    await act(async () => {
        fireEvent.click(screen.getByRole("button", {name: "Submit"}));
    });
};

describe("FlagSubmitCard", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    afterEach(() => {
        cleanup();
    });

    it("is a labelled section with one text field and the flag format shown verbatim", () => {
        renderCard();

        expect(screen.getByRole("region", {name: "Submit a flag"}).tagName).toBe("SECTION");
        expect(screen.getAllByRole("textbox")).toHaveLength(1);
        // Angle brackets and all, exactly as the spec wrote it.
        expect(screen.getByText("agoge{<challenge>_<20 hex>}").tagName).toBe("CODE");
        expect(field().maxLength).toBe(FLAG_MAX_LENGTH);
    });

    it("omits the format line when the board has none", () => {
        renderCard({...BOARD, flag_format: null});
        expect(screen.queryByText(/Format:/)).toBeNull();
    });

    it("keeps Submit disabled until a non-blank value is typed", () => {
        renderCard();
        const button = screen.getByRole("button", {name: "Submit"}) as HTMLButtonElement;
        expect(button.disabled).toBe(true);
        fireEvent.change(field(), {target: {value: "   "}});
        expect(button.disabled).toBe(true);
        fireEvent.change(field(), {target: {value: "agoge{x}"}});
        expect(button.disabled).toBe(false);
    });

    it("submits the value, shows a correct verdict as success with the points, clears and refreshes", async () => {
        vi.mocked(ctfBoardService.submitFlag).mockResolvedValue(RESULT({}));
        const onSubmitted = renderCard();

        await submit("agoge{web-1_0123456789abcdef0123}");

        expect(ctfBoardService.submitFlag).toHaveBeenCalledWith(WORKOUT_ID, "agoge{web-1_0123456789abcdef0123}");
        expect(showModal).toHaveBeenCalledWith(SimpleSnackbar, {
            message: "Correct! Flag accepted. (+100 points)",
            severity: "success",
        });
        expect(field().value).toBe("");
        expect(onSubmitted).toHaveBeenCalledTimes(1);
    });

    it.each([
        ["incorrect", "Incorrect flag.", 0, "error", "Incorrect flag."],
        ["duplicate", "Your team has already solved this flag.", 0, "info", "Your team has already solved this flag."],
        ["decoy", "That flag is out of scope for this exercise.", -50, "warning",
            "That flag is out of scope for this exercise. (-50 points)"],
    ] as const)("shows a %s verdict with its severity", async (verdict, message, points, severity, shown) => {
        vi.mocked(ctfBoardService.submitFlag).mockResolvedValue(
            RESULT({verdict, message, correct: false, points_awarded: points})
        );
        renderCard();

        await submit("agoge{guess}");

        expect(showModal).toHaveBeenCalledWith(SimpleSnackbar, {message: shown, severity});
    });

    it("keeps an incorrect value in the field so a typo can be fixed", async () => {
        vi.mocked(ctfBoardService.submitFlag).mockResolvedValue(
            RESULT({verdict: "incorrect", correct: false, points_awarded: 0, message: "Incorrect flag."})
        );
        renderCard();

        await submit("agoge{typo}");

        expect(field().value).toBe("agoge{typo}");
    });

    it("shows the server's message on a 429", async () => {
        const detail = "Too many submissions for this challenge. Try again in 42 seconds.";
        vi.mocked(ctfBoardService.submitFlag).mockRejectedValue(new HttpError(429, detail));
        const onSubmitted = renderCard();

        await submit("agoge{again}");

        expect(showModal).toHaveBeenCalledWith(SimpleSnackbar, {message: detail, severity: "warning"});
        expect(field().value).toBe("agoge{again}");
        expect(onSubmitted).toHaveBeenCalledTimes(1);
    });

    it("shows the server's message when submissions are closed (409) and refreshes the board", async () => {
        vi.mocked(ctfBoardService.submitFlag).mockRejectedValue(new HttpError(409, "Submissions are closed."));
        const onSubmitted = renderCard();

        await submit("agoge{late}");

        expect(showModal).toHaveBeenCalledWith(SimpleSnackbar, {message: "Submissions are closed.", severity: "warning"});
        // The refresh is what moves a stale RUNNING board to its real state.
        expect(onSubmitted).toHaveBeenCalledTimes(1);
    });

    it("shows a generic error for any other failure", async () => {
        vi.mocked(ctfBoardService.submitFlag).mockRejectedValue(new HttpError(500, "Internal Server Error"));
        renderCard();

        await submit("agoge{x}");

        expect(showModal).toHaveBeenCalledWith(SimpleSnackbar, {
            message: "The flag could not be submitted. Try again.",
            severity: "error",
        });
    });

    it("disables the field and button when the event is not running", () => {
        renderCard({...BOARD, state_name: "PAUSED"});

        expect(field().disabled).toBe(true);
        expect((screen.getByRole("button", {name: "Submit"}) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByText("Flags can be submitted while the event is running.")).toBeTruthy();
    });

    it("submits on Enter and ignores a second submit while one is pending", async () => {
        let resolve: (value: CtfSubmitResponse) => void = () => undefined;
        vi.mocked(ctfBoardService.submitFlag).mockReturnValue(new Promise((r) => {
            resolve = r;
        }));
        renderCard();

        fireEvent.change(field(), {target: {value: "agoge{x}"}});
        const form = field().closest("form") as HTMLFormElement;
        await act(async () => {
            fireEvent.submit(form);
        });
        await act(async () => {
            fireEvent.submit(form);
        });
        expect(ctfBoardService.submitFlag).toHaveBeenCalledTimes(1);

        await act(async () => {
            resolve(RESULT({}));
        });
        expect(showModal).toHaveBeenCalledTimes(1);
    });
});
