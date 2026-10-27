// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfEvent, CtfFlagSpec, CtfSpec, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfSpecEditor, {blankFlag, flagProblems, SPEC_EDIT_STATES, STANDARD_CATEGORIES} from "./CtfSpecEditor";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {updateSpec: vi.fn()},
}));

const CTF_ID = "eventevent";

const flag = (overrides: Partial<CtfFlagSpec> = {}): CtfFlagSpec => ({
    ...blankFlag("web"), id: "web-user", path: "/home/user/flag.txt", ...overrides,
});

const makeSpec = (flags: CtfFlagSpec[] = [flag(), flag({id: "web-root", slot: 2, points: 200, unlocks_after: ["web-user"]})]): CtfSpec => ({
    name: "Spring CTF",
    description: null,
    rules_url: null,
    flags,
    scoring: {flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false},
});

describe("blankFlag", () => {
    it("starts as a 100 point, slot 1 Linux file flag on the given server", () => {
        expect(blankFlag("web")).toMatchObject({
            id: "", server: "web", slot: 1, location_type: "file", operating_system: "linux",
            points: 100, decoy: false, unlocks_after: null, hint: null, hint_cost: 0,
        });
    });
});

describe("flagProblems", () => {
    it("accepts a valid flag", () => {
        expect(flagProblems(flag(), [])).toEqual([]);
    });

    it.each(["", "a", "-bad", "Upper", "has space", "x".repeat(33)])("rejects the id %j", (id) => {
        expect(flagProblems(flag({id}), [])[0]).toMatch(/^Id: 2-32 lowercase/);
    });

    it.each(["ab", "a1", "web-1", "x".repeat(32)])("accepts the id %j", (id) => {
        expect(flagProblems(flag({id}), [])).toEqual([]);
    });

    it("rejects an id used by another flag", () => {
        expect(flagProblems(flag({id: "dup", slot: 2}), [flag({id: "dup"})])).toContain("Id is already used by another flag.");
    });

    it("requires a server, and a unique slot per server", () => {
        expect(flagProblems(flag({server: ""}), [])).toContain("Choose a server.");
        expect(flagProblems(flag({id: "other"}), [flag()])).toContain("Slot 1 is already used on web.");
        expect(flagProblems(flag({id: "other"}), [flag({id: "x1", server: "db"})])).toEqual([]);
    });

    it("requires a non-blank path", () => {
        expect(flagProblems(flag({path: "   "}), [])).toContain("Path is required.");
    });

    it("requires positive points unless the flag is a decoy", () => {
        expect(flagProblems(flag({points: 0}), [])).toContain("Points must be greater than 0 (only a decoy may be 0 or negative).");
        expect(flagProblems(flag({points: 1}), [])).toEqual([]);
        expect(flagProblems(flag({points: 0, decoy: true}), [])).toEqual([]);
        expect(flagProblems(flag({points: -50, decoy: true}), [])).toEqual([]);
    });

    it.each(["registry", "ads"] as const)("requires Windows for %s flags", (location_type) => {
        expect(flagProblems(flag({location_type, operating_system: "linux"}), [])).toContain("Registry and ADS flags must be on Windows.");
        expect(flagProblems(flag({location_type, operating_system: "windows"}), [])).toEqual([]);
    });

    it("requires one operating system per server", () => {
        const problems = flagProblems(flag({id: "win", slot: 2, operating_system: "windows"}), [flag()]);
        expect(problems).toContain("Every flag on web must use the same operating system.");
    });
});

const renderEditor = (props: Partial<React.ComponentProps<typeof CtfSpecEditor>> = {}) => {
    const onSaved = vi.fn();
    const spec = props.spec ?? makeSpec();
    const utils = render(
        <CtfSpecEditor ctfId={CTF_ID} state={CtfStates.DRAFT} spec={spec} serverNames={["web", "db"]} onSaved={onSaved} {...props} />
    );
    return {onSaved, spec, ...utils};
};

const saveButton = () => screen.getByRole("button", {name: "Save flags"});

