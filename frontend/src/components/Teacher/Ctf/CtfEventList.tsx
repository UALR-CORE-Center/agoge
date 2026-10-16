import {ArrowOutwardRounded} from "@mui/icons-material";
import FlagIcon from "@mui/icons-material/Flag";
import {Alert, Box, Paper, Tab, Tabs, Tooltip} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useEffect, useState} from "react";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {CtfEventSummary, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {LinkButton} from "../../Buttons/LinkButton";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";

// Same tab styling as ActiveExpiredUnitTable, so the two lists look alike.
const tabSx = {
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
};

const convertTimestamp = (timestamp?: number | null): string => {
    return timestamp ? new Date(timestamp * 1000).toLocaleString() : 'N/A';
};

const generateEventLink = (ctfId: string) => (
    <Box sx={{display: 'flex', alignItems: 'start', height: '100%', minHeight: '50px', marginTop: '4px'}}>
        <LinkButton
            label={ctfId}
            buildId={ctfId}
            endpoint={URL_TEACHER_CTF_EVENT}
            width={"140px"}
            endIcon={<ArrowOutwardRounded />}
            target={"_self"}
        />
    </Box>
);

const columns: GridColDef[] = [
    {
        field: 'id',
        headerName: 'ID',
        renderCell: (params) => generateEventLink(params.row.id),
        // The link button is a fixed 140px.
        minWidth: 160,
    },
    {
        field: 'name',
        headerName: 'Name',
        width: 220,
        minWidth: 130,
        renderCell: (params) => (
            <Tooltip title={params.value}>
                <span>{params.value}</span>
            </Tooltip>
        ),
    },
    {field: 'state_name', headerName: 'State', width: 120, minWidth: 100},
    {field: 'board_count', headerName: 'Teams', type: 'number', width: 90, minWidth: 80},
    {field: 'unit_id', headerName: 'Unit', width: 130, minWidth: 110},
    {
        field: 'creation_timestamp',
        headerName: 'Created',
        width: 180,
        minWidth: 110,
        valueFormatter: (value?: number | null) => convertTimestamp(value),
    },
    {
        field: 'starts_at',
        headerName: 'Started',
        width: 180,
        minWidth: 110,
        valueFormatter: (value?: number | null) => convertTimestamp(value),
    },
    {
        field: 'ends_at',
        headerName: 'Ends',
        width: 180,
        minWidth: 110,
        valueFormatter: (value?: number | null) => convertTimestamp(value),
    },
];

const CtfEventList: React.FC = () => {
    const [events, setEvents] = useState<CtfEventSummary[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedTab, setSelectedTab] = useState<number>(0);

    useEffect(() => {
        let cancelled = false;
        const fetchEvents = async () => {
            try {
                const fetched = await ctfService.list();
                if (!cancelled) {
                    setEvents(fetched ?? []);
                }
            } catch (err) {
                if (!cancelled) {
                    const {status, message} = (err ?? {}) as {status?: number, message?: string};
                    setEvents([]);
                    setError(`${status || "Unknown Status"}: ${message || "Could not load CTF events."}`);
                }
                console.error(err);
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };
        fetchEvents();
        return () => {
            cancelled = true;
        };
    }, []);

    // Archived is the only read-only state; everything else (BROKEN included) still needs attention.
    const archived = selectedTab === 1;
    const rows = events.filter(event => (event.state === CtfStates.ARCHIVED) === archived);

    return (
        <Box sx={{width: '100%', minWidth: 0, p: {xs: 0, sm: 2}, mx: 'auto', overflow: 'hidden'}}>
            <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'flex-start', width: '100%'}}>
                <Tabs
                    variant={"scrollable"}
                    allowScrollButtonsMobile
                    value={selectedTab}
                    sx={{maxWidth: '100%'}}
                    onChange={(_event, value: number) => setSelectedTab(value)}
                >
                    <Tab label="Active" sx={tabSx} />
                    <Tab label="Archived" sx={tabSx} />
                </Tabs>
                {error && (
                    <Alert severity="error" sx={{mt: 2, width: '100%'}}>{error}</Alert>
                )}
                <Paper elevation={1} sx={{width: '100%', minWidth: 0, overflow: 'hidden', mt: 2, p: {xs: 1, sm: 2}}}>
                    <StyledDataGrid
                        data={rows}
                        columns={columns}
                        disableMultipleRowSelection={true}
                        disableSelectBtn={true}
                        disableCheckBoxes={true}
                        localeText={{
                            noRowsLabel: archived ? "No archived CTF events" : "No active CTF events",
                        }}
                        labelProps={{
                            text: "CTF Events",
                            icon: <FlagIcon fontSize={"large"} />,
                        }}
                        density={"comfortable"}
                        loading={loading}
                    />
                </Paper>
            </Box>
        </Box>
    );
};

export default CtfEventList;
