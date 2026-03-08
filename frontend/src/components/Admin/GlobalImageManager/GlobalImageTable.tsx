import {Check, CheckOutlined, CloudSyncOutlined, Memory, Refresh} from "@mui/icons-material";
import {Clear as ClearIcon} from "@mui/icons-material";
import {Chip, useTheme} from "@mui/material";
import {GridColDef, GridRenderCellParams, GridRowSelectionModel} from "@mui/x-data-grid";
import {useModal} from "mui-modal-provider";
import React, {useEffect, useState} from "react";
import {GlobalComputeImage} from "../../../services/Server/image.model";
import {serverService} from "../../../services/Server/server.service";
import {ExpandableCell} from "../../Common/DataGrid/ExpandableCell";
import StyledDataGrid, {ButtonConfig} from "../../Common/DataGrid/StyledDataGrid";
import ConfirmationListDialog from "../../Common/Dialogs/ConfirmationDialog/ConfirmationListDialog";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";

export const GlobalImageTable: React.FC = () => {
    const { showModal } = useModal();
    const [globalImages, setGlobalImages] = useState<GlobalComputeImage[]>([]);
    const [flattenedData, setFlattenedData] = useState<any[]>([]);
    const [selectedRows, setSelectedRows] = useState<any[]>([]);
    const [selectedRowNames, setSelectedRowNames] = useState<string[]>([]);
    const [confirmationDialogOpen, setConfirmationDialogOpen] = useState<boolean>(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [disableLoading, setDisableLoading] = useState<boolean>(false);
    const [enableLoading, setEnableLoading] = useState<boolean>(false);
    const [syncLoading, setSyncLoading] = useState<boolean>(false);
    const [refreshLoading, setRefreshLoading] = useState<boolean>(false);
    const theme = useTheme();

    const fetchImages = async (isRefresh = false) => {
        try {
            const fetchedImages = await serverService.list_global();
            setGlobalImages(fetchedImages);
        } catch (error) {
            console.error('Error fetching global images: ', error);
        } finally {
            if (!isRefresh) setLoading(false);
        }
    }

    useEffect(() => {
        fetchImages();
    }, []);

    useEffect(() => {
        const flattenData = () => {
            const flattened = globalImages.map(item => ({
                id: item.uuid,
                name: item.name,
                image: item.image,
                family: item.family,
                project: item.project,
                self_link: item.self_link,
                is_enabled: item.is_enabled,
                description: item.description
            }));
            setFlattenedData(flattened);
        }

        flattenData();
    }, [globalImages]);

    useEffect(() => {
        const interval = setInterval(() => {
            fetchImages();
        }, 1000 * 90);

        return () => clearInterval(interval);
    }, []);

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        const selectedData = globalImages.filter(
            row => selectionModel.includes(row.uuid)
        );
        setSelectedRows(selectedData);

        const selectedNames = selectedData.map(row => row.name);
        setSelectedRowNames(selectedNames);
    };

    const handleRequest = async (action: "disable" | "enable") => {
        if (selectedRows.length !== 0) {
            let loadingState: (arg0: boolean) => void;
            if (action === "disable") {
                loadingState = setDisableLoading;
            } else {
                loadingState = setEnableLoading;
            }
            loadingState(true);
            setErrorMessage(null);

            await serverService.post(selectedRows, action)
                .then((resp) => {
                    setGlobalImages(resp);
                    loadingState(false);
                })
                .catch((error) => {
                    console.error(`Request failed with error: ${error}`);
                    showModal(SimpleSnackbar, {
                        message: error ? error.message : "Error making request",
                        severity: "error"
                    });
                    loadingState(false);
                    setErrorMessage(error);
                });
        }
    }

    const handleEnable = async () => {
        return handleRequest("enable");
    }

    const handleDisable = async () => {
        await handleRequest("disable")
            .then(() => handleCloseDialog());
        return;
    }

    const handleSync = async () => {
        setSyncLoading(true);
        showModal(SimpleSnackbar, {
           message: "Sync task started. This could take a couple of minutes...",
           severity: "info"
        });

        await serverService.sync()
            .then((resp) => {
                setErrorMessage(null);
                setSyncLoading(false);
            }).catch((error) => {
                showModal(SimpleSnackbar, {
                    message: error ? error.message : "Error making request",
                    severity: "error"
                });
                setErrorMessage(error);
                setSyncLoading(false);
            });
    }

    const handleRefresh = async () => {
        setRefreshLoading(true);
        showModal(SimpleSnackbar, {
            message: "Refreshing ...",
            severity: "info"
        });
        await fetchImages();
        showModal(SimpleSnackbar, {
            message: "Image table updated",
            severity: "success"
        });
        setRefreshLoading(false);
    }

    const handleCloseDialog = () => {
        setConfirmationDialogOpen(false);
        setSelectedRows([]);
        setSelectedRowNames([]);
    }

    const projectColor = (project: string) => {
        if (project === 'windows-cloud' || project === 'windows-sql-cloud') {
            if(theme.palette.mode === 'dark'){
                return "";
            }
        } else {
            return "secondary";
        }
    }

    const columns: GridColDef[] = [
        {
            field: 'name',
            headerName: 'Name',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                    missingText={"No image name."}
                />
            ),
        },
        {
            field: 'description',
            headerName: "Description",
            flex: 1,
            filterable: true,
            sortable: false,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                    missingText={"No image description."}
                />
            ),
        },
        {
            field: 'project',
            headerName: 'Project',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value}
                    variant={"filled"}
                    sx={{backgroundColor: projectColor(params.value)}}
                />
            ),
        },
        {
            field: 'is_enabled',
            headerName: 'Enabled',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value ? (
                        <Check color={"success"} aria-hidden={false} aria-label={`${params.row.name} is enabled`}/>
                    ) : (
                        <ClearIcon color="error" aria-hidden={false} aria-label={`${params.row.name} is disabled`}/>
                    )}
                </div>
            ),
        },
    ]

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Sync",
                variant: 'contained',
                color: "info",
                icon: <CloudSyncOutlined />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Sync database with latest images.",
                onClick: handleSync,
                loading: syncLoading,
            },
            {
                label: "Enable",
                variant: 'contained',
                color: "success",
                icon: <CheckOutlined />,
                requiresSelection: true,
                addTooltip: true,
                tooltip: "Enable selected global compute images for custom server usage",
                onClick: handleEnable,
                loading: enableLoading,
            },
            {
                label: "Disable",
                variant: 'contained',
                color: "secondary",
                icon: <ClearIcon />,
                requiresSelection: true,
                addTooltip: true,
                tooltip: "Disable selected global compute images from custom server usage. " +
                    "Does not effect existing custom servers.",
                onClick: () => setConfirmationDialogOpen(true),
                loading: disableLoading
            },
            {
                label: "Refresh",
                variant: "contained",
                color: "inherit",
                icon: <Refresh />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Refresh table with database",
                onClick: () => handleRefresh(),
                loading: refreshLoading,
            }
        ]
        return buttonConfig;
    }

    return (
        <>
            <StyledDataGrid
                data={flattenedData}
                columns={columns}
                disableMultiRowSelection={false}
                disableSelectBtn={false}
                disableRowSelectionOnClick={true}
                labelProps={{
                    text: `Public Images`,
                    icon: <Memory fontSize={"large"} />,
                }}
                loading={loading}
                buttonsConfig={getButtonConfig()}
                onSelection={handleRowSelection}
                selectedRow={selectedRows}
            />
            <ConfirmationListDialog
                open={confirmationDialogOpen}
                handleClose={handleCloseDialog}
                handleConfirm={handleDisable}
                items={selectedRowNames}
                confirmText={"disable"}
                confirmType={"disable"}
                loading={disableLoading}
            />
        </>
    )
}
