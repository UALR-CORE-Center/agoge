import FlagIcon from '@mui/icons-material/Flag';
import {Box, Button, CircularProgress, Paper, TextField, Typography} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, {useState} from 'react';
import {CtfStudentBoardResponse, CtfSubmitResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";

// CtfSubmitRequest.flag max_length in common/models/agoge.py.
export const FLAG_MAX_LENGTH = 200;

type Severity = 'info' | 'warning' | 'error' | 'success';

const VERDICT_SEVERITY: Record<CtfSubmitResponse['verdict'], Severity> = {
    correct: 'success',
    incorrect: 'error',
    duplicate: 'info',
    decoy: 'warning',
};

const pointsSuffix = (points: number): string => {
    if (points === 0) {
        return '';
    }
    const unit = Math.abs(points) === 1 ? 'point' : 'points';
    return ` (${points > 0 ? '+' : '-'}${Math.abs(points)} ${unit})`;
};

interface FlagSubmitCardProps {
    workoutId: string;
    board: CtfStudentBoardResponse;
    // Re-reads the board so score, solved state and event state catch up without waiting for the 15 s poll.
    onSubmitted: () => void;
}

const FlagSubmitCard: React.FC<FlagSubmitCardProps> = ({workoutId, board, onSubmitted}) => {
    const {showModal} = useModal();
    const [flag, setFlag] = useState('');
    const [submitting, setSubmitting] = useState(false);
    // The board state is up to 15 s old; the API is still the authority and answers a closed event with a 409.
    const running = board.state_name === 'RUNNING';
    const canSubmit = running && !submitting && flag.trim().length > 0;

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!canSubmit) {
            return;
        }
        setSubmitting(true);
        try {
            // Sent untrimmed: the API normalizes the value itself before hashing it.
            const result = await ctfBoardService.submitFlag(workoutId, flag);
            showModal(SimpleSnackbar, {
                message: `${result.message}${pointsSuffix(result.points_awarded)}`,
                severity: VERDICT_SEVERITY[result.verdict] ?? 'info',
            });
            // A wrong value stays in the field so a typo can be corrected rather than retyped.
            if (result.verdict !== 'incorrect') {
                setFlag('');
            }
        } catch (e) {
            // 429 (rate limited) and 409 (submissions closed) carry a message written for the student.
            const status = e instanceof HttpError ? e.status : 500;
            const expected = status === 429 || status === 409;
            showModal(SimpleSnackbar, {
                message: expected && e instanceof HttpError ? e.message : 'The flag could not be submitted. Try again.',
                severity: expected ? 'warning' : 'error',
            });
        } finally {
            setSubmitting(false);
            onSubmitted();
        }
    };

    return (
        <Paper component="section" aria-labelledby="ctf-flag-submit-h2" sx={{width: '100%', mt: 2}}>
            <Box component="form" onSubmit={handleSubmit} noValidate sx={{p: 2}}>
                <Typography id="ctf-flag-submit-h2" component="h2" variant="h6" sx={{mb: 1}}>
                    Submit a flag
                </Typography>
                {board.flag_format && (
                    <Typography variant="body2" color="text.secondary" sx={{mb: 1}}>
                        Format:{' '}
                        <Box component="code" sx={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                            {board.flag_format}
                        </Box>
                    </Typography>
                )}
                <TextField
                    fullWidth
                    size="small"
                    label="Flag"
                    value={flag}
                    onChange={(e) => setFlag(e.target.value)}
                    disabled={!running}
                    autoComplete="off"
                    spellCheck={false}
                    helperText={running ? undefined : 'Flags can be submitted while the event is running.'}
                    slotProps={{htmlInput: {maxLength: FLAG_MAX_LENGTH}}}
                />
                <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    disabled={!canSubmit}
                    startIcon={submitting ? <CircularProgress size={20} color="inherit" /> : <FlagIcon />}
                    sx={{mt: 1}}
                >
                    Submit
                </Button>
            </Box>
        </Paper>
    );
};

export default FlagSubmitCard;
