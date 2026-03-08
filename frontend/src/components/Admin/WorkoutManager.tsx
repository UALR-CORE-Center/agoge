import { FitnessCenter } from "@mui/icons-material";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {
    Box,
    Button,
    Skeleton,
    Typography,
    Chip,
    Stack
} from "@mui/material";
import {
    DataGrid,
    GridColDef,
    GridActionsCellItem,
    GridRowModesModel,
    GridRowModes,
    GridRowId,
    GridRowModel,
    GridToolbar,
    GridRowSelectionModel
} from "@mui/x-data-grid";
import React, { memo, useEffect, useState } from "react";
import { URL_STUDENT_WORKOUT } from "../../router/urls";
import { adminService } from "../../services/Admin/admin.service";
import { unitService } from "../../services/Unit/unit.service";
import { Workout } from "../../services/Workout/workout.model";
import { AppUiObjectNames } from "../../types/AppObjectNames";
import {LinkButton} from "../Buttons/LinkButton";
import ConfirmationDialog from "../Common/Dialogs/ConfirmationDialog/Confirmation";
import EditFormDialog from "../Common/FormInputs/EditFormDialog";
import SimpleSnackbar from "../Common/SnackBar/SnackBar";
import StateChip from "../Common/Status/StateChip";
import EditWorkoutForm from "./EditWorkoutForm";

interface WorkoutManagerTabProps {
    viewType: 'active' | 'all'
}

type SnackbarSeverity = 'success' | 'error' | 'info' | 'warning';

