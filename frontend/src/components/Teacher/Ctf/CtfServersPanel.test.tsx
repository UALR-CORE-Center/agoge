// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfServersAction, CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfServersPanel, {CtfServerSummary, SERVER_ACTION_RULES, WORKOUT_RUNNING} from "./CtfServersPanel";
import {WORKOUT_NOT_BUILT} from "./CtfTeamsPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {controlServers: vi.fn()},
}));

const CTF_ID = "eventevent";

const team = (id: string, name: string, workoutState: number | null): CtfTeamRow => ({
    workout_id: id, team_name: name, members: ["a@x.io"], workout_state: workoutState,
    workout_state_name: workoutState === WORKOUT_RUNNING ? "RUNNING" : null, arm_status: "pending",
});

const servers: CtfServerSummary[] = [
    {name: "web", os: "linux", machine_type: "e2-small", flag_count: 2},
    {name: "db", os: null, machine_type: null, flag_count: 1},
];

const mixedTeams = [
    team("aaaaaaaaaa", "Red", WORKOUT_RUNNING),
    team("bbbbbbbbbb", "Blue", WORKOUT_NOT_BUILT),
    team("cccccccccc", "Green", WORKOUT_NOT_BUILT),
];

// Mirrors CtfSetup.SERVER_ACTIONS in api/core/ctf/setup.py, written independently so drift fails here.
const EXPECTED_LEGAL: Record<CtfServersAction, (keyof typeof CtfStates)[]> = {
    build: ["DRAFT", "ARMED", "BROKEN", "RUNNING", "PAUSED"],
    start: ["DRAFT", "ARMED", "BROKEN", "RUNNING", "PAUSED"],
    stop: ["DRAFT", "ARMED", "BROKEN", "PAUSED", "ENDED"],
};
const LABELS: Record<CtfServersAction, string> = {build: "Build all", start: "Start all", stop: "Stop all"};

const renderPanel = (state: number, teams: CtfTeamRow[] = mixedTeams) => {
    const onChanged = vi.fn();
    render(<CtfServersPanel ctfId={CTF_ID} state={state} servers={servers} teams={teams} onChanged={onChanged} />);
    return onChanged;
};

const actionButton = (action: CtfServersAction) =>
    within(screen.getByRole("group", {name: "Server actions"})).getByRole("button", {name: LABELS[action]});

describe("CtfServersPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });
    afterEach(cleanup);

    it.each(Object.entries(CtfStates))("enables only the server actions legal in %s", (stateName, state) => {
        renderPanel(state);
        for (const action of Object.keys(LABELS) as CtfServersAction[]) {
            const legal = EXPECTED_LEGAL[action].includes(stateName as keyof typeof CtfStates);
            expect(SERVER_ACTION_RULES[action].legalStates.includes(state)).toBe(legal);
            if (legal) {
                expect(actionButton(action)).toBeEnabled();
            } else {
                expect(actionButton(action)).toBeDisabled();
            }
        }
    });

    it("disables every action without teams and says to add one", () => {
        renderPanel(CtfStates.DRAFT, []);

        for (const action of Object.keys(LABELS) as CtfServersAction[]) {
            expect(actionButton(action)).toBeDisabled();
        }
        expect(screen.getByText("Add teams before building servers.")).toBeInTheDocument();
    });

    it("summarises the lab's servers and the running and unbuilt team counts", () => {
        renderPanel(CtfStates.DRAFT);

        expect(screen.getByText("web · linux · e2-small · 2 flags")).toBeInTheDocument();
        expect(screen.getByText("db · 1 flag")).toBeInTheDocument();
        expect(screen.getByText("1 of 3 teams running, 2 not built.")).toBeInTheDocument();
        expect(screen.getByText(/Build and start every team before you arm/)).toBeInTheDocument();
        expect(screen.getByText("Blue: Not built")).toBeInTheDocument();
        expect(screen.getByText("Red: RUNNING")).toBeInTheDocument();
    });

    it("drops the arming warning and uses singular wording once every team is running", () => {
        renderPanel(CtfStates.DRAFT, [team("aaaaaaaaaa", "Red", WORKOUT_RUNNING)]);

        expect(screen.getByText("1 of 1 team running, 0 not built.")).toBeInTheDocument();
        expect(screen.queryByText(/Build and start every team before you arm/)).not.toBeInTheDocument();
    });

    it("says when the lab has no servers", () => {
        render(<CtfServersPanel ctfId={CTF_ID} state={CtfStates.DRAFT} servers={[]} teams={mixedTeams} onChanged={vi.fn()} />);
        expect(screen.getByText("No servers in this lab.")).toBeInTheDocument();
    });

    it("explains a disabled action through its tooltip", async () => {
        renderPanel(CtfStates.RUNNING);
        const stop = actionButton("stop");
        expect(stop).toBeDisabled();

        fireEvent.mouseOver(stop.parentElement as HTMLElement);
        expect(await screen.findByRole("tooltip")).toHaveTextContent("Not available in this state.");
    });

    it.each(["build", "start", "stop"] as CtfServersAction[])("confirms before sending %s, then reports the team count and refreshes", async (action) => {
        vi.mocked(ctfService.controlServers).mockResolvedValue({messages: 2});
        const onChanged = renderPanel(CtfStates.DRAFT);

        fireEvent.click(actionButton(action));
        const dialog = screen.getByRole("dialog", {name: LABELS[action]});
        expect(dialog).toHaveAccessibleDescription(SERVER_ACTION_RULES[action].message);
        expect(ctfService.controlServers).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole("button", {name: LABELS[action]}));

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
        expect(ctfService.controlServers).toHaveBeenCalledWith(CTF_ID, action);
        expect(await screen.findByText(`${LABELS[action]} sent for 2 teams.`)).toBeInTheDocument();
    });

    it("uses singular wording for one team and a nothing-to-do notice for zero", async () => {
        vi.mocked(ctfService.controlServers).mockResolvedValueOnce({messages: 1}).mockResolvedValueOnce({messages: 0});
        renderPanel(CtfStates.DRAFT);

        fireEvent.click(actionButton("build"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Build all"}));
        expect(await screen.findByText("Build all sent for 1 team.")).toBeInTheDocument();
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

        fireEvent.click(actionButton("start"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Start all"}));
        expect(await screen.findByText("Nothing to do: no team needed this.")).toBeInTheDocument();
    });

    it("sends nothing when the confirmation is cancelled", async () => {
        const onChanged = renderPanel(CtfStates.DRAFT);

        fireEvent.click(actionButton("build"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Cancel"}));

        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(ctfService.controlServers).not.toHaveBeenCalled();
        expect(onChanged).not.toHaveBeenCalled();
    });

    it("shows the API error and does not refresh when the request is refused", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.controlServers).mockRejectedValue(new HttpError(409, "Cannot build in ENDED."));
        const onChanged = renderPanel(CtfStates.DRAFT);

        fireEvent.click(actionButton("build"));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Build all"}));

        expect(await screen.findByText("409: Cannot build in ENDED.")).toBeInTheDocument();
        expect(onChanged).not.toHaveBeenCalled();
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });
});
