import AcUnitIcon from "@mui/icons-material/AcUnit";
import LeaderboardIcon from "@mui/icons-material/Leaderboard";
import {Alert, Box} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfScoreboardRow, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import HttpError from "../../Common/Errors/HttpError";

// PRD performance budget: the dashboard polls the scoreboard every 30 s.
export const SCOREBOARD_POLL_INTERVAL_MS = 30000;

const formatTimestamp = (seconds: number) => new Date(seconds * 1000).toLocaleString();

interface CtfScoreboardPanelProps {
    ctfId: string;
    state: number;
    // From the 10 s state poll, so the banner follows a freeze toggle without waiting for the 30 s scoreboard poll.
    scoreboardFrozenAt: number | null;
    // Polls only while the Scoreboard tab is showing, so hidden panels add no load.
    active: boolean;
}

const CtfScoreboardPanel: React.FC<CtfScoreboardPanelProps> = ({ctfId, state, scoreboardFrozenAt, active}) => {
    const [rows, setRows] = useState<CtfScoreboardRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchScoreboard = useCallback(async () => {
        try {
            const fetched = await ctfService.getScoreboard(ctfId);
            setRows(fetched ?? []);
            setError(null);
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not load the scoreboard."}`);
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [ctfId]);

    // An archived event's scores cannot change any more; one read is enough.
    const archived = state === CtfStates.ARCHIVED;
    usePolling(fetchScoreboard, {enabled: active && !archived, interval: SCOREBOARD_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) {
            fetchScoreboard();
        }
    }, [active, archived, fetchScoreboard]);

    const columns: GridColDef<CtfScoreboardRow>[] = [
        {field: 'rank', headerName: 'Rank', type: 'number', width: 80, minWidth: 70},
        {field: 'team_name', headerName: 'Team', flex: 1, minWidth: 140},
        {field: 'score', headerName: 'Score', type: 'number', width: 100, minWidth: 80},
        {field: 'solve_count', headerName: 'Solves', type: 'number', width: 90, minWidth: 80},
        {field: 'decoy_count', headerName: 'Decoys', type: 'number', width: 90, minWidth: 80},
        {
            field: 'last_solve_at',
            headerName: 'Last solve',
            flex: 1,
            minWidth: 170,
            // The API ranks ties by the earliest last solve, so this column explains equal scores.
            valueGetter: (value?: number | null) => (value === null || value === undefined ? 'No solves' : formatTimestamp(value)),
            sortable: false,
        },
    ];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {scoreboardFrozenAt !== null && (
                // The instructor ranking ignores the freeze (CtfScoring.scoreboard), so say what students see instead.
                <Alert severity="info" icon={<AcUnitIcon />} sx={{mb: 2}}>
                    The scoreboard has been frozen since {formatTimestamp(scoreboardFrozenAt)}. Students see the
                    standings as they were then. This view still counts every solve.
                </Alert>
            )}
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            <StyledDataGrid
                data={rows}
                columns={columns}
                getRowId={(row: CtfScoreboardRow) => row.workout_id}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: "No teams in this event"}}
                labelProps={{text: "Scoreboard", icon: <LeaderboardIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
        </Box>
    );
};

export default CtfScoreboardPanel;
