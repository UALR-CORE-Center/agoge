// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfFlagSpec, CtfNestedGuestSpec, CtfSpec} from "../../../services/Ctf/ctf.model";
import {blankCtfSpec, blankFlag, blankGuest, CtfSpecFields, ctfSpecProblems, guestProblems} from "./CtfSpecEditor";

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
    it("defaults to the agoge prefix, a rate limit of 10 and no flags or nested guests", () => {
        expect(blankCtfSpec("My CTF")).toEqual({
            name: "My CTF",
            description: null,
            rules_url: null,
            flags: [],
            scoring: {flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false},
            nested_guests: [],
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

const guest = (overrides: Partial<CtfNestedGuestSpec> = {}): CtfNestedGuestSpec => ({
    ...blankGuest("hv"), name: "win-dc", domain: "win-dc-vm", ...overrides,
});

const guestSpec = (guests: CtfNestedGuestSpec[], flags: CtfFlagSpec[]): CtfSpec => ({
    ...blankCtfSpec("Spring CTF"), nested_guests: guests, flags,
});

const guestFlag = (overrides: Partial<CtfFlagSpec> = {}): CtfFlagSpec => ({
    ...blankFlag("hv"), id: "dc-flag", path: "/root/flag.txt", guest: "win-dc", ...overrides,
});

describe("guestProblems", () => {
    it("accepts a valid guest", () => {
        expect(guestProblems(guest(), [])).toEqual([]);
    });

    it.each(["", "a", "Upper", "-ab", "has space", "x".repeat(33)])("rejects the guest name %j", (name) => {
        expect(guestProblems(guest({name}), []).some((p) => p.startsWith("Name:"))).toBe(true);
    });

    it.each(["", "bad domain", "x".repeat(65), "a/b"])("rejects the domain %j", (domain) => {
        expect(guestProblems(guest({domain}), []).some((p) => p.startsWith("Domain:"))).toBe(true);
    });

    it("accepts a domain with dots, underscores and dashes", () => {
        expect(guestProblems(guest({domain: "Win_DC.vm-1"}), [])).toEqual([]);
    });

    it("rejects a duplicate name on the same server", () => {
        const problems = guestProblems(guest(), [guest({domain: "other"})]);
        expect(problems).toContain("Name is already used by another guest on hv.");
    });

    it("allows the same name on a different server", () => {
        expect(guestProblems(guest(), [guest({server: "hv2"})])).toEqual([]);
    });

    it("rejects a ninth guest on a server but allows the eighth", () => {
        const guests = (n: number) => Array.from({length: n}, (_v, i) => guest({name: `guest-${i}`}));
        expect(guestProblems(guest(), guests(7))).toEqual([]);
        expect(guestProblems(guest(), guests(8))).toContain("A server can run at most 8 nested guests.");
    });

    it("does not count guests on other servers toward the limit", () => {
        const others = Array.from({length: 8}, (_v, i) => guest({name: `guest-${i}`, server: "hv2"}));
        expect(guestProblems(guest(), others)).toEqual([]);
    });
});

describe("ctfSpecProblems with nested guests", () => {
    const servers = ["hv"];

    it("returns no problems for a flag planted in a declared guest", () => {
        const spec = guestSpec([guest({operating_system: "linux"})], [guestFlag()]);
        expect(ctfSpecProblems(spec, servers)).toEqual([]);
    });

    it("flags a guest whose server is not in the lab", () => {
        const spec = guestSpec([guest({server: "gone"})], [flag()]);
        expect(ctfSpecProblems(spec, ["web"])).toContain('Guest win-dc: server "gone" is not in this lab.');
    });

    it("prefixes guest problems with the guest name", () => {
        const spec = guestSpec([guest({domain: ""})], [flag({server: "hv"})]);
        expect(ctfSpecProblems(spec, servers).some((p) => p.startsWith("Guest win-dc: Domain:"))).toBe(true);
    });

    it("flags a flag whose guest is not declared", () => {
        const spec = guestSpec([], [guestFlag()]);
        expect(ctfSpecProblems(spec, servers)).toContain("Flag dc-flag: Guest win-dc is not declared on hv.");
    });

    it("flags a flag whose guest is declared on another server", () => {
        const spec = guestSpec([guest({server: "hv2"})], [guestFlag()]);
        expect(ctfSpecProblems(spec, ["hv", "hv2"])).toContain("Flag dc-flag: Guest win-dc is not declared on hv.");
    });

    it("flags an operating system that differs from the guest's", () => {
        const spec = guestSpec([guest({operating_system: "windows"})], [guestFlag({operating_system: "linux"})]);
        expect(ctfSpecProblems(spec, servers))
            .toContain("Flag dc-flag: Operating system must match guest win-dc (windows).");
    });

    it("allows a parent flag and a guest flag to share a slot", () => {
        const spec = guestSpec([guest()], [flag({id: "hv-root", server: "hv"}), guestFlag()]);
        expect(ctfSpecProblems(spec, servers)).toEqual([]);
    });

    it("allows the parent and its guest to use different operating systems", () => {
        const spec = guestSpec([guest({operating_system: "windows"})], [
            flag({id: "hv-root", server: "hv", operating_system: "linux"}),
            guestFlag({operating_system: "windows"}),
        ]);
        expect(ctfSpecProblems(spec, servers)).toEqual([]);
    });

    it("rejects slot reuse within one guest", () => {
        const spec = guestSpec([guest()], [guestFlag(), guestFlag({id: "dc-two"})]);
        const problems = ctfSpecProblems(spec, servers);
        expect(problems).toContain("Flag dc-flag: Slot 1 is already used on win-dc on hv.");
        expect(problems).toContain("Flag dc-two: Slot 1 is already used on win-dc on hv.");
    });

    it("allows the same slot in two different guests on one server", () => {
        const spec = guestSpec([guest(), guest({name: "other-vm", domain: "o"})], [guestFlag(), guestFlag({id: "o-flag", guest: "other-vm"})]);
        expect(ctfSpecProblems(spec, servers)).toEqual([]);
    });

    it("applies the single operating system rule per guest", () => {
        // Same declared guest, so a mismatch is reported as a guest OS mismatch and as a per-guest OS clash.
        const spec = guestSpec([guest({operating_system: "linux"})], [
            guestFlag(), guestFlag({id: "dc-two", slot: 2, operating_system: "windows"}),
        ]);
        expect(ctfSpecProblems(spec, servers))
            .toContain("Flag dc-flag: Every flag on win-dc on hv must use the same operating system.");
    });

    describe("offline Windows guest", () => {
        const offline = guest({operating_system: "windows", driver: "offline"});
        const winFlag = (overrides: Partial<CtfFlagSpec> = {}) =>
            guestFlag({operating_system: "windows", path: "C:\\flag.txt", ...overrides});
        const problemsFor = (f: CtfFlagSpec) => ctfSpecProblems(guestSpec([offline], [f]), servers);

        it("accepts a file flag", () => {
            expect(problemsFor(winFlag())).toEqual([]);
        });

        it("rejects the ads location", () => {
            expect(problemsFor(winFlag({location_type: "ads"})))
                .toContain("Flag dc-flag: An offline Windows guest supports only file, registry and env flags.");
        });

        it("rejects windows_access", () => {
            expect(problemsFor(winFlag({windows_access: "everyone"})))
                .toContain("Flag dc-flag: Windows access and Hidden are not supported on an offline Windows guest.");
        });

        it("rejects hidden", () => {
            expect(problemsFor(winFlag({hidden: true})))
                .toContain("Flag dc-flag: Windows access and Hidden are not supported on an offline Windows guest.");
        });

        it.each(["HKCU\\Software\\x", "HKLM\\HARDWARE\\x", "HKLM\\SOFTWARE", "SOFTWARE\\x", "hklm\\software\\x"])(
            "rejects the registry path %j", (path) => {
                expect(problemsFor(winFlag({location_type: "registry", path})).some((p) => p.includes("registry path must start with")))
                    .toBe(true);
            });

        it.each(["HKLM\\SOFTWARE\\Acme\\flag", "HKLM\\SYSTEM\\Acme"])("accepts the registry path %j", (path) => {
            expect(problemsFor(winFlag({location_type: "registry", path}))).toEqual([]);
        });

        it("does not restrict a qemu-agent Windows guest", () => {
            const agent = guest({operating_system: "windows", driver: "qemu-agent"});
            const spec = guestSpec([agent], [winFlag({location_type: "ads", hidden: true})]);
            expect(ctfSpecProblems(spec, servers).some((p) => p.includes("offline"))).toBe(false);
        });
    });
});

describe("CtfSpecFields nested guests", () => {
    beforeEach(() => vi.resetAllMocks());
    afterEach(cleanup);

    const servers = ["hv", "web"];

    it("adds a nested guest through the dialog", () => {
        const onChange = vi.fn();
        const spec = guestSpec([], [flag()]);
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={servers} />);

        fireEvent.click(screen.getByRole("button", {name: "Add nested guest"}));
        const dialog = screen.getByRole("dialog", {name: "Add nested guest"});
        expect(within(dialog).getByRole("button", {name: "Done"})).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText(/^Name/), {target: {value: "Win-DC"}});
        fireEvent.change(within(dialog).getByLabelText(/^libvirt domain/), {target: {value: "  win-dc-vm  "}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenCalledWith({
            ...spec,
            nested_guests: [{name: "win-dc", server: "hv", domain: "win-dc-vm", operating_system: "linux", driver: "qemu-agent"}],
        });
    });

    it("disables Add nested guest when the lab has no servers or is not editable", () => {
        const {rerender} = render(<CtfSpecFields value={validSpec()} onChange={vi.fn()} serverNames={[]} />);
        expect(screen.getByRole("button", {name: "Add nested guest"})).toBeDisabled();
        rerender(<CtfSpecFields value={validSpec()} onChange={vi.fn()} serverNames={servers} editable={false} />);
        expect(screen.getByRole("button", {name: "Add nested guest"})).toBeDisabled();
    });

    it("lists only the guests on the flag's server and sets the flag's OS from the picked guest", () => {
        const onChange = vi.fn();
        const guests = [
            guest({operating_system: "windows"}),
            guest({name: "web-vm", domain: "w", server: "web"}),
        ];
        const spec = guestSpec(guests, [flag({id: "hv-root", server: "hv", path: "/r"})]);
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={servers} />);

        fireEvent.click(screen.getByRole("button", {name: "Edit flag hv-root"}));
        const dialog = screen.getByRole("dialog", {name: "Edit flag hv-root"});
        fireEvent.mouseDown(within(dialog).getByRole("combobox", {name: "Nested guest"}));
        const listbox = screen.getByRole("listbox");
        expect(within(listbox).getByRole("option", {name: "win-dc"})).toBeInTheDocument();
        expect(within(listbox).queryByRole("option", {name: "web-vm"})).not.toBeInTheDocument();
        fireEvent.click(within(listbox).getByRole("option", {name: "win-dc"}));

        expect(within(dialog).getByRole("combobox", {name: "Operating system"})).toHaveAttribute("aria-disabled", "true");
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));

        expect(onChange).toHaveBeenCalledTimes(1);
        const saved = onChange.mock.calls[0][0] as CtfSpec;
        expect(saved.flags[0]).toMatchObject({id: "hv-root", server: "hv", guest: "win-dc", operating_system: "windows"});
    });

    it("hides the Nested guest select when the flag's server has no guests", () => {
        const spec = guestSpec([guest({server: "web", name: "web-vm", domain: "w"})], [flag({id: "hv-root", server: "hv", path: "/r"})]);
        render(<CtfSpecFields value={spec} onChange={vi.fn()} serverNames={servers} />);
        fireEvent.click(screen.getByRole("button", {name: "Edit flag hv-root"}));
        const dialog = screen.getByRole("dialog", {name: "Edit flag hv-root"});
        expect(within(dialog).queryByRole("combobox", {name: "Nested guest"})).not.toBeInTheDocument();
    });

    it("renames a guest and the flags that reference it", () => {
        const onChange = vi.fn();
        const spec = guestSpec([guest()], [
            guestFlag(),
            flag({id: "hv-root", server: "hv", path: "/r"}),
        ]);
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={servers} />);

        fireEvent.click(screen.getByRole("button", {name: "Edit guest win-dc"}));
        const dialog = screen.getByRole("dialog", {name: "Edit guest win-dc"});
        fireEvent.change(within(dialog).getByLabelText(/^Name/), {target: {value: "dc-two"}});
        fireEvent.click(within(dialog).getByRole("button", {name: "Done"}));

        const saved = onChange.mock.calls[0][0] as CtfSpec;
        expect(saved.nested_guests?.[0].name).toBe("dc-two");
        expect(saved.flags[0].guest).toBe("dc-two");
        expect(saved.flags[1].guest ?? null).toBeNull();
    });

    it("disables Delete guest while a flag references it", () => {
        render(<CtfSpecFields value={guestSpec([guest()], [guestFlag()])} onChange={vi.fn()} serverNames={servers} />);
        expect(screen.getByRole("button", {name: "Delete guest win-dc"})).toBeDisabled();
    });

    it("deletes an unreferenced guest", () => {
        const onChange = vi.fn();
        const spec = guestSpec([guest()], [flag({server: "hv"})]);
        render(<CtfSpecFields value={spec} onChange={onChange} serverNames={servers} />);

        fireEvent.click(screen.getByRole("button", {name: "Delete guest win-dc"}));

        expect(onChange).toHaveBeenCalledWith({...spec, nested_guests: []});
    });
});
