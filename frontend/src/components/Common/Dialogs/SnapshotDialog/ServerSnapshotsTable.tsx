import {AddAPhoto, Restore} from "@mui/icons-material";
import {Box} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import {useModal} from "mui-modal-provider";
import React, {useState} from "react";
import {SnapshotsModel} from "../../../../services/Server/snapshots.model";
import {snapshotService} from "../../../../services/Server/snapshots.service";
import {PubSub} from "../../../../types/PubSub";
import StyledDataGrid, {ButtonConfig} from "../../DataGrid/StyledDataGrid";
import SimpleSnackbar from "../../SnackBar/SnackBar";
import StatusBadge from "../../Status/StatusBadge";
import {CourseObject, SnapshotAction} from "./types";
import DeleteIcon from "@mui/icons-material/Delete";

interface Props {
    disabled: boolean;
    loading: boolean;
    data: SnapshotsModel;
    buildId?: string;
    courseObject: CourseObject;
    refreshing: boolean;
}


const InitialProcessingState = {
    loading: false,
    action: undefined
}

export const ServerSnapshotsTable: React.FC<Props> = (props) => {
    const {showModal} = useModal();
    const snapshots = props.data.snapshots!;
    const serverId = props.data.server_id;
    const [selectedRows, setSelectedRows] = useState<any[]>([]);
    const [processing, setIsProcessing] = useState<{
        loading: boolean,
        action: SnapshotAction
    }>(InitialProcessingState);

    const convertTimestamp = (timestamp?: number): string => {
        return timestamp ? new Date(timestamp * 1000).toLocaleString() : 'N/A';
    };

    const buttonController = async (action: SnapshotAction) => {
        let course_object;
        if (props.courseObject === "templateServer") {
            course_object = PubSub.CourseObjects.TEMPLATE_SERVER;
        } else {
            course_object = PubSub.CourseObjects.LAB_SERVER;
        }

        try {

            if (action === "snapshot") {
                setIsProcessing({action: action, loading: true});
                const buildId = props?.buildId ? props.buildId : undefined;
                await snapshotService.put(
                    serverId,
                    course_object,
                    PubSub.Actions.SNAPSHOT,
                    undefined,
                    buildId
                );
            } else if (action === "restore") {
                setIsProcessing({action: action, loading: true});
                if (selectedRows.length === 0) {
                    return;
                }
                const snapshotName = selectedRows[0];
                await snapshotService.put(
                    serverId,
                    course_object,
                    PubSub.Actions.RESTORE,
                    snapshotName
                );
            } else if (action === 'delete') {
                setIsProcessing({action: action, loading: true});
                if (selectedRows.length === 0) {
                    return;
                }
                const snapshotName = selectedRows[0];
                await snapshotService.delete_(
                    serverId,
                    snapshotName,
                    course_object
                );
            }
            showModal(SimpleSnackbar, {
                message: `Processing ${action} request. This could take up to 3 minutes.`,
                severity: "success",
            });
        } catch (error) {
            console.log(error);
            showModal(SimpleSnackbar, {
                message: error ? error.message : "Error making request",
                severity: "error"
            });
        } finally {
            setIsProcessing({action: undefined, loading: false});
        }
    }

    const isTableHeaderButtonDisabled = (action: SnapshotAction) => {
        if (props.disabled) {
            return true;
        }
        if (['delete', 'restore'].includes(String(action))) {
            const availableSnapshots = props.data?.snapshots;
            if (selectedRows.length === 0) {
                return true;
            } else if (availableSnapshots && availableSnapshots.length > 0) {
                return false;
            }
        } else {
            return false;
        }
    }

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Snapshot",
                variant: 'contained',
                color: 'success',
                requiresSelection: false,
                icon: <AddAPhoto />,
                addTooltip: true,
                tooltip: "Take a snapshot of server",
                onClick: () => buttonController('snapshot'),
                isDisabled: isTableHeaderButtonDisabled("snapshot"),
                loading: processing.loading && processing.action === 'snapshot'
            },
            {
                label: "Restore",
                variant: 'contained',
                color: 'primary',
                requiresSelection: true,
                icon: <Restore />,
                addTooltip: true,
                tooltip: "Restore server from selected snapshot",
                onClick: () => buttonController('restore'),
                isDisabled: isTableHeaderButtonDisabled('restore'),
                loading: processing.loading && processing.action === 'restore'
            },
            {
                label: "Delete",
                variant: 'contained',
                color: 'error',
                requiresSelection: true,
                icon: <DeleteIcon />,
                addTooltip: true,
                tooltip: "Delete selected snapshot",
                onClick: () => buttonController('delete'),
                isDisabled: isTableHeaderButtonDisabled('delete'),
                loading: processing.loading && processing.action === 'delete'
            },
        ];
        return buttonConfig;
    }

    const columns: GridColDef[] = [
        {
            field: 'name',
            headerName: "Name",
            headerAlign: "center",
            minWidth: 200
        },
        {
            field: 'creation_timestamp',
            headerName: 'Creation Date',
            headerAlign: "center",
            minWidth: 200,
            renderCell: (params: any) => {
                return convertTimestamp(params.value);
            }
        },
        {
            field: 'type_',
            headerName: 'Snapshot Type',
            headerAlign: "center",
            minWidth: 150,
            renderCell: (params: any) => {
                const color = (params.value==='manual')?'neutral':'primary';
                return (
                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        height: '100%',
                        width: '100%',
                    }}>
                        <StatusBadge
                            color={color}
                            label={params.value}
                        />
                    </Box>
                );
            }
        }
    ];

    return (
        <>
            <StyledDataGrid
                data={snapshots}
                columns={columns}
                disableMultiRowSelection={true}
                disableSelectBtn={false}
                disableRowSelectionOnClick={true}
                density={"compact"}
                loading={props.loading}
                onSelection={setSelectedRows}
                selectedRow={selectedRows}
                labelProps={{disable: true}}
                buttonsConfig={getButtonConfig()}
                getRowId={row => row.name}
                localeText={{noRowsLabel: "No snapshots found"}}
                refreshing={props.refreshing}
            />
        </>
    );
}
