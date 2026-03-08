import {
    Build,
    CloudUpload,
    DeleteOutlined,
    EditNote,
    EditNoteOutlined,
    FileCopyOutlined,
    KeyboardTab,
} from '@mui/icons-material';
import AddIcon from '@mui/icons-material/Add';
import {Box, Button, Chip, Container, Paper, useTheme} from '@mui/material';
import {GridColDef, GridRenderCellParams, GridRowSelectionModel} from '@mui/x-data-grid';
import {useModal} from 'mui-modal-provider';
import React, {useEffect, useState} from 'react';
import {useNavigate} from 'react-router-dom';

import {useAuthContext} from '../../../../context/AuthContext';
import {URL_TEACHER_SPECIFICATION_EDIT, URL_TEACHER_UNIT} from '../../../../router/urls';
import {Specification} from '../../../../services/Specification/specification.model';
import {specificationService} from '../../../../services/Specification/specification.service';
import {SpecificationEditId} from "../../../../services/Specification/specificationEdit.model";
import {specificationEditService} from '../../../../services/Specification/specificationEdit.service';
import {unitService} from '../../../../services/Unit/unit.service';
import {SpecificationStates} from '../../../../types/AgogeStates';
import {AppUiObjectNames} from '../../../../types/AppObjectNames';
import {ActionButton} from "../../../Buttons/ControlButtons/ActionButton";
import {CreateCopyButton} from "../../../Buttons/ControlButtons/CreateCopyButton";
import {DeleteButton} from "../../../Buttons/ControlButtons/DeleteButton";
import {ExpandableCell} from '../../../Common/DataGrid/ExpandableCell';
import StyledDataGrid, {ButtonConfig} from "../../../Common/DataGrid/StyledDataGrid";
import SimpleSnackbar from '../../../Common/SnackBar/SnackBar';
import BuildWaitDialog from './BuildWaitDialog';
import CatalogDetailsDialog from "./CatalogDetailsDialog";
import FileUploadDialog from './FileUploadDialog';
import {InstructionsDialog} from "./InstructionsDialog";
import {WorkoutModal} from './WorkoutModal';


interface ButtonLoaders {
    confirmDelete: boolean;
    create: boolean;
    copy: boolean;
    delete: boolean;
}

