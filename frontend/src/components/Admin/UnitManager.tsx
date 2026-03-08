import AssignmentIcon from "@mui/icons-material/Assignment";
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import {
    Box,
    Skeleton,
    Typography,
    Button,
    Stack
} from '@mui/material';
import {
    DataGrid,
    GridColDef,
    GridActionsCellItem,
    GridRowModesModel,
    GridRowModes,
    GridRowId,
    GridRowModel,
    useGridApiRef,
    GridToolbar,
    GridRowSelectionModel
} from '@mui/x-data-grid';
import {RichTreeView} from "@mui/x-tree-view";
import {useModal} from "mui-modal-provider";
import React, { memo, useEffect, useState } from 'react';
import { URL_TEACHER_UNIT } from "../../router/urls";
import { adminService } from "../../services/Admin/admin.service";
import { Unit } from "../../services/Unit/unit.model";
import { unitService } from '../../services/Unit/unit.service';
import { AppUiObjectNames } from "../../types/AppObjectNames";
import {LinkButton} from "../Buttons/LinkButton";
import ConfirmationDialog from "../Common/Dialogs/ConfirmationDialog/Confirmation";
import EditFormDialog from "../Common/FormInputs/EditFormDialog";
import SimpleSnackbar from "../Common/SnackBar/SnackBar";
import EditUnitForm from './EditUnitForm';

interface UnitManagerTabProps {
    viewType: 'active' | 'all';
}

