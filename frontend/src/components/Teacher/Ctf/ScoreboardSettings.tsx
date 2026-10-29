import {Alert, Box, Button, FormControlLabel, Stack, Switch, Typography} from '@mui/material';
import {LocalizationProvider} from '@mui/x-date-pickers';
import {AdapterDateFns} from '@mui/x-date-pickers/AdapterDateFnsV3';
import {DateTimePicker} from '@mui/x-date-pickers/DateTimePicker';
import React, {useEffect, useState} from 'react';
import {CtfStates, CtfUpdateRequest} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";

export interface ScoreboardSettingsEvent {
    state: number;
    ends_at: number | null;
    scoreboard_frozen_at: number | null;
    public_scoreboard_enabled: boolean;
}

interface ScoreboardSettingsProps {
    ctfId: string;
    event: ScoreboardSettingsEvent;
    // Re-reads state after a successful PUT; awaited so a toggle does not snap back before the new value arrives.
    onUpdated: () => Promise<void> | void;
}

// MUI renders a Switch as a plain checkbox; role="switch" makes screen readers announce it as on/off.
const SWITCH_ROLE = {role: 'switch'};

const toDate = (seconds: number | null) => (seconds === null ? null : new Date(seconds * 1000));
const toSeconds = (date: Date) => Math.floor(date.getTime() / 1000);
const formatTimestamp = (seconds: number) => new Date(seconds * 1000).toLocaleString();

const ScoreboardSettings: React.FC<ScoreboardSettingsProps> = ({ctfId, event, onUpdated}) => {
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [endsDraft, setEndsDraft] = useState<Date | null>(() => toDate(event.ends_at));

    // Follow the stored end time when it changes (here or from another instructor); an unchanged poll keeps the draft.
    useEffect(() => {
        setEndsDraft(toDate(event.ends_at));
    }, [event.ends_at]);

    // CtfEvent.update answers 409 for an ARCHIVED event, so nothing here can be changed.
    const readOnly = event.state === CtfStates.ARCHIVED;
    const disabled = readOnly || saving;

    const send = async (request: CtfUpdateRequest, failure: string) => {
        setSaving(true);
        setError(null);
        try {
            await ctfService.update(ctfId, request);
            await onUpdated();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || failure}`);
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    const frozen = event.scoreboard_frozen_at !== null;
    // The freeze is a timestamp, not a state (PRD SC-16): freezing stamps "now", and an explicit null unfreezes.
    const handleFreeze = (checked: boolean) =>
        send({scoreboard_frozen_at: checked ? Date.now() / 1000 : null}, "Could not change the scoreboard freeze.");

    const handlePublic = (checked: boolean) =>
        send({public_scoreboard_enabled: checked}, "Could not change the public scoreboard setting.");

    const draftValid = endsDraft !== null && !Number.isNaN(endsDraft.getTime());
    // An end time already in the past would stop a running clock at once; End is the action for that.
    const draftUnchanged = draftValid && event.ends_at !== null && toSeconds(endsDraft) === Math.floor(event.ends_at);
    // The saved end time of an ended event is in the past by design; only a time the game master picked is an error.
    const draftInPast = draftValid && !draftUnchanged && endsDraft.getTime() <= Date.now();
    const canSaveEnd = draftValid && !draftInPast && !draftUnchanged;

    const handleSaveEnd = () => {
        if (draftValid) {
            send({ends_at: toSeconds(endsDraft)}, "Could not change the end time.");
        }
    };

    const handleClearEnd = () => send({ends_at: null}, "Could not clear the end time.");

    return (
        <Box component="section" aria-labelledby="ctf-scoreboard-settings-heading" sx={{mt: 3}}>
            <Typography id="ctf-scoreboard-settings-heading" variant="overline" component="h2" color="text.secondary">
                Scoreboard settings
            </Typography>
            <Stack spacing={1}>
                <Box>
                    <FormControlLabel
                        control={
                            <Switch
                                checked={frozen}
                                disabled={disabled}
                                inputProps={SWITCH_ROLE}
                                onChange={(_e, checked) => handleFreeze(checked)}
                            />
                        }
                        label="Freeze scoreboard"
                    />
                    {frozen && (
                        <Typography variant="body2" color="text.secondary">
                            Frozen at {formatTimestamp(event.scoreboard_frozen_at as number)}. Students still submit,
                            but the public scoreboard ignores later solves.
                        </Typography>
                    )}
                </Box>
                <FormControlLabel
                    control={
                        <Switch
                            checked={event.public_scoreboard_enabled}
                            disabled={disabled}
                            inputProps={SWITCH_ROLE}
                            onChange={(_e, checked) => handlePublic(checked)}
                        />
                    }
                    label="Public scoreboard"
                />
                <LocalizationProvider dateAdapter={AdapterDateFns}>
                    <DateTimePicker
                        label="Ends at"
                        value={endsDraft}
                        onChange={(value) => setEndsDraft(value)}
                        disabled={disabled}
                        disablePast
                        closeOnSelect={false}
                        slotProps={{
                            textField: {
                                fullWidth: true,
                                helperText: draftInPast
                                    ? "Choose a time in the future."
                                    : event.ends_at === null ? "No end time is set." : undefined,
                                error: draftInPast,
                            },
                        }}
                    />
                </LocalizationProvider>
                <Box sx={{display: 'flex', gap: 1}}>
                    <Button variant="outlined" onClick={handleSaveEnd} disabled={disabled || !canSaveEnd}>
                        Save end time
                    </Button>
                    <Button onClick={handleClearEnd} disabled={disabled || event.ends_at === null}>
                        Clear end time
                    </Button>
                </Box>
            </Stack>
            {error && <Alert severity="error" sx={{mt: 2}}>{error}</Alert>}
        </Box>
    );
};

export default ScoreboardSettings;
