// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {act, cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfEvent, CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {unitService} from "../../../services/Unit/unit.service";
import HttpError from "../../Common/Errors/HttpError";
import {CtfServerSummary} from "./CtfServersPanel";
import CtfSetupPanel, {TEAMS_POLL_INTERVAL_MS} from "./CtfSetupPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {get: vi.fn(), getTeams: vi.fn()},
}));
// The real unit service imports Firebase, which cannot initialise under test.
vi.mock("../../../services/Unit/unit.service", () => ({
    unitService: {get: vi.fn()},
}));
// The three children have their own tests; here they only expose what the panel hands them.
vi.mock("./CtfTeamsPanel", () => ({
    default: (props: {ctfId: string; state: number; joinCode: string | null; teams: CtfTeamRow[]; loading: boolean; onChanged: () => void}) => (
        <div data-testid="teams" data-join={props.joinCode ?? ""} data-state={props.state} data-loading={String(props.loading)}>
            teams: {props.teams.map((t) => t.team_name).join(",")}
            <button onClick={props.onChanged}>teams changed</button>
        </div>
    ),
}));
vi.mock("./CtfSpecEditor", () => ({
    default: (props: {spec: {flags: unknown[]}; serverNames: string[]; onSaved: () => void}) => (
        <div data-testid="spec" data-servers={props.serverNames.join(",")}>
            flags: {props.spec.flags.length}
            <button onClick={props.onSaved}>spec saved</button>
        </div>
    ),
}));
vi.mock("./CtfServersPanel", () => ({
    default: (props: {servers: CtfServerSummary[]}) => (
        <div data-testid="servers">{JSON.stringify(props.servers)}</div>
    ),
}));

const CTF_ID = "eventevent";

const makeEvent = (overrides: Partial<CtfEvent> = {}): CtfEvent => ({
    id: CTF_ID,
    unit_id: "unitunitab",
    instructor_id: [],
    spec: {
        name: "Spring CTF", description: null, rules_url: null,
        flags: [
            {id: "a1", server: "web", slot: 1, category: null, location_type: "file", path: "/a", operating_system: "linux",
                access_level: "user", points: 10, decoy: false, hint: null, hint_cost: 0, unlocks_after: null, file_mode: null, file_owner: null},
            {id: "a2", server: "web", slot: 2, category: null, location_type: "file", path: "/b", operating_system: "linux",
                access_level: "user", points: 10, decoy: false, hint: null, hint_cost: 0, unlocks_after: null, file_mode: null, file_owner: null},
            {id: "b1", server: "ghost", slot: 1, category: null, location_type: "file", path: "/c", operating_system: "linux",
                access_level: "user", points: 10, decoy: false, hint: null, hint_cost: 0, unlocks_after: null, file_mode: null, file_owner: null},
        ],
        scoring: {flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false},
    },
    seed_version: 1,
    creation_timestamp: 1,
    starts_at: null,
    ends_at: null,
    paused_at: null,
    accumulated_pause_seconds: 0,
    scoreboard_frozen_at: null,
    public_scoreboard_enabled: false,
    board_ids: [],
    join_code: "JOIN42",
    boards_pending: 0,
    state: CtfStates.DRAFT,
    state_timestamp: "t",
    ...overrides,
});

const teamRow = (name: string): CtfTeamRow => ({
    workout_id: `${name}wwwwww`, team_name: name, members: [], workout_state: -1, workout_state_name: null, arm_status: "pending",
});

const flush = () => act(async () => {
    await Promise.resolve();
});

const renderPanel = (props: Partial<React.ComponentProps<typeof CtfSetupPanel>> = {}) => {
    const onTeamsChanged = vi.fn();
    render(<CtfSetupPanel ctfId={CTF_ID} state={CtfStates.DRAFT} active onTeamsChanged={onTeamsChanged} {...props} />);
    return onTeamsChanged;
};