const UnitManagerTab: React.FC<UnitManagerTabProps> = memo(({ viewType }) => {
    const {showModal} = useModal();
    const [isLoading, setIsLoading] = useState(true);
    const [unitList, setUnitList] = useState<Unit[]>([]);
    const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});
    const apiRef = useGridApiRef();
    const [openDialog, setOpenDialog] = useState(false);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedUnit, setSelectedUnit] = useState<Unit | null>(null);
    const [selectedRows, setSelectedRows] = useState<any[]>([]);
    const [buttonLoading, setButtonLoading] = useState<boolean>(false);

    useEffect(() => {
        const fetchUnits = async () => {
            setIsLoading(true);
            try {
                const fetchedUnitList = await unitService.list_filtered(viewType === 'active' ? "active" : "30-days");
                setUnitList(fetchedUnitList || []);
            } catch (error) {
                setUnitList([]);
                console.error("Failed to fetch units:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchUnits();
    }, [viewType]);

    const handleConfirmDelete = async () => {
        setButtonLoading(true);
        try {
            await adminService.delete_unit(String(selectedRows[0] || ''));
            showModal(SimpleSnackbar, {
                message: 'Processing delete request ...',
                severity: 'info',
                autoHideDuration: 3000
            });
        } catch (error) {
            console.error("Error performing delete_action:", error);
            showModal(SimpleSnackbar, {
                message: 'Failed to delete unit',
                severity: 'error',
                autoHideDuration: 3000
            });
        } finally {
            setButtonLoading(false);
        }
    };

    const handleEditClick = (id: GridRowId) => () => {
        const unit = unitList.find((u) => u.id === id);
        if (unit) {
            setSelectedUnit(unit);
            setEditDialogOpen(true);
        }
    };

    const handleSaveClick = (id: GridRowId) => () => {
        setRowModesModel({ ...rowModesModel, [id]: { mode: GridRowModes.View } });
    };

    const processRowUpdate = (newRow: GridRowModel) => {
        const updatedRow = { ...newRow, isNew: false };
        setUnitList(prevState => prevState.map(unit => (unit.id === newRow.id ? { ...unit, ...updatedRow } : unit)));
        return updatedRow;
    };

    const handleRowModesModelChange = (newRowModesModel: GridRowModesModel) => {
        setRowModesModel(newRowModesModel);
    };

    const handleRowSelectionModelChange = (rowSelectionModel: GridRowSelectionModel) => {
        setSelectedRows([...rowSelectionModel]);
    };

    const handleEditSave = async () => {
        if (selectedUnit) {
            try {
                await adminService.patch(selectedUnit.id, selectedUnit, "unit");
                setUnitList(prevState => prevState.map(unit => (unit.id === selectedUnit.id ? selectedUnit : unit))); // Update the unitList state
                showModal(SimpleSnackbar, {
                    message: "Successfully updated",
                    severity: "success",
                })
                setEditDialogOpen(false);
            } catch (error) {
                console.error("Error updating unit:", error);
                showModal(SimpleSnackbar, {
                    message: "Failed to update",
                    severity: "error",
                })
            }
        }
    };

    const columns: GridColDef[] = [
        {
            field: 'id',
            headerName: 'ID',
            renderCell: (params: { row: any; }) => {
                return (
                    <LinkButton
                        buildId={params.row.id}
                        endpoint={URL_TEACHER_UNIT}
                        color={"primary"}
                        target={"_self"}
                    />
                )
            },
            minWidth: 150
        },
        {
            field: 'lms_integration',
            headerName: 'LMS Course',
            width: 150,
            renderCell: ( cellValues: any) => (
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        height: '100%',
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word'
                    }}
                >
                    <Typography>
                        {
                            cellValues.row.lms_integration
                                ? cellValues.row?.lms_integration.name
                                : 'N/A'
                        }
                    </Typography>
                </Box>
            )
        },
        {
            field: 'name',
            headerName: 'Name',
            width: 200,
            renderCell: (cellValues: any) => (
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    height: '100%',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                    }}
                >
                    <Typography variant={"body1"} sx={{ py: "1px" }}>
                        {cellValues.row.summary.name}
                    </Typography>
                </Box>
            )
        },
        { field: 'join_code', headerName: 'Join Code', width: 100 },
        {
            field: 'creation_timestamp',
            headerName: 'Created',
            width: 140,
            valueGetter: (value: any) => value ? value * 1000 : value,
            valueFormatter: (value?: number) => value == null ? '' : new Date(value).toLocaleDateString("en-US", {
                month: 'short',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }),
        },
        {
            field: 'workspace_settings',
            headerName: 'Expires',
            width: 140,
            valueGetter: (params: any) => {
                const timestamp = params.expires;
                return timestamp ? timestamp * 1000 : timestamp;
            },
            valueFormatter: (params: number) => {
                return params ? new Date(params).toLocaleDateString("en-US", {
                    month: 'short',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                }) : '';
            },
        },
        {
            field: 'instructor_id',
            headerName: 'Instructor',
            width: 240,
            editable: true,
            renderCell: (cellValues: any) => {
                // If there is a single instructor and returns a string, this forces it to be put into an array
                const instructorList = Array.isArray(cellValues.row.instructor_id)
                    ? cellValues.row.instructor_id
                    : [cellValues.row.instructor_id];

                const instructorTreeItems = [
                    {
                        id: 'instructors',
                        label: `Instructors: ${instructorList.length}`,
                        children: instructorList.map((instructor: any, index: any) => ({
                            id: `instructor-${index}`,
                            label: instructor,
                        })),
                    }
                ];

                return (
                    <Box sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        height: '100%',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        maxWidth: '100%',
                    }}>
                        <RichTreeView items={instructorTreeItems} />
                    </Box>
                );
            }
        },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 90,
            getActions: ({ id }) => {
                const isInEditMode = rowModesModel[id]?.mode === GridRowModes.Edit;

                if (isInEditMode) {
                    return [
                        <GridActionsCellItem
                            icon={<SaveIcon />}
                            label="Save"
                            sx={{ color: 'primary.main' }}
                            onClick={handleSaveClick(id)}
                        />,
                    ];
                }

                return [
                    <GridActionsCellItem
                        icon={<EditIcon />}
                        label="Edit"
                        onClick={handleEditClick(id)}
                        color="inherit"
                    />,
                ];
            },
        },
    ];

    return (
        <Box sx={{ height: '100%', p: 2 }}>
            <Stack
                alignItems={"center"}
                direction={"row"}
                gap={1}
                paddingTop={1}
            >
                <AssignmentIcon fontSize={"large"}/>
                <Typography
                    variant={"h5"}
                    component={"h2"}
                >
                    {
                        viewType === 'active'
                            ? `Active ${AppUiObjectNames.UNIT.toString()}s`
                            : `All ${AppUiObjectNames.UNIT.toString()}s`
                    }
                </Typography>
            </Stack>
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                <Button
                    variant="outlined"
                    color="error"
                    sx={{ m: 2 }}
                    onClick={() => setOpenDialog(true)}
                    disabled={selectedRows.length === 0}
                >
                    Delete
                </Button>
            </Box>
            {isLoading ? (
                <Box sx={{ width: '100%', height: 400, mt: 4 }}>
                    <Skeleton variant="rectangular" width="100%" height="100%" />
                </Box>
            ) : (
                <Box sx={{ height: 500, width: '100%' }}>
                    <DataGrid
                        rows={unitList}
                        columns={columns}
                        density="comfortable"
                        apiRef={apiRef}
                        checkboxSelection={true}
                        rowModesModel={rowModesModel}
                        processRowUpdate={processRowUpdate}
                        onRowSelectionModelChange={handleRowSelectionModelChange}
                        onRowModesModelChange={handleRowModesModelChange}
                        pageSizeOptions={[10, 20, 50, 100]}
                        disableColumnFilter
                        disableColumnSelector
                        disableDensitySelector
                        disableRowSelectionOnClick
                        disableMultipleRowSelection
                        slots={{ toolbar: GridToolbar }}
                        slotProps={{
                            toolbar: {
                                printOptions: { disableToolbarButton: true },
                                csvOptions: { disableToolbarButton: true },
                                showQuickFilter: true,
                                quickFilterProps: { debounceMs: 250 },
                            },
                        }}
                    />
                    <ConfirmationDialog
                        open={openDialog}
                        onClose={() => setOpenDialog(false)}
                        handleConfirm={async () => {
                            await handleConfirmDelete();
                            setOpenDialog(false);
                        }}
                        expectedText={selectedRows[0]}
                        loading={buttonLoading}
                        action={"delete"}
                    />
                    <EditFormDialog
                        title={"Edit Unit Teachers"}
                        open={editDialogOpen}
                        onClose={() => setEditDialogOpen(false)}
                        onSave={handleEditSave}
                        formComponent={EditUnitForm}
                        formProps={{
                            unit: selectedUnit,
                            onChange: setSelectedUnit
                        }}
                        loading={isLoading}
                    />
                </Box>
            )}
        </Box>
    );
});

export default UnitManagerTab;
