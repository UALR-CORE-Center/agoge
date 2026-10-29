// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import ScoreboardSettings, {ScoreboardSettingsEvent} from "./ScoreboardSettings";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {update: vi.fn()},
}));

const CTF_ID = "eventevent";
const NOW = new Date(2026, 9, 16, 12, 0, 0);
const NOW_SECONDS = NOW.getTime() / 1000;

const baseEvent = (overrides: Partial<ScoreboardSettingsEvent> = {}): ScoreboardSettingsEvent => ({
    state: CtfStates.RUNNING,
    ends_at: null,
    scoreboard_frozen_at: null,
    public_scoreboard_enabled: false,
    ...overrides,
});

const renderSettings = (event: ScoreboardSettingsEvent, onUpdated = vi.fn()) => {
    const utils = render(
        <ThemeProvider theme={darkTheme}>
            <ScoreboardSettings ctfId={CTF_ID} event={event} onUpdated={onUpdated} />
        </ThemeProvider>
    );
    return {onUpdated, ...utils};
};

const freezeSwitch = () => screen.getByRole("switch", {name: "Freeze scoreboard"});
const publicSwitch = () => screen.getByRole("switch", {name: "Public scoreboard"});
const endsInput = () => screen.getByRole("textbox", {name: "Ends at"});
const saveEnd = () => screen.getByRole("button", {name: "Save end time"});
const clearEnd = () => screen.getByRole("button", {name: "Clear end time"});

