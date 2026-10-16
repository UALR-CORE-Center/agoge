import {Box, Typography} from "@mui/material";
import {
    GridCallbackDetails,
    GridColDef,
    GridColumnVisibilityModel,
    GridRenderCellParams,
    GridRowParams,
} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useMemo, useState} from "react";

/*
 * Responsive behaviour for StyledDataGrid, in two tiers:
 *
 * 1. Fluid: fixed column widths become proportional flex columns with a minimum
 *    width, so the grid fills its container and shrinks with it instead of
 *    pushing columns past the right edge.
 * 2. Stacked: once the grid itself is narrower than the sum of the visible
 *    columns' minimum widths (all columns can no longer fit on one line), each
 *    row is rendered as a card of label/value pairs in a single column.
 *    Selection, quick search and pagination keep working because the grid,
 *    its rows and its hidden columns are all still there.
 *
 * The setpoint is measured on the grid's container rather than the viewport,
 * because grids live in pages, accordions and dialogs of very different widths.
 */

export const STACKED_FIELD = '__stacked__';
export const STACKED_CELL_CLASS = 'agoge-stacked-cell';

// MUI's default column width, used when a column declares neither width nor minWidth.
const DEFAULT_COLUMN_WIDTH = 100;
const CHECKBOX_COLUMN_WIDTH = 50;
const GRID_BORDERS = 2;
// Switch back to columns only once there is clearly room, so a scrollbar
// appearing or disappearing near the setpoint can't make the layout flicker.
const HYSTERESIS = 24;

const minWidthOf = (col: GridColDef) => col.minWidth ?? col.width ?? DEFAULT_COLUMN_WIDTH;

const toFluid = (col: GridColDef): GridColDef => {
    if (col.flex) {
        return col;
    }
    const {width, ...rest} = col;
    // Keep each column's designed width as its share of the space.
    return {...rest, flex: width ?? col.minWidth ?? DEFAULT_COLUMN_WIDTH, minWidth: minWidthOf(col)};
};

interface StackedRowProps {
    params: GridRenderCellParams;
    columns: GridColDef[];
}

const StackedRow: React.FC<StackedRowProps> = ({params, columns}) => {
    const renderValue = (col: GridColDef): React.ReactNode => {
        const cellParams = params.api.getCellParams(params.id, col.field);
        if (col.renderCell) {
            return col.renderCell(cellParams as GridRenderCellParams);
        }
        if ('getActions' in col && typeof col.getActions === 'function') {
            return <Box sx={{display: 'flex', flexWrap: 'wrap'}}>{col.getActions({id: params.id, row: params.row, columns: [col]} as GridRowParams)}</Box>;
        }
        const value = cellParams.formattedValue ?? cellParams.value;
        if (typeof value === 'boolean') {
            return value ? 'Yes' : 'No';
        }
        return value == null || value === '' ? '—' : String(value);
    };

    return (
        <Box sx={{containerType: 'inline-size', width: '100%'}}>
            <Box
                component="dl"
                sx={(theme) => ({
                    m: 0,
                    display: 'grid',
                    gridTemplateColumns: 'minmax(6rem, 30%) minmax(0, 1fr)',
                    columnGap: 2,
                    rowGap: 1,
                    alignItems: 'center',
                    // Very narrow cards (phones): label above its value.
                    [theme.containerQueries.down(360)]: {
                        gridTemplateColumns: 'minmax(0, 1fr)',
                        rowGap: 0.25,
                        '& dd': {mb: 1},
                    },
                })}
            >
                {columns.map((col) => (
                    <React.Fragment key={col.field}>
                        <Typography
                            component="dt"
                            variant="body2"
                            sx={{fontWeight: 600, color: 'text.secondary', overflowWrap: 'anywhere'}}
                        >
                            {col.headerName ?? col.field}
                        </Typography>
                        <Box
                            component="dd"
                            sx={{
                                m: 0,
                                minWidth: 0,
                                overflowWrap: 'anywhere',
                                // Cell renderers often centre content for a table column (some via
                                // inline styles); in a card every value lines up on the left.
                                '& > div, & > .MuiBox-root': {justifyContent: 'flex-start !important', textAlign: 'left'},
                                // Long words may break, but never a button's label.
                                '& .MuiButtonBase-root': {whiteSpace: 'nowrap', overflowWrap: 'normal'},
                            }}
                        >
                            {renderValue(col)}
                        </Box>
                    </React.Fragment>
                ))}
            </Box>
        </Box>
    );
};

