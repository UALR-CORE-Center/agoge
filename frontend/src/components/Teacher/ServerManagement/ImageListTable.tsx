import Cancel from '@mui/icons-material/Cancel';
import ComputerIcon from '@mui/icons-material/Computer';
import DeleteForeverOutlinedIcon from '@mui/icons-material/DeleteForeverOutlined';
import LockOpenOutlinedIcon from '@mui/icons-material/LockOpenOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import {CircularProgress, Paper, Typography, Button} from '@mui/material';
import {GridColDef, GridRowSelectionModel} from "@mui/x-data-grid";
import {useModal} from "mui-modal-provider";
import React, {useCallback, useEffect, useState} from 'react';

import {useNavigate} from "react-router-dom";
import {useAuthContext} from '../../../context/AuthContext';
import {usePolling} from "../../../hooks/usePolling";
import {URL_TEACHER_SERVERS_CREATE, URL_TEACHER_SERVERS_EDITOR} from '../../../router/urls';
import {AgogeImage} from '../../../services/Server/image.model';
import {imageService} from '../../../services/Server/image.service';
import {ServerStates} from "../../../types/AgogeStates";
import {AppUiObjectNames} from "../../../types/AppObjectNames";
import {PubSub} from '../../../types/PubSub';

import {ServerConnectButton} from "../../Buttons/ConnectButton/ServerConnectButton";
import {SnapshotButton} from "../../Buttons/ControlButtons/SnapshotButton";
import {StartButton} from "../../Buttons/ControlButtons/StartButton";
import {StopButton} from "../../Buttons/ControlButtons/StopButton";
import {ExpandableCell} from "../../Common/DataGrid/ExpandableCell";
import StyledDataGrid, {ButtonConfig} from "../../Common/DataGrid/StyledDataGrid";
import ConfirmationDialog from '../../Common/Dialogs/ConfirmationDialog/Confirmation';
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import StatusBadge from '../../Common/Status/StatusBadge';
import {EditImageButton} from "./Buttons/EditImageButton";
import {ImageActionButton} from "./Buttons/ImageActionButton";
import {ConfirmCancelDialog} from "./ConfirmCancelDialog";
import {ImageDetailsDialog} from "./ImageDetailsDialog/ImageDetailsDialog";
import {resolveStatus} from "../../Common/Status/StateMapping";

type MessageSeverity = 'success' | 'error' | 'warning' | 'info';
type RowActions = "start" | "stop" | "checkIn" | "checkOut" | "snapshot" | "delete" | "cancel";
type ActiveRow = {open: boolean, row: AgogeImage | undefined}
type ActionButtons = {
    buttonId: string;
    start: boolean;
    stop: boolean;
    checkIn: boolean;
    checkOut: boolean;
    snapshot: boolean;
    delete: boolean;
    cancel: boolean;
}

