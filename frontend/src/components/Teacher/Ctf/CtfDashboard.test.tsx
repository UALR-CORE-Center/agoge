// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {act, cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import React from "react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_ERROR, URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {CtfStateResponse, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfDashboard, {DASHBOARD_TABS, defaultTabFor, STATE_POLL_INTERVAL_MS} from "./CtfDashboard";
import {FLAGS_POLL_INTERVAL_MS} from "./CtfFlagsPanel";
import {SCOREBOARD_POLL_INTERVAL_MS} from "./CtfScoreboardPanel";
import {formatDuration, remainingSeconds} from "./ctfTime";

// The real Setup panel pulls in unit.service and so Firebase; its own behavior is covered elsewhere.
vi.mock("./CtfSetupPanel", () => ({
    default: ({ctfId, state, active}: {ctfId: string; state: number; active: boolean}) => (
        <div data-testid="setup-panel" data-active={String(active)}>setup for {ctfId} in {state}</div>
    ),
}));

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getFlags: vi.fn(), getHosts: vi.fn(), getLog: vi.fn(), getScoreboard: vi.fn(), getState: vi.fn(), getSubmissions: vi.fn(), processAction: vi.fn()},
}));

const NOW = 1_800_000_000;

const stateResponse = (overrides: Partial<CtfStateResponse> = {}): CtfStateResponse => ({
    id: "eventevent",
    state: CtfStates.RUNNING,
    state_name: "RUNNING",
    state_timestamp: "2027-03-01T00:00:00Z",
    starts_at: NOW - 600,
    ends_at: NOW + 3661,
    paused_at: null,
    accumulated_pause_seconds: 0,
    scoreboard_frozen_at: null,
    public_scoreboard_enabled: false,
    budget_exceeded: false,
    boards: [],
    ...overrides,
});

const renderDashboard = () => render(
    <ThemeProvider theme={darkTheme}>
        <MemoryRouter initialEntries={[`${URL_TEACHER_CTF_EVENT}/eventevent`]}>
            <Routes>
                <Route path={`${URL_TEACHER_CTF_EVENT}/:ctf_id`} element={<CtfDashboard />} />
                <Route path={URL_ERROR} element={<div>error page</div>} />
            </Routes>
        </MemoryRouter>
    </ThemeProvider>
);

// Let the awaited getState promise settle and React flush the resulting state.
const flush = () => act(async () => {
    await Promise.resolve();
});

describe("remainingSeconds", () => {
    it("is null for an open-ended event and 0 once ended", () => {
        expect(remainingSeconds({state: CtfStates.RUNNING, ends_at: null, paused_at: null}, NOW)).toBeNull();
        expect(remainingSeconds({state: CtfStates.ENDED, ends_at: NOW + 100, paused_at: null}, NOW)).toBe(0);
    });

    it("holds the clock at paused_at while paused and never goes negative", () => {
        expect(remainingSeconds({state: CtfStates.PAUSED, ends_at: NOW + 100, paused_at: NOW - 50}, NOW)).toBe(150);
        expect(remainingSeconds({state: CtfStates.RUNNING, ends_at: NOW - 5, paused_at: null}, NOW)).toBe(0);
        expect(remainingSeconds({state: CtfStates.RUNNING, ends_at: NOW + 0.2, paused_at: null}, NOW)).toBe(1);
    });

    it("formats as HH:MM:SS", () => {
        expect(formatDuration(3661)).toBe("01:01:01");
        expect(formatDuration(0)).toBe("00:00:00");
    });
});

