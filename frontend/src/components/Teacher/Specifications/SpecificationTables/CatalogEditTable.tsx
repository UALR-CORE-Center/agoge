import {Clear, DeleteOutlined, Done, KeyboardBackspace} from '@mui/icons-material';
import EditIcon from '@mui/icons-material/Edit';
import {Box, Button, Container, Paper, useTheme} from '@mui/material';
import {GridColDef, GridRenderCellParams, GridRowSelectionModel} from '@mui/x-data-grid';
import {useModal} from 'mui-modal-provider';
import React, {useEffect, useState} from 'react';

import {useNavigate} from "react-router-dom";
import {useAuthContext} from '../../../../context/AuthContext';
import {
  URL_TEACHER_SPECIFICATION_EDIT,
  URL_TEACHER_SPECIFICATIONS_BASE,
} from '../../../../router/urls';
import {SpecificationEdit} from '../../../../services/Specification/specificationEdit.model';
import {specificationEditService} from '../../../../services/Specification/specificationEdit.service';
import {SpecificationStates} from '../../../../types/AgogeStates';
import {AppUiObjectNames} from '../../../../types/AppObjectNames';
import {LinkButton} from "../../../Buttons/LinkButton";
import {ExpandableCell} from '../../../Common/DataGrid/ExpandableCell';
import StyledDataGrid, {ButtonConfig} from "../../../Common/DataGrid/StyledDataGrid";
import ConfirmationDialog from '../../../Common/Dialogs/ConfirmationDialog/Confirmation';
import SimpleSnackbar from '../../../Common/SnackBar/SnackBar';


interface LoadingButtonStates {
    delete: boolean;
    deleting: boolean;
}

