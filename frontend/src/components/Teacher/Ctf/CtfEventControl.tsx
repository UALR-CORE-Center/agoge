import {Alert, Box, Button} from '@mui/material';
import React, {useState} from 'react';
import {CtfAction, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import ConfirmationDialog from "../../Common/Dialogs/ConfirmationDialog/Confirmation";
import HttpError from "../../Common/Errors/HttpError";

interface ActionRule {
    label: string;
    // Must match CtfEvent.ACTIONS in api/core/ctf/event.py; the API answers anything else with 409.
    legalStates: readonly number[];
    // End and Archive cannot be undone, so they use the type-to-confirm dialog.
    irreversible: boolean;
    message: string;
}

export const CTF_ACTION_RULES: Record<CtfAction, ActionRule> = {
    arm: {
        label: 'Arm',
        legalStates: [CtfStates.DRAFT, CtfStates.ARMED, CtfStates.BROKEN],
        irreversible: false,
        message: 'Plant flags on every board. Boards that are already armed are planted again.',
    },
    start: {
        label: 'Start',
        legalStates: [CtfStates.ARMED],
        irreversible: false,
        message: 'Start the clock. Students can submit flags as soon as the event is running.',
    },
    pause: {
        label: 'Pause',
        legalStates: [CtfStates.RUNNING],
        irreversible: false,
        message: 'Hold the clock. Submissions are refused until the event is resumed.',
    },
    resume: {
        label: 'Resume',
        legalStates: [CtfStates.PAUSED],
        irreversible: false,
        message: 'Restart the clock and accept submissions again.',
    },
    end: {
        label: 'End',
        legalStates: [CtfStates.RUNNING, CtfStates.PAUSED],
        irreversible: true,
        message: 'End the event? The clock stops, the scoreboard becomes final and no further submissions are accepted. This cannot be undone.',
    },
    archive: {
        label: 'Archive',
        legalStates: [CtfStates.DRAFT, CtfStates.ARMED, CtfStates.ENDED, CtfStates.BROKEN],
        irreversible: true,
        message: 'Archive the event? It becomes read-only and its boards are released. This cannot be undone.',
    },
};

const ACTION_ORDER: CtfAction[] = ['arm', 'start', 'pause', 'resume', 'end', 'archive'];

export const isActionLegal = (action: CtfAction, state: number) =>
    CTF_ACTION_RULES[action].legalStates.includes(state);

interface CtfEventControlProps {
    ctfId: string;
    state: number;
    // Called after a successful action so the dashboard re-reads state instead of waiting for the next poll.
    onActionComplete: () => void;
}

const CtfEventControl: React.FC<CtfEventControlProps> = ({ctfId, state, onActionComplete}) => {
    // `selected` outlives `open` so a dialog keeps its labels while it fades out.
    const [selected, setSelected] = useState<CtfAction>('arm');
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleClose = () => {
        if (!loading) {
            setOpen(false);
        }
    };

    const handleConfirm = async () => {
        setLoading(true);
        setError(null);
        try {
            await ctfService.processAction(ctfId, {action: selected});
            onActionComplete();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || `Could not ${selected} the CTF event.`}`);
            console.error(err);
        } finally {
            setLoading(false);
            setOpen(false);
        }
    };

    const rule = CTF_ACTION_RULES[selected];

    return (
        <Box sx={{mt: 2}}>
            <Box role="group" aria-label="Event actions" sx={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1}}>
                {ACTION_ORDER.map((action) => (
                    <Button
                        key={action}
                        variant="outlined"
                        color={CTF_ACTION_RULES[action].irreversible ? 'error' : 'primary'}
                        disabled={loading || !isActionLegal(action, state)}
                        onClick={() => {
                            setError(null);
                            setSelected(action);
                            setOpen(true);
                        }}
                    >
                        {CTF_ACTION_RULES[action].label}
                    </Button>
                ))}
            </Box>
            {error && <Alert severity="error" sx={{mt: 2}}>{error}</Alert>}
            <ActionConfirmDialog
                open={open && !rule.irreversible}
                title={`${rule.label} CTF event`}
                message={rule.message}
                confirmLabel={rule.label}
                onConfirm={handleConfirm}
                onClose={handleClose}
                loading={loading}
            />
            <ConfirmationDialog
                open={open && rule.irreversible}
                onClose={handleClose}
                handleConfirm={handleConfirm}
                expectedText={ctfId}
                action={selected === 'archive' ? 'archive' : 'end'}
                confirmLabel={rule.label}
                message={rule.message}
                loading={loading}
            />
        </Box>
    );
};

export default CtfEventControl;
