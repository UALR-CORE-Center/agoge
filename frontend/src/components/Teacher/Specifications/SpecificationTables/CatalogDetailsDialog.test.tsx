// @vitest-environment jsdom
import {render, screen} from "@testing-library/react";
import React from "react";
import {describe, expect, it} from "vitest";
import {Specification} from "../../../../services/Specification/specification.model";
import CatalogDetailsDialog from "./CatalogDetailsDialog";

const catalogSpec = (overrides: Record<string, unknown> = {}) => ({
    id: "wireguard-factory-lab",
    summary: {name: "WireGuard Factory Lab", description: "A managed lab", tags: null},
    networks: null,
    routes: null,
    servers: [
        {name: "wireguard", image: "ubuntu", details: null, tags: null, nics: null},
        {name: "kali", image: "kali", tags: null},
    ],
    ...overrides,
}) as unknown as Specification;

describe("CatalogDetailsDialog", () => {
    it("renders catalog specs whose servers have no details", () => {
        render(<CatalogDetailsDialog specification={catalogSpec()}/>);

        expect(screen.getByText("WireGuard Factory Lab details")).toBeTruthy();
        expect(screen.getAllByText("No Labels")).toHaveLength(2);
        // One for the lab summary, one per server's network tags
        expect(screen.getAllByText("No Tags")).toHaveLength(3);
    });

    it("renders a spec with no summary", () => {
        render(<CatalogDetailsDialog specification={catalogSpec({summary: null})}/>);

        expect(screen.getByText("Lab details")).toBeTruthy();
    });
});
