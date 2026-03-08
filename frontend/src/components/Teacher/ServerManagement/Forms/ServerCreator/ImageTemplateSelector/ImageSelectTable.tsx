import {Box, Button, Chip, Stack, Typography} from '@mui/material';
import {
    GridColDef,
    GridFilterListIcon,
    GridFilterModel,
    GridRenderCellParams,
    GridRowSelectionModel,
    useGridApiRef,
} from '@mui/x-data-grid-pro';
import {ClearIcon} from '@mui/x-date-pickers';
import React, {useEffect, useState} from 'react';

import {GlobalComputeImage, ImageSummary, ImageSummaryLists} from '../../../../../../services/Server/image.model';
import {serverService} from '../../../../../../services/Server/server.service';
import {ExpandableCell} from '../../../../../Common/DataGrid/ExpandableCell';
import StyledDataGrid from '../../../../../Common/DataGrid/StyledDataGrid';
import {ResponsiveGrid} from '../../../../../Common/Grid/ResponsiveGrid';

interface Props {
    onSelect: (selectedRow: any) => void;
    hasError?: boolean;
}

export const ImageSelectTable: React.FC<Props> = (props) => {
    const apiRef = useGridApiRef();
    const [imageLists, setImageLists] = useState<ImageSummaryLists | null>(null);
    const [loading, setLoading] = useState(true);
    const [flattenedData, setFlattenedData] = useState<any[]>([]);
    const [selectedImageRow, setSelectedImageRow] = useState<any[]>([]);
    const [projectList, setProjectList] = useState<any[]>([]);
    const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });


    useEffect(() => {
        const fetchData = async () => {
            try {
                const response: ImageSummaryLists = await serverService.list();
                setImageLists(response);
            } catch (error) {
                console.error('Error fetching image lists:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    useEffect(() => {
        const sortImages = () => {
            const flattenedImages: React.SetStateAction<any[]> = [];
            const projectSet = new Set<string>();

            imageLists?.project.forEach((image) => {
                if (image.is_enabled){
                    const flattened = getFlattenedData(image, "project") as GlobalComputeImage;
                    flattenedImages.push(flattened);
                    projectSet.add(flattened.project);
                }
            });

            imageLists?.custom.forEach((image) => {
                const flattened = getFlattenedData(image, "custom") as ImageSummary;
                flattenedImages.push(flattened);
            });
            projectSet.add('custom');

            setProjectList(Array.from(projectSet));
            setFlattenedData(flattenedImages);
        };

        sortImages();
    }, [imageLists]);

    const getFlattenedData = (image: any, model: "project" | "custom"): GlobalComputeImage | ImageSummary => {
        if (model === "project") {
            return {
                os: image.os,
                id: image.uuid,
                name: image.name,
                uuid: image.uuid,
                image: image.image,
                family: image.family,
                project: image.project,
                disk_size: image.disk_size,
                self_link: image.self_link,
                is_enabled: image.is_enabled,
                description: image?.description,
                creationTimestamp: image.creationTimestamp,
            } as GlobalComputeImage;
        } else {
            return  {
                id: image.name,
                os: image.os,
                name: image.name,
                disk_size: image.add_disk,
                self_link: image.self_link,
                family: 'custom',
                project: 'custom',
                description: image.description,
                base_family: image?.base_family
            } as ImageSummary;
        }
    }

    const projectColor = (project: string) => {
        if (project === 'windows-cloud' || project === 'windows-sql-cloud') {
            return "info";
        } else if (project === 'custom') {
            return "success";
        } else {
            return "secondary";
        }
    }

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        const selectedRow = flattenedData.filter(
            row => selectionModel.includes(row.id)
        );
        setSelectedImageRow(selectedRow[0]);
        props.onSelect(selectedRow[0]);
    }

    const handleFilterByProject = (project: string) => {
        apiRef.current.setFilterModel({
            items: [
                { field: 'project', operator: 'contains', value: project }
            ]
        });
    };

    const handleClearFilter = () => {
        apiRef.current.setFilterModel({ items: [] });
    };

    const dataGridFilterButtons = () => {
        const buttons = projectList
            .sort((a, b) => a.localeCompare(b))
            .map((project, index) => (
            <Button
                key={index}
                variant={"text"}
                onClick={() => handleFilterByProject(project)}
                sx={{width: "100%"}}
                color={"info"}
            >
                {project.replace("-cloud", "")}
            </Button>
        ));

        buttons.push(
            <Button
                startIcon={<ClearIcon />}
                variant={"text"}
                sx={{width: "100%", color:'error.main'}}
                onClick={() => handleClearFilter()}
            >
                Clear Filter
            </Button>
        )

        return buttons;
    }

    const columns: GridColDef[] = [
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
            field: 'project',
            headerName: 'Project',
            flex: 1,
            filterable: true,
            sortable: true,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value}
                    variant={"filled"}
                    color={projectColor(params.value)}
                />
            ),
        },
        {
            field: "disk_size",
            headerName: "Disk Size (GB)",
            flex: 1,
            filterable: false,
            sortable: false,
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
        }
    ]

    return (
        <>
            <Box>
                <Box sx={{ border: "1px solid gray", borderRadius: "4px", p: 2}}>
                    <Stack direction={"row"} alignItems={"center"} p={1}>
                        <GridFilterListIcon />
                        <Typography>
                            Image Filters
                        </Typography>
                    </Stack>
                    <ResponsiveGrid
                        items={dataGridFilterButtons()}
                        itemPadding={0}
                    />
                </Box>

                <Box style={{width: "100%", marginBottom: 5}}>
                    <StyledDataGrid
                        data={flattenedData}
                        columns={columns}
                        disableMultiRowSelection={true}
                        disableSelectBtn={true}
                        disableRowSelectionOnClick={false}
                        density={"compact"}
                        labelProps={{
                            disable: true
                        }}
                        loading={loading}
                        onSelection={handleRowSelection}
                        selectedRow={selectedImageRow}
                        pageSize={5}
                        disableAutoHeight={false}
                        filterModel={filterModel}
                        onFilterModelChange={
                            (newFilterModel) => setFilterModel(newFilterModel)
                        }
                        apiRef={apiRef}
                    />
                    {props.hasError && (
                        <Typography color={"error"} variant={"body2"} mt={1}>
                            *You must select an image before proceeding.
                        </Typography>
                    )}
                </Box>
            </Box>
        </>
    );
}