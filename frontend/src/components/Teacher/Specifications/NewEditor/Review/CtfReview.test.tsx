// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {blankCtfSpec, blankFlag} from "../../../Ctf/CtfSpecEditor";
import {EditorForms} from "../utils/EditorTypes";
import CtfReview from "./CtfReview";

// The helpers imported below pull in the Ctf service (and so firebase) at module load.
vi.mock("../../../../../services/Ctf/ctf.service", () => ({ctfService: {updateSpec: vi.fn()}}));

const specWith = (flags: ReturnType<typeof blankFlag>[]) =>
    ({ctf: {...blankCtfSpec("Spring CTF"), flags}}) as unknown as SpecificationEdit;

describe("CtfReview", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("renders each flag id with its details", () => {
        const specification = specWith([
            {...blankFlag("web"), id: "web-user", path: "/home/user/flag.txt"},
            {...blankFlag("db"), id: "db-decoy", slot: 2, path: "/tmp/x", points: 0, decoy: true},
        ]);
        render(<CtfReview specification={specification} loading={false} elevation={1} onNavigateToStep={vi.fn()} />);

        expect(screen.getByText("web-user")).toBeInTheDocument();
        expect(screen.getByText("db-decoy")).toBeInTheDocument();
        expect(screen.getByText("web (slot 1)")).toBeInTheDocument();
        expect(screen.getByText("file: /home/user/flag.txt")).toBeInTheDocument();
        expect(screen.getByText("0 (decoy)")).toBeInTheDocument();
        expect(screen.getByText("CTF Review: Spring CTF")).toBeInTheDocument();
        expect(screen.queryByText(/No flags/)).not.toBeInTheDocument();
    });

    it("shows the empty state when the ctf block has no flags", () => {
        render(<CtfReview specification={specWith([])} loading={false} elevation={1} onNavigateToStep={vi.fn()} />);
        expect(screen.getByText("No flags. A CTF template needs at least one.")).toBeInTheDocument();
    });

    it("shows the empty state when there is no ctf block", () => {
        render(<CtfReview specification={undefined} loading={false} elevation={1} onNavigateToStep={vi.fn()} />);
        expect(screen.getByText(/No flags/)).toBeInTheDocument();
        expect(screen.getByText("CTF Review")).toBeInTheDocument();
    });

    it("navigates to the CTF step when Edit is clicked", () => {
        const onNavigateToStep = vi.fn();
        render(<CtfReview specification={specWith([])} loading={false} elevation={1} onNavigateToStep={onNavigateToStep} />);

        fireEvent.click(screen.getByRole("button", {name: "Edit"}));

        expect(onNavigateToStep).toHaveBeenCalledExactlyOnceWith(EditorForms.Ctf);
    });
});
