import { Box, TextField, useTheme } from '@mui/material';
import { DataGrid, GridRowSelectionModel } from '@mui/x-data-grid';
import React, { ReactElement, useEffect, useState } from 'react';

interface DataTableProps {
    title?: ReactElement;
    columns?: any[];
    data: any[];
    onCheckboxChange?: (selectedRows: any[]) => void;
    selectedRows?: Set<number>;
    renderCell?: (row: any, column: string) => React.ReactNode;
    showSearch?: boolean;
    getRowId?: (row: any) => any;
    checkboxSelection?: boolean;
    loading?: boolean;
    showContainer?: boolean;
}

const generateColumnsFromData = (data: any[]) => {
    if (data.length === 0) return [];
    const keys = Object.keys(data[0]);
    return keys.map(key => ({
        display: 'flex',
        flex: 1,
        field: key,
        headerName: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        resizable: false,
        renderCell: (params: any) =>
            typeof params.value === 'object' && params.value !== null
                ? JSON.stringify(params.value)
                : params.value
    }));
};

const calculateColumnWidths = (data: any[]) => {
    if (data.length === 0) return {};
    const widths: { [key: string]: number } = {};
    data.forEach(row => {
        Object.keys(row).forEach(key => {
            const value = row[key];
            const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
            const width = Math.min(Math.max(text.length * 10, 100), 300); // min 100px, max 300px
            if (!widths[key] || width > widths[key]) {
                widths[key] = width;
            }
        });
    });
    return widths;
};

const DataTable: React.FC<DataTableProps> = ({
    title,
    columns,
    data,
    onCheckboxChange,
    selectedRows = new Set(),
    renderCell,
    showSearch = true,
    getRowId,
    checkboxSelection = true,
    loading = false,
}) => {
    const [selectionModel, setSelectionModel] = useState<GridRowSelectionModel>([]);
    const [searchQuery, setSearchQuery] = useState<string>('');
    const [filteredData, setFilteredData] = useState<any[]>(data);
    const [dynamicColumns, setDynamicColumns] = useState<any[]>(columns || []);

    const theme = useTheme();

    useEffect(() => {
        setFilteredData(
            data.filter(row =>
                Object.values(row).some(value =>
                    String(value).toLowerCase().includes(searchQuery.toLowerCase())
                )
            )
        );
    }, [searchQuery, data]);

    useEffect(() => {
        const selectedIDs = new Set(selectionModel);
        const selectedRows = data.filter(row => selectedIDs.has(getRowId ? getRowId(row) : row.id));
        if (onCheckboxChange) {
            onCheckboxChange(selectedRows);
        }
    }, [selectionModel, data, onCheckboxChange, getRowId]);

    useEffect(() => {
        // Check if columns have defined widths
        const widths = calculateColumnWidths(filteredData);

        const updatedColumns = (columns || generateColumnsFromData(data)).map(column => ({
            ...column,
            width: column.width !== undefined ? column.width : (widths[column.field] || 150), // Only calculate if width isn't provided
            resizable: column.resizable !== undefined ? column.resizable : false, // Use passed resizable if provided
        }));

        setDynamicColumns(updatedColumns);
    }, [filteredData, columns, data]);

    const processedData = filteredData.map(row => {
        const processedRow = { ...row };
        for (const key in processedRow) {
            if (typeof processedRow[key] === 'object' && processedRow[key] !== null) {
                processedRow[key] = JSON.stringify(processedRow[key]);
            }
        }
        return processedRow;
    });

    return (
        <Box sx={{ height: '100%', width: '100%' }}>
            {title && (
                <Box>
                    {title}
                </Box>
            )}
            {showSearch && (
                <TextField
                    label="Search"
                    variant="outlined"
                    fullWidth
                    margin={"dense"}
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    sx={{
                        '& .MuiInputBase-root': {
                            color: theme.palette.text.primary,
                        },
                        '& .MuiOutlinedInput-root': {
                            '& fieldset': {
                                borderColor: theme.palette.divider,
                            },
                            '&:hover fieldset': {
                                borderColor: theme.palette.text.primary,
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: theme.palette.primary.main,
                            },
                        },
                        '& .MuiInputLabel-root': {
                            color: theme.palette.text.primary,
                        },
                        '& .MuiOutlinedInput-input': {
                            height: '1.5em',
                        },
                    }}
                />
            )}

            <DataGrid
                initialState={{
                    pagination: {
                        paginationModel: {
                            pageSize: 10
                        }
                    }
                }}
                autoHeight
                getRowHeight={() => 'auto'}
                pageSizeOptions={[10, 20, 50]}
                getRowId={getRowId}
                rows={processedData}
                columns={dynamicColumns}
                checkboxSelection={checkboxSelection}
                disableRowSelectionOnClick
                onRowSelectionModelChange={newSelection => {
                    setSelectionModel(newSelection);
                }}
                rowSelectionModel={selectionModel}
                loading={loading} // Use built-in loading prop
                sx={{
                    '& .MuiDataGrid-columnHeaders': {
                        textAlign: 'center',
                        backgroundColor: theme.palette.background.default,
                    },
                    '& .MuiDataGrid-columnHeaderTitle': {
                        textAlign: 'center',
                    },
                    '& .MuiDataGrid-cell': {
                        textAlign: 'center',
                    },
                    '& .MuiDataGrid-checkboxInput': {
                        color: theme.palette.text.primary,
                    },
                }}
            />
        </Box>
    );
};

export default DataTable;