describe("CtfDashboard", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        vi.setSystemTime(NOW * 1000);
    });
    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("shows the state chip, remaining time and every panel tab", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        renderDashboard();
        await flush();

        expect(ctfService.getState).toHaveBeenCalledWith("eventevent");
        expect(screen.getByText("Running")).toBeInTheDocument();
        expect(screen.getByText("01:01:01")).toBeInTheDocument();
        const tabs = screen.getAllByRole("tab").map(tab => tab.textContent);
        expect(tabs).toEqual([...DASHBOARD_TABS]);
        expect(screen.queryByText(/budget has been exceeded/)).not.toBeInTheDocument();

        expect(tabs[0]).toBe("Setup");
        fireEvent.click(screen.getByRole("tab", {name: "Hosts"}));
        expect(screen.getByRole("tab", {name: "Hosts"})).toHaveAttribute("aria-selected", "true");
        expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", screen.getByRole("tab", {name: "Hosts"}).id);
    });

    it("picks Setup for a DRAFT event and Flags for every other state", () => {
        expect(DASHBOARD_TABS[defaultTabFor(CtfStates.DRAFT)]).toBe("Setup");
        for (const state of Object.values(CtfStates).filter((value) => value !== CtfStates.DRAFT)) {
            expect(DASHBOARD_TABS[defaultTabFor(state)]).toBe("Flags");
        }
    });

    it("opens a DRAFT event on the Setup tab and mounts the setup panel as active", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.DRAFT, state_name: "DRAFT", starts_at: null, ends_at: null}));
        renderDashboard();
        await flush();

        expect(screen.getByRole("tab", {name: "Setup"})).toHaveAttribute("aria-selected", "true");
        expect(screen.getByTestId("setup-panel")).toHaveAttribute("data-active", "true");
        expect(screen.getByTestId("setup-panel")).toHaveTextContent(`setup for eventevent in ${CtfStates.DRAFT}`);
        expect(ctfService.getFlags).not.toHaveBeenCalled();
    });

    it("keeps the tab the user chose when a later poll reports a new state", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.DRAFT, state_name: "DRAFT"}));
        vi.mocked(ctfService.getHosts).mockResolvedValue([]);
        renderDashboard();
        await flush();
        fireEvent.click(screen.getByRole("tab", {name: "Hosts"}));

        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS);
        });
        await flush();
        expect(screen.getByRole("tab", {name: "Hosts"})).toHaveAttribute("aria-selected", "true");
    });

    it("blocks Arm until the event has a team, then allows it", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.DRAFT, state_name: "DRAFT", boards: []}));
        renderDashboard();
        await flush();
        const group = () => within(screen.getByRole("group", {name: "Event actions"}));
        expect(group().getByRole("button", {name: "Arm"})).toBeDisabled();

        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({
            state: CtfStates.DRAFT, state_name: "DRAFT",
            boards: [{workout_id: "boardaaaaa", team_name: "Red", arm_status: "pending", arm_error: null, plant_failed_count: 0, plant_stale_count: 0}],
        }));
        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS);
        });
        await flush();
        expect(group().getByRole("button", {name: "Arm"})).toBeEnabled();
    });

    it("mounts the Flags panel in the Flags tab and polls flags only while that tab is shown", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        vi.mocked(ctfService.getFlags).mockResolvedValue([]);
        renderDashboard();
        await flush();

        const flagsTab = screen.getByRole("tab", {name: "Flags"});
        expect(within(screen.getByRole("tabpanel")).getByText("No flags in this event")).toBeInTheDocument();
        expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", flagsTab.id);
        expect(ctfService.getFlags).toHaveBeenCalledWith("eventevent");
        const calls = vi.mocked(ctfService.getFlags).mock.calls.length;

        fireEvent.click(screen.getByRole("tab", {name: "Hosts"}));
        await act(async () => {
            vi.advanceTimersByTime(FLAGS_POLL_INTERVAL_MS * 2);
        });
        await flush();
        expect(ctfService.getFlags).toHaveBeenCalledTimes(calls);
    });

    it("mounts the Hosts panel in the Hosts tab and reads hosts only once that tab is shown", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        vi.mocked(ctfService.getFlags).mockResolvedValue([]);
        vi.mocked(ctfService.getHosts).mockResolvedValue([]);
        renderDashboard();
        await flush();
        expect(ctfService.getHosts).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("tab", {name: "Hosts"}));
        await flush();
        expect(ctfService.getHosts).toHaveBeenCalledWith("eventevent");
        expect(within(screen.getByRole("tabpanel")).getByText("No hosts in this event")).toBeInTheDocument();
    });

    it("mounts the Scoreboard panel, polls it every 30 s and shows the freeze from the state poll", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        vi.mocked(ctfService.getFlags).mockResolvedValue([]);
        vi.mocked(ctfService.getScoreboard).mockResolvedValue([]);
        renderDashboard();
        await flush();
        expect(ctfService.getScoreboard).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("tab", {name: "Scoreboard"}));
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);
        expect(within(screen.getByRole("tabpanel")).getByText("No teams in this event")).toBeInTheDocument();
        expect(within(screen.getByRole("tabpanel")).queryByText(/has been frozen/)).not.toBeInTheDocument();

        // The next 10 s state poll reports a freeze; the banner follows it before the scoreboard re-reads.
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({scoreboard_frozen_at: NOW - 60}));
        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS);
        });
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(1);
        expect(within(screen.getByRole("tabpanel")).getByText(/has been frozen/)).toBeInTheDocument();

        await act(async () => {
            vi.advanceTimersByTime(SCOREBOARD_POLL_INTERVAL_MS - STATE_POLL_INTERVAL_MS);
        });
        await flush();
        expect(ctfService.getScoreboard).toHaveBeenCalledTimes(2);
    });

    it("mounts the Event Log panel and reads the log only once its tab is opened", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        vi.mocked(ctfService.getFlags).mockResolvedValue([]);
        vi.mocked(ctfService.getLog).mockResolvedValue([]);
        renderDashboard();
        await flush();
        expect(ctfService.getLog).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("tab", {name: "Event Log"}));
        await flush();
        expect(ctfService.getLog).toHaveBeenCalledWith("eventevent", undefined);
        expect(within(screen.getByRole("tabpanel")).getByText("No actions logged yet")).toBeInTheDocument();
    });

    it("mounts the Submissions panel with team names from the state poll", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({
            boards: [
                {workout_id: "boardaaaaa", team_name: "Red", arm_status: "armed", arm_error: null, plant_failed_count: 0, plant_stale_count: 0},
                {workout_id: "boardbbbbb", team_name: "Blue", arm_status: "armed", arm_error: null, plant_failed_count: 0, plant_stale_count: 0},
            ],
        }));
        vi.mocked(ctfService.getFlags).mockResolvedValue([]);
        vi.mocked(ctfService.getSubmissions).mockResolvedValue([{
            id: "sub-1", ctf_id: "eventevent", workout_id: "boardaaaaa", flag_id: "web-1", submitted_digest: "d",
            verdict: "cross_submission", matched_workout_id: "boardbbbbb", points_awarded: 0,
            submitted_at: NOW - 30, origin_ip: null,
        }]);
        renderDashboard();
        await flush();
        expect(ctfService.getSubmissions).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("tab", {name: "Submissions"}));
        await flush();
        expect(ctfService.getSubmissions).toHaveBeenCalledWith("eventevent", undefined);
        const panel = within(screen.getByRole("tabpanel"));
        expect(panel.getByRole("gridcell", {name: "Red"})).toBeInTheDocument();
        expect(panel.getByRole("gridcell", {name: "Blue"})).toBeInTheDocument();
    });

    it("counts down between polls and re-reads state every 10 s", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        renderDashboard();
        await flush();

        await act(async () => {
            vi.advanceTimersByTime(1000);
        });
        expect(screen.getByText("01:01:00")).toBeInTheDocument();
        expect(ctfService.getState).toHaveBeenCalledTimes(1);

        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.PAUSED, state_name: "PAUSED", paused_at: NOW}));
        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS - 1000);
        });
        await flush();
        expect(ctfService.getState).toHaveBeenCalledTimes(2);
        expect(screen.getByText("Paused")).toBeInTheDocument();
        // The paused clock is held at paused_at, not the wall clock.
        expect(screen.getByText("01:01:01 (paused)")).toBeInTheDocument();
    });

    it("re-reads state right after an Event Control action instead of waiting for the next poll", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        vi.mocked(ctfService.processAction).mockResolvedValue({} as never);
        renderDashboard();
        await flush();
        expect(screen.getByRole("button", {name: "Start"})).toBeDisabled();

        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.PAUSED, state_name: "PAUSED", paused_at: NOW}));
        fireEvent.click(screen.getByRole("button", {name: "Pause"}));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Pause"}));
        await flush();
        await flush();

        expect(ctfService.processAction).toHaveBeenCalledWith("eventevent", {action: "pause"});
        expect(ctfService.getState).toHaveBeenCalledTimes(2);
        expect(screen.getByText("Paused")).toBeInTheDocument();
        // Let the dialog's exit transition finish; until then the page behind it is aria-hidden.
        await act(async () => {
            vi.advanceTimersByTime(500);
        });
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        expect(within(screen.getByRole("group", {name: "Event actions"})).getByRole("button", {name: "Resume"})).toBeEnabled();
    });

    it("shows a banner when the project budget is exceeded", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({budget_exceeded: true, ends_at: null}));
        renderDashboard();
        await flush();

        expect(screen.getByRole("alert")).toHaveTextContent(/budget has been exceeded/);
        expect(screen.getByText("No end time")).toBeInTheDocument();
    });

    it("keeps polling and shows the error when a state read fails", async () => {
        vi.mocked(ctfService.getState).mockRejectedValue(new HttpError(500, "boom"));
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        renderDashboard();
        await flush();

        expect(screen.getByText("500: boom")).toBeInTheDocument();

        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse());
        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS);
        });
        await flush();
        expect(screen.queryByText("500: boom")).not.toBeInTheDocument();
        expect(screen.getByText("Running")).toBeInTheDocument();
    });

    it("sends a missing event to the error page", async () => {
        vi.mocked(ctfService.getState).mockRejectedValue(new HttpError(404, "Not found"));
        renderDashboard();
        await flush();

        expect(screen.getByText("error page")).toBeInTheDocument();
    });

    it("stops polling once the event is archived", async () => {
        vi.mocked(ctfService.getState).mockResolvedValue(stateResponse({state: CtfStates.ARCHIVED, state_name: "ARCHIVED"}));
        renderDashboard();
        await flush();

        await act(async () => {
            vi.advanceTimersByTime(STATE_POLL_INTERVAL_MS * 3);
        });
        expect(ctfService.getState).toHaveBeenCalledTimes(1);
    });
});
