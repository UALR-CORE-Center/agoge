// @vitest-environment jsdom
import React from "react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { rubricService } from "../../../services/Rubric/rubric.service";
import HttpError from "../../Common/Errors/HttpError";
import UnitRubricEditor from "./UnitRubricEditor";

vi.mock("../../../context/AuthContext", () => ({
    useAuthContext: () => ({ firebaseUser: { user: { uid: "test-instructor" } } }),
}));
vi.mock("../../../services/Rubric/rubric.service", () => ({
    rubricService: { get: vi.fn(), generate_rubric: vi.fn(), patch: vi.fn() },
}));

const rubric = {
    build_id: "abcdefghij",
    categories: ["Configuration"],
    headers: ["Proficient"],
    criteria: [{ category: "Configuration", index: 0, description: "Complete configuration." }],
};
const quotaMessage = "Rubric generation is unavailable because the OpenAI API account has no credits remaining.";

function renderEditor(isExpired = false) {
    return render(
        <MemoryRouter>
            <UnitRubricEditor buildId={rubric.build_id} isExpired={isExpired} rubricEnabled />
        </MemoryRouter>
    );
}

describe("rubric editor", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(rubricService.get).mockResolvedValue(null);
        vi.mocked(rubricService.generate_rubric).mockResolvedValue(rubric);
    });
    afterEach(cleanup);

    it.each([undefined, false])("does not expose rubric tools without explicit lab opt-in (%s)", (enabled) => {
        render(<UnitRubricEditor buildId={rubric.build_id} isExpired={false} rubricEnabled={enabled} />);
        expect(screen.queryByRole("button", { name: "Manage Rubric" })).not.toBeInTheDocument();
        expect(rubricService.get).not.toHaveBeenCalled();
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
    });

    it("does not load or generate a rubric when the lab page mounts", () => {
        renderEditor();
        expect(rubricService.get).not.toHaveBeenCalled();
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
    });

    it("only looks up the rubric when opening or reopening the editor", async () => {
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));

        expect(await screen.findByText("No rubric has been created for this lab.")).toBeInTheDocument();
        expect(screen.getByText("AI generation uses OpenAI API credits.")).toBeInTheDocument();
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));

        expect(await screen.findByText("No rubric has been created for this lab.")).toBeInTheDocument();
        expect(rubricService.get).toHaveBeenCalledTimes(2);
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
    });

    it("retries a failed lookup without generating a rubric", async () => {
        vi.mocked(rubricService.get)
            .mockRejectedValueOnce(new HttpError(503, "Lookup unavailable."))
            .mockResolvedValueOnce(null);
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Lookup unavailable.");
        expect(screen.queryByRole("button", { name: "Generate with AI" })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry loading" }));

        expect(await screen.findByText("No rubric has been created for this lab.")).toBeInTheDocument();
        expect(rubricService.get).toHaveBeenCalledTimes(2);
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
    });

    it("keeps quota errors in the dialog and retries only on an explicit AI action", async () => {
        vi.mocked(rubricService.generate_rubric)
            .mockRejectedValueOnce(new HttpError(503, quotaMessage))
            .mockResolvedValueOnce(rubric);
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));
        fireEvent.click(await screen.findByRole("button", { name: "Generate with AI" }));

        expect(await screen.findByRole("alert")).toHaveTextContent(quotaMessage);
        expect(screen.getByRole("dialog")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
        expect(rubricService.generate_rubric).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByRole("button", { name: "Generate with AI" }));

        expect(await screen.findByDisplayValue("Complete configuration.")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(rubricService.generate_rubric).toHaveBeenCalledTimes(2);
        expect(rubricService.get).toHaveBeenCalledOnce();
    });

    it("shows the generated rubric without a second read or generation", async () => {
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));
        fireEvent.click(await screen.findByRole("button", { name: "Generate with AI" }));

        expect(await screen.findByDisplayValue("Complete configuration.")).toBeInTheDocument();
        expect(rubricService.get).toHaveBeenCalledOnce();
        expect(rubricService.generate_rubric).toHaveBeenCalledWith(
            rubric.build_id, expect.objectContaining({ id: rubric.build_id, confirm_ai_generation: true })
        );
        expect(rubricService.generate_rubric).toHaveBeenCalledOnce();
    });

    it("opens an existing rubric without calling the AI service", async () => {
        vi.mocked(rubricService.get).mockResolvedValue(rubric);
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));

        expect(await screen.findByDisplayValue("Complete configuration.")).toBeInTheDocument();
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
    });

    it("preserves unsaved edits and reports a save failure", async () => {
        vi.mocked(rubricService.get).mockResolvedValue(rubric);
        vi.mocked(rubricService.patch).mockRejectedValueOnce(new HttpError(503, "Save unavailable."));
        renderEditor();
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));
        fireEvent.change(await screen.findByDisplayValue("Complete configuration."), {
            target: { value: "Updated criterion." },
        });
        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Save unavailable.");
        expect(screen.getByDisplayValue("Updated criterion.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
        expect(rubricService.patch).toHaveBeenCalledWith(
            rubric.build_id,
            expect.objectContaining({ criteria: [expect.objectContaining({ description: "Updated criterion." })] })
        );
    });

    it("does not generate a missing rubric for an expired lab", async () => {
        renderEditor(true);
        fireEvent.click(screen.getByRole("button", { name: "Manage Rubric" }));

        expect(await screen.findByText("No rubric has been created for this lab.")).toBeInTheDocument();
        expect(rubricService.generate_rubric).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate with AI" })).not.toBeInTheDocument();
    });

    it("disables repeat requests while generation is in progress", async () => {
        let finishGeneration!: (value: typeof rubric) => void;
        vi.mocked(rubricService.generate_rubric).mockReturnValue(new Promise(resolve => {
            finishGeneration = resolve;
        }));
        renderEditor();
        const manageButton = screen.getByRole("button", { name: "Manage Rubric" });
        fireEvent.click(manageButton);
        const generateButton = await screen.findByRole("button", { name: "Generate with AI" });
        fireEvent.click(generateButton);
        await waitFor(() => expect(rubricService.generate_rubric).toHaveBeenCalledOnce());
        expect(manageButton).toBeDisabled();
        expect(generateButton).toBeDisabled();
        expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
        fireEvent.click(manageButton);
        fireEvent.click(generateButton);
        expect(rubricService.generate_rubric).toHaveBeenCalledOnce();

        await act(async () => finishGeneration(rubric));
        expect(screen.getByDisplayValue("Complete configuration.")).toBeInTheDocument();
    });
});