interface Options {
    columns: readonly GridColDef[];
    checkboxSelection: boolean;
    initialVisibilityModel?: GridColumnVisibilityModel;
    onColumnVisibilityModelChange?: (model: GridColumnVisibilityModel, details: GridCallbackDetails) => void;
    enabled: boolean;
}

export const useResponsiveColumns = ({
    columns,
    checkboxSelection,
    initialVisibilityModel,
    onColumnVisibilityModelChange,
    enabled,
}: Options) => {
    const [containerWidth, setContainerWidth] = useState<number | null>(null);
    const [stacked, setStacked] = useState(false);
    // The visibility the user chose (Columns panel / initialState). Restored when
    // leaving stacked mode, which temporarily hides every real column.
    const [userVisibility, setUserVisibility] = useState<GridColumnVisibilityModel>(initialVisibilityModel ?? {});

    // The container element is held in state (the ref callback is the setter) and
    // the observer lives in an effect keyed on it. That way StrictMode's dev-only
    // unmount/remount, or the element being replaced, tears the observer down and
    // builds a fresh one, instead of leaving a disconnected observer behind.
    const [container, containerRef] = useState<HTMLElement | null>(null);
    useEffect(() => {
        if (!container || typeof ResizeObserver === 'undefined') {
            return;
        }
        const observer = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
        observer.observe(container);
        return () => observer.disconnect();
    }, [container]);

    const visibleColumns = useMemo(
        () => columns.filter((col) => userVisibility[col.field] !== false),
        [columns, userVisibility]
    );

    const requiredWidth = useMemo(
        () => visibleColumns.reduce((sum, col) => sum + minWidthOf(col), 0)
            + (checkboxSelection ? CHECKBOX_COLUMN_WIDTH : 0)
            + GRID_BORDERS,
        [visibleColumns, checkboxSelection]
    );

    useEffect(() => {
        if (!enabled || containerWidth === null) {
            setStacked(false);
            return;
        }
        setStacked((wasStacked) =>
            wasStacked ? containerWidth < requiredWidth + HYSTERESIS : containerWidth < requiredWidth
        );
    }, [enabled, containerWidth, requiredWidth]);

    const gridColumns = useMemo(() => {
        if (!enabled) {
            return columns as GridColDef[];
        }
        const fluid = columns.map(toFluid);
        if (!stacked) {
            return fluid;
        }
        const stackedColumn: GridColDef = {
            field: STACKED_FIELD,
            headerName: '',
            flex: 1,
            sortable: false,
            filterable: false,
            disableColumnMenu: true,
            hideable: false,
            cellClassName: STACKED_CELL_CLASS,
            // Quick search only looks at visible columns, so give the card
            // column the text of every field it shows.
            valueGetter: (_value, row) => visibleColumns
                .map((col) => row?.[col.field])
                .filter((v) => v != null && typeof v !== 'object')
                .join(' '),
            renderCell: (params) => <StackedRow params={params} columns={visibleColumns}/>,
        };
        return [...fluid, stackedColumn];
    }, [enabled, columns, stacked, visibleColumns]);

    const columnVisibilityModel = useMemo<GridColumnVisibilityModel>(() => {
        if (!stacked) {
            return userVisibility;
        }
        const hidden = Object.fromEntries(columns.map((col) => [col.field, false]));
        return {...hidden, [STACKED_FIELD]: true};
    }, [stacked, columns, userVisibility]);

    const handleVisibilityChange = useCallback((model: GridColumnVisibilityModel, details: GridCallbackDetails) => {
        // In stacked mode the grid reports our own "hide everything" model; ignore it.
        if (stacked) {
            return;
        }
        setUserVisibility(model);
        onColumnVisibilityModelChange?.(model, details);
    }, [stacked, onColumnVisibilityModelChange]);

    return {
        containerRef,
        stacked,
        columns: gridColumns,
        columnVisibilityModel,
        onColumnVisibilityModelChange: handleVisibilityChange,
    };
};