const CatalogTable: React.FC = () => {
    const {showModal} = useModal();
    const theme = useTheme();
    const { agogeUser} = useAuthContext();
    const navigate = useNavigate();
    const [catalogList, setCatalogList] = useState<Specification[]>([]);
    const [flattenedData, setFlattenedData] = useState<any[]>([]);
    const [selectedRow, setSelectedRow] = useState<any>(null);
    const [workoutModalOpen, setWorkoutModalOpen] = useState<boolean>(false);
    const [waitingModalOpen, setWaitingModalOpen] = useState<boolean>(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [buttonLoading, setButtonLoading] = useState<ButtonLoaders>({
        confirmDelete: false,
        create: false,
        copy: false,
        delete: false
    });

    const hasAssessment = (spec: Specification) => {
        if (spec.assessment) {
            if (spec.assessment.questions !== null) return "Agoge";
        } else if (spec.lms_quiz) {
            return "LMS Quiz";
        }
        return "No Assessment";
    }

    useEffect(() => {
        const fetchSpecs = async () => {
            try {
                const fetchedSpecs = await specificationService.list();
                const catalogList = fetchedSpecs.filter(spec => !spec.build_type || spec.build_type === 'unit');
                setCatalogList(catalogList);
            } catch (error) {
                console.error('Error fetching specifications:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchSpecs();
    }, []);

    useEffect(() => {
        const flattenData = () => {
            const flattened = catalogList.map(item => ({
                id: item.id,
                name: item.summary?.name || 'N/A',
                description: item.summary?.description || 'N/A',
                tags: item.summary?.tags || [],
                discriminator: item.discriminator,
                lms_quiz: item.lms_quiz || null,
                assessment: item.assessment || null,
                assessment_type: hasAssessment(item),
                student_instruction: item.summary?.student_instructions_url,
                teacher_instruction: item.summary?.teacher_instructions_url,
            }));
            setFlattenedData(flattened);
        };

        flattenData();
    }, [catalogList]);

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        if (selectionModel.length > 0) {
            const selectedRowData = catalogList.find((row) => row.id === selectionModel[0]);
            setSelectedRow(selectedRowData);
        } else {
            setSelectedRow(null);
        }
    };

    const handleFormSubmit = async (formData: any) => {
        setWorkoutModalOpen(false);
        setWaitingModalOpen(true);
        try {
            const response = await unitService.create(formData);
            if (response?.build_id) {
                navigate(`${URL_TEACHER_UNIT}/${response.build_id}`);
            } else {
                throw new Error("Failed to redirect to unit. Received an invalid response");
            }
        } catch (error) {
            setErrorMessage('Failed to create lab.');
            setWaitingModalOpen(false);
            setWorkoutModalOpen(true);
            showModal(SimpleSnackbar, {
                message: `Failed to create lab. ${error}`,
                severity: "error",
            });
        }
    };

    const handleBuildDialog = () => {
        setWorkoutModalOpen(true);
    };

    const handleCreateNew = async () => {
        try {
            showModal(SimpleSnackbar, {
                message: "Creating new specification template ...",
                severity: "info",
                autoHideDuration: 5000,
                vertical: "bottom",
            });
            setButtonLoading((prevState) => ({...prevState, create: true}));
            const newSpecId = await specificationEditService.create(SpecificationStates.CREATE);
            navigateToEdit(newSpecId);
        } catch (error) {
            console.log(error);
            showModal(SimpleSnackbar, {
                message: "Failed to create specification template",
                severity: "error",
                vertical: "bottom",
            });
        } finally {
            setButtonLoading((prevState) => ({...prevState, create: false}));
        }
    };

    const navigateToEdit = (spec: SpecificationEditId) => {
        if (spec?.build_id) {
            navigate(`${URL_TEACHER_SPECIFICATION_EDIT}/${spec.build_id}`);
        } else {
            console.log("Received response but could not process data", spec);
        }
    };

    const handleConfirmDelete = async (row: Partial<Specification>) => {
        setCatalogList(prevList => prevList.filter(item => item.id !== row.id));
        setFlattenedData(prevData => prevData.filter(item => item.id !== row.id));
    };

    const columns: GridColDef[] = [
        {
            field: 'name',
            headerName: 'Name',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: any) => (
                <ExpandableCell {...params} value={params.value} variant={"body1"} />
            ),
        },
        {
            field: 'discriminator',
            headerName: 'Discriminator',
            sortable: false,
            filterable: false,
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
                    <Chip
                        variant={"outlined"}
                        label={`#${cellValues.row.discriminator}`}
                        sx={{
                            borderColor: theme.palette.primary.light,
                            borderRadius: "4px",
                        }}
                    />
                </Box>
            )
        },
        {
            field: 'assessment_type',
            headerName: 'Assessment',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value && params.value !== 'No Assessment' ? (
                        <Chip variant={"outlined"} label={params.value} color="success" />
                    ) : (
                        <Chip variant={"outlined"} label={params.value} color="error" />
                    )}
                </div>
            ),
        },
        {
            field: 'actions',
            headerName: 'Actions',
            minWidth: 180,
            renderCell: (params: any) => {
                return renderLabRowActions(params.row);
            }
        },
        {
            field: 'description',
            headerName: 'Description',
            width: 150,
            filterable: false,
            sortable: false,
            renderCell: (params: GridRenderCellParams) => {
                const spec = catalogList.find(cl => cl.id === params.row.id);
                return (
                    <Button
                        onClick={() => showModal(CatalogDetailsDialog, {specification: spec!})}
                    >
                        View Details
                    </Button>
                )
            }
        },
    ];

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Create New Template",
                variant: 'contained',
                color: "info",
                icon: <AddIcon />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Create a new specification to use in future labs",
                loading: buttonLoading.create,
                onClick: handleCreateNew
            },
            {
                label: "Upload New Template",
                variant: 'outlined',
                color: "success",
                icon: <CloudUpload />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Upload a new specification to use in future labs",
                onClick: () => showModal(FileUploadDialog)
            },
            {
                label: "Build Lab",
                variant: 'outlined',
                color: "info",
                requiresSelection: true,
                icon: <Build />,
                addTooltip: true,
                tooltip: "Build a lab using selected specification",
                onClick: handleBuildDialog
            }
        ]
        return buttonConfig;
    }

    const renderLabRowActions = (row: Specification) => {
        return (
            <>
                <CreateCopyButton
                    title={"Create Copy"}
                    label={"Create Copy of Specification"}
                    isDisabled={loading}
                    iconButton={true}
                    iconProps={{
                        size: 'small',
                        fontSize: 'small',
                        label: 'create copy of specification'
                    }}
                    IconComponent={FileCopyOutlined}
                    row={row}
                />
                {((row as any).student_instruction || (row as any).teacher_instruction) && (
                    <ActionButton
                        title="View Instructions"
                        label="Instructions"
                        controlType="specification"
                        action="viewInstructions"
                        isActionDisabled={({ loading }) => loading}
                        iconButton={true}
                        OutlinedIconComponent={EditNoteOutlined}
                        iconProps={{
                            size: "small",
                            fontSize: "small",
                            label: "view instructions"
                        }}
                        row={row}
                        onClick={() => showModal(InstructionsDialog, {row: row})}
                        data={{ id: row.id }}
                        successMessage="Instructions loaded!"
                        errorMessage="Failed to load instructions!"
                        color="info"
                        IconComponent={EditNote}
                    />
                )}
                {agogeUser?.user?.permissions.admin && (
                    <DeleteButton
                        title="Delete Specification"
                        label="Delete Specification"
                        controlType="specification"
                        isDisabled={loading}
                        iconButton={true}
                        iconProps={{
                            size: "small",
                            fontSize: "small",
                            label: "delete specification"
                        }}
                        row={row}
                        IconComponent={DeleteOutlined}
                        onSuccess={() => handleConfirmDelete(row)}
                    />
                )}
            </>
        )
    };
    return (
        <>
            <Container maxWidth={"lg"}>
                <Paper
                    sx={{
                        mt: 10,
                        height: "auto",
                        display: "flex",
                        flexDirection: "column",
                        overflow: "hidden",
                        padding: 1,
                    }}
                    square={false}
                >
                    <Box mb={2}>
                        <Button
                            variant="outlined"
                            color="info"
                            onClick={() => navigate(URL_TEACHER_SPECIFICATION_EDIT)}
                            sx={(theme) => ({
                                mt: 2,
                                ml: 2,
                                borderColor: theme.palette.info.light,
                                color: theme.palette.info.light
                            })}
                            endIcon={<KeyboardTab />}
                        >
                            View Existing Catalog Edits
                        </Button>
                    </Box>
                    <StyledDataGrid
                        data={flattenedData}
                        buttonsConfig={getButtonConfig()}
                        columns={columns}
                        disableMultiRowSelection={true}
                        disableSelectBtn={false}
                        disableRowSelectionOnClick={true}
                        labelProps={{
                            text: `${AppUiObjectNames.UNIT} Catalog`
                        }}
                        loading={loading}
                        onSelection={handleRowSelection}
                        selectedRow={selectedRow}
                    />
                </Paper>
            </Container>

            {/* Generate Page Modals */}
            <BuildWaitDialog
                open={waitingModalOpen}
                onClose={() => setWaitingModalOpen(false)}
            />
            {selectedRow && (
                <>
                    <WorkoutModal
                        open={workoutModalOpen}
                        user={agogeUser.user}
                        onClose={() => setWorkoutModalOpen(false)}
                        onSubmit={handleFormSubmit}
                        selectedRow={selectedRow}
                    />
                </>
            )}
        </>
    );
};

export default CatalogTable;