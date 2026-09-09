import {Memory} from "@mui/icons-material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box, Button,
    Chip,
    CircularProgress,
    Typography,
    useTheme
} from '@mui/material';
import {
    GridColDef,
    GridFilterModel,
    GridRenderCellParams,
    GridRowSelectionModel,
    useGridApiRef,
} from '@mui/x-data-grid';
import React, {useEffect, useState} from "react";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {ImageStates} from "../../../../../types/AgogeStates";
import {IFormFieldMeta} from "../../../../../types/Form";
import {ExpandableCell} from "../../../../Common/DataGrid/ExpandableCell";
import StyledDataGrid from '../../../../Common/DataGrid/StyledDataGrid';

interface Props {
    loading: boolean;
    images: AgogeImage[];
    onSelect: (selectedRow: any, index: number) => void;
    hasError?: boolean;
    formField: IFormFieldMeta;
    index: number;
}

export const SelectImageTable: React.FC<Props> = (props) => {
    const apiRef = useGridApiRef();
    const theme = useTheme();
    const images = props.images;
    const [flattened, setFlattened] = useState<AgogeImage[]>([]);
    const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });
    const [isInitialized, setIsInitialized]  = useState<boolean>(false);

    const getFlattenedData = (image: any): AgogeImage => {
        const getOs = () => {
            return image?.base_family ? image.base_family : image.os;
        }

        const diskSize = () => {
            if (image.disks) {
                return image.disks[0].initializeParams.diskSizeGb;
            } else {
                return image.add_disk;
            }
        }

        return {
            ...image,
            id: image.image,
            os: getOs(),
            dns_record: "",
            in_use_by: "",
            disk_size: diskSize()
        }
    }

    const getImage = () => {
        return images.find(img => img.image == props.formField.value);
    }

    const isCheckedOut = (): boolean => {
        const image = getImage();
        if (image) {
            return Number(image.status) === Number(ImageStates.CHECKED_OUT);
        } else {
            return false;
        }
    }

    const getStatusNode = (status: number) => {
        let statusText, statusColor;

        if (status === Number(ImageStates.CHECKED_OUT)) {
            statusText = "Checked Out";
            statusColor = 'error';
        } else {
            statusText = "Checked In";
            statusColor = 'success';
        }

        return (
            <Chip
                label={statusText}
                variant={"filled"}
                color={statusColor}
            />
        )
    }

    const handleRowSelection = (selectionModel: GridRowSelectionModel): void => {
        const selectedRow = flattened.filter(
            row => selectionModel.includes(row.id)
        );

        if (selectedRow) props.onSelect(selectedRow[0], props.index);
    }

    const initialValue = () => {
        if (props.formField && !isInitialized) {
            const imageId = props.formField.value;
            const defaultRow = getImage();

            if (apiRef.current && defaultRow != undefined) {

                console.log(`SelectImageTable initial value: ${imageId}`);

                apiRef.current.setRowSelectionModel([imageId]);

                handleRowSelection([imageId]);
                setIsInitialized(true);
            }
        }
    }

    useEffect((): void => {
        if (!props.loading) {
            const cleaned = images
                .filter((image) => image.image_exists)
                .map(getFlattenedData);
            setFlattened(cleaned);
        }
    }, [images, props.loading]);

    useEffect(() => {
        if (flattened.length > 0) {
            initialValue();
        }
    }, [flattened]);

    const columns: GridColDef[] = [
        {
            field: "image",
            headerName: "Image",
        },
        {
            field: 'name',
            headerName: 'Name',
            flex: 1,
            filterable: true,
            renderCell: (params: any) => (
                <Button
                    variant="text"
                    tabIndex={0}
                    aria-label={`Select ${params.value || "image"}`}
                    fullWidth
                >
                    {params.value || "No image name."}
                </Button>
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
            field: "os",
            headerName: "Operating System",
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <>
                    <Typography variant={"button"}>
                        {params.value}
                    </Typography>
                </>
            )
        },
        {
            field: "add_disk",
            headerName: "Disk Size (GB)",
            flex: 1,
            filterable: false,
            sortable: false,
        },
        {
            field: 'status',
            headerName: 'Status',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                getStatusNode(params.value)
            ),
        },
    ];

    return (
        <>
            <Accordion sx={{ background: "inherit", mb: 2 }}>
                <AccordionSummary
                    expandIcon={<ExpandMoreIcon />}
                    aria-controls={"image-select-accordion"}
                    id={`${props.index}-image-select-accordion-header`}
                    sx={{background: theme.palette.action.hover}}
                >
                    <>
                        {props.loading ? <CircularProgress size={18} sx={{mr: 1}} /> : <Memory sx={{mr: 1}}/>}
                        <Typography mr={1}>Server Image *</Typography>
                        (<Typography color={props.formField.value.trim() != "" ? "info" : "error"}>
                            {getImage()?.image || "No image selected"}
                        </Typography>)
                    </>
                </AccordionSummary>
                <AccordionDetails>
                    <Box style={{width: "100%", marginBottom: 5}}>
                        <StyledDataGrid
                            data={flattened}
                            columns={columns}
                            disableMultiRowSelection={true}
                            disableSelectBtn={true}
                            disableRowSelectionOnClick={false}
                            density={"compact"}
                            labelProps={{disable: true}}
                            loading={props.loading}
                            onSelection={handleRowSelection}
                            selectedRow={getImage()}
                            pageSize={5}
                            disableAutoHeight={false}
                            filterModel={filterModel}
                            onFilterModelChange={
                                (newFilterModel) => setFilterModel(newFilterModel)
                            }
                            apiRef={apiRef}
                            initialState={{
                                columns: {
                                    columnVisibilityModel: {
                                        image: false
                                    }
                                }
                            }}
                        />
                        {props.hasError && (
                            <Typography color={"error"} variant={"body2"} mt={1}>
                                *You must select an image before proceeding.
                            </Typography>
                        )}
                        {isCheckedOut() && (
                            <Typography color={"warning"} variant={"body1"} mt={1}>
                                Warning: The selected compute image is currently checked out.
                                Changes will not appear in lab builds until the image is checked in and updated.
                            </Typography>
                        )}
                    </Box>
                </AccordionDetails>
            </Accordion>
        </>
    )
}