const CatalogEditTable: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const {showModal} = useModal();
    const {agogeUser} = useAuthContext();
    const [editList, setEditList] = useState<SpecificationEdit[]>([]);
    const [flattenedData, setFlattenedData] = useState<any[]>([]);
    const [selectedRow, setSelectedRow] = useState<any>(null);
    const [confirmationDialogOpen, setConfirmationDialogOpen] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(true);
    const [buttonLoading, setButtonLoading] = useState<LoadingButtonStates>({
        delete: false,
        deleting: false
    });

    useEffect(() => {
        const fetchSpecs = async () => {
            try {
                const fetchedSpecs = await specificationEditService.list();
                const editsList = fetchedSpecs.filter(spec => !spec.build_type || spec.build_type === 'unit');
                setEditList(editsList);
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
            const flattened = editList.map(item => ({
                id: item.edit_id,
                name: item.summary?.name || 'N/A',
                description: item.summary?.description || 'N/A',
                author: item.summary?.author,
                discriminator: item.discriminator,
                servers: item.servers || null,
                networks: item.networks || null,
                assessment: item.assessment || item.lms_quiz || null,
                web_apps: item.web_applications || null,
                editStatus: item?.status ? item.status : SpecificationStates.EDIT
            }));
            setFlattenedData(flattened);
        };

        flattenData();
    }, [editList]);

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        if (selectionModel.length > 0) {
            const selectedRowData = editList.find((row) => row.edit_id === selectionModel[0]);
            setSelectedRow(selectedRowData);
        } else {
            setSelectedRow(null);
        }
    };

    const handleDeleteDialog = () => {
        setButtonLoading((prevState) => ({...prevState, delete: true}));
        setConfirmationDialogOpen(true);
    };

    const handleConfirmDelete = async () => {
        if (!selectedRow) {
            showModal(SimpleSnackbar, {
                message: "You must select a specification edit first",
                severity: "error"
            });
            setConfirmationDialogOpen(false);
            return;
        }

        try {
            setButtonLoading((prevState) => ({...prevState, deleting: true}));
            setConfirmationDialogOpen(false);
            await specificationEditService.del(selectedRow.edit_id);
            setEditList(prevList => prevList.filter(item => item.edit_id !== selectedRow.edit_id));
            setFlattenedData(prevData => prevData.filter(item => item.id !== selectedRow.edit_id));
            showModal(SimpleSnackbar, {
                message: "Edit deleted successfully.",
                severity: "success"
            });
        } catch (error) {
            console.error('Error deleting specification edit:', error);
            showModal(SimpleSnackbar, {
                message: "Failed to delete specification edit.",
                severity: "error"
            });
        } finally {
            setSelectedRow(null);
            setButtonLoading({deleting: false, delete: false});
        }
    };


    const columns: GridColDef[] = [
        {
            field: 'id',
            headerName: 'Edit ID',
            width: 171,
            filterable: true,
            sortable: true,
            renderCell: (params: any) => (
                <LinkButton
                    variant={"contained"}
                    color={"info"}
                    buildId={params.value}
                    endpoint={URL_TEACHER_SPECIFICATION_EDIT}
                    endIcon={<EditIcon />}
                    target={"_self"}
                    width={"150px"}
                />
            )
        },
        {
            field: 'author',
            headerName: 'Author',
            minWidth: 120,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <ExpandableCell
                    {...params}
                    value={params.value || 'N/A'}
                    variant={"body1"}
                />
            ),
        },
        {
            field: 'name',
            headerName: 'Name',
            minWidth: 150,
            filterable: true,
            sortable: true,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                />
            ),
        },
        {
            field: 'description',
            headerName: 'Description',
            width: 300,
            filterable: true,
            sortable: false,
            renderCell: (params: GridRenderCellParams) => (
                <ExpandableCell
                    {...params}
                    value={params.value || 'No lab description'}
                    variant={"body1"}
                />
            ),
        },
        {
            field: 'networks',
            headerName: 'Networks',
            sortable: false,
            filterable: false,
            width: 82,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value ? (
                        <Done color={"success"} />
                    ) : (
                        <Clear color={"error"} />
                    )}
                </div>
            ),
        },
        {
            field: 'servers',
            headerName: 'Servers',
            sortable: false,
            filterable: false,
            width: 82,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value ? (
                        <Done color={"success"} />
                    ) : (
                        <Clear color={"error"} />
                    )}
                </div>
            ),
        },
        {
            field: 'web_apps',
            headerName: 'Web Apps',
            sortable: false,
            filterable: false,
            width: 82,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value ? (
                        <Done color={"success"} />
                    ) : (
                        <Clear color={"error"} />
                    )}
                </div>
            ),
        },
        {
            field: 'assessment',
            headerName: 'Assessment',
            sortable: false,
            filterable: false,
            width: 94,
            renderCell: (params: GridRenderCellParams) => (
                <div>
                    {params.value ? (
                        <Done color={"success"} />
                    ) : (
                        <Clear color={"error"} />
                    )}
                </div>
            ),
        },
    ];

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Delete",
                variant: 'outlined',
                color: "error",
                requiresSelection: true,
                icon: <DeleteOutlined />,
                addTooltip: true,
                tooltip: "Delete the selected specification edit",
                onClick: handleDeleteDialog,
                loading: buttonLoading.delete
            },
        ];

        return buttonConfig;
    }

    return  (
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
                            variant={"outlined"}
                            color={"info"}
                            onClick={() => navigate(URL_TEACHER_SPECIFICATIONS_BASE)}
                            sx={{ mt: 2, ml: 2 }}
                            endIcon={<KeyboardBackspace />}
                        >
                            View Lab Catalog
                        </Button>
                    </Box>
                    <StyledDataGrid
                        data={flattenedData}
                        columns={columns}
                        disableMultiRowSelection={true}
                        disableSelectBtn={false}
                        labelProps={{
                            text: `${AppUiObjectNames.UNIT} Specification Edits`
                        }}
                        density={"comfortable"}
                        loading={loading}
                        buttonsConfig={getButtonConfig()}
                        onSelection={handleRowSelection}
                        selectedRow={selectedRow}
                    />
                </Paper>
            </Container>

            {/* Generate Page Modals */}
            {selectedRow && (
                <>
                    <ConfirmationDialog
                        open={confirmationDialogOpen}
                        action={"delete"}
                        onClose={() => setConfirmationDialogOpen(false)}
                        handleConfirm={handleConfirmDelete}
                        expectedText={selectedRow?.id}
                        loading={buttonLoading.deleting}
                    />
                </>
            )}
        </>
    );
}

export default CatalogEditTable;
