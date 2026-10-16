// @vitest-environment jsdom
import {act, cleanup, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import CtfBanner, {safeRulesUrl} from "./CtfBanner";

const BOARD: CtfStudentBoardResponse = {
    enrolled: true,
    ctf_id: "eventevent",
    name: "Spring CTF",
    description: null,
    rules_url: "https://example.edu/rules",
    state_name: "RUNNING",
    remaining_seconds: 3661,
    flag_format: "agoge{...}",
    score: 0,
    challenges: [],
    public_scoreboard_enabled: false,
};

const tick = (ms: number) => act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
});

describe("CtfBanner", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("is a section labelled by the event name, with state, time and rules link", () => {
        render(<CtfBanner board={BOARD} />);

        const section = screen.getByRole("region", {name: "Spring CTF"});
        expect(section.tagName).toBe("SECTION");
        expect(screen.getByRole("heading", {level: 2, name: "Spring CTF"})).toBeTruthy();
        expect(screen.getAllByText("Running").length).toBeGreaterThan(0);
        expect(screen.getByText("01:01:01")).toBeTruthy();

        const link = screen.getByRole("link", {name: /Rules of engagement/});
        expect(link.getAttribute("href")).toBe("https://example.edu/rules");
        expect(link.getAttribute("target")).toBe("_blank");
        expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    });

    it("counts down locally between board polls while running", async () => {
        render(<CtfBanner board={BOARD} />);
        await tick(5000);
        expect(screen.getByText("01:00:56")).toBeTruthy();
    });

    it("restarts the countdown from each new board snapshot", async () => {
        const {rerender} = render(<CtfBanner board={BOARD} />);
        await tick(10000);
        rerender(<CtfBanner board={{...BOARD, remaining_seconds: 100}} />);
        expect(screen.getByText("00:01:40")).toBeTruthy();
    });

    it("holds the clock while paused", async () => {
        render(<CtfBanner board={{...BOARD, state_name: "PAUSED"}} />);
        await tick(5000);
        expect(screen.getByText("01:01:01 (paused)")).toBeTruthy();
        expect(screen.getAllByText("Paused").length).toBeGreaterThan(0);
    });

    it("never counts below zero", async () => {
        render(<CtfBanner board={{...BOARD, remaining_seconds: 2}} />);
        await tick(5000);
        expect(screen.getByText("00:00:00")).toBeTruthy();
    });

    it("says so when the event has no end time", () => {
        render(<CtfBanner board={{...BOARD, state_name: "ARMED", remaining_seconds: null}} />);
        expect(screen.getByText("No end time")).toBeTruthy();
    });

    it("omits the rules link when there is no usable URL", () => {
        render(<CtfBanner board={{...BOARD, rules_url: null}} />);
        expect(screen.queryByRole("link")).toBeNull();
        cleanup();
        // A `javascript:` URL from the spec must never become a clickable link.
        render(<CtfBanner board={{...BOARD, rules_url: "javascript:alert(1)"}} />);
        expect(screen.queryByRole("link")).toBeNull();
    });

    it("falls back to a generic heading when the event has no name", () => {
        render(<CtfBanner board={{...BOARD, name: null}} />);
        expect(screen.getByRole("heading", {level: 2, name: "CTF event"})).toBeTruthy();
    });
});

describe("safeRulesUrl", () => {
    it("accepts only http and https URLs", () => {
        expect(safeRulesUrl("https://example.edu/rules")).toBe("https://example.edu/rules");
        expect(safeRulesUrl("http://example.edu/")).toBe("http://example.edu/");
        expect(safeRulesUrl("javascript:alert(1)")).toBeNull();
        expect(safeRulesUrl("data:text/html,hi")).toBeNull();
        expect(safeRulesUrl("not a url")).toBeNull();
        expect(safeRulesUrl("")).toBeNull();
        expect(safeRulesUrl(null)).toBeNull();
    });
});