describe("ScoreboardSettings", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        // Only Date is faked: MUI transitions and testing-library's waitFor still need real timers.
        vi.useFakeTimers({toFake: ["Date"]});
        vi.setSystemTime(NOW);
    });
    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("freezing sends PUT with the current time, then re-reads state", async () => {
        vi.mocked(ctfService.update).mockResolvedValue({} as never);
        const {onUpdated} = renderSettings(baseEvent());

        expect(freezeSwitch()).not.toBeChecked();
        fireEvent.click(freezeSwitch());

        await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
        expect(ctfService.update).toHaveBeenCalledWith(CTF_ID, {scoreboard_frozen_at: NOW_SECONDS});
    });

    it("unfreezing sends an explicit null and shows when it was frozen", async () => {
        vi.mocked(ctfService.update).mockResolvedValue({} as never);
        const frozenAt = NOW_SECONDS - 600;
        const {onUpdated} = renderSettings(baseEvent({scoreboard_frozen_at: frozenAt}));

        expect(freezeSwitch()).toBeChecked();
        expect(screen.getByText(new RegExp(`Frozen at ${new Date(frozenAt * 1000).toLocaleString()}`)))
            .toBeInTheDocument();
        fireEvent.click(freezeSwitch());

        await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
        // The key must be present: CtfEvent.update applies only fields in the body, so omitting it would not unfreeze.
        expect(ctfService.update).toHaveBeenCalledWith(CTF_ID, {scoreboard_frozen_at: null});
    });

    it.each([
        [false, true],
        [true, false],
    ])("public scoreboard toggle from %s sends %s", async (current, sent) => {
        vi.mocked(ctfService.update).mockResolvedValue({} as never);
        const {onUpdated} = renderSettings(baseEvent({public_scoreboard_enabled: current}));

        fireEvent.click(publicSwitch());

        await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
        expect(ctfService.update).toHaveBeenCalledWith(CTF_ID, {public_scoreboard_enabled: sent});
    });

    it("saves a picked end time as epoch seconds", async () => {
        vi.mocked(ctfService.update).mockResolvedValue({} as never);
        const {onUpdated} = renderSettings(baseEvent());

        expect(saveEnd()).toBeDisabled();
        expect(clearEnd()).toBeDisabled();
        fireEvent.change(endsInput(), {target: {value: "10/16/2026 05:30 PM"}});
        expect(saveEnd()).toBeEnabled();
        fireEvent.click(saveEnd());

        await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
        const expected = new Date(2026, 9, 16, 17, 30, 0).getTime() / 1000;
        expect(ctfService.update).toHaveBeenCalledWith(CTF_ID, {ends_at: expected});
    });

    it("refuses to save an end time in the past", () => {
        renderSettings(baseEvent());

        fireEvent.change(endsInput(), {target: {value: "10/16/2026 11:00 AM"}});

        expect(saveEnd()).toBeDisabled();
        expect(screen.getByText("Choose a time in the future.")).toBeInTheDocument();
    });

    it("does not flag the stored end time of an ended event as an error", () => {
        const endedAt = new Date(2026, 9, 16, 9, 0, 0).getTime() / 1000;
        renderSettings(baseEvent({state: CtfStates.ENDED, ends_at: endedAt}));

        expect(endsInput()).toHaveValue("10/16/2026 09:00 AM");
        expect(screen.queryByText("Choose a time in the future.")).not.toBeInTheDocument();
        expect(saveEnd()).toBeDisabled();
    });

    it("shows the stored end time, keeps Save disabled until it changes, and clears it with null", async () => {
        vi.mocked(ctfService.update).mockResolvedValue({} as never);
        const endsAt = new Date(2026, 9, 16, 18, 0, 0).getTime() / 1000;
        const {onUpdated} = renderSettings(baseEvent({ends_at: endsAt}));

        expect(endsInput()).toHaveValue("10/16/2026 06:00 PM");
        expect(saveEnd()).toBeDisabled();
        fireEvent.click(clearEnd());

        await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
        expect(ctfService.update).toHaveBeenCalledWith(CTF_ID, {ends_at: null});
    });

    it("follows a changed end time from the next poll", () => {
        const first = new Date(2026, 9, 16, 18, 0, 0).getTime() / 1000;
        const second = new Date(2026, 9, 16, 19, 0, 0).getTime() / 1000;
        const {rerender} = renderSettings(baseEvent({ends_at: first}));

        rerender(
            <ThemeProvider theme={darkTheme}>
                <ScoreboardSettings ctfId={CTF_ID} event={baseEvent({ends_at: second})} onUpdated={vi.fn()} />
            </ThemeProvider>
        );

        expect(endsInput()).toHaveValue("10/16/2026 07:00 PM");
    });

    it("disables every control while ARCHIVED", () => {
        renderSettings(baseEvent({state: CtfStates.ARCHIVED, ends_at: NOW_SECONDS + 3600}));

        expect(freezeSwitch()).toBeDisabled();
        expect(publicSwitch()).toBeDisabled();
        expect(endsInput()).toBeDisabled();
        expect(saveEnd()).toBeDisabled();
        expect(clearEnd()).toBeDisabled();
    });

    it("disables the controls while a request is in flight", async () => {
        let resolve: (value: never) => void = () => undefined;
        vi.mocked(ctfService.update).mockReturnValue(new Promise((r) => { resolve = r; }));
        const {onUpdated} = renderSettings(baseEvent());

        fireEvent.click(publicSwitch());

        await waitFor(() => expect(freezeSwitch()).toBeDisabled());
        expect(publicSwitch()).toBeDisabled();
        resolve({} as never);
        await waitFor(() => expect(freezeSwitch()).toBeEnabled());
        expect(onUpdated).toHaveBeenCalledTimes(1);
    });

    it("shows the API error and does not re-read state", async () => {
        vi.mocked(ctfService.update).mockRejectedValue(new HttpError(409, "CTF event is ARCHIVED and read-only"));
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        const {onUpdated} = renderSettings(baseEvent());

        fireEvent.click(freezeSwitch());

        expect(await screen.findByText("409: CTF event is ARCHIVED and read-only")).toBeInTheDocument();
        expect(onUpdated).not.toHaveBeenCalled();
        expect(freezeSwitch()).toBeEnabled();
    });
});
