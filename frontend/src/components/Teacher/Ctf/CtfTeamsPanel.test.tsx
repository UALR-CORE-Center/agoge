// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfTeamsPanel, {
    MEMBER_EDIT_STATES,
    TEAM_EDIT_STATES,
    WORKOUT_NOT_BUILT,
    workoutStateLabel,
} from "./CtfTeamsPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {addTeam: vi.fn(), removeTeam: vi.fn(), setTeamMembers: vi.fn()},
}));

const CTF_ID = "eventevent";

const team = (id: string, name: string, overrides: Partial<CtfTeamRow> = {}): CtfTeamRow => ({
    workout_id: id,
    team_name: name,
    members: ["ana@x.io", "ben@x.io"],
    workout_state: WORKOUT_NOT_BUILT,
    workout_state_name: null,
    arm_status: "pending",
    ...overrides,
});

const teams = [
    team("redredredd", "Red"),
    team("bluebluebl", "Blue", {workout_state: 50, workout_state_name: "RUNNING"}),
];

const renderPanel = (props: Partial<React.ComponentProps<typeof CtfTeamsPanel>> = {}) => {
    const onChanged = vi.fn();
    render(
        <CtfTeamsPanel ctfId={CTF_ID} state={CtfStates.DRAFT} joinCode="JOIN42" teams={teams} loading={false}
                       onChanged={onChanged} {...props} />
    );
    return onChanged;
};

describe("workoutStateLabel", () => {
    it("labels missing, unbuilt and named workout states", () => {
        expect(workoutStateLabel(team("a", "A", {workout_state: null}))).toBe("Missing");
        expect(workoutStateLabel(team("a", "A", {workout_state: WORKOUT_NOT_BUILT}))).toBe("Not built");
        expect(workoutStateLabel(team("a", "A", {workout_state: 50, workout_state_name: "RUNNING"}))).toBe("RUNNING");
        expect(workoutStateLabel(team("a", "A", {workout_state: 12, workout_state_name: null}))).toBe("12");
    });
});