describe("CtfSpecEditor", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });
    afterEach(cleanup);

    it("only edits in DRAFT", () => {
        expect(SPEC_EDIT_STATES).toEqual([CtfStates.DRAFT]);
    });

    it("lists the flags with their kind", () => {
        renderEditor();
        expect(screen.getByRole("gridcell", {name: "web-user"})).toBeInTheDocument();
        expect(screen.getByRole("gridcell", {name: "web-root"})).toBeInTheDocument();
        expect(screen.getByText("Open")).toBeInTheDocument();
        expect(screen.getByText("Locked")).toBeInTheDocument();
        expect(saveButton()).toBeDisabled();
        expect(screen.getByRole("button", {name: "Discard changes"})).toBeDisabled();
    });

    it.each([CtfStates.ARMING, CtfStates.ARMED, CtfStates.RUNNING, CtfStates.ARCHIVED])("is read-only outside DRAFT (state %i)", (state) => {
        renderEditor({state});

        expect(screen.getByText("Flags are fixed once the event has been armed.")).toBeInTheDocument();
        expect(screen.getByLabelText(/^Event name/)).toBeDisabled();
        expect(screen.getByRole("button", {name: "Add flag"})).toBeDisabled();
        expect(screen.getByRole("button", {name: "Edit flag web-user"})).toBeDisabled();
        expect(screen.getByRole("button", {name: "Delete flag web-user"})).toBeDisabled();
        expect(saveButton()).toBeDisabled();
    });

    it("cannot add a flag when the lab has no servers", () => {
        renderEditor({serverNames: []});
        expect(screen.getByRole("button", {name: "Add flag"})).toBeDisabled();
    });

    it("adds a flag through the dialog and saves it with the updateSpec call", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        const {onSaved, spec} = renderEditor();

        fireEvent.click(screen.getByRole("button", {name: "Add flag"}));
        const dialog = screen.getByRole("dialog", {name: "Add flag"});
        expect(within(dialog).getByRole("button", {name: "Done"})).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText(/^Id/), {target: {value: "WEB-Three"}});
        fireEvent.change(within(dialog).getByLabelText(/^Slot/), {target: {value: "3"}});
        fireEvent.change(within(dialog).getByLabelText(/^Path/), {target: {value: "  /root/flag.txt  "}});
        fireEvent.change(within(dialog).getByLabelText("Category"), {target: {value: "  web  "}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));

        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(screen.getByRole("gridcell", {name: "web-three"})).toBeInTheDocument();
        expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();

        fireEvent.click(saveButton());
        await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
        const [id, sent] = vi.mocked(ctfService.updateSpec).mock.calls[0];
        expect(id).toBe(CTF_ID);
        expect(sent.flags).toHaveLength(3);
        expect(sent.flags[2]).toMatchObject({
            id: "web-three", server: "web", slot: 3, path: "/root/flag.txt", category: "web",
            hint: null, unlocks_after: null, file_mode: null, file_owner: null,
        });
        expect(sent.flags.slice(0, 2)).toEqual(spec.flags);
    });

    it("confirms the save once the refreshed spec matches the draft", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        const {rerender} = renderEditor();

        fireEvent.change(screen.getByLabelText(/^Event name/), {target: {value: "Renamed"}});
        fireEvent.click(saveButton());
        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        rerender(
            <CtfSpecEditor ctfId={CTF_ID} state={CtfStates.DRAFT} spec={{...makeSpec(), name: "Renamed"}}
                           serverNames={["web", "db"]} onSaved={vi.fn()} />
        );

        expect(await screen.findByText("Flags saved.")).toBeInTheDocument();
        expect(saveButton()).toBeDisabled();
    });

    it("blocks Done and lists the problem for a flag reusing a slot", () => {
        renderEditor();
        fireEvent.click(screen.getByRole("button", {name: "Add flag"}));
        const dialog = screen.getByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText(/^Id/), {target: {value: "fresh"}});
        fireEvent.change(within(dialog).getByLabelText(/^Path/), {target: {value: "/x"}});

        expect(within(dialog).getByText("Slot 1 is already used on web.")).toBeInTheDocument();
        expect(within(dialog).getByRole("button", {name: "Done"})).toBeDisabled();
    });

    it("edits a flag in place", () => {
        renderEditor();
        fireEvent.click(screen.getByRole("button", {name: "Edit flag web-root"}));
        const dialog = screen.getByRole("dialog", {name: "Edit flag web-root"});
        fireEvent.change(within(dialog).getByLabelText(/^Points/), {target: {value: "350"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));

        expect(screen.getByRole("gridcell", {name: "350"})).toBeInTheDocument();
        expect(saveButton()).toBeEnabled();
    });

    it("renaming a flag updates the unlocks_after of the flags that depend on it", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        renderEditor();

        fireEvent.click(screen.getByRole("button", {name: "Edit flag web-user"}));
        const dialog = screen.getByRole("dialog");
        fireEvent.change(within(dialog).getByLabelText(/^Id/), {target: {value: "web-foothold"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));
        fireEvent.click(saveButton());

        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        const sent = vi.mocked(ctfService.updateSpec).mock.calls[0][1];
        expect(sent.flags.map((f) => f.id)).toEqual(["web-foothold", "web-root"]);
        expect(sent.flags[1].unlocks_after).toEqual(["web-foothold"]);
    });

    it("deleting a flag removes it from other flags' unlock lists", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        renderEditor();

        fireEvent.click(screen.getByRole("button", {name: "Delete flag web-user"}));
        fireEvent.click(saveButton());

        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        const sent = vi.mocked(ctfService.updateSpec).mock.calls[0][1];
        expect(sent.flags.map((f) => f.id)).toEqual(["web-root"]);
        expect(sent.flags[0].unlocks_after?.length ?? 0).toBe(0);
    });

    it("will not delete the last remaining flag", () => {
        renderEditor({spec: makeSpec([flag()])});
        expect(screen.getByRole("button", {name: "Delete flag web-user"})).toBeDisabled();
    });

    it("trims the description and rules URL and sends null for blanks", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        renderEditor();

        fireEvent.change(screen.getByLabelText("Description"), {target: {value: "   "}});
        fireEvent.change(screen.getByLabelText("Rules of engagement URL"), {target: {value: " https://x.io/rules "}});
        fireEvent.change(screen.getByLabelText(/^Flag prefix/), {target: {value: "CTF"}});
        fireEvent.click(saveButton());

        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        const sent = vi.mocked(ctfService.updateSpec).mock.calls[0][1];
        expect(sent.description).toBeNull();
        expect(sent.rules_url).toBe("https://x.io/rules");
        expect(sent.scoring.flag_prefix).toBe("ctf");
    });

    it("shows the API error, keeps the draft and does not call onSaved when saving fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.updateSpec).mockRejectedValue(new HttpError(422, "Bad flag path."));
        const {onSaved} = renderEditor();

        fireEvent.change(screen.getByLabelText(/^Event name/), {target: {value: "Renamed"}});
        fireEvent.click(saveButton());

        expect(await screen.findByText("422: Bad flag path.")).toBeInTheDocument();
        expect(onSaved).not.toHaveBeenCalled();
        expect(screen.getByLabelText(/^Event name/)).toHaveValue("Renamed");
        await waitFor(() => expect(saveButton()).toBeEnabled());
    });

    it("discards local edits back to the saved spec", () => {
        renderEditor();
        fireEvent.change(screen.getByLabelText(/^Event name/), {target: {value: "Renamed"}});
        expect(saveButton()).toBeEnabled();

        fireEvent.click(screen.getByRole("button", {name: "Discard changes"}));

        expect(screen.getByLabelText(/^Event name/)).toHaveValue("Spring CTF");
        expect(saveButton()).toBeDisabled();
    });

    it("replaces the draft when a new spec arrives from a refreshed event", () => {
        const {rerender} = renderEditor();
        rerender(
            <CtfSpecEditor ctfId={CTF_ID} state={CtfStates.DRAFT} spec={{...makeSpec(), name: "From server"}}
                           serverNames={["web", "db"]} onSaved={vi.fn()} />
        );
        expect(screen.getByLabelText(/^Event name/)).toHaveValue("From server");
    });
});

