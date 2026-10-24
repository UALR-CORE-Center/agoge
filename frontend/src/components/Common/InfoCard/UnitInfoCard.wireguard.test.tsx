// @vitest-environment jsdom
import React from "react";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import "@testing-library/jest-dom/vitest";
import {UnitInfoCard} from "./UnitInfoCard";

const {copy} = vi.hoisted(() => ({copy: vi.fn()}));
vi.mock("../../../hooks/useClipboard", () => ({useClipboard: () => ({copy})}));

const endpoint = {id: "10000", connection_id: "test-dev-787001:abcdefghij",
    hostname: "wg10000.test-dev-787001.example.edu.", port: 51820, status: "reserved"};
const data = {summary: {name: "Remote lab", teacher_instructions_url: null}, wireguard_endpoint: endpoint};

describe("instructor remote lab connection details", () => {
    afterEach(cleanup);
    beforeEach(() => vi.clearAllMocks());

    it("shows and copies a stable connection ID alongside its current gateway DNS", () => {
        render(<UnitInfoCard data={data} />);
        expect(screen.getByText("test-dev-787001:abcdefghij")).toBeInTheDocument();
        expect(screen.getByText("Gateway number: 10000")).toBeInTheDocument();
        expect(screen.getByText("wg10000.test-dev-787001.example.edu:51820")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Copy remote lab connection ID"}));
        expect(copy).toHaveBeenLastCalledWith("test-dev-787001:abcdefghij");
        fireEvent.click(screen.getByRole("button", {name: "Copy gateway DNS and port"}));
        expect(copy).toHaveBeenLastCalledWith("wg10000.test-dev-787001.example.edu:51820");
    });

    it("keeps identity visible while stopped without presenting the tunnel as connected", () => {
        render(<UnitInfoCard data={{...data, wireguard_lease: {kit_id: "remote-lab-01", device_id: "peer-01",
            equipment_subnet: "172.30.0.0/24", student_subnets: [], service_ready: true,
            tunnel_ready: true, health_timestamp: Date.now() / 1000, status: "reserved"}}} />);
        expect(screen.getByText("test-dev-787001:abcdefghij")).toBeInTheDocument();
        expect(screen.getByText("Gateway unavailable")).toBeInTheDocument();
        expect(screen.getByText("Remote tunnel status unknown")).toBeInTheDocument();
    });

    it("does not use the recycled gateway number as a substitute connection ID", () => {
        render(<UnitInfoCard data={{...data, wireguard_endpoint: {...endpoint, connection_id: null}}} />);
        expect(screen.getByRole("button", {name: "Copy remote lab connection ID"})).toBeDisabled();
        expect(screen.getByText("Pending")).toBeInTheDocument();
    });
});