describe("CtfSetupPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.useFakeTimers();
        vi.mocked(ctfService.get).mockResolvedValue(makeEvent());
        vi.mocked(ctfService.getTeams).mockResolvedValue([teamRow("Red")]);
        vi.mocked(unitService.get).mockResolvedValue({
            servers: [
                {name: "web", machine_type: "e2-small", details: {os: "linux"}},
                {name: "db"},
                {machine_type: "no-name"},
            ],
        } as never);
    });
    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("shows a skeleton until the event loads, then composes the three sections", async () => {
        renderPanel();
        expect(screen.queryByTestId("teams")).not.toBeInTheDocument();
        await flush();
        await flush();

        expect(ctfService.get).toHaveBeenCalledWith(CTF_ID);
        expect(unitService.get).toHaveBeenCalledWith("unitunitab");
        expect(screen.getByRole("heading", {name: "1. Teams"})).toBeInTheDocument();
        expect(screen.getByRole("heading", {name: "2. Flags"})).toBeInTheDocument();
        expect(screen.getByRole("heading", {name: "3. Servers"})).toBeInTheDocument();
        expect(screen.getByTestId("teams")).toHaveAttribute("data-join", "JOIN42");
        expect(screen.getByTestId("teams")).toHaveTextContent("teams: Red");
        expect(screen.getByTestId("spec")).toHaveTextContent("flags: 3");
    });

    it("builds the server summaries from the unit, counting each server's flags and skipping unnamed ones", async () => {
        renderPanel();
        await flush();
        await flush();

        expect(JSON.parse(screen.getByTestId("servers").textContent ?? "")).toEqual([
            {name: "web", os: "linux", machine_type: "e2-small", flag_count: 2},
            {name: "db", os: null, machine_type: null, flag_count: 0},
        ]);
        expect(screen.getByTestId("spec")).toHaveAttribute("data-servers", "web,db");
    });

    it("falls back to the flags' servers for the editor when the unit read fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(unitService.get).mockRejectedValue(new Error("nope"));
        renderPanel();
        await flush();
        await flush();

        expect(screen.getByTestId("spec")).toHaveAttribute("data-servers", "web,ghost");
        expect(JSON.parse(screen.getByTestId("servers").textContent ?? "")).toEqual([]);
    });

    it("shows the error instead of the sections when the event cannot be read", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.get).mockRejectedValue(new HttpError(404, "No such event."));
        renderPanel();
        await flush();

        expect(screen.getByRole("alert")).toHaveTextContent("404: No such event.");
        expect(screen.queryByTestId("teams")).not.toBeInTheDocument();
        expect(unitService.get).not.toHaveBeenCalled();
    });

    it("shows the setup hint only in DRAFT", async () => {
        const {unmount} = render(<CtfSetupPanel ctfId={CTF_ID} state={CtfStates.DRAFT} active onTeamsChanged={vi.fn()} />);
        await flush();
        await flush();
        expect(screen.getByText(/Set up the event before arming/)).toBeInTheDocument();
        unmount();

        render(<CtfSetupPanel ctfId={CTF_ID} state={CtfStates.RUNNING} active onTeamsChanged={vi.fn()} />);
        await flush();
        await flush();
        expect(screen.queryByText(/Set up the event before arming/)).not.toBeInTheDocument();
    });

    it("polls teams every 15 s while active and never faster than 10 s", async () => {
        expect(TEAMS_POLL_INTERVAL_MS).toBeGreaterThanOrEqual(10000);
        renderPanel();
        await flush();
        const initial = vi.mocked(ctfService.getTeams).mock.calls.length;
        expect(initial).toBeGreaterThanOrEqual(1);

        await act(async () => {
            vi.advanceTimersByTime(TEAMS_POLL_INTERVAL_MS - 1);
        });
        expect(ctfService.getTeams).toHaveBeenCalledTimes(initial);
        await act(async () => {
            vi.advanceTimersByTime(1);
        });
        await flush();
        expect(ctfService.getTeams).toHaveBeenCalledTimes(initial + 1);
    });

    it("does not poll teams while the Setup tab is hidden", async () => {
        renderPanel({active: false});
        await flush();
        await act(async () => {
            vi.advanceTimersByTime(TEAMS_POLL_INTERVAL_MS * 3);
        });
        expect(ctfService.getTeams).not.toHaveBeenCalled();
    });

    it("reads teams once, without polling, for an archived event", async () => {
        renderPanel({state: CtfStates.ARCHIVED});
        await flush();
        await act(async () => {
            vi.advanceTimersByTime(TEAMS_POLL_INTERVAL_MS * 3);
        });
        await flush();
        expect(ctfService.getTeams).toHaveBeenCalledTimes(1);
    });

    it("re-reads teams and tells the dashboard after a roster change", async () => {
        const onTeamsChanged = renderPanel();
        await flush();
        await flush();
        const before = vi.mocked(ctfService.getTeams).mock.calls.length;

        vi.mocked(ctfService.getTeams).mockResolvedValue([teamRow("Red"), teamRow("Blue")]);
        fireEvent.click(screen.getByRole("button", {name: "teams changed"}));
        await flush();
        await flush();

        expect(ctfService.getTeams).toHaveBeenCalledTimes(before + 1);
        expect(onTeamsChanged).toHaveBeenCalledTimes(1);
        expect(screen.getByTestId("teams")).toHaveTextContent("teams: Red,Blue");
    });

    it("re-reads the event after the flags are saved", async () => {
        renderPanel();
        await flush();
        await flush();
        expect(ctfService.get).toHaveBeenCalledTimes(1);

        vi.mocked(ctfService.get).mockResolvedValue(makeEvent({spec: {...makeEvent().spec, flags: []}}));
        fireEvent.click(screen.getByRole("button", {name: "spec saved"}));
        await flush();
        await flush();

        expect(ctfService.get).toHaveBeenCalledTimes(2);
        expect(screen.getByTestId("spec")).toHaveTextContent("flags: 0");
    });

    it("shows a dismissible error when teams cannot be read", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.getTeams).mockRejectedValue(new HttpError(500, "boom"));
        renderPanel();
        await flush();
        await flush();

        expect(screen.getByText("500: boom")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Close"}));
        expect(screen.queryByText("500: boom")).not.toBeInTheDocument();
        expect(screen.getByTestId("teams")).toHaveAttribute("data-loading", "false");
    });
});
