// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {blankCtfSpec, blankFlag} from "../../Ctf/CtfSpecEditor";
import CtfForm from "./CtfForm";

vi.mock("../../../../services/Ctf/ctf.service", () => ({
    ctfService: {updateSpec: vi.fn()},
}));

describe("CtfForm", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("lists the problems of a blank spec", () => {
        render(<CtfForm value={blankCtfSpec()} onChange={vi.fn()} serverNames={["web"]} disableForm={false} />);
        expect(screen.getByText("Event name is required.")).toBeInTheDocument();
        expect(screen.getByText("Add at least one flag.")).toBeInTheDocument();
    });

    it("tells the user to add a server when the lab has none", () => {
        render(<CtfForm value={blankCtfSpec("CTF")} onChange={vi.fn()} serverNames={[]} disableForm={false} />);
        expect(screen.getByText(/Add a server in the Servers step/)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Add flag"})).toBeDisabled();
    });

    it("omits the server warning and problems for a valid spec", () => {
        const value = {...blankCtfSpec("CTF"), flags: [{...blankFlag("web"), id: "web-user", path: "/flag.txt"}]};
        render(<CtfForm value={value} onChange={vi.fn()} serverNames={["web"]} disableForm={false} />);
        expect(screen.queryByText(/Add a server in the Servers step/)).not.toBeInTheDocument();
        expect(screen.queryByText("Add at least one flag.")).not.toBeInTheDocument();
    });

    it("disables editing when the form is disabled", () => {
        render(<CtfForm value={blankCtfSpec("CTF")} onChange={vi.fn()} serverNames={["web"]} disableForm={true} />);
        expect(screen.getByLabelText(/^Event name/)).toBeDisabled();
    });
});
