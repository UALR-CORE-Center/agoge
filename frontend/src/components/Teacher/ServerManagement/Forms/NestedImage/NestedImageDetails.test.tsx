// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {NestedGuest, NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import NestedGuestDetails from "./NestedGuestDetails";
import NestedTunnelHints from "./NestedTunnelHints";

vi.mock("../../../../../services/Server/nested.service", () => ({
    nestedService: {list_catalog: vi.fn()},
}));

const guest = (name: string, osId: string, nics: NestedGuest["nics"], overrides: Partial<NestedGuest> = {}): NestedGuest => ({
    name, os_id: osId, media_id: null, vcpus: 2, memory_mb: 4096, disk_gb: 40, nics,
    admin_username: "Administrator", admin_password: `${name}-secret`, packages: [], post_install_script: null,
    console: true, autostart: true, start_order: 0, start_delay_seconds: 0, ...overrides,
});

const spec: NestedHostSpec = {
    parent_os: "debian-12",
    build_machine_type: "n2-standard-8",
    networks: [{name: "lab", cidr: "192.168.100.0/24", mode: "nat", parent_address: "192.168.100.1", dhcp: true,
        dhcp_start: "192.168.100.100", dhcp_end: "192.168.100.199"}],
    guests: [
        guest("dc01", "server-2022", [{network: "lab", ip: "192.168.100.10", expose: true}]),
        guest("kali", "kali-rolling", [{network: "lab", ip: null, expose: false}], {console: false, admin_username: "kali"}),
    ],
    exposures: [["dc01", 0]],
    console_ports: {dc01: 5901},
    vnc_passwords: {dc01: "vncpw001"},
};

describe("NestedGuestDetails", () => {
    afterEach(cleanup);

    it("shows each guest's status, IPs and console, with passwords hidden until asked", () => {
        render(<NestedGuestDetails spec={spec} build={{
            phase: "building", guests: {dc01: "installing"}, message: "Installing dc01",
            heartbeat_at: null, started_at: null, updated_at: null,
        }} />);
        expect(screen.getByText("Building guests")).toBeInTheDocument();
        expect(screen.getByText("Installing dc01")).toBeInTheDocument();
        const rows = within(screen.getByRole("table", {name: "nested guests"})).getAllByRole("row").slice(1);
        expect(within(rows[0]).getByText("Installing")).toBeInTheDocument();
        expect(within(rows[0]).getByText("lab: 192.168.100.10")).toBeInTheDocument();
        expect(within(rows[0]).getByText("Exposed on alias slot 0")).toBeInTheDocument();
        expect(within(rows[0]).getByText("Port 5901")).toBeInTheDocument();
        expect(within(rows[1]).getByText("Pending")).toBeInTheDocument();
        expect(within(rows[1]).getByText("lab: DHCP")).toBeInTheDocument();
        expect(within(rows[1]).getByText("None")).toBeInTheDocument();
        expect(screen.queryByText("dc01-secret")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("checkbox", {name: "Show passwords"}));
        expect(within(rows[0]).getByText("dc01-secret")).toBeInTheDocument();
        expect(within(rows[0]).getByText("VNC vncpw001")).toBeInTheDocument();
        expect(within(rows[1]).getByText("kali-secret")).toBeInTheDocument();
    });
});

describe("NestedTunnelHints", () => {
    beforeEach(() => {
        vi.mocked(nestedService.list_catalog).mockResolvedValue([
            {id: "server-2022", family: "windows"} as NestedOsCatalogEntry,
            {id: "kali-rolling", family: "linux"} as NestedOsCatalogEntry,
        ]);
    });
    afterEach(() => {
        cleanup();
        vi.clearAllMocks();
    });

    it("shows the console, RDP for Windows and SSH for Linux at the reported lease, through the parent", async () => {
        const build = {
            phase: "ready" as const, guests: {}, message: null, heartbeat_at: null, started_at: null, updated_at: null,
            guest_addresses: {kali: {"0": "192.168.100.150"}},
        };
        render(<NestedTunnelHints spec={spec} build={build} hostname={"adlab.example.test"} username={"agoge"} />);
        expect(screen.getByText(/Loading the guests' operating systems/)).toBeInTheDocument();
        expect(await screen.findByText("ssh -L 13389:192.168.100.10:3389 agoge@adlab.example.test")).toBeInTheDocument();
        expect(screen.getByText("ssh -L 2223:192.168.100.150:22 agoge@adlab.example.test")).toBeInTheDocument();
        expect(screen.getByText("ssh -L 5901:localhost:5901 agoge@adlab.example.test")).toBeInTheDocument();
        expect(screen.getByText(/dc01 console \(VNC viewer to localhost:5901\)/)).toBeInTheDocument();
        // Windows gets no SSH tunnel and Linux no RDP tunnel.
        expect(screen.queryByText(/192\.168\.100\.10:22 /)).not.toBeInTheDocument();
        expect(screen.queryByText(/192\.168\.100\.150:3389 /)).not.toBeInTheDocument();
        expect(screen.queryByText(/Loading the guests' operating systems/)).not.toBeInTheDocument();
    });

    it("shows each guest's login under its RDP or SSH tunnel and the VNC password under its console", async () => {
        const build = {
            phase: "ready" as const, guests: {}, message: null, heartbeat_at: null, started_at: null, updated_at: null,
            guest_addresses: {kali: {"0": "192.168.100.150"}},
        };
        render(<NestedTunnelHints spec={spec} build={build} hostname={"adlab.example.test"} username={"agoge"} />);
        await screen.findByText("ssh -L 2223:192.168.100.150:22 agoge@adlab.example.test");
        expect(screen.getByText("dc01 username:")).toBeInTheDocument();
        expect(screen.getByText("Administrator")).toBeInTheDocument();
        expect(screen.getByText("dc01-secret")).toBeInTheDocument();
        expect(screen.getByText("kali username:")).toBeInTheDocument();
        expect(screen.getByText(/kali SSH \(ssh -p 2223 kali@localhost\)/)).toBeInTheDocument();
        expect(screen.getByText("kali-secret")).toBeInTheDocument();
        expect(screen.getByText("dc01 VNC password:")).toBeInTheDocument();
        expect(screen.getByText("vncpw001")).toBeInTheDocument();
    });

    it("shows a console-only guest's admin login once, for its console login screen", async () => {
        // No catalog entry and no address: dc01 is reachable only at its console, and still gets its login.
        vi.mocked(nestedService.list_catalog).mockResolvedValue([]);
        render(<NestedTunnelHints spec={spec} build={null} hostname={"adlab.example.test"} username={"agoge"} />);
        await waitFor(() => expect(screen.queryByText(/Loading the guests' operating systems/)).not.toBeInTheDocument());
        const dc01 = screen.getByRole("region", {name: "dc01 connections"});
        expect(within(dc01).getByText("ssh -L 5901:localhost:5901 agoge@adlab.example.test")).toBeInTheDocument();
        expect(within(dc01).getAllByText("dc01 username:")).toHaveLength(1);
        expect(within(dc01).getByText("Administrator")).toBeInTheDocument();
        expect(within(dc01).getByText("dc01-secret")).toBeInTheDocument();
        expect(within(dc01).getByText("vncpw001")).toBeInTheDocument();
        // kali has no console and no address yet, so it has nothing to connect to.
        expect(screen.queryByRole("region", {name: "kali connections"})).not.toBeInTheDocument();
    });

    it("renders nothing without a hostname to tunnel through", () => {
        const {container} = render(<NestedTunnelHints spec={spec} build={null} hostname={null} username={"agoge"} />);
        expect(container).toBeEmptyDOMElement();
    });
});