describe("CtfTeamsPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });
    afterEach(cleanup);

    it("only lets teams change in DRAFT, and members until the event ends", () => {
        expect(TEAM_EDIT_STATES).toEqual([CtfStates.DRAFT]);
        expect(MEMBER_EDIT_STATES).not.toContain(CtfStates.ENDED);
        expect(MEMBER_EDIT_STATES).not.toContain(CtfStates.ARCHIVED);
    });

    it("lists each team with members and server state", () => {
        renderPanel();
        expect(screen.getByRole("gridcell", {name: "Red"})).toBeInTheDocument();
        expect(screen.getByRole("gridcell", {name: "Blue"})).toBeInTheDocument();
        expect(screen.getByText("Not built")).toBeInTheDocument();
        expect(screen.getByText("RUNNING")).toBeInTheDocument();
        expect(screen.getAllByText("ana@x.io")).toHaveLength(2);
    });

    it("shows the join code and copies it", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {value: {writeText}, configurable: true});
        renderPanel();

        expect(screen.getByText("JOIN42")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Copy join code"}));
        await waitFor(() => expect(writeText).toHaveBeenCalledWith("JOIN42"));
    });

    it("hides the join code banner when the event has none", () => {
        renderPanel({joinCode: null});
        expect(screen.queryByRole("button", {name: "Copy join code"})).not.toBeInTheDocument();
    });

    it("adds a team with a trimmed name and de-duplicated lowercase emails, then refreshes", async () => {
        vi.mocked(ctfService.addTeam).mockResolvedValue(team("newnewnewn", "Green"));
        const onChanged = renderPanel();

        fireEvent.click(screen.getByRole("button", {name: "Add team"}));
        const dialog = screen.getByRole("dialog", {name: "Add team"});
        expect(within(dialog).getByRole("button", {name: "Save"})).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText("Team name"), {target: {value: "  Green  "}});
        fireEvent.change(within(dialog).getByLabelText("Member emails"), {target: {value: "Cy@x.io, cy@x.io\ndee@x.io"}});
        expect(within(dialog).getByText(/2 members/)).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole("button", {name: "Save"}));

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
        expect(ctfService.addTeam).toHaveBeenCalledWith(CTF_ID, {team_name: "Green", members: ["cy@x.io", "dee@x.io"]});
        await waitFor(() => expect(screen.queryByRole("dialog", {name: "Add team"})).not.toBeInTheDocument());
    });

    it("blocks saving a team with an invalid email and names the offender", () => {
        renderPanel();
        fireEvent.click(screen.getByRole("button", {name: "Add team"}));
        const dialog = screen.getByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText("Team name"), {target: {value: "Green"}});
        fireEvent.change(within(dialog).getByLabelText("Member emails"), {target: {value: "ok@x.io, bogus"}});

        expect(within(dialog).getByText("Not email addresses: bogus")).toBeInTheDocument();
        expect(within(dialog).getByRole("button", {name: "Save"})).toBeDisabled();
    });

    it("blocks saving a team over the member limit", () => {
        renderPanel();
        fireEvent.click(screen.getByRole("button", {name: "Add team"}));
        const dialog = screen.getByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText("Team name"), {target: {value: "Big"}});
        const emails = Array.from({length: 51}, (_v, i) => `u${i}@x.io`).join("\n");
        fireEvent.change(within(dialog).getByLabelText("Member emails"), {target: {value: emails}});

        expect(within(dialog).getByText("A team can have at most 50 members.")).toBeInTheDocument();
        expect(within(dialog).getByRole("button", {name: "Save"})).toBeDisabled();
    });

    it("keeps the add dialog open and shows the API error when the add fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.addTeam).mockRejectedValue(new HttpError(409, "Team name already used."));
        const onChanged = renderPanel();

        fireEvent.click(screen.getByRole("button", {name: "Add team"}));
        const dialog = screen.getByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText("Team name"), {target: {value: "Red"}});
        fireEvent.change(within(dialog).getByLabelText("Member emails"), {target: {value: "a@x.io"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Save"}));

        expect(await within(dialog).findByRole("alert")).toHaveTextContent("409: Team name already used.");
        expect(onChanged).not.toHaveBeenCalled();
    });

    it("edits a team's members, prefilled, without asking for a name", async () => {
        vi.mocked(ctfService.setTeamMembers).mockResolvedValue(team("redredredd", "Red"));
        const onChanged = renderPanel();

        fireEvent.click(screen.getByRole("button", {name: "Edit members of Red"}));
        const dialog = screen.getByRole("dialog", {name: "Members of Red"});
        expect(within(dialog).queryByLabelText("Team name")).not.toBeInTheDocument();
        const field = within(dialog).getByLabelText("Member emails") as HTMLTextAreaElement;
        expect(field.value).toBe("ana@x.io\nben@x.io");
        fireEvent.change(field, {target: {value: "ana@x.io\ncy@x.io"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Save"}));

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
        expect(ctfService.setTeamMembers).toHaveBeenCalledWith(CTF_ID, "redredredd", ["ana@x.io", "cy@x.io"]);
    });

    it("lets members be edited after arming but disables adding, importing and removing", () => {
        renderPanel({state: CtfStates.RUNNING});
        expect(screen.getByRole("button", {name: "Add team"})).toBeDisabled();
        expect(screen.getByRole("button", {name: "Import CSV"})).toBeDisabled();
        expect(screen.getByRole("button", {name: "Edit members of Red"})).toBeEnabled();
        expect(screen.getByRole("button", {name: "Remove Red"})).toBeDisabled();
    });

    it("locks member editing once the event has ended", () => {
        renderPanel({state: CtfStates.ENDED});
        expect(screen.getByRole("button", {name: "Edit members of Red"})).toBeDisabled();
    });

    it("allows Remove only for a DRAFT team that was never built, and explains why otherwise", async () => {
        renderPanel();
        expect(screen.getByRole("button", {name: "Remove Red"})).toBeEnabled();
        const built = screen.getByRole("button", {name: "Remove Blue"});
        expect(built).toBeDisabled();

        fireEvent.mouseOver(built.parentElement as HTMLElement);
        expect(await screen.findByRole("tooltip")).toHaveTextContent("only an unbuilt team can be removed");
    });

    it("leaves a team whose workout record is missing removable, so a dangling team can be cleaned up", () => {
        renderPanel({teams: [team("gonegonego", "Gone", {workout_state: null})]});
        expect(screen.getByRole("button", {name: "Remove Gone"})).toBeEnabled();
    });

    it("explains that teams can only be removed before arming outside DRAFT", async () => {
        renderPanel({state: CtfStates.ARMED});
        fireEvent.mouseOver(screen.getByRole("button", {name: "Remove Red"}).parentElement as HTMLElement);
        expect(await screen.findByRole("tooltip")).toHaveTextContent("Teams can only be removed before arming.");
    });

    it("removes a team after confirmation and refreshes", async () => {
        vi.mocked(ctfService.removeTeam).mockResolvedValue({build_id: "redredredd", exists: null});
        const onChanged = renderPanel();

        fireEvent.click(screen.getByRole("button", {name: "Remove Red"}));
        const dialog = screen.getByRole("dialog", {name: "Remove team"});
        expect(ctfService.removeTeam).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole("button", {name: "Remove"}));

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
        expect(ctfService.removeTeam).toHaveBeenCalledWith(CTF_ID, "redredredd");
    });

    it("shows the error and does not refresh when removal fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.removeTeam).mockRejectedValue(new HttpError(409, "Team is built."));
        const onChanged = renderPanel();

        fireEvent.click(screen.getByRole("button", {name: "Remove Red"}));
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", {name: "Remove"}));

        expect(await screen.findByText("409: Team is built.")).toBeInTheDocument();
        expect(onChanged).not.toHaveBeenCalled();
    });

    describe("CSV import", () => {
        const openImport = () => {
            fireEvent.click(screen.getByRole("button", {name: "Import CSV"}));
            return screen.getByRole("dialog", {name: "Import teams"});
        };
        const enterRoster = (dialog: HTMLElement, text: string) =>
            fireEvent.change(within(dialog).getByLabelText("Roster"), {target: {value: text}});

        it("previews the parsed teams and calls addTeam once per team", async () => {
            vi.mocked(ctfService.addTeam).mockResolvedValue(team("x", "x"));
            const onChanged = renderPanel();
            const dialog = openImport();
            expect(within(dialog).getByRole("button", {name: "Import"})).toBeDisabled();

            enterRoster(dialog, "team,email\nGreen,a@x.io\nGreen,b@x.io\nGold,c@x.io");
            expect(within(dialog).getByText(/2 teams, 3 members/)).toBeInTheDocument();
            fireEvent.click(within(dialog).getByRole("button", {name: "Import"}));

            await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
            expect(ctfService.addTeam).toHaveBeenCalledTimes(2);
            expect(ctfService.addTeam).toHaveBeenNthCalledWith(1, CTF_ID, {team_name: "Green", members: ["a@x.io", "b@x.io"]});
            expect(ctfService.addTeam).toHaveBeenNthCalledWith(2, CTF_ID, {team_name: "Gold", members: ["c@x.io"]});
            await waitFor(() => expect(screen.queryByRole("dialog", {name: "Import teams"})).not.toBeInTheDocument());
        });

        it("blocks import and lists parse errors", () => {
            renderPanel();
            const dialog = openImport();
            enterRoster(dialog, "Green,a@x.io\nbroken");

            expect(within(dialog).getByText('Line 2: expected "team,email"')).toBeInTheDocument();
            expect(within(dialog).getByRole("button", {name: "Import"})).toBeDisabled();
        });

        it("reports each failed team, still imports the rest, and stays open", async () => {
            vi.spyOn(console, "error").mockImplementation(() => {});
            vi.mocked(ctfService.addTeam)
                .mockRejectedValueOnce(new HttpError(409, "Duplicate team."))
                .mockResolvedValueOnce(team("x", "x"));
            const onChanged = renderPanel();
            const dialog = openImport();
            enterRoster(dialog, "Green,a@x.io\nGold,b@x.io");
            fireEvent.click(within(dialog).getByRole("button", {name: "Import"}));

            expect(await within(dialog).findByText("Green: 409: Duplicate team.")).toBeInTheDocument();
            expect(ctfService.addTeam).toHaveBeenCalledTimes(2);
            expect(onChanged).toHaveBeenCalledTimes(1);
            expect(screen.getByRole("dialog", {name: "Import teams"})).toBeInTheDocument();
        });
    });
});
