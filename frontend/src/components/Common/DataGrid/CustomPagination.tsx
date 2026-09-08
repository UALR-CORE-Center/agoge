import {TablePaginationProps} from "@mui/material";
import MuiPagination from "@mui/material/Pagination";
import {
    GridApi,
    gridPageCountSelector,
    GridPagination,
    useGridApiContext,
    useGridSelector
} from "@mui/x-data-grid";
import React from "react";

function Pagination(
{
    page,
    onPageChange,
    className,
}: Pick<TablePaginationProps, 'page' | 'onPageChange' | 'className'>) {
    const apiRef = useGridApiContext<GridApi>();
    const pageCount = useGridSelector(apiRef, gridPageCountSelector) as number;

    return (
        <MuiPagination
            color="primary"
            className={className}
            count={pageCount}
            page={page + 1}
            onChange={(event, newPage) => {
                onPageChange(event as any, newPage - 1);
            }}
        />
    );
}

export function CustomPagination(props: any) {
    return <GridPagination ActionsComponent={Pagination} {...props} />;
}