describe("flag dialog category", () => {
    afterEach(cleanup);

    const openAddDialog = (spec?: CtfSpec) => {
        renderEditor(spec ? {spec} : {});
        fireEvent.click(screen.getByRole("button", {name: "Add flag"}));
        return screen.getByRole("dialog", {name: "Add flag"});
    };

    it("offers the standard CTF categories", () => {
        const dialog = openAddDialog();
        fireEvent.mouseDown(within(dialog).getByLabelText("Category"));

        const options = screen.getAllByRole("option").map((option) => option.textContent);
        expect(options).toEqual([...STANDARD_CATEGORIES]);
    });

    it("also offers custom categories already used by other flags, once each", () => {
        const dialog = openAddDialog(makeSpec([
            flag({category: "Badge Hunt"}),
            flag({id: "web-root", slot: 2, category: "Badge Hunt"}),
            flag({id: "web-env", slot: 3, category: "Web"}),
        ]));
        fireEvent.mouseDown(within(dialog).getByLabelText("Category"));

        const options = screen.getAllByRole("option").map((option) => option.textContent);
        expect(options.filter((option) => option === "Badge Hunt")).toHaveLength(1);
        expect(options.filter((option) => option === "Web")).toHaveLength(1);
    });

    it("keeps a typed custom category", async () => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        const dialog = openAddDialog();
        fireEvent.change(within(dialog).getByLabelText(/^Id/), {target: {value: "web-three"}});
        fireEvent.change(within(dialog).getByLabelText(/^Slot/), {target: {value: "3"}});
        fireEvent.change(within(dialog).getByLabelText(/^Path/), {target: {value: "/root/flag.txt"}});
        fireEvent.change(within(dialog).getByLabelText("Category"), {target: {value: "Badge Hunt"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

        fireEvent.click(saveButton());
        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        expect(vi.mocked(ctfService.updateSpec).mock.calls[0][1].flags[2].category).toBe("Badge Hunt");
    });
});

describe("flag dialog Windows access", () => {
    beforeEach(() => vi.mocked(ctfService.updateSpec).mockReset());
    afterEach(cleanup);

    const windowsFlag = (overrides: Partial<CtfFlagSpec> = {}) => flag({
        id: "dc-file", server: "dc", operating_system: "windows", path: "C:\\Secrets\\flag.txt", ...overrides,
    });

    const openEditDialog = (target: CtfFlagSpec) => {
        renderEditor({spec: makeSpec([target])});
        fireEvent.click(screen.getByRole("button", {name: `Edit flag ${target.id}`}));
        return screen.getByRole("dialog", {name: `Edit flag ${target.id}`});
    };

    const saveDialog = async (dialog: HTMLElement) => {
        vi.mocked(ctfService.updateSpec).mockResolvedValue({} as CtfEvent);
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        fireEvent.click(saveButton());
        await waitFor(() => expect(ctfService.updateSpec).toHaveBeenCalled());
        return vi.mocked(ctfService.updateSpec).mock.calls[0][1].flags[0];
    };

    it("is offered for Windows file flags but not Linux ones", () => {
        const dialog = openEditDialog(windowsFlag());
        expect(within(dialog).getByRole("combobox", {name: "Windows access"})).toBeInTheDocument();
        expect(within(dialog).getByLabelText(/Hidden file/)).toBeInTheDocument();
        expect(within(dialog).queryByLabelText("File mode")).not.toBeInTheDocument();
        cleanup();

        const linux = openEditDialog(flag());
        expect(within(linux).queryByRole("combobox", {name: "Windows access"})).not.toBeInTheDocument();
        expect(within(linux).queryByLabelText(/Hidden file/)).not.toBeInTheDocument();
    });

    it("asks for a user only with user access, and requires a valid one", () => {
        const dialog = openEditDialog(windowsFlag());
        expect(within(dialog).queryByLabelText(/^Windows user/)).not.toBeInTheDocument();

        fireEvent.mouseDown(within(dialog).getByRole("combobox", {name: "Windows access"}));
        fireEvent.click(screen.getByRole("option", {name: "Administrators and one user"}));

        expect(within(dialog).getByRole("button", {name: "Done"})).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText(/^Windows user/), {target: {value: "student"}});
        expect(within(dialog).getByRole("button", {name: "Done"})).toBeEnabled();
    });

    it("saves access, user and hidden for a Windows file flag", async () => {
        const dialog = openEditDialog(windowsFlag({windows_access: "user", windows_user: "student"}));
        fireEvent.click(within(dialog).getByLabelText(/Hidden file/));

        expect(await saveDialog(dialog)).toMatchObject({windows_access: "user", windows_user: "student", hidden: true});
    });

    it("drops the user when access is not 'user', and every Windows option on a Linux flag", async () => {
        const dialog = openEditDialog(windowsFlag({windows_access: "everyone", windows_user: "stale"}));
        expect(await saveDialog(dialog)).toMatchObject({windows_access: "everyone", windows_user: null});
        cleanup();
        vi.mocked(ctfService.updateSpec).mockReset();

        const linux = openEditDialog(flag({windows_access: "administrators", hidden: true}));
        expect(await saveDialog(linux)).toMatchObject({windows_access: null, windows_user: null, hidden: false});
    });
});

describe("flagProblems Windows user", () => {
    it("requires a valid user name only for user access on a Windows file", () => {
        const base = {...blankFlag("dc"), id: "dc-file", operating_system: "windows" as const, path: "C:\\flag.txt"};
        expect(flagProblems({...base, windows_access: "user", windows_user: null}, [])[0]).toMatch(/^Windows user/);
        expect(flagProblems({...base, windows_access: "user", windows_user: "bad name!"}, [])[0]).toMatch(/^Windows user/);
        expect(flagProblems({...base, windows_access: "user", windows_user: "student"}, [])).toEqual([]);
        expect(flagProblems({...base, windows_access: "everyone"}, [])).toEqual([]);
    });
});
