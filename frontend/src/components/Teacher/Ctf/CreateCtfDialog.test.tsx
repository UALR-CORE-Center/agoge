// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {CtfTemplateRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CreateCtfDialog, {DEFAULT_EXPIRY_DAYS} from "./CreateCtfDialog";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {create: vi.fn(), getTemplates: vi.fn()},
}));

const DAY_SECONDS = 24 * 60 * 60;

const templates: CtfTemplateRow[] = [
    {
        id: "spec-web", name: "Web Lab", description: "Break the web app", ctf_name: "Web CTF", flag_count: 3,
        servers: [{name: "web", os: "linux", machine_type: "e2-small"}, {name: "db", os: null, machine_type: null}],
    },
    {id: "spec-bare", name: "Bare Lab", description: null, ctf_name: "Bare CTF", flag_count: 1, servers: []},
];

const renderDialog = (onClose = vi.fn(), open = true) => {
    render(
        <MemoryRouter initialEntries={["/start"]}>
            <Routes>
                <Route path="/start" element={<CreateCtfDialog open={open} onClose={onClose} />} />
                <Route path={`${URL_TEACHER_CTF_EVENT}/:id`} element={<div>event page</div>} />
            </Routes>
        </MemoryRouter>
    );
    return onClose;
};

const chooseTemplate = async (name: string) => {
    fireEvent.mouseDown(await screen.findByRole("combobox", {name: "Template"}));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name}));
};

describe("CreateCtfDialog", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(ctfService.getTemplates).mockResolvedValue(templates);
    });
    afterEach(cleanup);

    it("loads templates only when open", async () => {
        renderDialog(vi.fn(), false);
        await Promise.resolve();
        expect(ctfService.getTemplates).not.toHaveBeenCalled();
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("keeps Create disabled until a template is chosen", async () => {
        renderDialog();
        expect(await screen.findByText(/Lab templates with a ctf block/)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Create"})).toBeDisabled();

        await chooseTemplate("Web Lab");
        expect(screen.getByRole("button", {name: "Create"})).toBeEnabled();
    });

    it("summarises the chosen template with its flag count and servers", async () => {
        renderDialog();
        await chooseTemplate("Web Lab");

        expect(screen.getByText("Web CTF")).toBeInTheDocument();
        expect(screen.getByText("Break the web app")).toBeInTheDocument();
        expect(screen.getByText(/3 flags on web, db/)).toBeInTheDocument();
    });

    it("uses singular wording and 'no servers' for a minimal template", async () => {
        renderDialog();
        await chooseTemplate("Bare Lab");

        expect(screen.getByText(/1 flag on no servers/)).toBeInTheDocument();
    });

    it("explains when no template has a ctf block", async () => {
        vi.mocked(ctfService.getTemplates).mockResolvedValue([]);
        renderDialog();

        expect(await screen.findByText("No lab templates have a ctf block yet.")).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Create"})).toBeDisabled();
    });

    it("creates with a null name and a +14 day expiry in epoch seconds, then opens the event", async () => {
        vi.mocked(ctfService.create).mockResolvedValue({build_id: "newevent01", exists: null});
        renderDialog();
        await chooseTemplate("Web Lab");

        const before = Math.floor(Date.now() / 1000);
        fireEvent.click(screen.getByRole("button", {name: "Create"}));

        expect(await screen.findByText("event page")).toBeInTheDocument();
        const after = Math.ceil(Date.now() / 1000);
        expect(ctfService.create).toHaveBeenCalledTimes(1);
        const body = vi.mocked(ctfService.create).mock.calls[0][0];
        expect(body.spec_id).toBe("spec-web");
        expect(body.name).toBeNull();
        expect(Number.isInteger(body.expires)).toBe(true);
        // The default is set when the dialog mounts, so allow a little slack before the click.
        expect(body.expires).toBeGreaterThanOrEqual(before + DEFAULT_EXPIRY_DAYS * DAY_SECONDS - 60);
        expect(body.expires).toBeLessThanOrEqual(after + DEFAULT_EXPIRY_DAYS * DAY_SECONDS);
    });

    it("sends the trimmed event name, and null when it is only whitespace", async () => {
        vi.mocked(ctfService.create).mockResolvedValue({build_id: "newevent01", exists: null});
        renderDialog();
        await chooseTemplate("Web Lab");

        fireEvent.change(screen.getByLabelText("Event name"), {target: {value: "  Spring Qualifier  "}});
        fireEvent.click(screen.getByRole("button", {name: "Create"}));
        await screen.findByText("event page");
        expect(vi.mocked(ctfService.create).mock.calls[0][0].name).toBe("Spring Qualifier");
    });

    it("treats a whitespace-only name as no name", async () => {
        vi.mocked(ctfService.create).mockResolvedValue({build_id: "newevent01", exists: null});
        renderDialog();
        await chooseTemplate("Web Lab");

        fireEvent.change(screen.getByLabelText("Event name"), {target: {value: "   "}});
        fireEvent.click(screen.getByRole("button", {name: "Create"}));
        await screen.findByText("event page");
        expect(vi.mocked(ctfService.create).mock.calls[0][0].name).toBeNull();
    });

    it("shows the API error, stays open and lets the user retry", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.create).mockRejectedValueOnce(new HttpError(409, "CTF is disabled."));
        renderDialog();
        await chooseTemplate("Web Lab");

        fireEvent.click(screen.getByRole("button", {name: "Create"}));

        expect(await screen.findByRole("alert")).toHaveTextContent("409: CTF is disabled.");
        expect(screen.queryByText("event page")).not.toBeInTheDocument();
        await waitFor(() => expect(screen.getByRole("button", {name: "Create"})).toBeEnabled());

        vi.mocked(ctfService.create).mockResolvedValue({build_id: "newevent01", exists: null});
        fireEvent.click(screen.getByRole("button", {name: "Create"}));
        expect(await screen.findByText("event page")).toBeInTheDocument();
    });

    it("shows an error when templates cannot load", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(ctfService.getTemplates).mockRejectedValue(new HttpError(503, "Unavailable."));
        renderDialog();

        expect(await screen.findByRole("alert")).toHaveTextContent("503: Unavailable.");
        expect(screen.getByRole("button", {name: "Create"})).toBeDisabled();
    });

    it("calls onClose from Cancel", async () => {
        const onClose = renderDialog();
        await screen.findByText(/Lab templates with a ctf block/);

        fireEvent.click(screen.getByRole("button", {name: "Cancel"}));
        expect(onClose).toHaveBeenCalledTimes(1);
    });
});
