import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {Box, Link, Paper, Typography} from '@mui/material';
import React, {useEffect, useState} from 'react';
import {CtfStates, CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import CtfStateChip from "../../Teacher/Ctf/CtfStateChip";
import {formatDuration} from "../../Teacher/Ctf/ctfTime";

interface CtfBannerProps {
    board: CtfStudentBoardResponse;
}

// rules_url is instructor-authored spec text; only http(s) links are rendered so a `javascript:` URL can never run.
export const safeRulesUrl = (url: string | null): string | null => {
    if (!url) {
        return null;
    }
    try {
        const parsed = new URL(url);
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null;
    } catch {
        return null;
    }
};

const stateValue = (stateName: string | null): number =>
    stateName !== null && stateName in CtfStates ? CtfStates[stateName as keyof typeof CtfStates] : -1;

const useCountdown = (board: CtfStudentBoardResponse): number | null => {
    const [elapsed, setElapsed] = useState(0);
    const running = board.state_name === 'RUNNING';

    // remaining_seconds is a snapshot from the 15 s board poll; tick locally from it, and restart on every new board.
    // Only a RUNNING event's clock moves: the API holds it while paused and reports 0 once ended.
    useEffect(() => {
        setElapsed(0);
        if (!running || board.remaining_seconds === null) {
            return;
        }
        const startedAt = Date.now();
        const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
        return () => clearInterval(timer);
    }, [board, running]);

    return board.remaining_seconds === null ? null : Math.max(0, board.remaining_seconds - elapsed);
};

const CtfBanner: React.FC<CtfBannerProps> = ({board}) => {
    const remaining = useCountdown(board);
    const rulesUrl = safeRulesUrl(board.rules_url);
    const paused = board.state_name === 'PAUSED';

    return (
        <Paper component="section" aria-labelledby="ctf-banner-h2" sx={{width: '100%', mb: 2}}>
            <Box sx={{p: 2}}>
                <Typography id="ctf-banner-h2" component="h2" variant="h6" sx={{mb: 1}}>
                    {board.name || 'CTF event'}
                </Typography>
                <CtfStateChip state={stateValue(board.state_name)} />
                <Typography variant="overline" component="h3" color="text.secondary" sx={{display: 'block', mt: 1}}>
                    Time remaining
                </Typography>
                <Typography variant="h5" component="p" sx={{fontVariantNumeric: 'tabular-nums'}}>
                    {remaining === null ? 'No end time' : formatDuration(remaining)}
                    {paused && remaining !== null ? ' (paused)' : ''}
                </Typography>
                {rulesUrl && (
                    <Link
                        href={rulesUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{display: 'inline-flex', alignItems: 'center', gap: 0.5, mt: 1}}
                    >
                        Rules of engagement
                        <OpenInNewIcon fontSize="inherit" titleAccess="opens in a new tab" />
                    </Link>
                )}
            </Box>
        </Paper>
    );
};

export default CtfBanner;
