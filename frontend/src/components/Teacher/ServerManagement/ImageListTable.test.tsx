// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import React from "react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {imageService} from "../../../services/Server/image.service";
import {ServerStates} from "../../../types/AgogeStates";
import {PubSub} from "../../../types/PubSub";
import ImageListTable from "./ImageListTable";

vi.mock("react-router-dom", () => ({useNavigate: () => vi.fn()}));
vi.mock("mui-modal-provider", () => ({useModal: () => ({showModal: vi.fn()})}));
vi.mock("../../../context/AuthContext", () => ({
    useAuthContext: () => ({agogeUser: {user: {permissions: {admin: true}}}}),
}));
vi.mock("../../../hooks/usePolling", () => ({
    // Run the callback once, like the first poll tick.
    usePolling: (callback: () => void, options: { enabled: boolean }) => {
        const ref = React.useRef(callback);
        ref.current = callback;
        React.useEffect(() => {
            if (options.enabled) ref.current();
        }, [options.enabled]);
    },
}));
vi.mock("../../../services/Server/image.service", () => ({
    imageService: {list: vi.fn(), post_action: vi.fn(), delete_image: vi.fn()},
}));
vi.mock("../../../services/Server/nested.service", () => ({
    nestedService: {get_build_status: vi.fn()},
}));
// The real grid virtualizes columns and rows, which jsdom cannot lay out; render only the actions cell.
vi.mock("../../Common/DataGrid/StyledDataGrid", () => ({
    default: ({data, columns}: { data: any[], columns: any[] }) => {
        const actions = columns.find(column => column.field === "imageActions");
        return <div>{data.map(row => <div key={row.name}>{actions.renderCell({row})}</div>)}</div>;
    },
}));
vi.mock("../../Buttons/ConnectButton/ServerConnectButton", () => ({ServerConnectButton: () => null}));
vi.mock("../../Buttons/ControlButtons/SnapshotButton", () => ({SnapshotButton: () => null}));
vi.mock("../../Buttons/ControlButtons/StartButton", () => ({StartButton: () => null}));
vi.mock("../../Buttons/ControlButtons/StopButton", () => ({StopButton: () => null}));
vi.mock("./Buttons/EditImageButton", () => ({EditImageButton: () => null}));
vi.mock("./ImageDetailsDialog/ImageDetailsDialog", () => ({ImageDetailsDialog: () => null}));
vi.mock("./SharedImageCopyDialog", () => ({SharedImageCopyDialog: () => null}));
vi.mock("./SharedImageWarningDialog", () => ({SharedImageWarningDialog: () => null}));

const checkedOutImage = (imageExists: boolean) => ({
    name: "kali-template",
    state: ServerStates.STOPPED,
    is_shared: false,
    can_edit_shared: false,
    image_exists: imageExists,
});

describe("ImageListTable cancel changes", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(imageService.post_action).mockResolvedValue(undefined as never);
    });
    afterEach(cleanup);

    it.each([false, true])(
        "cancels a checked-out local image with CANCEL and never deletes it when image_exists is %s",
        async (imageExists) => {
            vi.mocked(imageService.list).mockResolvedValue([checkedOutImage(imageExists)] as never);
            render(<ImageListTable />);

            fireEvent.click(await screen.findByRole("button", {name: "cancel template server changes button"}));
            fireEvent.click(await screen.findByRole("button", {name: "Confirm"}));

            await waitFor(() => expect(imageService.post_action).toHaveBeenCalledTimes(1));
            expect(imageService.post_action).toHaveBeenCalledWith(
                [expect.objectContaining({name: "kali-template", image_exists: imageExists})],
                String(PubSub.Actions.CANCEL),
                false,
            );
            expect(imageService.delete_image).not.toHaveBeenCalled();
        },
    );
});
