import {Clear, Done, Layers} from "@mui/icons-material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary, Box,
    Button,
    CircularProgress, Stack,
    Typography,
    useTheme
} from "@mui/material";
import {GridRowSelectionModel} from "@mui/x-data-grid";
import {GridColDef, GridFilterListIcon, GridFilterModel, useGridApiRef} from "@mui/x-data-grid-pro";
import {ClearIcon} from "@mui/x-date-pickers";
import React, {useEffect, useState} from "react";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {ExpandableCell} from "../../../../Common/DataGrid/ExpandableCell";
import StyledDataGrid from "../../../../Common/DataGrid/StyledDataGrid";
import {ResponsiveGrid} from "../../../../Common/Grid/ResponsiveGrid";
import {IFormKeys} from "../FormFields";


interface Props {
    loading: boolean;
    options: ServerMachineTypes[];
    onSelect: (selectedRow: any) => void;
    formFields: any;
    hasError?: boolean;
}

export const SelectMachineTypeTable: React.FC<Props> = (props) => {
    const apiRef = useGridApiRef();
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';
    const machineTypes = props.options;
    const formField = props.formFields[IFormKeys.MACHINE_TYPE];
    const [flattened, setFlattened] = useState<ServerMachineTypes[]>([]);
    const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });
    const [isInitialized, setIsInitialized]  = useState<boolean>(false);
    const [mTypeGroups, setMTypeGroups] = useState<string[]>([]);

    const getMTypeGroup = (mType: ServerMachineTypes) => {
        const splitName = mType.name.split("-");
        splitName.pop();
        return splitName.join("-");
    }

    const getMType = () => {
        return machineTypes.find(mType => mType.name == formField);
    }

    const handleRowSelection = (selectionModel: GridRowSelectionModel) => {
        const selectedRow = flattened.filter(
            row => selectionModel.includes(row.id)
        );
        if (selectedRow) props.onSelect(selectedRow[0]);
    }

    const handleClearFilter = () => {
        apiRef.current.setFilterModel({ items: [] });
    };

    const handleFilterBtn = (mTypeName: string) => {
        apiRef.current.setFilterModel({
            items: [
                { field: 'id', operator: 'contains', value: mTypeName }
            ]
        });
    }

    const dataGridFilterButtons = () => {
        const buttons = mTypeGroups
            .sort((a, b) => a.localeCompare(b))
            .map((mType, index) => (
                <Button
                    key={index}
                    variant={"text"}
                    onClick={() => handleFilterBtn(mType)}
                    sx={{width: "100%"}}
                    color={"info"}
                >
                    {mType}
                </Button>
            ));

        buttons.push(
            <Button
                startIcon={<ClearIcon />}
                variant={"text"}
                sx={{width: "100%"}}
                color={"secondary"}
                onClick={() => handleClearFilter()}
            >
                Clear Filter
            </Button>
        )

        return buttons;
    }

    const renderSharedCoreCell = (shared: boolean) => {
        if (shared) {
            return (<Done color={"success"} />);
        } else {
            return (<Clear color={"error"} />);
        }
    }

    const initialValue = () => {
        if (formField && !isInitialized) {
            const defaultRow = getMType();

            if (apiRef.current && defaultRow != undefined) {
                apiRef.current.setRowSelectionModel([formField]);
                setIsInitialized(true);
            }
        }
    }

    useEffect(() => {
        if (!props.loading && machineTypes) {
            const mTypeSet = new Set<string>();
            machineTypes.forEach((mType) => {
                mTypeSet.add(getMTypeGroup(mType))
            })

            setMTypeGroups(Array.from(mTypeSet));
            setFlattened(machineTypes);
        }

    }, [machineTypes, props.loading]);

    useEffect(() => {
        if (flattened.length > 0) {
            initialValue();
        }
    }, [flattened]);

    const columns: GridColDef[] = [
        {
            field: 'id',
            headerName: 'Id',
        },
        {
            field: 'name',
            headerName: 'Name',
            flex: 1,
            filterable: true,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                    missingText={"No machine type name."}
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
                    missingText={"No machine type description."}
                />
            ),
        },
        {
            field: 'is_shared_core',
            headerName: "Shared Core",
            flex: 1,
            filterable: true,
            sortable: false,
            renderCell: (params: any) => (
                renderSharedCoreCell(params.value)
            )
        }
    ]

    const buttonBackground = (): string => {
        return isDarkMode ? "#121212" : "#dad6d6";
    }
    
    return (
        <>
            <Accordion sx={{ background: "inherit", mb: 2 }}>
                <AccordionSummary
                    expandIcon={<ExpandMoreIcon />}
                    aria-controls={"image-select-accordion"}
                    id={`image-select-accordion-header`}
                    sx={{background: theme.palette.action.hover}}
                >
                    <>
                        {props.loading ? <CircularProgress size={18} sx={{mr: 1}} /> : <Layers sx={{mr: 1}}/>}
                        <Typography mr={1}>Machine Type</Typography>
                        (
                        <Typography color={formField.trim() != "" ? "info" : "error"}>
                            {getMType()?.id || "No machine type selected"}
                        </Typography>
                        )
                    </>
                </AccordionSummary>
                <AccordionDetails>
                    <Box
                        sx={{
                            border: "1px solid gray",
                            borderRadius: "4px",
                            p: 2,
                            background: buttonBackground()
                        }}
                    >
                        <Stack direction={"row"} alignItems={"center"} p={1}>
                            <GridFilterListIcon />
                            <Typography>
                                Machine Type Filters
                            </Typography>
                        </Stack>
                        <ResponsiveGrid
                            items={dataGridFilterButtons()}
                            itemPadding={0}
                        />
                    </Box>
                    <Box style={{ width: "100%", marginBottom: 5 }}>
                        <StyledDataGrid
                            data={flattened}
                            columns={columns}
                            disableMultiRowSelection={true}
                            disableSelectBtn={true}
                            disableRowSelectionOnClick={false}
                            density={"compact"}
                            labelProps={{
                                disable: true
                            }}
                            loading={props.loading}
                            onSelection={handleRowSelection}
                            selectedRow={getMType()}
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
                                        id: false,
                                    }
                                }
                            }}
                        />
                    </Box>
                </AccordionDetails>
            </Accordion>
        </>
    )
}