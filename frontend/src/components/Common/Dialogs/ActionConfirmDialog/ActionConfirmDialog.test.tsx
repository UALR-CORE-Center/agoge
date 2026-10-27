// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import React from "react";
import {afterEach, describe, expect, it, vi} from "vitest";
import ActionConfirmDialog from "./ActionConfirmDialog";

const renderDialog = (overrides: Partial<React.ComponentProps<typeof ActionConfirmDialog>> = {}) => {
    const props = {
        open: true,
        title: "Start event?",
        message: "Students can begin submitting flags.",
        confirmLabel: "Start",
        onConfirm: vi.fn(),
        onClose: vi.fn(),
        loading: false,
        ...overrides,
    };
    render(<ActionConfirmDialog {...props} />);
    return props;
};

describe("ActionConfirmDialog", () => {
    afterEach(cleanup);

    it("renders the title, message and confirm label as an accessible dialog", () => {
        renderDialog();

        const dialog = screen.getByRole("dialog", {name: "Start event?"});
        expect(dialog).toHaveAccessibleDescription("Students can begin submitting flags.");
        expect(screen.getByRole("button", {name: "Start"})).toBeEnabled();
        expect(screen.getByRole("button", {name: "Cancel"})).toBeEnabled();
    });

    it("renders nothing when closed", () => {
        renderDialog({open: false});

        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("calls onConfirm, not onClose, when the confirm button is clicked", () => {
        const props = renderDialog();

        fireEvent.click(screen.getByRole("button", {name: "Start"}));

        expect(props.onConfirm).toHaveBeenCalledTimes(1);
        expect(props.onClose).not.toHaveBeenCalled();
    });

    it("calls onClose on Cancel and on Escape", () => {
        const props = renderDialog();

        fireEvent.click(screen.getByRole("button", {name: "Cancel"}));
        fireEvent.keyDown(screen.getByRole("dialog"), {key: "Escape"});

        expect(props.onClose).toHaveBeenCalledTimes(2);
        expect(props.onConfirm).not.toHaveBeenCalled();
    });

    // While the request runs the dialog must stay up so its outcome is visible.
    it("disables both buttons and ignores Escape while loading", () => {
        const props = renderDialog({loading: true});

        expect(screen.getByRole("button", {name: /Start/})).toBeDisabled();
        expect(screen.getByRole("button", {name: "Cancel"})).toBeDisabled();
        fireEvent.keyDown(screen.getByRole("dialog"), {key: "Escape"});

        expect(props.onClose).not.toHaveBeenCalled();
        expect(props.onConfirm).not.toHaveBeenCalled();
    });

    it("accepts rich message content", () => {
        renderDialog({message: <span>This hint costs <strong>50</strong> points.</span>});

        expect(screen.getByRole("dialog")).toHaveAccessibleDescription("This hint costs 50 points.");
    });
});