const ImageListTable: React.FC = () => {
    const navigate = useNavigate();
    const { agogeUser } = useAuthContext();
    const {showModal} = useModal();
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [activeButton, setActiveButton] = useState<ActionButtons>({
        buttonId: "",
        start: false,
        stop: false,
        checkIn: false,
        checkOut: false,
        snapshot: false,
        delete: false,
        cancel: false,
    });
    const [activeImages, setImages] = useState<AgogeImage[]>([]);
    const [selectedRows, setSelectedRows] = useState<any[]>([]);
    const [openDeleteDialog, setOpenDeleteDialog] = useState<ActiveRow>(
        {
            open: false,
            row: undefined
        }
    );
    const [imageDialog, setImageDialog] = useState<boolean>(false);
    const [imageDialogContents, setImageDialogContents] = useState<AgogeImage | null>(null);
    const [imageName, setImageName] = useState<string>('');
    const [cancelModal, setCancelModal] = useState<ActiveRow>({open: false, row: undefined});
    const [cancelingRows, setCancelingRows] = useState<{ name: string, initialState: number }[]>([]);
    const [initialState, setInitialState] = useState<boolean>(true);

    const fetchImages = async (showLoading: boolean = false) => {
        if (showLoading) {
            setLoading(true);
        }
        try {
            const fetchedImages = await imageService.list();

            const imagesWithId = fetchedImages.map(image => ({
                ...image,
                id: image.name,
            }));

            setImages(prevImages => {
                if (JSON.stringify(prevImages) !== JSON.stringify(imagesWithId)) {
                    return imagesWithId;
                }
                return prevImages;
            });
        } catch (error: any) {
            console.error(error);
            if(error?.status !== 404) {
                setError("Unknown Error has occurred.");
            }
            setImages([]);
        } finally {
            if (showLoading) {
                setLoading(false);
                setInitialState(false);
            }
        }
    };


    const fetchImageCallback = useCallback(() => fetchImages(initialState), [initialState])
    usePolling(fetchImageCallback, {enabled: true})
    useEffect(() => {
        const updatedCancelingRows = cancelingRows.filter(({ name, initialState }) => {
            const correspondingImage = activeImages.find(image => image.name === name);
            return correspondingImage && correspondingImage.state === initialState;
        });

        if (updatedCancelingRows !== cancelingRows) {
            setCancelingRows(updatedCancelingRows);
        }
    }, [activeImages]);

    if (error) {
        return <Typography color="error">{error}</Typography>;
    }

    const handlePostRequest = async (action: string, row) => {
        try {
            await imageService.post_action([row], action);
        } catch (error: any) {
            if(error?.status === 503){
                showSnackbar("error","Image is still processing. Please try again in a short time.")
            }
            console.error('Error', error);
        }
    };

    const showSnackbar = (severity: MessageSeverity, message: string) => {
        showModal(SimpleSnackbar, {
            message: message,
            severity: severity,
        });
    }

    const buttonController = async (
        action: RowActions,
        severity: MessageSeverity,
        message: string,
        row: AgogeImage
    ) => {
        switch (action) {
            case 'checkOut':
                setActiveButton((prevState) => (
                    {...prevState, [action]: true, buttonId: row.name}
                ));

                showSnackbar(severity, message);
                await handlePostRequest(String(PubSub.Actions.CHECK_OUT), row);
                break;
            case 'checkIn':
                setActiveButton((prevState) => (
                    {...prevState, [action]: true, buttonId: row.name}
                ));
                showSnackbar(severity, message);
                await handlePostRequest(String(PubSub.Actions.CHECK_IN), row);
                break;
            case 'delete':
                setImageName(row?.name || '');
                setOpenDeleteDialog({open: true, row: row});
                break;
            case 'cancel':
                setImageName(row?.name || '');
                setCancelModal({open: true, row: row});
                break;
            default:
                console.error(message);
                showSnackbar('error', 'An error occurred');
                break;
        }
        setActiveButton((prevState) => ({...prevState, [action]: false, buttonId: ""}));
        fetchImages(false);
    };

    const handleConfirmDelete = async () => {
        const activeRow = openDeleteDialog.row;
        if (!activeRow) return;
        setOpenDeleteDialog({open: false, row: undefined});
        setActiveButton((prevState) => (
            {...prevState, delete: true, buttonId: activeRow.name}
        ));
        try {
            showSnackbar('warning', 'Server deletion task started ...');
            await imageService.delete_image(activeRow.name);
        } catch (error) {
            console.error('Error deleting server:', error);
            showSnackbar('error', 'Failed to delete server')
        } finally {
            setActiveButton((prevState) => (
                {...prevState, delete: false, buttonId: ""}
            ));
            setImageName('');
        }
    };

    const handleConfirmCancel = async () => {
        const selectedRow = cancelModal.row;
        if (!selectedRow) {
            return;
        }

        if (!cancelingRows.some(r => r.name === selectedRow?.name)) {
            setCancelingRows((prevCancelingRows) => [
                ...prevCancelingRows,
                { name: selectedRow.name, initialState: selectedRow.state }
            ]);
        }

        setActiveButton((prevState) => (
            {...prevState, checkIn: true, cancel: true, buttonId: selectedRow.name}
        ))
        setCancelModal({open: false, row: undefined});
        try {
            if (selectedRow?.image_exists) {
                await handlePostRequest(String(PubSub.Actions.CANCEL), selectedRow);
            } else{
                await imageService.delete_image(selectedRow.name)
            }
        } catch (error) {
            showSnackbar('error', "Failed to cancel changes.");
        } finally {
            showSnackbar('success', "Successfully canceled changes.");
            setImageName('');
            setActiveButton((prevState) => (
                {...prevState, checkIn: true, cancel: true, buttonId: ""}
            ));
        }
    };

    const handleCloseDeleteDialog = () => {
        setOpenDeleteDialog({open: false, row: undefined});
        setActiveButton((prevState) => (
            {...prevState, delete: false, buttonId: ""}
        ));
        setImageName('');
    };

    const handleCancelModalClose = () => {
        setActiveButton((prevState) => (
            {...prevState, cancel: false, buttonId: ""}
        ));
        setCancelModal({open: false, row: undefined});
    };

    const handleImageDialogClose = () => {
        setImageDialog(false);
        setImageDialogContents(null);
    }

    const handleImageDialogBtn = (rowData: AgogeImage)  => {
        setImageDialogContents(rowData);
        setImageDialog(true);
    }

    const handleImageEditorBtn = (rowData: AgogeImage) =>{
        navigate(`${URL_TEACHER_SERVERS_EDITOR}/${rowData.id}`);
    }

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        const selectedRowData = activeImages.filter((row) => selectionModel.includes(row.name));
        setSelectedRows(selectedRowData);
    };

    const isRowActionDisabled = (action: RowActions, row: AgogeImage) => {
        let disabled = false;
        if ("checkOut" === action) {
            disabled = [ServerStates.STOPPED, ServerStates.RUNNING].includes(row.state);
        } else if (["checkIn", "cancel", "snapshot"].includes(action)) {
            disabled = [ServerStates.START].includes(row.state);
        } else if (action === "start") {
            disabled = [ServerStates.START, ServerStates.RUNNING].includes(row.state);
        } else if (action === "stop") {
            disabled = [ServerStates.START, ServerStates.STOPPED].includes(row.state);
        }
        return disabled || loading || activeButton[action];
    }

    const imageRowActions = (row: AgogeImage) => {
        const isCheckedOut = [
            ServerStates.STOPPED,
            ServerStates.STOPPING,
            ServerStates.STARTING,
            ServerStates.RUNNING
        ].includes(row.state);
        const isCheckedIn = [ServerStates.START].includes(row.state);

        return (
            <>
                {isCheckedIn && (
                    <ImageActionButton
                        title={"Check Out Template Server"}
                        controlType={"server"}
                        iconButton={true}
                        iconProps={{
                            label: "check out template server button",
                            color: "info"
                        }}
                        onClick={() => buttonController(
                            'checkOut',
                            'success',
                            'Checking out server... This may take up to 2 minutes',
                            row
                        )}
                        row={row}
                        Icon={LockOutlinedIcon}
                        isDisabled={isRowActionDisabled("checkOut", row)}
                        loading={activeButton.checkOut && activeButton.buttonId == row.name}
                    />
                )}
                {isCheckedOut && (
                    <ImageActionButton
                        title={"Check In Template Server"}
                        controlType={"server"}
                        iconButton={true}
                        iconProps={{
                            label: "check in template server button",
                            color: "info"
                        }}
                        onClick={() => buttonController(
                            'checkIn',
                            'success',
                            'Checking in server... This may take up to 2 minutes',
                            row
                        )}
                        row={row}
                        Icon={LockOpenOutlinedIcon}
                        isDisabled={isRowActionDisabled("checkIn", row)}
                        loading={activeButton.checkIn && activeButton.buttonId == row.name}
                    />
                )}
                <StartButton
                    title={"Start Template Server"}
                    label={"Start Template Server"}
                    controlType={"server"}
                    iconButton={true}
                    iconProps={{
                        size: "medium",
                        label: "start template server button"
                    }}
                    isDisabled={isRowActionDisabled("start", row)}
                    row={row}
                    data={[row]}
                />
                <StopButton
                    title={"Stop Template Server"}
                    label={"Stop Template Server"}
                    controlType={"server"}
                    iconButton={true}
                    iconProps={{
                        size: "medium",
                        label: "stop template server button"
                    }}
                    isDisabled={isRowActionDisabled("stop", row)}
                    row={row}
                    data={[row]}
                />
                {isCheckedOut && (
                    <SnapshotButton
                        title={"Manage Template Server Snapshots"}
                        controlType={"server"}
                        iconButton={true}
                        iconProps={{
                            label: "manage template server snapshots button",
                            fontSize: "small",
                        }}
                        row={row}
                        isDisabled={isRowActionDisabled("snapshot", row)}
                    />
                )}
                <EditImageButton
                    title={'Edit template server image'}
                    row={row}
                    onClick={handleImageEditorBtn}
                />
                {isCheckedOut && (
                    <ImageActionButton
                        title={"Cancel Template Server Changes"}
                        controlType={"server"}
                        iconButton={true}
                        iconProps={{
                            label: "cancel template server changes button",
                            color: "error"
                        }}
                        onClick={() => buttonController(
                            'cancel',
                            'success',
                            'Canceling server changes... This may take up to 2 minutes',
                            row
                        )}
                        row={row}
                        Icon={Cancel}
                        isDisabled={isRowActionDisabled("cancel", row)}
                        loading={activeButton.cancel && activeButton.buttonId == row.name}
                    />
                )}
                {!!(agogeUser && agogeUser.user?.permissions && agogeUser.user.permissions.admin) && (
                    <ImageActionButton
                        title={"Delete Template Server Image"}
                        controlType={"server"}
                        iconButton={true}
                        iconProps={{label: "delete template server button", color: "error"}}
                        onClick={() => buttonController(
                            'delete',
                            'success',
                            'Deleting template server... This may take up to 2 minutes',
                            row
                        )}
                        row={row}
                        Icon={DeleteForeverOutlinedIcon}
                        isDisabled={isRowActionDisabled("delete", row)}
                        loading={activeButton.delete && activeButton.buttonId == row.name}
                    />
                )}
            </>
        );
    }

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Create Image",
                variant: 'contained',
                color: "primary",
                icon: <ComputerIcon />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Create a new server image",
                onClick: () => navigate(URL_TEACHER_SERVERS_CREATE)
            }
        ];
        return buttonConfig;
    }

    const newColumns: GridColDef[] = [
        {
            field: 'state',
            headerName: 'State',
            align: 'center',
            minWidth: 120,
            renderCell: (params: any) => {
                const isLoading = ![0, 4, 6, 11].includes(params.value);
                const status = resolveStatus("server",params.value)

                return (
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            height: '100%',
                            width: '100%'
                        }}
                    >
                        {isLoading ? (
                            <CircularProgress size={24} />
                        ) : (
                            <StatusBadge color={status.color} label={status.text} sx={{ color: "black" }} />
                        )}
                    </div>
                );
            }
        },
        {
            field: 'name',
            headerName: 'Name',
            minWidth: 150,
            filterable: true,
            sortable:true,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value || 'N/A'}
                    variant={"body1"}
                />
            )
        },
        {
            field: 'status',
            headerName: 'Availability',
            minWidth: 120,
            renderCell: (params: any) => {
                const status = resolveStatus("image", params.value);
                return (
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            height: '100%',
                            width: '100%'
                        }}
                    >
                        <StatusBadge color={status.color} label={status.text} />
                    </div>
                );
            }
        },
        {
            field: 'in_use_by',
            headerName: 'In use by',
            width: 200,
            filterable: true,
            sortable:true,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value || ' '}
                    variant={"body1"}
                />
            )
        },
        {
            field: 'imageDetails',
            headerName: 'Details',
            width: 150,
            filterable: false,
            sortable: false,
            renderCell: (params: any) => (
                <Button onClick={() => handleImageDialogBtn(params.row)}>
                    View Details
                </Button>
            )
        },
        {
            field: 'connect',
            headerName: 'Connect',
            width: 150,
            renderCell: (params: any) => (
                <ServerConnectButton item={params.row} />
            )
        },
        {
            field: 'imageActions',
            headerName: 'Actions',
            minWidth: 150,
            filterable: false,
            sortable: false,
            renderCell: (params: any) => (imageRowActions(params.row))
        },
    ];

    return (
        <>
            <Paper
                elevation={1}
                square={false}
                sx={{ padding: "10px" }}
            >
                <StyledDataGrid
                    data={activeImages}
                    columns={newColumns}
                    disableMultiRowSelection={true}
                    disableSelectBtn={false}
                    disableRowSelectionOnClick={true}
                    localeText={{noRowsLabel: "No images found"}}
                    labelProps={{
                        text: `${AppUiObjectNames.SERVER_MANAGER}`,
                        icon: <ComputerIcon fontSize={"large"} />,
                    }}
                    density={"comfortable"}
                    loading={loading}
                    buttonsConfig={getButtonConfig()}
                    onSelection={handleRowSelection}
                    selectedRow={selectedRows}
                />
            </Paper>
            <ConfirmationDialog
                open={openDeleteDialog.open}
                action={"delete"}
                onClose={handleCloseDeleteDialog}
                handleConfirm={handleConfirmDelete}
                expectedText={imageName}
                loading={activeButton.delete}
            />
            <ConfirmCancelDialog
                open={cancelModal.open}
                onClose={handleCancelModalClose}
                description={`Are you sure you want to cancel changes to ${imageName}?`}
                onCancel={handleConfirmCancel}
            />
            <ImageDetailsDialog
                open={imageDialog}
                image={imageDialogContents}
                onClose={handleImageDialogClose}
                loading={loading}
            />
        </>
    );
};

export default ImageListTable;