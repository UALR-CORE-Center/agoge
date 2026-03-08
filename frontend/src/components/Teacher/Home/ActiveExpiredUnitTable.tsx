import {ArrowOutwardRounded} from "@mui/icons-material";
import AddIcon from "@mui/icons-material/Add";
import AssignmentIcon from '@mui/icons-material/Assignment';
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {
    Box,
    Paper,
    Tab,
    Tabs,
    Typography,
    Button,
    Tooltip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton
} from '@mui/material';
import {GridActionsCellItem, GridColDef, GridRowId, GridRowModes, GridRowModesModel} from "@mui/x-data-grid";
import {RichTreeView} from "@mui/x-tree-view";
import React, {useCallback, useEffect, useState} from 'react';
import {useClipboard} from "../../../hooks/useClipboard";
import {URL_TEACHER_SPECIFICATIONS_BASE, URL_TEACHER_UNIT} from "../../../router/urls";
import { Unit } from "../../../services/Unit/unit.model";
import { unitService } from "../../../services/Unit/unit.service";
import {AppUiObjectNames} from "../../../types/AppObjectNames";
import EditUnitForm from "../../Admin/EditUnitForm";
import {LinkButton} from "../../Buttons/LinkButton";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import EditFormDialog from "../../Common/FormInputs/EditFormDialog";
import {useNavigate} from "react-router-dom";

const generateUnitLink = (unitId: string) => {
    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'start',
                justifyContent: 'start',
                height: '100%',
                minHeight: '50px',
                marginTop: '4px',
            }}
        >
            <LinkButton
                label={unitId}
                buildId={unitId}
                endpoint={URL_TEACHER_UNIT}
                width={"140px"}
                endIcon={<ArrowOutwardRounded />}
                target={"_self"}
            />
        </Box>
    );
};

const convertTimestamp = (timestamp?: number): string => {
    return timestamp ? new Date(timestamp * 1000).toDateString() : 'N/A';
};

