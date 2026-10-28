// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import React from "react";
import {afterEach, describe, expect, it} from "vitest";
import {NestedGuest} from "../../../../../services/Server/nested.model";
import NetworkTopology from "./NetworkTopology";
import {defaultNestedNetwork} from "./nestedWizardState";

const guest = (name: string, nics: NestedGuest["nics"]): NestedGuest => ({
    name, os_id: "windows-server-2019", media_id: null, vcpus: 2, memory_mb: 4096, disk_gb: 40, nics,
    admin_username: "Administrator", admin_password: "Passw0rd!", packages: [], post_install_script: null,
    console: true, autostart: true, start_order: 0, start_delay_seconds: 0,
});

describe("NetworkTopology", () => {
    afterEach(cleanup);

    it("draws a rail per network and drops each guest NIC onto its rail", () => {
        const networks = [
            defaultNestedNetwork(),
            {...defaultNestedNetwork(), name: "wire", cidr: "10.9.9.0/24", mode: "isolated" as const,
                parent_address: null, dhcp: false, dhcp_start: null, dhcp_end: null},
        ];
        const guests = [
            guest("dc01", [{network: "lab", ip: "192.168.100.10", expose: true}, {network: "wire", ip: null, expose: false}]),
            // A NIC on a deleted network has no rail and is left out.
            guest("ws01", [{network: "gone", ip: null, expose: false}]),
        ];
        render(<NetworkTopology networks={networks} guests={guests} />);

        expect(screen.getByRole("img", {name: "Network topology: 2 network(s), 2 guest(s)"})).toBeInTheDocument();
        const rails = screen.getAllByTestId("topology-rail");
        expect(rails[0]).toHaveTextContent("192.168.100.0/24 · NAT");
        expect(rails[1]).toHaveTextContent("10.9.9.0/24 · isolated");

        const [parent, dc01, ws01] = screen.getAllByTestId("topology-node");
        // The parent only joins the network it has an address on.
        expect(within(parent).getAllByText(/^192\.168\.100\.1$/)).toHaveLength(1);
        expect(parent.querySelectorAll("circle")).toHaveLength(1);
        expect(dc01).toHaveTextContent("dc01");
        expect(dc01).toHaveTextContent("192.168.100.10");
        expect(dc01).toHaveTextContent("DHCP");
        expect(dc01.querySelectorAll("circle")).toHaveLength(2);
        expect(ws01.querySelectorAll("circle")).toHaveLength(0);
    });

    it("colors only guests with an exposed NIC green", () => {
        const guests = [
            guest("dc01", [{network: "lab", ip: "192.168.100.10", expose: true}]),
            guest("ws01", [{network: "lab", ip: null, expose: false}]),
        ];
        render(<NetworkTopology networks={[defaultNestedNetwork()]} guests={guests} />);

        const [parent, dc01, ws01] = screen.getAllByTestId("topology-node");
        expect(dc01).toHaveAttribute("data-exposed", "true");
        expect(dc01.querySelector("title")).toHaveTextContent("dc01: reachable across the VPC");
        const green = dc01.querySelector("rect")!.getAttribute("stroke");
        for (const node of [parent, ws01]) {
            expect(node).not.toHaveAttribute("data-exposed");
            expect(node.querySelector("rect")!.getAttribute("stroke")).not.toBe(green);
        }
    });
});