const WorkoutManagerTab: React.FC<WorkoutManagerTabProps> = memo(({ viewType }) => {
    const [isLoading, setIsLoading] = useState(true);
    const [workoutList, setWorkoutList] = useState<Workout[]>([]);
    const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});
    const [openDialog, setOpenDialog] = useState(false);
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState('');
    const [snackbarSeverity, setSnackbarSeverity] = useState<SnackbarSeverity>('info');
    const [selectedRows, setSelectedRows] = useState<any[]>([]);
    const [editRowId, setEditRowId] = useState<string | number | null>(null);
    const [originalState, setOriginalState] = useState<string | undefined>(undefined);
    const [editedState, setEditedState] = useState<string | undefined>(undefined);
    const [rows, setRows] = useState<Workout[]>([]);

    const [selectedWorkout, setSelectedWorkout] = useState<Workout | null>(null);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editLoading, setEditLoading] = useState<boolean>(false);


    useEffect(() => {
        setRows([]);
        setIsLoading(true);
        const fetchWorkouts = async () => {
            try {
                const fetchedWorkoutList = await unitService.list_workouts_filtered(viewType === 'active' ? "active" : "14-days");
                setWorkoutList(fetchedWorkoutList || []);
                setRows(fetchedWorkoutList || []);
            } catch (error) {
                setWorkoutList([]);
                console.error("Failed to fetch workouts:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchWorkouts();
    }, [viewType]);

    const processRowUpdate = (newRow: GridRowModel) => {
        const updatedRow = { ...newRow, isNew: false };
        setWorkoutList(prevState => prevState.map(workout => (workout.id === newRow.id ? { ...workout, ...updatedRow } : workout)));
        setRows(prevState => prevState.map(row => (row.id === newRow.id ? { ...row, ...updatedRow } : row)));
        return updatedRow;
    };

    const handleRowModesModelChange = (newRowModesModel: GridRowModesModel) => {
        setRowModesModel(newRowModesModel);
    };

    const handleRowSelectionModelChange = (rowSelectionModel: GridRowSelectionModel) => {
        setSelectedRows([...rowSelectionModel]);
    };

    const handleConfirmDelete = async () => {
        try {
            await adminService.delete_workout(String(selectedRows[0] || ''));
            setSnackbarMessage('Successfully deleted');
            setSnackbarSeverity('success');
        } catch (error) {
            console.error("Error performing delete_action:", error);
            setSnackbarMessage('Failed to delete');
            setSnackbarSeverity('error');
        } finally {
            setSnackbarOpen(true);
        }
    };

    const handleCloseSnackbar = () => {
        setSnackbarOpen(false);
    };

    const handleStateChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setEditedState(event.target.value);
    };


    const handleEditClick = (id: GridRowId) => () => {
        const workout = workoutList.find((workout) => workout.id === id);
        if (workout) {
            setSelectedWorkout(workout);
            setEditDialogOpen(true);
        }
    };

    const handleSaveClick = (id: GridRowId) => () => {
        setRowModesModel({ ...rowModesModel, [id]: { mode: GridRowModes.View } });
    };

    const handleEditSave = async () => {
        if (selectedWorkout) {
            setEditLoading(true);
            try {
                await adminService.patch(selectedWorkout.id, selectedWorkout, "workout");
                setWorkoutList(prevState => prevState.map(workout => (workout.id === selectedWorkout.id ? selectedWorkout : workout)));
                setRows((prevState) => prevState.map((row) => (row.id === selectedWorkout.id ? selectedWorkout : row)));
                setSnackbarMessage('Successfully updated');
                setSnackbarSeverity('success');
            } catch(error) {
                console.error("Error updating unit:", error);
                setSnackbarMessage("Failed to update");
                setSnackbarSeverity('error');
            } finally {
                setEditDialogOpen(false);
                setSnackbarOpen(true);
            }
        }
        setEditLoading(false);
    }

    const columns: GridColDef[] = [
        {
            field: 'id',
            headerName: 'ID',
            width: 160,
            editable: false,
            sortable: true,
            renderCell: (params) => {
                return (
                    <LinkButton
                        buildId={params.row.id}
                        endpoint={URL_STUDENT_WORKOUT}
                        target={"_self"}
                    />
                )
            }
        },
        {
            field: 'name',
            headerName: 'Name',
            flex: 200,
            editable: false,
            renderCell: (params) => {
                return (
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        height: '100%',
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word'
                    }}
                    >
                        <Typography sx={{ py: "1px" }}>
                            {params.row.summary?.name ? params.row.summary.name : ""}
                        </Typography>
                    </Box>
                )
            }
        },
        {
            field: 'student_email',
            headerName: 'Student Email',
            width: 220,
            editable: false,
            renderCell: (params) => {
                return (
                    <Chip
                        variant={"filled"}
                        size={"medium"}
                        label={params.row.student_email}
                        sx={{ borderRadius: "6px" }}
                    />
                );
            }
        },
        {
            field: 'state',
            headerName: 'State',
            width: 100,
            editable: false,
            renderCell: (params) => {
                return (
                    <StateChip
                        state={params.row.state}
                        stateType={"workout"}
                        size={"medium"}
                        onChange={handleStateChange}
                    />
                )
            }
        },
        {
            field: 'expires',
            headerName: 'Expires',
            width: 140,
            editable: false,
            valueGetter: (value: any) => value ? value * 1000 : value,
            valueFormatter: (value: number) => value == null ? "" : new Date(value).toLocaleDateString("en-US", {
                month: 'short',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }),
        },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 90,
            getActions: ({id}) => {
                const isInEditMode = rowModesModel[id]?.mode === GridRowModes.Edit;

                if (isInEditMode) {
                    return [
                      <GridActionsCellItem
                          icon={<SaveIcon />}
                          label="Save"
                          sx={{ color: 'primary.main' }}
                          onClick={handleSaveClick(id)}
                      />
                    ];
                }

                return [
                    <GridActionsCellItem
                        icon={<EditIcon />}
                        label="Edit"
                        onClick={handleEditClick(id)}
                        color="inherit"

                    />
                ];
            }

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
                <FitnessCenter fontSize={"large"}/>
                <Typography
                    variant="h5"
                    component={"h2"}
                >
                    {
                        viewType === 'active'
                            ? `Active ${AppUiObjectNames.WORKOUT.toString()}s`
                            : `All ${AppUiObjectNames.WORKOUT.toString()}s`
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
                {/*<Button variant="contained" sx={{ m: 2 }} onClick={handleBuildClick}>Build in place</Button>*/}
                {/*<Button variant="contained" sx={{ m: 2 }} onClick={handleRestoreClick}>Restore</Button>*/}
            </Box>
            {isLoading ? (
                <Box sx={{ width: "100%", height: 350, mt: 4 }}>
                    <Skeleton variant="rectangular" width="100%" height="100%" />
                </Box>
            ) : (
                <Box sx={{ height: 500, width: '100%' }}>
                    <DataGrid
                        rows={rows}
                        columns={columns}
                        editMode={"cell"}
                        density="comfortable"
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
                    <EditFormDialog
                        title={"Edit workout email"}
                        open={editDialogOpen}
                        onClose={() => setEditDialogOpen(false)}
                        onSave={handleEditSave}
                        loading={editLoading}
                        formComponent={EditWorkoutForm}
                        formProps={{
                            workout: selectedWorkout,
                            onChange: setSelectedWorkout
                        }}
                    />
                    <ConfirmationDialog
                        open={openDialog}
                        onClose={() => setOpenDialog(false)}
                        handleConfirm={async () => {
                            await handleConfirmDelete();
                            setOpenDialog(false);
                        }}
                        action={"delete"}
                        expectedText={selectedRows[0]}
                        loading={false}
                    />
                    <SimpleSnackbar
                        message={snackbarMessage}
                        open={snackbarOpen}
                        onClose={handleCloseSnackbar}
                        severity={snackbarSeverity}
                    />
                </Box>
            )}
        </Box>
    );
});

export default WorkoutManagerTab;
