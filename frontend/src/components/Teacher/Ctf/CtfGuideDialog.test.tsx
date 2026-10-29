// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import {afterEach, describe, expect, it} from "vitest";
import CtfGuideDialog, {GUIDE_SECTIONS} from "./CtfGuideDialog";

afterEach(cleanup);

describe("CtfGuideDialog", () => {
    it("opens the guide with every section and closes it", async () => {
        const user = userEvent.setup();
        render(<CtfGuideDialog />);

        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", {name: "Open the game master guide"}));

        expect(screen.getByRole("dialog", {name: "Game Master Guide"})).toBeInTheDocument();
        for (const section of GUIDE_SECTIONS) {
            expect(screen.getByRole("button", {name: section.title})).toBeInTheDocument();
        }

        await user.click(screen.getByRole("button", {name: "Close"}));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });
});
