import FlagIcon from "@mui/icons-material/Flag";
import {Alert, Box, Chip, MenuItem, TextField, Typography} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfBoardStatus, CtfStates, CtfSubmission, VERDICTS, Verdict} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import HttpError from "../../Common/Errors/HttpError";

// Matches the event log panel; the PRD only requires that no CTF poll is faster than 10 s.
export const SUBMISSIONS_POLL_INTERVAL_MS = 15000;
// CtfEvent.MAX_PANEL_ROWS: the API returns at most this many rows, newest first.
export const SUBMISSIONS_ROW_CAP = 500;

export const VERDICT_LABELS: Record<Verdict, string> = {
    correct: 'Correct',
    incorrect: 'Incorrect',
    duplicate: 'Duplicate',
    decoy: 'Decoy',
    cross_submission: 'Cross-team submission',
    rate_limited: 'Rate limited',
    closed: 'Closed',
};

const VERDICT_COLORS: Record<Verdict, 'success' | 'warning' | 'error' | 'info' | 'default'> = {
    correct: 'success',
    incorrect: 'default',
    duplicate: 'info',
    decoy: 'warning',
    // A team holding another board's flag is the case a game master most needs to notice.
    cross_submission: 'error',
    rate_limited: 'warning',
    closed: 'default',
};

// The empty string is the "All verdicts" choice, which sends no `verdict` query parameter.
type VerdictFilter = Verdict | '';

const formatTimestamp = (seconds: number) => new Date(seconds * 1000).toLocaleString();

// The API already sorts newest first; sorting again keeps that order a property of this panel.
export const newestFirst = (rows: CtfSubmission[]) => [...rows].sort((a, b) => b.submitted_at - a.submitted_at);

interface CtfSubmissionLogPanelProps {
    ctfId: string;
    state: number;
    // From the dashboard's 10 s state poll, so team names cost no extra read.
    boards: CtfBoardStatus[];
    // Polls only while the Submissions tab is showing, so hidden panels add no load.
    active: boolean;
}

const CtfSubmissionLogPanel: React.FC<CtfSubmissionLogPanelProps> = ({ctfId, state, boards, active}) => {
    const [submissions, setSubmissions] = useState<CtfSubmission[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [verdictFilter, setVerdictFilter] = useState<VerdictFilter>('');
    // Read synchronously by in-flight requests, so a response for a filter the user has since changed is dropped.
    const filterRef = useRef<VerdictFilter>('');

    const teamNames = useMemo(
        () => new Map(boards.map(board => [board.workout_id, board.team_name])),
        [boards]
    );
    // Falls back to the workout id so a row never shows a blank team.
    const teamName = useCallback((workoutId: string) => teamNames.get(workoutId) || workoutId, [teamNames]);

    const fetchSubmissions = useCallback(async (filter: VerdictFilter) => {
        try {
            const fetched = await ctfService.getSubmissions(ctfId, filter || undefined);
            if (filterRef.current !== filter) {
                return;
            }
            setSubmissions(newestFirst(fetched ?? []));
            setError(null);
        } catch (err) {
            if (filterRef.current !== filter) {
                return;
            }
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not load the submission log."}`);
            console.error(err);
        } finally {
            if (filterRef.current === filter) {
                setLoading(false);
            }
        }
    }, [ctfId]);

    const pollSubmissions = useCallback(() => fetchSubmissions(filterRef.current), [fetchSubmissions]);

    // An archived event refuses submissions, so no new rows appear; one read is enough.
    const archived = state === CtfStates.ARCHIVED;
    usePolling(pollSubmissions, {enabled: active && !archived, interval: SUBMISSIONS_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) {
            pollSubmissions();
        }
    }, [active, archived, pollSubmissions]);

    const handleFilterChange = (value: VerdictFilter) => {
        filterRef.current = value;
        setVerdictFilter(value);
        setLoading(true);
        // Read now rather than waiting up to a full poll interval for the filter to apply.
        fetchSubmissions(value);
    };

    const columns: GridColDef<CtfSubmission>[] = [
        {
            field: 'submitted_at',
            headerName: 'Time',
            flex: 1,
            minWidth: 170,
            valueFormatter: (value: number) => formatTimestamp(value),
        },
        {
            field: 'workout_id',
            headerName: 'Team',
            flex: 1,
            minWidth: 140,
            valueGetter: (value: string) => teamName(value),
        },
        {
            field: 'flag_id',
            headerName: 'Flag',
            flex: 1,
            minWidth: 120,
            // Null when the submission did not parse as a flag of this event.
            valueGetter: (value?: string | null) => value ?? '',
        },
        {
            field: 'verdict',
            headerName: 'Verdict',
            flex: 1,
            minWidth: 190,
            renderCell: ({value}) => (
                <Chip
                    size="small"
                    variant="outlined"
                    label={VERDICT_LABELS[value as Verdict] ?? value}
                    color={VERDICT_COLORS[value as Verdict] ?? 'default'}
                />
            ),
        },
        {
            field: 'matched_workout_id',
            headerName: 'Matched team',
            flex: 1,
            minWidth: 140,
            // The board whose flag was submitted; only a cross-team submission names one.
            valueGetter: (value: string | null, row: CtfSubmission) =>
                row.verdict === 'cross_submission' && value ? teamName(value) : '',
        },
        {field: 'points_awarded', headerName: 'Points', type: 'number', width: 90},
        {
            field: 'origin_ip',
            headerName: 'Origin IP',
            flex: 1,
            minWidth: 130,
            valueGetter: (value?: string | null) => value ?? '',
        },
    ];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            <Box sx={{display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap'}}>
                <TextField
                    select
                    size="small"
                    label="Verdict"
                    value={verdictFilter}
                    onChange={(e) => handleFilterChange(e.target.value as VerdictFilter)}
                    sx={{minWidth: 220}}
                >
                    <MenuItem value="">All verdicts</MenuItem>
                    {VERDICTS.map(verdict => (
                        <MenuItem key={verdict} value={verdict}>{VERDICT_LABELS[verdict]}</MenuItem>
                    ))}
                </TextField>
                {submissions.length >= SUBMISSIONS_ROW_CAP && (
                    <Typography variant="body2" color="text.secondary">
                        Showing the newest {SUBMISSIONS_ROW_CAP} submissions.{verdictFilter ? '' : ' Filter by verdict to see older ones.'}
                    </Typography>
                )}
            </Box>
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            <StyledDataGrid
                data={submissions}
                columns={columns}
                getRowId={(row: CtfSubmission) => row.id}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: verdictFilter ? "No submissions with this verdict" : "No submissions yet"}}
                labelProps={{text: "Submissions", icon: <FlagIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
        </Box>
    );
};

export default CtfSubmissionLogPanel;
