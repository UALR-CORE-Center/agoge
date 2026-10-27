// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {ThemeProvider} from "@mui/material/styles";
import {act, cleanup, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {CtfStates} from "../../../services/Ctf/ctf.model";
import {darkTheme} from "../../../styles/theme";
import {CtfStateMapping, resolveCtfStatus} from "../../Common/Status/StateMapping";
import CtfStateChip from "./CtfStateChip";

// The app theme defines the custom `ready`/`neutral` palette keys the mapping uses.
const renderChip = (state: number) => {
    const view = render(<ThemeProvider theme={darkTheme}><CtfStateChip state={state} /></ThemeProvider>);
    const rerender = (next: number) =>
        view.rerender(<ThemeProvider theme={darkTheme}><CtfStateChip state={next} /></ThemeProvider>);
    return {...view, rerender};
};

describe("CtfStateMapping", () => {
    it("maps every CtfStates value to text, a theme palette colour and an icon", () => {
        const palette = darkTheme.palette as unknown as Record<string, unknown>;
        for (const value of Object.values(CtfStates)) {
            const status = CtfStateMapping[value];
            expect(status.text).not.toBe("");
            expect(palette[status.color as string]).toBeDefined();
            expect(React.isValidElement(status.icon)).toBe(true);
        }
    });

    it("resolves an unknown state to Unknown instead of a known label", () => {
        expect(resolveCtfStatus(99).text).toBe("Unknown");
        expect(resolveCtfStatus(CtfStates.BROKEN).text).toBe("Broken");
    });
});

describe("CtfStateChip", () => {
    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("renders the state label with its icon", () => {
        const {container} = renderChip(CtfStates.RUNNING);

        expect(screen.getByText("Running")).toBeInTheDocument();
        expect(container.querySelector(".MuiChip-icon")).not.toBeNull();
    });

    it("does not announce the initial state", () => {
        renderChip(CtfStates.ARMED);

        expect(screen.getByRole("status")).toHaveTextContent("");
    });

    it("announces a state change through the live region, then clears it", () => {
        vi.useFakeTimers();
        const {rerender} = renderChip(CtfStates.ARMING);

        rerender(CtfStates.BROKEN);

        const live = screen.getByRole("status");
        expect(live).toHaveAttribute("aria-live", "polite");
        expect(live).toHaveTextContent("CTF event status is now Broken");
        expect(screen.getByText("Broken")).toBeInTheDocument();

        act(() => {
            vi.advanceTimersByTime(800);
        });
        expect(live).toHaveTextContent("");
    });
});
