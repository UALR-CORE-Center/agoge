import AssignmentIcon from "@mui/icons-material/Assignment";
import {LoadingButton} from "@mui/lab";
import {
    Box,
    Stack,
    Theme,
    Typography,
    Skeleton,
    Tooltip,
    CircularProgress,
} from "@mui/material";
import {TypographyProps} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import { SxProps } from "@mui/system";
import {
    DataGridPro,
    GridRowHeightReturnValue,
    GridToolbar,
    DataGridProProps,
} from "@mui/x-data-grid-pro";
import React, {useState, useEffect, useId} from "react";
import {CustomPagination} from "./CustomPagination";


interface DataGridProps extends DataGridProProps {
    data: any[];
    loading?: boolean;
    labelProps?: {
        text?: string;
        sx?: SxProps<Theme>;
        icon?: React.ReactNode;
        variant?: TypographyProps["variant"];
        disable?: boolean;
    };
    pageSize?: 5 | 10 | 25 | 50 | 100;
    disableSelectBtn?: boolean;
    disableMultiRowSelection?: boolean;
    disableRowSelectionOnClick?: boolean;
    disableCheckBoxes?: boolean;
    onSelection?: (value: any) => void;
    selectedRow?: any;
    buttonsConfig?: ButtonConfig[];
    showCellBorder?: boolean;
    disableAutoHeight?: boolean;

    // Could be updated to be JSX.Element for customizing
    refreshing?: boolean;
    refreshingText?: string;
}

export type ButtonConfig = {
    label: string;
    variant: 'outlined' | 'contained';
    color: 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' | "inherit";
    icon?: React.ReactNode;
    onClick: () => void;
    requiresSelection?: boolean;
    addTooltip: boolean;
    tooltip?: string;
    loading?: boolean;
    href?: string;
    isDisabled?: boolean;
};

