// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfHostRow, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {darkTheme} from "../../../styles/theme";
import HttpError from "../../Common/Errors/HttpError";
import CtfHostsPanel, {RESET_STATES, hostRowId, resetBlocker} from "./CtfHostsPanel";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {getHosts: vi.fn(), resetHost: vi.fn()},
}));

const CTF_ID = "eventevent";

const host = (overrides: Partial<CtfHostRow> = {}): CtfHostRow => ({
    workout_id: "boardaaaaa",
    team_name: "Red",
    server: "web",
    server_state: 50,
    server_state_name: "RUNNING",
    flag_count: 2,
    rebuild_allowed: true,
    ...overrides,
});

const HOSTS: CtfHostRow[] = [
    host(),
    host({server: "vpn", flag_count: 0, rebuild_allowed: false}),
    host({workout_id: "boardbbbbb", team_name: "Blue"}),
    host({workout_id: "boardbbbbb", team_name: "Blue", server: "db", server_state: null, server_state_name: null, rebuild_allowed: false}),
];

const renderPanel = (state: number = CtfStates.RUNNING) => render(
    <ThemeProvider theme={darkTheme}>
        <CtfHostsPanel ctfId={CTF_ID} state={state} active={true} />
    </ThemeProvider>
);

const openMenu = async (server: string, team: string) => {
    fireEvent.click(await screen.findByRole("button", {name: `Reset ${server} for ${team}`}));
    return screen.findByRole("menu");
};

const menuItem = (menu: HTMLElement, label: string) =>
    within(menu).getByText(label).closest('[role="menuitem"]') as HTMLElement;

describe("resetBlocker", () => {
    it("blocks replant on a flagless server and rebuild when it is not allowed, with the reason", () => {
        expect(resetBlocker(host(), "replant")).toBeNull();
        expect(resetBlocker(host(), "rebuild")).toBeNull();
        expect(resetBlocker(host({flag_count: 0}), "replant")).toMatch(/no flags/);
        expect(resetBlocker(host({rebuild_allowed: false}), "rebuild")).toMatch(/WireGuard/);
        for (const mode of ["replant", "restart", "rebuild"] as const) {
            expect(resetBlocker(host({server_state: null, server_state_name: null}), mode)).toMatch(/not been built/);
        }
        expect(resetBlocker(host({flag_count: 0, rebuild_allowed: false}), "restart")).toBeNull();
    });

    it("names the guest or its parent in a guest row's reason", () => {
        expect(resetBlocker(host({guest: "dc01", flag_count: 0}), "replant")).toMatch(/guest carries no flags/);
        expect(resetBlocker(host({guest: "dc01", flag_count: 0}), "rebuild")).toBeNull();
        expect(resetBlocker(host({guest: "dc01", server_state: null}), "restart")).toMatch(/parent server has not been built/);
    });
});

describe("hostRowId", () => {
    it("keeps a guest row apart from its parent and from a server whose name holds the guest's", () => {
        const ids = [host(), host({guest: "a"}), host({server: "web-a"})].map(hostRowId);
        expect(new Set(ids).size).toBe(3);
    });
});