const ActiveExpiredUnitTable: React.FC = () => {
    const [activeUnits, setActiveUnits] = useState<Unit[]>([]);
    const [expiredUnits, setExpiredUnits] = useState<Unit[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});
    const [selectedUnit, setSelectedUnit] = useState<Unit | null>(null);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editLoading, setEditLoading] = useState<boolean>(false);
    const [errorDialogOpen, setErrorDialogOpen] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedTab, setSelectedTab] = useState<number>(0);
    const { copy } = useClipboard();
    const navigate = useNavigate()

    useEffect(() => {
        const fetchUnits = async () => {
            try {
                const fetchedUnits = await unitService.list();
                setActiveUnits(fetchedUnits.active);
                setExpiredUnits(fetchedUnits.expired);
            } catch (error: any) {
                setActiveUnits([]);
                setExpiredUnits([]);
                if(error?.status !== 404){
                    setErrorDialogOpen(true);
                    setError(`${error?.status || "Unknown Status"}: ${error?.message || "What an edge case you've found"}`);
                }
                console.error(error);
            } finally {
                setLoading(false);
            }
        };

        fetchUnits();
    }, []);

    const handleCloseDialog = () => {
        setErrorDialogOpen(false);
    };

    const handleTabChange = (event: React.ChangeEvent<{}>, newValue: number) => {
        setSelectedTab(newValue);
    };

    const processUnits = (units: Unit[]) => {
        return units.map(unit => ({
            id: unit.id,
            summaryName: unit.summary.name,
            lmsIntegrationName: unit?.lms_integration?.lms_connection?.name || 'N/A',
            summaryDescription: unit.summary.description || 'N/A',
            creationTimestamp: unit.creation_timestamp,
            workspaceExpires: unit.workspace_settings?.expires,
            instructorId: unit.instructor_id
        }));
    };

    const handleSaveClick = (id: GridRowId) => () => {
        setRowModesModel({ ...rowModesModel, [id]: { mode: GridRowModes.View } });
    };

    const handleEditClick = (id: GridRowId) => () => {
        let tabUnits = activeUnits;
        if (selectedTab !== 0) {
            tabUnits = expiredUnits;
        }
        const unit = tabUnits.find((u) => u.id === id);
        if (unit) {
            setSelectedUnit(unit);
            setEditDialogOpen(true);
        }
    };

    const handleEditSave = async () => {
        if (selectedUnit) {
            setEditLoading(true);
            try {
                await unitService.patch(selectedUnit.id, selectedUnit);
                if (selectedTab === 0) {
                    setActiveUnits((prevUnits) =>
                        prevUnits.map((unit) =>
                            unit.id === selectedUnit.id ? selectedUnit : unit
                        )
                    );
                } else {
                    setExpiredUnits((prevUnits) =>
                        prevUnits.map((unit) =>
                            unit.id === selectedUnit.id ? selectedUnit : unit
                        )
                    );
                }
                setEditDialogOpen(false);
            } catch (error) {
                console.error("Error saving unit:", error);
            }
        }
        setEditLoading(false);
    };

    const renderTable = (units: Unit[]) => {
        const noRowsMessage = selectedTab === 0
            ? "No active labs found"
            : "No expired labs found";
        return (
            <Paper elevation={1} sx={{width:'100%',overflow:'hidden',p:2}}>
                <Box sx={{width:'100%', minWidth:'1000px'}}>
                    <StyledDataGrid
                        data={processUnits(units)}
                        columns={newColumns}
                        disableMultipleRowSelection={true}
                        disableSelectBtn={true}
                        disableCheckBoxes={true}
                        localeText={{
                            noRowsLabel: noRowsMessage,
                        }}
                        labelProps={{
                            text: `Your ${AppUiObjectNames.UNIT.toString()}s`,
                            icon: <AssignmentIcon fontSize={"large"}/>
                        }}
                        density={"comfortable"}
                        loading={loading}
                    />
                </Box>
            </Paper>
        );
    };

    const newColumns: GridColDef[] = [
        {
            field: 'id',
            headerName: 'ID',
            renderCell: (params: { row: any; }) => generateUnitLink(params.row.id),
            minWidth: 160
        },
        {
            field: 'summaryName',
            headerName: 'Name',
            width: 200,
            renderCell: (params: any) => (
                <Tooltip title={params.value}>
                    <span>{params.value}</span>
                </Tooltip>
            )
        },
        {
            field: 'lmsIntegrationName',
            headerName: 'LMS Course',
            minWidth: 50,
            renderCell: (params: any) => (
                <Tooltip title={params.value}>
                    <span>{params.value}</span>
                </Tooltip>
            )
        },
        {
            field: 'summaryDescription', headerName: 'Description', width: 250, renderCell: (params: any) => (
                <Tooltip title={params.value}>
                    <span>{params.value}</span>
                </Tooltip>
            )
        },
        {
            field: 'creationTimestamp',
            headerName: 'Created',
            type: 'dateTime',
            width:150,
            valueFormatter: (value?: number) => {
                return convertTimestamp(value)
            }
        },
        {
            field: 'workspaceExpires',
            headerName: 'Expires',
            type: 'dateTime',
            width:150,
            valueFormatter: (value?: number) => {
                return convertTimestamp(value)
            }
        },
        {
            field: 'instructorId',
            headerName: 'Instructor',
            width: 240,
            editable: true,
            renderCell: (cellValues: any) => {
                let instructorList = [];

                if (typeof cellValues.row.instructorId === 'string') {
                    instructorList = cellValues.row.instructorId
                        .replace(/[\[\]"]/g, '')
                        .split(',')
                        .map((id: string) => ({
                            id: id.trim(),
                            label: id.trim(),
                        }));
                }
                else if (Array.isArray(cellValues.row.instructorId)) {
                    instructorList = cellValues.row.instructorId.map((id: string) => ({
                        id: id.trim(),
                        label: id.trim(),
                    }));
                }

                const instructorTreeItems = [
                    {
                        id: 'instructors',
                        label: `Instructors: ${instructorList.length}`,
                        children: instructorList,
                    }
                ];

                return (
                    <Box
                        sx={{
                            position: 'relative',
                            '&:focus-visible::after, &.Mui-focusVisible::after': {
                                content: '""',
                                position: 'absolute',
                                inset: 0,
                                borderRadius: '4px',
                                boxShadow: 'inset 0 0 0 2px #82B6E3',
                                pointerEvents: 'none',
                            },
                        }}
                    >
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
            renderCell: (params: { id: GridRowId }) => {
                const { id } = params;
                const isInEditMode = rowModesModel[id]?.mode === GridRowModes.Edit;

                return (
                    <Box
                        sx={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'flex-start',
                            height: '100%',
                            width: '100%',
                        }}
                    >
                        {isInEditMode ? (
                            <GridActionsCellItem
                                icon={<SaveIcon />}
                                label="Save"
                                sx={{ color: 'primary.main' }}
                                onClick={handleSaveClick(id)}
                            />
                        ) : (
                            <GridActionsCellItem
                                icon={
                                    <Tooltip title="Edit Instructors" placement="bottom" >
                                        <EditIcon />
                                    </Tooltip>
                                }
                                label="Edit"
                                onClick={handleEditClick(id)}
                                color="inherit"
                            />
                        )}
                    </Box>
                );
            },
        }
    ];

    return (
        <Box
            sx={{
                width: '100%',
                p:2,
                mx: 'auto',
                overflow: 'hidden',
            }}
        >
            <Box
                sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    width: '100%',
                }}
            >
                <Tabs
                    variant={"scrollable"}
                    value={selectedTab}
                    onChange={handleTabChange}
                >
                    <Tab
                        label={`Active ${AppUiObjectNames.UNIT}s`}
                        sx={{
                            position: 'relative',
                            borderRadius: 2,
                            '&:focus-visible::after, &.Mui-focusVisible::after': {
                                content: '""',
                                position: 'absolute',
                                inset: 0,
                                borderRadius: 'inherit',
                                boxShadow: 'inset 0 0 0 2px #82B6E3',
                                pointerEvents: 'none',
                            },
                        }}
                    />
                    <Tab
                        label={`Expired ${AppUiObjectNames.UNIT}s`}
                        sx={{
                            position: 'relative',
                            borderRadius: 2,
                            '&:focus-visible::after, &.Mui-focusVisible::after': {
                                content: '""',
                                position: 'absolute',
                                inset: 0,
                                borderRadius: 'inherit',
                                boxShadow: 'inset 0 0 0 2px #82B6E3',
                                pointerEvents: 'none',
                            },
                        }}
                    />
                </Tabs>
                <Button
                    color={"primary"}
                    onClick={() => navigate(URL_TEACHER_SPECIFICATIONS_BASE)}
                    variant={"contained"}
                    startIcon={<AddIcon />}
                    sx={{
                        mt: 2,
                        mb:2
                    }}
                >
                    Create New
                </Button>
                <Box
                    sx={{
                        width: '100%',
                        display: 'flex',
                        justifyContent: 'center',
                    }}
                >
                    {selectedTab === 0 ? renderTable(activeUnits) : renderTable(expiredUnits)}
                </Box>
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
                    loading={editLoading}
                />
                <Dialog
                    open={errorDialogOpen}
                    onClose={handleCloseDialog}
                >
                    <DialogTitle>We&#39;re Sorry!</DialogTitle>
                    <DialogContent>
                        <Typography>
                            Something went wrong on our end. Please copy the error below and share it with your administrator so we can fix it.
                        </Typography>
                        <Box
                            component="section"
                            sx={{
                                mt:1,
                                p: 1,
                                border: '1px solid grey',
                                borderRadius: '4px',
                            }}
                        >
                            <Typography sx={{ wordBreak: 'break-all' }}>
                                {error}
                                <IconButton
                                    onClick={() => copy(error)}
                                    sx={{ ml: 1 }}
                                    aria-label="Copy error"
                                >
                                    <ContentCopyIcon />
                                </IconButton>
                            </Typography>
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleCloseDialog} color="primary">
                            Close
                        </Button>
                    </DialogActions>
                </Dialog>
            </Box>
        </Box>
    );
};

export default ActiveExpiredUnitTable;
