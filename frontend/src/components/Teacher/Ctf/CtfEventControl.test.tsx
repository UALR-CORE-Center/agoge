// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfAction, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import ConfirmationDialog from "../../Common/Dialogs/ConfirmationDialog/Confirmation";
import HttpError from "../../Common/Errors/HttpError";
import CtfEventControl, {CTF_ACTION_RULES, isActionLegal} from "./CtfEventControl";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {processAction: vi.fn()},
}));

const CTF_ID = "eventevent";
const LABELS: Record<CtfAction, string> = {
    arm: "Arm", start: "Start", pause: "Pause", resume: "Resume", end: "End", archive: "Archive",
};

// Mirrors CtfEvent.ACTIONS in api/core/ctf/event.py, written out independently so a drift fails here.
const EXPECTED_ENABLED: Record<keyof typeof CtfStates, CtfAction[]> = {
    DRAFT: ['arm', 'archive'],
    ARMING: [],
    ARMED: ['arm', 'start', 'archive'],
    RUNNING: ['pause', 'end'],
    PAUSED: ['resume', 'end'],
    ENDED: ['archive'],
    ARCHIVED: [],
    BROKEN: ['arm', 'archive'],
};

const renderControl = (state: number, onActionComplete = vi.fn()) => {
    render(
        <ThemeProvider theme={darkTheme}>
            <CtfEventControl ctfId={CTF_ID} state={state} onActionComplete={onActionComplete} />
        </ThemeProvider>
    );
    return onActionComplete;
};

const actionButton = (action: CtfAction) =>
    within(screen.getByRole("group", {name: "Event actions"})).getByRole("button", {name: LABELS[action]});

describe("CtfEventControl", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });
    afterEach(() => {
        cleanup();
    });

    it.each(Object.entries(EXPECTED_ENABLED))("enables only the legal actions in %s", (stateName, enabled) => {
        const state = CtfStates[stateName as keyof typeof CtfStates];
        renderControl(state);
        for (const action of Object.keys(LABELS) as CtfAction[]) {
            const shouldEnable = enabled.includes(action);
            expect(isActionLegal(action, state)).toBe(shouldEnable);
            if (shouldEnable) {
                expect(actionButton(action)).toBeEnabled();
            } else {
                expect(actionButton(action)).toBeDisabled();
            }
        }
    });

    it("confirms a reversible action with the plain dialog and refreshes state on success", async () => {
        vi.mocked(ctfService.processAction).mockResolvedValue({} as never);
        const onActionComplete = renderControl(CtfStates.ARMED);

        fireEvent.click(actionButton("start"));
        const dialog = screen.getByRole("dialog", {name: "Start CTF event"});
        expect(dialog).toHaveAccessibleDescription(CTF_ACTION_RULES.start.message);
        expect(within(dialog).queryByLabelText("Confirmation")).not.toBeInTheDocument();

        fireEvent.click(within(dialog).getByRole("button", {name: "Start"}));

        await waitFor(() => expect(onActionComplete).toHaveBeenCalledTimes(1));
        expect(ctfService.processAction).toHaveBeenCalledWith(CTF_ID, {action: "start"});
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });

    it("does nothing when the plain dialog is cancelled", async () => {
        const onActionComplete = renderControl(CtfStates.RUNNING);

        fireEvent.click(actionButton("pause"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Cancel"}));

        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(ctfService.processAction).not.toHaveBeenCalled();
        expect(onActionComplete).not.toHaveBeenCalled();
    });

    it.each(["end", "archive"] as CtfAction[])("requires typing the event id to %s, on a button that names the action", async (action) => {
        vi.mocked(ctfService.processAction).mockResolvedValue({} as never);
        const onActionComplete = renderControl(action === "end" ? CtfStates.RUNNING : CtfStates.ENDED);

        fireEvent.click(actionButton(action));
        const dialog = screen.getByRole("dialog");
        expect(within(dialog).getByText(CTF_ACTION_RULES[action].message)).toBeInTheDocument();
        expect(within(dialog).queryByRole("button", {name: "Delete"})).not.toBeInTheDocument();
        const confirm = within(dialog).getByRole("button", {name: LABELS[action]});
        expect(confirm).toBeDisabled();

        fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: "wrong"}});
        expect(confirm).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: CTF_ID}});
        expect(confirm).toBeEnabled();
        fireEvent.click(confirm);

        await waitFor(() => expect(onActionComplete).toHaveBeenCalledTimes(1));
        expect(ctfService.processAction).toHaveBeenCalledWith(CTF_ID, {action});
    });

    it("shows the API error and does not refresh when the action is refused", async () => {
        vi.mocked(ctfService.processAction).mockRejectedValue(
            new HttpError(409, "Cannot pause a CTF event that is PAUSED")
        );
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        const onActionComplete = renderControl(CtfStates.RUNNING);

        fireEvent.click(actionButton("pause"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Pause"}));

        expect(await screen.findByRole("alert")).toHaveTextContent("409: Cannot pause a CTF event that is PAUSED");
        expect(onActionComplete).not.toHaveBeenCalled();
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        // The buttons come back once the request settles.
        expect(actionButton("pause")).toBeEnabled();
    });
});

describe("ConfirmationDialog", () => {
    afterEach(() => {
        cleanup();
    });

    // Existing delete callers pass no confirmLabel and must keep their wording.
    it("still reads Delete when no confirmLabel is given", () => {
        render(<ConfirmationDialog open onClose={vi.fn()} handleConfirm={vi.fn()} expectedText="abc" loading={false} />);
        expect(screen.getByRole("button", {name: "Delete"})).toBeDisabled();
        expect(screen.getByText(/delete the selected items/)).toBeInTheDocument();
    });
});