describe("CtfHostsPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(ctfService.getHosts).mockResolvedValue(HOSTS);
    });

    afterEach(() => {
        cleanup();
    });

    it("renders one row per board per server with team, server state and flag count", async () => {
        renderPanel();
        await screen.findByRole("button", {name: "Reset db for Blue"});
        expect(screen.getAllByRole("button", {name: /^Reset /})).toHaveLength(4);
        const row = screen.getByRole("button", {name: "Reset web for Red"}).closest('[role="row"]') as HTMLElement;
        expect(within(row).getByRole("gridcell", {name: "RUNNING"})).toBeInTheDocument();
        expect(within(row).getByRole("gridcell", {name: "2"})).toBeInTheDocument();
        const unbuilt = screen.getByRole("button", {name: "Reset db for Blue"}).closest('[role="row"]') as HTMLElement;
        expect(within(unbuilt).getByRole("gridcell", {name: "Not built"})).toBeInTheDocument();
        expect(ctfService.getHosts).toHaveBeenCalledWith(CTF_ID);
    });

    it("offers replant, restart and rebuild with none pre-selected", async () => {
        renderPanel();
        const menu = await openMenu("web", "Red");
        const items = within(menu).getAllByRole("menuitem");
        expect(items.map(item => item.textContent)).toEqual([
            expect.stringContaining("Replant"), expect.stringContaining("Restart"), expect.stringContaining("Rebuild"),
        ]);
        items.forEach(item => {
            expect(item).not.toHaveAttribute("aria-disabled");
            expect(item).not.toHaveClass("Mui-selected");
        });
        expect(ctfService.resetHost).not.toHaveBeenCalled();
    });

    it("disables rebuild with a tooltip when rebuild_allowed is false", async () => {
        renderPanel();
        const menu = await openMenu("vpn", "Red");
        const rebuild = menuItem(menu, "Rebuild");
        expect(rebuild).toHaveAttribute("aria-disabled", "true");
        expect(menuItem(menu, "Replant")).toHaveAttribute("aria-disabled", "true");
        expect(menuItem(menu, "Restart")).not.toHaveAttribute("aria-disabled");

        fireEvent.mouseOver(rebuild.parentElement as HTMLElement);
        expect(await screen.findByRole("tooltip")).toHaveTextContent("WireGuard endpoint");
    });

    it("disables every mode on a server that has not been built", async () => {
        renderPanel();
        const menu = await openMenu("db", "Blue");
        within(menu).getAllByRole("menuitem").forEach(item => expect(item).toHaveAttribute("aria-disabled", "true"));
    });

    it("restarts a host after a plain confirmation, then re-reads the hosts", async () => {
        vi.mocked(ctfService.resetHost).mockResolvedValue({id: CTF_ID} as never);
        renderPanel();
        fireEvent.click(menuItem(await openMenu("web", "Blue"), "Restart"));

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toHaveTextContent("Stop and start web for Blue.");
        expect(within(dialog).queryByLabelText("Confirmation")).not.toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole("button", {name: "Restart"}));

        await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(CTF_ID, "boardbbbbb", "web", {mode: "restart"}));
        expect(await screen.findByText("Restart of web for Blue started.")).toBeInTheDocument();
        await waitFor(() => expect(ctfService.getHosts).toHaveBeenCalledTimes(2));
    });

    it("replants a host after a plain confirmation", async () => {
        vi.mocked(ctfService.resetHost).mockResolvedValue({id: CTF_ID} as never);
        renderPanel();
        fireEvent.click(menuItem(await openMenu("web", "Red"), "Replant"));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Replant"}));
        await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(CTF_ID, "boardaaaaa", "web", {mode: "replant"}));
    });

    it("rebuilds only after the server name is typed into the confirmation dialog", async () => {
        vi.mocked(ctfService.resetHost).mockResolvedValue({id: CTF_ID} as never);
        renderPanel();
        fireEvent.click(menuItem(await openMenu("web", "Blue"), "Rebuild"));

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toHaveTextContent("Delete and recreate web for Blue.");
        const confirm = within(dialog).getByRole("button", {name: "Rebuild"});
        expect(confirm).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: "wrong"}});
        expect(confirm).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: "web"}});
        expect(confirm).toBeEnabled();
        fireEvent.click(confirm);

        await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(CTF_ID, "boardbbbbb", "web", {mode: "rebuild"}));
    });

    it("does not reset when the dialog is cancelled", async () => {
        renderPanel();
        fireEvent.click(menuItem(await openMenu("web", "Red"), "Restart"));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Cancel"}));
        expect(ctfService.resetHost).not.toHaveBeenCalled();
    });

    it("shows the API error when a reset is refused", async () => {
        vi.mocked(ctfService.resetHost).mockRejectedValue(new HttpError(409, "Cannot reset a host of a CTF event that is ENDED"));
        renderPanel();
        fireEvent.click(menuItem(await openMenu("web", "Red"), "Restart"));
        fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Restart"}));
        expect(await screen.findByText("409: Cannot reset a host of a CTF event that is ENDED")).toBeInTheDocument();
    });

    it("enables Reset only in the states the API accepts", async () => {
        for (const state of Object.values(CtfStates)) {
            renderPanel(state);
            const button = await screen.findByRole("button", {name: "Reset web for Red"});
            if (RESET_STATES.includes(state)) {
                expect(button).toBeEnabled();
            } else {
                expect(button).toBeDisabled();
            }
            cleanup();
        }
        expect([...RESET_STATES].sort()).toEqual(
            [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN].sort()
        );
    });

    describe("guest rows", () => {
        const GUEST_HOSTS: CtfHostRow[] = [
            host({flag_count: 0}),
            host({guest: "dc01", flag_count: 2}),
            host({guest: "ws01", flag_count: 0}),
        ];

        beforeEach(() => {
            vi.mocked(ctfService.getHosts).mockResolvedValue(GUEST_HOSTS);
            vi.mocked(ctfService.resetHost).mockResolvedValue({id: CTF_ID} as never);
        });

        it("renders each guest indented under its parent with its own reset button", async () => {
            renderPanel();
            const guestButton = await screen.findByRole("button", {name: "Reset dc01 on web for Red"});
            expect(screen.getAllByRole("button", {name: /^Reset /})).toHaveLength(3);
            const rows = screen.getAllByRole("row").filter(r => within(r).queryByRole("button", {name: /^Reset /}));
            expect(rows.map(r => within(r).getByRole("button").getAttribute("aria-label"))).toEqual([
                "Reset web for Red", "Reset dc01 on web for Red", "Reset ws01 on web for Red",
            ]);
            const guestRow = guestButton.closest('[role="row"]') as HTMLElement;
            expect(within(guestRow).getByTestId("SubdirectoryArrowRightIcon")).toBeInTheDocument();
            expect(within(guestRow).getByRole("gridcell", {name: "2"})).toBeInTheDocument();
        });

        it("disables replant on a flagless guest but leaves restart and rebuild", async () => {
            renderPanel();
            const menu = await openMenu("ws01 on web", "Red");
            expect(menuItem(menu, "Replant")).toHaveAttribute("aria-disabled", "true");
            expect(menuItem(menu, "Restart")).not.toHaveAttribute("aria-disabled");
            expect(menuItem(menu, "Rebuild")).not.toHaveAttribute("aria-disabled");
            expect(menu).toHaveTextContent("agoge-pristine");
        });

        it("sends the guest with a guest reset", async () => {
            renderPanel();
            fireEvent.click(menuItem(await openMenu("dc01 on web", "Red"), "Replant"));
            const dialog = await screen.findByRole("dialog");
            expect(dialog).toHaveTextContent("Plant every flag on dc01 on web for Red again. The parent VM keeps running");
            fireEvent.click(within(dialog).getByRole("button", {name: "Replant"}));
            await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(
                CTF_ID, "boardaaaaa", "web", {mode: "replant", guest: "dc01"},
            ));
            expect(await screen.findByText("Replant of dc01 on web for Red started.")).toBeInTheDocument();
        });

        it("rebuilds a guest only after the guest name is typed", async () => {
            renderPanel();
            fireEvent.click(menuItem(await openMenu("dc01 on web", "Red"), "Rebuild"));
            const dialog = await screen.findByRole("dialog");
            expect(dialog).toHaveTextContent("Revert dc01 on web for Red to its agoge-pristine snapshot");
            const confirm = within(dialog).getByRole("button", {name: "Rebuild"});
            fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: "web"}});
            expect(confirm).toBeDisabled();
            fireEvent.change(within(dialog).getByLabelText("Confirmation"), {target: {value: "dc01"}});
            fireEvent.click(confirm);
            await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(
                CTF_ID, "boardaaaaa", "web", {mode: "rebuild", guest: "dc01"},
            ));
        });

        it("resets the parent row without a guest", async () => {
            renderPanel();
            fireEvent.click(menuItem(await openMenu("web", "Red"), "Restart"));
            fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", {name: "Restart"}));
            await waitFor(() => expect(ctfService.resetHost).toHaveBeenCalledWith(CTF_ID, "boardaaaaa", "web", {mode: "restart"}));
        });
    });

    it("shows a load error", async () => {
        vi.mocked(ctfService.getHosts).mockRejectedValue(new HttpError(500, "boom"));
        renderPanel();
        expect(await screen.findByText("500: boom")).toBeInTheDocument();
    });
});
