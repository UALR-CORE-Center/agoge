// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {act, cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfLogEntry, CtfStates, LOG_ACTIONS} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfEventLogPanel, {LOG_ACTION_LABELS, LOG_POLL_INTERVAL_MS, LOG_ROW_CAP, newestFirst} from "./CtfEventLogPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getLog: vi.fn()},
}));

const CTF_ID = "eventevent";
const NOW = 1_800_000_000;

const entry = (overrides: Partial<CtfLogEntry> = {}): CtfLogEntry => ({
    id: "log-1",
    ctf_id: CTF_ID,
    action: "CTF_START",
    actor: "gm@example.com",
    target: null,
    result: "OK",
    detail: null,
    created_at: NOW - 300,
    ...overrides,
});

// Deliberately not newest first, so the panel's own ordering is what the tests see.
const ENTRIES: CtfLogEntry[] = [
    entry({id: "log-1", action: "CTF_ARM", created_at: NOW - 900}),
    entry({id: "log-3", action: "HOST_RESET", target: "boardaaaaa", result: "DENIED", detail: {server: "web", mode: "rebuild"}, created_at: NOW - 60}),
    entry({id: "log-2", action: "CTF_START", result: "ERROR", created_at: NOW - 300}),
];

interface PanelProps {
    state?: number;
    active?: boolean;
}

const panel = ({state = CtfStates.RUNNING, active = true}: PanelProps = {}) => (
    <ThemeProvider theme={darkTheme}>
        <CtfEventLogPanel ctfId={CTF_ID} state={state} active={active} />
    </ThemeProvider>
);

// Let the awaited getLog promise settle and React flush the resulting state.
const flush = () => act(async () => {
    await Promise.resolve();
});

const actionOrder = () => screen.getAllByRole("row").slice(1)
    .map(r => within(r).getAllByRole("gridcell")[1].textContent);

const chooseAction = async (label: string) => {
    fireEvent.mouseDown(screen.getByRole("combobox", {name: "Action"}));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name: label}));
    await flush();
};

describe("CtfEventLogPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        vi.setSystemTime(NOW * 1000);
        vi.mocked(ctfService.getLog).mockResolvedValue(ENTRIES);
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("sorts entries newest first", () => {
        expect(newestFirst(ENTRIES).map(e => e.id)).toEqual(["log-3", "log-2", "log-1"]);
    });

    it("renders the log newest first with time, action, result, actor, target and detail", async () => {
        render(panel());
        await flush();

        expect(ctfService.getLog).toHaveBeenCalledWith(CTF_ID, undefined);
        expect(actionOrder()).toEqual(["Host reset", "Start", "Arm"]);
        const reset = screen.getByRole("gridcell", {name: "Host reset"}).closest('[role="row"]') as HTMLElement;
        const cells = within(reset).getAllByRole("gridcell").map(c => c.textContent);
        expect(cells).toEqual([
            new Date((NOW - 60) * 1000).toLocaleString(),
            "Host reset",
            "DENIED",
            "gm@example.com",
            "boardaaaaa",
            "server: web, mode: rebuild",
        ]);
    });

    it("offers every log action as a filter and re-reads with it at once", async () => {
        render(panel());
        await flush();

        fireEvent.mouseDown(screen.getByRole("combobox", {name: "Action"}));
        const options = within(screen.getByRole("listbox")).getAllByRole("option").map(o => o.textContent);
        expect(options).toEqual(["All actions", ...LOG_ACTIONS.map(a => LOG_ACTION_LABELS[a])]);
        fireEvent.keyDown(screen.getByRole("listbox"), {key: "Escape"});

        vi.mocked(ctfService.getLog).mockResolvedValue([ENTRIES[1]]);
        await chooseAction("Host reset");
        expect(ctfService.getLog).toHaveBeenLastCalledWith(CTF_ID, "HOST_RESET");
        expect(actionOrder()).toEqual(["Host reset"]);

        // The filter sticks across polls.
        await act(async () => {
            vi.advanceTimersByTime(LOG_POLL_INTERVAL_MS);
        });
        await flush();
        expect(ctfService.getLog).toHaveBeenLastCalledWith(CTF_ID, "HOST_RESET");

        vi.mocked(ctfService.getLog).mockResolvedValue([]);
        await chooseAction("Score adjustment");
        expect(screen.getByText("No entries for this action")).toBeInTheDocument();

        vi.mocked(ctfService.getLog).mockResolvedValue(ENTRIES);
        await chooseAction("All actions");
        expect(ctfService.getLog).toHaveBeenLastCalledWith(CTF_ID, undefined);
        expect(actionOrder()).toEqual(["Host reset", "Start", "Arm"]);
    });

    it("drops a response for a filter the user has already changed", async () => {
        let resolveStale: (rows: CtfLogEntry[]) => void = () => undefined;
        vi.mocked(ctfService.getLog).mockResolvedValueOnce(ENTRIES);
        render(panel());
        await flush();

        vi.mocked(ctfService.getLog)
            .mockImplementationOnce(() => new Promise(resolve => {
                resolveStale = resolve;
            }))
            .mockResolvedValueOnce([ENTRIES[0]]);
        await chooseAction("Host reset");
        await chooseAction("Arm");
        expect(actionOrder()).toEqual(["Arm"]);

        await act(async () => {
            resolveStale([ENTRIES[1]]);
        });
        await flush();
        expect(actionOrder()).toEqual(["Arm"]);
    });

    it("re-reads every 15 s while active and not while hidden", async () => {
        const {rerender} = render(panel({active: false}));
        await act(async () => {
            vi.advanceTimersByTime(LOG_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getLog).not.toHaveBeenCalled();

        rerender(panel());
        await flush();
        expect(ctfService.getLog).toHaveBeenCalledTimes(1);
        await act(async () => {
            vi.advanceTimersByTime(LOG_POLL_INTERVAL_MS - 1);
        });
        expect(ctfService.getLog).toHaveBeenCalledTimes(1);
        await act(async () => {
            vi.advanceTimersByTime(1);
        });
        await flush();
        expect(ctfService.getLog).toHaveBeenCalledTimes(2);
    });

    it("reads an archived event once and stops polling", async () => {
        render(panel({state: CtfStates.ARCHIVED}));
        await flush();
        expect(ctfService.getLog).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(LOG_POLL_INTERVAL_MS * 2);
        });
        expect(ctfService.getLog).toHaveBeenCalledTimes(1);
    });

    it("says when the log is capped at the API's row limit", async () => {
        const full = Array.from({length: LOG_ROW_CAP}, (_, i) => entry({id: `log-${i}`, created_at: NOW - i}));
        vi.mocked(ctfService.getLog).mockResolvedValue(full);
        render(panel());
        await flush();
        expect(screen.getByText(/Showing the newest 500 entries/)).toBeInTheDocument();
    });

    it("shows a load error and clears it on the next successful poll", async () => {
        vi.mocked(ctfService.getLog).mockRejectedValue(new HttpError(500, "boom"));
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        render(panel());
        await flush();
        expect(screen.getByText("500: boom")).toBeInTheDocument();

        vi.mocked(ctfService.getLog).mockResolvedValue(ENTRIES);
        await act(async () => {
            vi.advanceTimersByTime(LOG_POLL_INTERVAL_MS);
        });
        await flush();
        expect(screen.queryByText("500: boom")).not.toBeInTheDocument();
        expect(actionOrder()).toEqual(["Host reset", "Start", "Arm"]);
    });
});
