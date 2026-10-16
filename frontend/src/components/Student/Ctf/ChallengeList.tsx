import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import {
    Alert,
    Box,
    Button,
    Chip,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography
} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, {useCallback, useEffect, useState} from 'react';
import {usePolling} from "../../../hooks/usePolling";
import {CtfChallenge, CtfPublicScoreboardRow, CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import HttpError from "../../Common/Errors/HttpError";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";

// PRD performance budget: scoreboards poll every 30 s.
export const PUBLIC_SCOREBOARD_POLL_INTERVAL_MS = 30000;

const pointsLabel = (points: number) => `${points} ${Math.abs(points) === 1 ? 'point' : 'points'}`;

const hintCostMessage = (cost: number) => cost > 0
    ? `Taking this hint deducts ${pointsLabel(cost)} from your team's score. You pay only once; the hint stays visible afterwards.`
    : 'This hint is free. Taking it does not change your score.';

interface ChallengeListProps {
    workoutId: string;
    board: CtfStudentBoardResponse;
    // Re-reads the board so the score reflects a hint's cost without waiting for the 15 s poll.
    onChanged: () => void;
}

/**
 * The team's challenges: category, points, solved state and hints. It shows only what CtfChallenge carries, so a
 * flag's host and path never reach the page (SC-17). When the event publishes standings, the anonymized public
 * scoreboard follows, with the caller's row highlighted.
 */
const ChallengeList: React.FC<ChallengeListProps> = ({workoutId, board, onChanged}) => {
    const {showModal} = useModal();
    const [pendingHint, setPendingHint] = useState<CtfChallenge | null>(null);
    const [takingHint, setTakingHint] = useState(false);
    // Hints taken here show at once; the next board read carries them as `hint` anyway.
    const [revealed, setRevealed] = useState<Record<string, string>>({});
    const [standings, setStandings] = useState<CtfPublicScoreboardRow[] | null>(null);
    // Without it, a failed first read would leave "Loading standings…" up until a later poll succeeds.
    const [standingsFailed, setStandingsFailed] = useState(false);
    const running = board.state_name === 'RUNNING';
    const showStandings = board.public_scoreboard_enabled;

    useEffect(() => {
        setRevealed({});
        setStandings(null);
        setStandingsFailed(false);
    }, [workoutId]);

    const fetchStandings = useCallback(async () => {
        try {
            setStandings(await ctfBoardService.getPublicScoreboard(workoutId) ?? []);
            setStandingsFailed(false);
        } catch (e) {
            setStandingsFailed(true);
            // 404: the instructor turned the public scoreboard off since the last board read.
            if (e instanceof HttpError && e.status === 404) {
                setStandings(null);
            }
            // Any other failure keeps the last good standings; the next poll retries.
        }
    }, [workoutId]);

    usePolling(fetchStandings, {enabled: showStandings, interval: PUBLIC_SCOREBOARD_POLL_INTERVAL_MS});

    useEffect(() => {
        if (!showStandings) {
            setStandings(null);
            setStandingsFailed(false);
        }
    }, [showStandings]);

    const handleTakeHint = async () => {
        if (!pendingHint) {
            return;
        }
        setTakingHint(true);
        try {
            const result = await ctfBoardService.takeHint(workoutId, pendingHint.flag_id);
            setRevealed((prev) => ({...prev, [result.flag_id]: result.hint}));
        } catch (e) {
            // 409 (hints closed outside RUNNING) and 404 (hint unavailable) carry a message written for the student.
            const status = e instanceof HttpError ? e.status : 500;
            const expected = status === 409 || status === 404;
            showModal(SimpleSnackbar, {
                message: expected && e instanceof HttpError ? e.message : 'The hint could not be loaded. Try again.',
                severity: expected ? 'warning' : 'error',
            });
        } finally {
            setTakingHint(false);
            setPendingHint(null);
            onChanged();
        }
    };

    const hintCell = (challenge: CtfChallenge) => {
        const hint = challenge.hint ?? revealed[challenge.flag_id];
        if (hint) {
            return <Typography variant="body2" sx={{whiteSpace: 'pre-wrap'}}>{hint}</Typography>;
        }
        if (!challenge.hint_available) {
            return <Typography variant="body2" color="text.secondary">No hint</Typography>;
        }
        return (
            <Button
                size="small"
                variant="outlined"
                startIcon={<LightbulbIcon />}
                // Points only move while the event runs; the API answers anything else with a 409.
                disabled={!running}
                onClick={() => setPendingHint(challenge)}
                aria-label={`Take hint for ${challenge.flag_id} (costs ${pointsLabel(challenge.hint_cost)})`}
            >
                Take hint ({challenge.hint_cost > 0 ? `-${challenge.hint_cost}` : 'free'})
            </Button>
        );
    };

    return (
        <Paper component="section" aria-labelledby="ctf-challenges-h2" sx={{width: '100%', mt: 2, p: 2}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap'}}>
                <Typography id="ctf-challenges-h2" component="h2" variant="h6">
                    Challenges
                </Typography>
                {board.score !== null && (
                    <Typography variant="body1">Team score: <strong>{board.score}</strong></Typography>
                )}
            </Box>

            {board.challenges.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>
                    No challenges are available yet.
                </Typography>
            ) : (
                <TableContainer sx={{mt: 1}}>
                    <Table size="small" aria-labelledby="ctf-challenges-h2">
                        <TableHead>
                            <TableRow>
                                <TableCell>Challenge</TableCell>
                                <TableCell>Category</TableCell>
                                <TableCell align="right">Points</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell>Hint</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {board.challenges.map((challenge) => (
                                <TableRow key={challenge.flag_id}>
                                    <TableCell component="th" scope="row">{challenge.flag_id}</TableCell>
                                    <TableCell>{challenge.category ?? 'General'}</TableCell>
                                    <TableCell align="right">{challenge.points}</TableCell>
                                    <TableCell>
                                        {challenge.solved ? (
                                            <Chip size="small" color="success" icon={<CheckCircleIcon />} label="Solved" />
                                        ) : (
                                            <Chip size="small" variant="outlined" label="Unsolved" />
                                        )}
                                    </TableCell>
                                    <TableCell>{hintCell(challenge)}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}

            {showStandings && (
                <Box component="section" aria-labelledby="ctf-standings-h3" sx={{mt: 3}}>
                    <Typography id="ctf-standings-h3" component="h3" variant="subtitle1" sx={{fontWeight: 'bold'}}>
                        Standings
                    </Typography>
                    {standings === null ? (
                        standingsFailed ? (
                            <Alert severity="warning">The standings are unavailable right now.</Alert>
                        ) : (
                            <Typography variant="body2" color="text.secondary">Loading standings…</Typography>
                        )
                    ) : standings.length === 0 ? (
                        <Alert severity="info">No standings yet.</Alert>
                    ) : (
                        <TableContainer>
                            <Table size="small" aria-labelledby="ctf-standings-h3">
                                <TableHead>
                                    <TableRow>
                                        <TableCell align="right">Rank</TableCell>
                                        <TableCell>Team</TableCell>
                                        <TableCell align="right">Score</TableCell>
                                        <TableCell align="right">Solves</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {standings.map((row) => (
                                        <TableRow
                                            key={row.team_label}
                                            selected={row.is_you}
                                            aria-current={row.is_you ? 'true' : undefined}
                                        >
                                            <TableCell align="right">{row.rank}</TableCell>
                                            <TableCell component="th" scope="row">
                                                {row.team_label}{row.is_you && <strong> (you)</strong>}
                                            </TableCell>
                                            <TableCell align="right">{row.score}</TableCell>
                                            <TableCell align="right">{row.solve_count}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </Box>
            )}

            <ActionConfirmDialog
                open={pendingHint !== null}
                title={pendingHint ? `Take the hint for ${pendingHint.flag_id}?` : 'Take hint?'}
                message={pendingHint ? hintCostMessage(pendingHint.hint_cost) : ''}
                confirmLabel="Take hint"
                onConfirm={handleTakeHint}
                onClose={() => setPendingHint(null)}
                loading={takingHint}
            />
        </Paper>
    );
};

export default ChallengeList;