const StyledDataGrid: React.FC<DataGridProps> = ({
                                                     refreshing = false,
                                                     refreshingText = 'Refreshing',
                                                     ...props
                                                 })  => {
    const [searchQuery, setSearchQuery] = useState<string>('');
    const [filteredData, setFilteredData] = useState<any[]>(props.data);
    const [internalRefreshing, setInternalRefreshing] = useState(refreshing);
    const headingId = useId();


    useEffect(() => {
        // Creates a delay when updating the internal refreshing logic. This prevents
        // "Refreshing" from popping up for .5 seconds and then disappearing - right now
        // we're using a 1.5s buffer
        setTimeout(() => setInternalRefreshing(refreshing), refreshing ? 0: 1500)
    }, [refreshing]);




    useEffect(() => {
        setFilteredData(
            props.data.filter(row =>
                Object.values(row).some(value => String(value).toLowerCase().includes(searchQuery.toLowerCase()))
            )
        );
    }, [props.data, searchQuery]);

    const checkButtonDisabled = (button: ButtonConfig, selectedRow: any): boolean => {
        if (button.isDisabled !== undefined) {
            return button.isDisabled;
        }
        const requiresSelection = button.requiresSelection ?? false;
        return requiresSelection && (!selectedRow || selectedRow.length === 0);
    };

    const renderButtons = () => {
        return (
            <Box
                sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 2,
                    justifyContent: 'flex-start',
                    width: '100%',
                }}
            >
                {props.buttonsConfig?.map((button, index) => {
                    const isDisabled = checkButtonDisabled(button, props.selectedRow);

                    const buttonElement = (
                        <LoadingButton
                            key={index}
                            variant={button.variant}
                            color={button.color || 'primary'}
                            onClick={() => button.onClick()}
                            disabled={isDisabled}
                            startIcon={button.icon}
                            sx={{
                                mx: '2',
                            }}
                            loading={button.loading}
                            loadingPosition="start"
                            href={button?.href}
                        >
                            {button.label}
                        </LoadingButton>
                    );

                    if (button.addTooltip && button.tooltip) {
                        return (
                            <Tooltip key={index} title={button.tooltip} describeChild>
                                <span>{buttonElement}</span>
                            </Tooltip>
                        );
                    }

                    return buttonElement;
                })}
            </Box>
        );
    };

    const autoHeightProps = () => {
        if (!props.disableAutoHeight) {
            return {
                getRowHeight: (): GridRowHeightReturnValue => 'auto',
                getEstimatedRowHeight: () => 100,
                autoHeight: true,
            };
        }
        return {};
    };

    const render = () => {
        if (props.loading) {
            return (
                <Skeleton variant={"rectangular"} width="100%" height={300} />
            );
        } else {
            return (
                <DataGridPro
                    aria-labelledby={props.labelProps?.text ? headingId : undefined}
                    {...props}
                    {...autoHeightProps()}
                    sx={{
                        ...props.sx,
                        '&.MuiDataGrid-root--densityCompact .MuiDataGrid-cell': { py: '8px' },
                        '&.MuiDataGrid-root--densityStandard .MuiDataGrid-cell': { py: '15px' },
                        '&.MuiDataGrid-root--densityComfortable .MuiDataGrid-cell': { py: '22px' },
                    }}
                    checkboxSelection={props.disableCheckBoxes === undefined ? true : !props.disableCheckBoxes}
                    rows={props.data}
                    loading={!!props.loading}
                    filterDebounceMs={60}
                    disableMultipleRowSelection={props.disableMultiRowSelection ?? false}
                    disableRowSelectionOnClick={
                        props.disableRowSelectionOnClick ? props.disableRowSelectionOnClick : false
                    }
                    disableDensitySelector={false}
                    disableColumnFilter={false}
                    density={props.density ? props.density : "comfortable"}
                    slots={{
                        toolbar: GridToolbar,
                        pagination: CustomPagination,
                    }}
                    slotProps={{
                        toolbar: {
                            csvOptions: { disableToolbarButton: true },
                            printOptions: { disableToolbarButton: true },
                            showQuickFilter: true,
                            quickFilterProps: { debounceMs: 250 },
                        },
                    }}
                    onRowSelectionModelChange={props.onSelection}
                    pagination
                    initialState={{
                        ...props?.initialState,
                        pagination: {
                            paginationModel: {
                                pageSize: props.pageSize ? props.pageSize : 10
                            }
                        }
                    }}
                    pageSizeOptions={[5, 10, 20, 50, 100]}
                    showCellVerticalBorder={!!props.showCellBorder}
                />
            );
        }
    };

    const renderLabel = () => {
        if (props.labelProps?.disable) {
            return null;
        } else {
            return (
                <Stack alignItems="center" direction="row" gap={1} paddingTop={1}>
                    {props.labelProps?.icon ?? <AssignmentIcon fontSize="large" />}
                    <Typography
                        id={props.labelProps?.text ? headingId : undefined}
                        variant={props.labelProps?.variant ?? "h4"}
                        component="h2"
                        sx={{
                            fontFamily: "monospace",
                            letterSpacing: 2,
                            ...(props.labelProps?.sx ?? {}),
                        }}
                    >
                        {props.labelProps?.text}
                    </Typography>
                </Stack>
            )
        }
    }


    const theme = useTheme();
    return (
        <>
            {renderLabel()}
            <Box sx={{ py: 2 }}>
                <Stack direction={'row'} alignItems={'center'} justifyContent={'space-between'}>
                    {
                        renderButtons()
                    }

                    {
                        internalRefreshing &&
                        <Stack gap={1} direction={'row'} alignItems={'center'} role="status" aria-live="polite">
                            <Typography variant={'body2'} color={theme.palette.text.secondary}>
                                {refreshingText}
                            </Typography>
                            <CircularProgress thickness={5} size={15} aria-label="Refreshing"/>
                        </Stack>
                    }
                </Stack>
            </Box>
            {render()}
        </>
    );
};

export default StyledDataGrid;
