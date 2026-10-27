import HistoryIcon from "@mui/icons-material/History";
import {Alert, Box, Chip, MenuItem, TextField, Typography} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useRef, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfLogEntry, CtfStates, LOG_ACTIONS, LogAction, LogResult} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import HttpError from "../../Common/Errors/HttpError";

// Matches the hosts panel; the PRD only requires that no CTF poll is faster than 10 s.
export const LOG_POLL_INTERVAL_MS = 15000;
// CtfEvent.MAX_PANEL_ROWS: the API returns at most this many rows, newest first.
export const LOG_ROW_CAP = 500;

export const LOG_ACTION_LABELS: Record<LogAction, string> = {
    CTF_CREATE: 'Event created',
    CTF_UPDATE: 'Event updated',
    CTF_ARM: 'Arm',
    CTF_START: 'Start',
    CTF_PAUSE: 'Pause',
    CTF_RESUME: 'Resume',
    CTF_END: 'End',
    CTF_ARCHIVE: 'Archive',
    CTF_DELETE: 'Event deleted',
    FLAG_REPLANT: 'Flag replant',
    FLAG_REVEAL: 'Flag reveal',
    HOST_RESET: 'Host reset',
    SCORE_ADJUST: 'Score adjustment',
    TEAM_ADD: 'Team added',
    TEAM_REMOVE: 'Team removed',
    TEAM_UPDATE: 'Team roster changed',
    SPEC_UPDATE: 'Flags edited',
    SERVERS_BUILD: 'Servers built',
    SERVERS_START: 'Servers started',
    SERVERS_STOP: 'Servers stopped',
};

const RESULT_COLORS: Record<LogResult, 'success' | 'warning' | 'error'> = {
    OK: 'success',
    DENIED: 'warning',
    ERROR: 'error',
};

// The empty string is the "All actions" choice, which sends no `action` query parameter.
type ActionFilter = LogAction | '';

const formatTimestamp = (seconds: number) => new Date(seconds * 1000).toLocaleString();

const formatDetail = (detail: CtfLogEntry['detail']) =>
    detail && Object.keys(detail).length > 0
        ? Object.entries(detail).map(([key, value]) => `${key}: ${value}`).join(', ')
        : '';

// The API already sorts newest first; sorting again keeps that order a property of this panel.
export const newestFirst = (entries: CtfLogEntry[]) => [...entries].sort((a, b) => b.created_at - a.created_at);

interface CtfEventLogPanelProps {
    ctfId: string;
    state: number;
    // Polls only while the Event Log tab is showing, so hidden panels add no load.
    active: boolean;
}

const CtfEventLogPanel: React.FC<CtfEventLogPanelProps> = ({ctfId, state, active}) => {
    const [entries, setEntries] = useState<CtfLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionFilter, setActionFilter] = useState<ActionFilter>('');
    // Read synchronously by in-flight requests, so a response for a filter the user has since changed is dropped.
    const filterRef = useRef<ActionFilter>('');

    const fetchLog = useCallback(async (filter: ActionFilter) => {
        try {
            const fetched = await ctfService.getLog(ctfId, filter || undefined);
            if (filterRef.current !== filter) {
                return;
            }
            setEntries(newestFirst(fetched ?? []));
            setError(null);
        } catch (err) {
            if (filterRef.current !== filter) {
                return;
            }
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not load the event log."}`);
            console.error(err);
        } finally {
            if (filterRef.current === filter) {
                setLoading(false);
            }
        }
    }, [ctfId]);

    const pollLog = useCallback(() => fetchLog(filterRef.current), [fetchLog]);

    // Rows already written for an archived event can still be read, but no new ones appear; one read is enough.
    const archived = state === CtfStates.ARCHIVED;
    usePolling(pollLog, {enabled: active && !archived, interval: LOG_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) {
            pollLog();
        }
    }, [active, archived, pollLog]);

    const handleFilterChange = (value: ActionFilter) => {
        filterRef.current = value;
        setActionFilter(value);
        setLoading(true);
        // Read now rather than waiting up to a full poll interval for the filter to apply.
        fetchLog(value);
    };

    const columns: GridColDef<CtfLogEntry>[] = [
        {
            field: 'created_at',
            headerName: 'Time',
            flex: 1,
            minWidth: 170,
            valueFormatter: (value: number) => formatTimestamp(value),
        },
        {
            field: 'action',
            headerName: 'Action',
            flex: 1,
            minWidth: 140,
            valueGetter: (value: LogAction) => LOG_ACTION_LABELS[value] ?? value,
        },
        {
            field: 'result',
            headerName: 'Result',
            width: 110,
            minWidth: 100,
            renderCell: ({value}) => (
                <Chip size="small" variant="outlined" label={value} color={RESULT_COLORS[value as LogResult] ?? 'default'} />
            ),
        },
        {field: 'actor', headerName: 'Actor', flex: 1, minWidth: 160},
        {field: 'target', headerName: 'Target', flex: 1, minWidth: 120, valueGetter: (value?: string | null) => value ?? ''},
        {
            field: 'detail',
            headerName: 'Detail',
            flex: 2,
            minWidth: 180,
            valueGetter: (value: CtfLogEntry['detail']) => formatDetail(value),
            sortable: false,
        },
    ];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            <Box sx={{display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap'}}>
                <TextField
                    select
                    size="small"
                    label="Action"
                    value={actionFilter}
                    onChange={(e) => handleFilterChange(e.target.value as ActionFilter)}
                    sx={{minWidth: 220}}
                >
                    <MenuItem value="">All actions</MenuItem>
                    {LOG_ACTIONS.map(action => (
                        <MenuItem key={action} value={action}>{LOG_ACTION_LABELS[action]}</MenuItem>
                    ))}
                </TextField>
                {entries.length >= LOG_ROW_CAP && (
                    <Typography variant="body2" color="text.secondary">
                        Showing the newest {LOG_ROW_CAP} entries.{actionFilter ? '' : ' Filter by action to see older ones.'}
                    </Typography>
                )}
            </Box>
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            <StyledDataGrid
                data={entries}
                columns={columns}
                getRowId={(row: CtfLogEntry) => row.id}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: actionFilter ? "No entries for this action" : "No actions logged yet"}}
                labelProps={{text: "Event Log", icon: <HistoryIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
        </Box>
    );
};

export default CtfEventLogPanel;
