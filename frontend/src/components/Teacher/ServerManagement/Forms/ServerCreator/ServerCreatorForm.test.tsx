// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import React from "react";
import {createMemoryRouter, RouterProvider} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {URL_TEACHER_SERVERS} from "../../../../../router/urls";
import {imageService} from "../../../../../services/Server/image.service";
import ServerCreatorForm from "./ServerCreatorForm";

// A real data-router navigation builds a fetch Request, which jsdom's AbortSignal cannot satisfy under Node's undici.
const navigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (importOriginal) => ({
    ...await importOriginal<typeof import("react-router-dom")>(),
    useNavigate: () => navigate,
}));
vi.mock("../../../../../services/Server/image.service", () => ({
    imageService: {create: vi.fn()},
}));
vi.mock("./ImageTemplateSelector/ImageSelectTable", () => ({
    ImageSelectTable: ({onSelect}: {onSelect: (row: unknown) => void}) => (
        <button
            type="button"
            onClick={() => onSelect({
                id: "debian-12-bookworm-v20261001",
                name: "debian-12-bookworm-v20261001",
                family: "debian-12",
                os: "linux",
                disk_size: 10,
                project: "debian-cloud",
                architecture: "X86_64",
            })}
        >
            pick debian
        </button>
    ),
}));
vi.mock("../NestedImage/NestedImageWizard", () => ({
    default: () => <div>nested wizard</div>,
}));

// The form uses react-router's data-router <Form>, so it needs a data router rather than MemoryRouter.
const renderForm = () => {
    const router = createMemoryRouter([{path: "/", element: <ServerCreatorForm />}]);
    return render(<RouterProvider router={router} />);
};

describe("ServerCreatorForm", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(imageService.create).mockResolvedValue({} as never);
    });
    afterEach(cleanup);

    it("is headed Create Server and switches to the nested wizard", () => {
        renderForm();

        expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("Create Server");
        expect(screen.queryByText("Edit Server")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Standard VM"})).toHaveAttribute("aria-pressed", "true");

        fireEvent.click(screen.getByRole("button", {name: "Nested lab host"}));
        expect(screen.getByText("nested wizard")).toBeInTheDocument();
        expect(screen.queryByRole("button", {name: "Create Server"})).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: "Standard VM"}));
        expect(screen.queryByText("nested wizard")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "Create Server"})).toBeInTheDocument();
    });

    it("submits the standard body with the display key the API reads", async () => {
        renderForm();

        fireEvent.change(screen.getByRole("textbox", {name: /Server Name/}),
            {target: {value: "web-01"}});
        fireEvent.click(screen.getByRole("button", {name: /Server Image/}));
        fireEvent.click(screen.getByRole("button", {name: "pick debian"}));
        fireEvent.mouseDown(screen.getByRole("combobox"));
        fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", {name: /e2-medium/}));
        fireEvent.click(screen.getByRole("checkbox", {name: "Enable display"}));
        fireEvent.change(screen.getByRole("textbox", {name: /Server description/}),
            {target: {value: "A web server"}});
        fireEvent.change(screen.getByRole("textbox", {name: "Username"}), {target: {value: "gm"}});
        fireEvent.change(screen.getByRole("textbox", {name: /SSH Public Key/}),
            {target: {value: "ssh-ed25519 AAAA gm@laptop"}});

        fireEvent.click(screen.getByRole("button", {name: "Create Server"}));

        await waitFor(() => expect(imageService.create).toHaveBeenCalledTimes(1));
        expect(vi.mocked(imageService.create).mock.calls[0][0]).toEqual({
            server_name: "web-01",
            machine_type: "e2-medium",
            os: "linux",
            disk_size: "10",
            display: "true",
            description: "A web server",
            labels: "",
            username: "gm",
            ssh_key: "ssh-ed25519 AAAA gm@laptop",
            image_template: "debian-12-bookworm-v20261001",
            image_scope: "global",
        });
        await waitFor(() => expect(navigate).toHaveBeenCalledWith(URL_TEACHER_SERVERS));
    });
});
