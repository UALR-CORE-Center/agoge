// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfFlagSpec, CtfSpec} from "../../../services/Ctf/ctf.model";
import {blankCtfSpec, blankFlag, CtfSpecFields, ctfSpecProblems} from "./CtfSpecEditor";

vi.mock("../../../services/Ctf/ctf.service", () => ({
    ctfService: {updateSpec: vi.fn()},
}));

const flag = (overrides: Partial<CtfFlagSpec> = {}): CtfFlagSpec => ({
    ...blankFlag("web"), id: "web-user", path: "/home/user/flag.txt", ...overrides,
});

const validSpec = (overrides: Partial<CtfSpec> = {}): CtfSpec => ({
    ...blankCtfSpec("Spring CTF"), flags: [flag()], ...overrides,
});

describe("blankCtfSpec", () => {
    it("defaults to the agoge prefix, a rate limit of 10 and no flags", () => {
        expect(blankCtfSpec("My CTF")).toEqual({
            name: "My CTF",
            description: null,
            rules_url: null,
            flags: [],
            scoring: {flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false},
        });
    });

    it("uses an empty name when none is given", () => {
        expect(blankCtfSpec().name).toBe("");
    });
});

describe("ctfSpecProblems", () => {
    it("returns no problems for a valid spec", () => {
        expect(ctfSpecProblems(validSpec(), ["web"])).toEqual([]);
    });

    it.each(["", "   "])("requires an event name (%j)", (name) => {
        expect(ctfSpecProblems(validSpec({name}), ["web"])).toContain("Event name is required.");
    });

    it.each(["", "a", "Upper", "1abc", "has-dash", "x".repeat(17)])("rejects the flag prefix %j", (flag_prefix) => {
        const spec = validSpec();
        spec.scoring = {...spec.scoring, flag_prefix};
        expect(ctfSpecProblems(spec, ["web"]).some((p) => p.startsWith("Flag prefix:"))).toBe(true);
    });

    it.each(["ab", "a1", "x".repeat(16)])("accepts the flag prefix %j", (flag_prefix) => {
        const spec = validSpec();
        spec.scoring = {...spec.scoring, flag_prefix};
        expect(ctfSpecProblems(spec, ["web"])).toEqual([]);
    });

    it.each([0, -1, 101, 1.5, NaN])("rejects the rate limit %j", (submission_rate_limit) => {
        const spec = validSpec();
        spec.scoring = {...spec.scoring, submission_rate_limit};
        expect(ctfSpecProblems(spec, ["web"])).toContain("Submissions per flag per minute must be between 1 and 100.");
    });

    it.each([1, 100])("accepts the rate limit boundary %j", (submission_rate_limit) => {
        const spec = validSpec();
        spec.scoring = {...spec.scoring, submission_rate_limit};
        expect(ctfSpecProblems(spec, ["web"])).toEqual([]);
    });

    it("requires at least one flag", () => {
        expect(ctfSpecProblems(validSpec({flags: []}), ["web"])).toContain("Add at least one flag.");
    });

    it("flags a flag whose server is not in the lab", () => {
        const problems = ctfSpecProblems(validSpec(), ["db"]);
        expect(problems).toContain('Flag web-user: server "web" is not in this lab.');
    });

    it("surfaces a duplicate slot on a server through the flag problems", () => {
        const spec = validSpec({flags: [flag(), flag({id: "web-root"})]});
        const problems = ctfSpecProblems(spec, ["web"]);
        expect(problems).toContain("Flag web-user: Slot 1 is already used on web.");
        expect(problems).toContain("Flag web-root: Slot 1 is already used on web.");
    });

    it("labels an unnamed flag by its position", () => {
        const problems = ctfSpecProblems(validSpec({flags: [flag({id: ""})]}), ["web"]);
        expect(problems.some((p) => p.startsWith("Flag #1: Id:"))).toBe(true);
    });
});

describe("CtfSpecFields", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    it("reports the new name through onChange without mutating the rest of the spec", () => {
        const onChange = vi.fn();
        const spec = validSpec();
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={["web"]} />);

        fireEvent.change(screen.getByLabelText(/^Event name/), {target: {value: "Fall CTF"}});

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenCalledWith({...spec, name: "Fall CTF"});
    });

    it("lowercases the flag prefix it reports", () => {
        const onChange = vi.fn();
        const spec = validSpec();
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={["web"]} />);

        fireEvent.change(screen.getByLabelText(/^Flag prefix/), {target: {value: "CTF"}});

        expect(onChange).toHaveBeenCalledWith({...spec, scoring: {...spec.scoring, flag_prefix: "ctf"}});
    });

    it("disables Add flag when the lab has no servers", () => {
        render(<CtfSpecFields value={validSpec()} onChange={vi.fn()} serverNames={[]} />);
        expect(screen.getByRole("button", {name: "Add flag"})).toBeDisabled();
    });

    it("enables Add flag when the lab has a server", () => {
        render(<CtfSpecFields value={validSpec()} onChange={vi.fn()} serverNames={["web"]} />);
        expect(screen.getByRole("button", {name: "Add flag"})).toBeEnabled();
    });

    it("disables the inputs and Add flag when not editable", () => {
        render(<CtfSpecFields value={validSpec()} onChange={vi.fn()} serverNames={["web"]} editable={false} />);
        expect(screen.getByLabelText(/^Event name/)).toBeDisabled();
        expect(screen.getByRole("button", {name: "Add flag"})).toBeDisabled();
    });
});
