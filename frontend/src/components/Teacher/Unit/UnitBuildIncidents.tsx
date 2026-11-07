import {Alert, AlertTitle, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography} from '@mui/material';
import React, {useEffect, useId, useRef, useState} from 'react';
import {useBuildAvailability} from '../../../context/BuildAvailabilityContext';
import {useClipboard} from '../../../hooks/useClipboard';
import {BuildIncident, quotaHoldMessage, quotaLabel} from '../../../services/BuildIncidents/build-incidents.model';
import {unitService} from '../../../services/Unit/unit.service';
import {Workout} from '../../../services/Workout/workout.model';
import {workoutService} from '../../../services/Workout/workout.service';
import {WorkoutStates} from '../../../types/AgogeStates';
import {PubSub} from '../../../types/PubSub';
import ConfirmationDialog from '../../Common/Dialogs/ConfirmationDialog/Confirmation';
import HttpError from '../../Common/Errors/HttpError';

interface Props {
    incidents: BuildIncident[];
    unitId: string;
    unitState?: string;
    workouts: Workout[];
    workoutsNeedNetwork?: boolean;
    sharedNeedsNetwork?: boolean;
    onChanged: () => void | Promise<void>;
}

function incidentTitle(incident: BuildIncident) {
    if (incident.kind === 'cleanup_failed') return 'Cleanup needs attention';
    if (incident.kind === 'build_blocked') return incident.workout_id ? 'Workout build paused' : 'Lab build paused';
    return incident.workout_id ? 'Workout build failed' : 'Lab build failed';
}

const stageLabel = (stage: string) => stage.replace(/[_-]/g, ' ');

function describeIncident(incident: BuildIncident) {
    if (incident.kind === 'cleanup_failed') return 'Agoge could not verify cleanup. Some resources may still exist.';
    if (incident.reason.includes('RATE_LIMIT') || incident.reason.includes('CONCURRENT_OPERATIONS')) {
        return `Google Cloud throttled requests during ${stageLabel(incident.stage)}.`;
    }
    const quota = incident.metric || incident.limit_name;
    if (quota) {
        return `Google Cloud reached its ${quotaLabel({
            metric: quota, scope: incident.scope || 'cloud', limit: incident.limit
        })} quota during ${stageLabel(incident.stage)}.`;
    }
    if (incident.reason === 'QUOTA_EXCEEDED') {
        return `Google Cloud rejected ${stageLabel(incident.stage)} because a quota was reached. Google Cloud did not provide the quota name.`;
    }
    return `Agoge could not complete ${stageLabel(incident.stage)}.`;
}

function formatReport(incident: BuildIncident) {
    return [
        incidentTitle(incident),
        `Incident ID: ${incident.id}`,
        incident.unit_id && `Lab ID: ${incident.unit_id}`,
        incident.workout_id && `Workout ID: ${incident.workout_id}`,
        incident.project && `Project: ${incident.project}`,
        `Time (UTC): ${incident.occurred_at}`,
        `Stage: ${stageLabel(incident.stage)}`,
        `Provider reason: ${incident.reason}`,
        incident.metric && `Quota: ${incident.metric}`,
        incident.limit_name && `Quota limit name: ${incident.limit_name}`,
        incident.limit != null && `Limit: ${incident.limit}`,
        incident.scope && `Scope: ${incident.scope}`,
    ].filter(Boolean).join('\n');
}

const promptedKey = (id: string) => `agoge:lab-incident-prompt:${id}`;
const wasPrompted = (id: string) => {
    try {
        return sessionStorage.getItem(promptedKey(id)) === '1';
    } catch {
        return false;
    }
};

export default function UnitBuildIncidents({
    incidents, unitId, unitState, workouts, workoutsNeedNetwork, sharedNeedsNetwork, onChanged
}: Props) {
    const {copy} = useClipboard();
    const availability = useBuildAvailability();
    const supportContact = availability?.support_contact || 'your Agoge administrator';
    const [promptId, setPromptId] = useState<string | null>(null);
    const [confirmId, setConfirmId] = useState<string | null>(null);
    const [requesting, setRequesting] = useState(false);
    const [requestedTargets, setRequestedTargets] = useState<Record<string, string>>({});
    const [retrying, setRetrying] = useState<string | null>(null);
    const [retryNotice, setRetryNotice] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const prompted = useRef(new Set<string>());
    const titleId = useId();
    const openIncidents = incidents.filter(incident => incident.status === 'open');
    const prompt = openIncidents.find(incident => incident.id === promptId);
    const confirmation = openIncidents.find(incident => incident.id === confirmId);

    useEffect(() => {
        if (prompt || confirmation || requesting) return;
        const next = incidents.find(incident => incident.status === 'open' && incident.kind !== 'cleanup_failed'
            && !prompted.current.has(incident.id) && !wasPrompted(incident.id));
        if (!next) return;
        prompted.current.add(next.id);
        try {
            sessionStorage.setItem(promptedKey(next.id), '1');
        } catch {
            // The page also remembers prompts when browser storage is unavailable.
        }
        setPromptId(next.id);
    }, [confirmation, incidents, prompt, requesting]);

    function target(incident: BuildIncident) {
        return incident.workout_id || unitId;
    }

    function stateOf(incident: BuildIncident) {
        return Number(incident.workout_id
            ? workouts.find(workout => workout.id === incident.workout_id)?.state
            : unitState);
    }

    function cleanupFailureStamp(incident: BuildIncident) {
        return openIncidents.filter(candidate => candidate.kind === 'cleanup_failed' && target(candidate) === target(incident))
            .map(candidate => `${candidate.id}:${candidate.last_seen_at || candidate.occurred_at}`).sort().join(',');
    }

    function cleanupPending(incident: BuildIncident) {
        const failure = cleanupFailureStamp(incident);
        const requested = requestedTargets[target(incident)] === failure;
        if (failure) return requested;
        return requested
            || [WorkoutStates.DELETING_SERVERS, WorkoutStates.COMPLETED_DELETING_SERVERS].includes(stateOf(incident));
    }

    function retryIsPaused(incident: BuildIncident) {
        return Boolean(availability?.hold && (incident.workout_id ? workoutsNeedNetwork : sharedNeedsNetwork));
    }

    async function retryBuild(incident: BuildIncident) {
        if (retryIsPaused(incident) || retrying) return;
        setRetrying(incident.id);
        setError(null);
        setRetryNotice(null);
        try {
            await unitService.put_action(unitId, String(PubSub.Actions.BUILD), undefined,
                incident.workout_id ? [incident.workout_id] : undefined);
            setRetryNotice(target(incident));
            void onChanged();
        } catch (err) {
            setError(err instanceof HttpError ? err.message : 'Could not request a build retry. Please try again.');
        } finally {
            setRetrying(null);
        }
    }

    const cleanupLabel = (incident: BuildIncident) => incident.workout_id ? 'Clean up failed workout' : 'Delete lab';

    function chooseCleanup(incident: BuildIncident) {
        setError(null);
        setPromptId(null);
        setConfirmId(incident.id);
    }

    async function requestCleanup() {
        if (!confirmation || requesting) return;
        setRequesting(true);
        try {
            if (confirmation.workout_id) {
                await workoutService.put_action(confirmation.workout_id, String(PubSub.Actions.DELETE));
            } else {
                await unitService.delete_unit(unitId);
            }
            setRequestedTargets(previous => ({...previous, [target(confirmation)]: cleanupFailureStamp(confirmation)}));
            setConfirmId(null);
            void onChanged();
        } catch (err) {
            setConfirmId(null);
            setError(err instanceof HttpError ? err.message : 'Could not request cleanup. Please try again.');
        } finally {
            setRequesting(false);
        }
    }

    if (openIncidents.length === 0) {
        return Number(unitState) === WorkoutStates.BROKEN ? (
            <Alert severity="error" sx={{width: '100%', mb: 2}}>
                <AlertTitle>This lab is broken</AlertTitle>
                Contact {supportContact} with lab ID {unitId} for help.
            </Alert>
        ) : null;
    }

    return (
        <Stack spacing={1} sx={{width: '100%', mb: 2}}>
            {openIncidents.map(incident => (
                <Alert severity={incident.kind === 'build_blocked' ? 'warning' : 'error'} key={incident.id}>
                    <AlertTitle>{incidentTitle(incident)}</AlertTitle>
                    <Typography variant="body2">
                        {incident.workout_id && `Workout ${incident.workout_id}. `}
                        {describeIncident(incident)} {incident.kind !== 'cleanup_failed' && 'Some lab resources may already exist. '}
                        Copy the report and send it to {supportContact}.
                    </Typography>
                    <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap', mt: 1}}>
                        <Button size="small" color="inherit" onClick={() => copy(formatReport(incident))}>Copy report</Button>
                        {cleanupPending(incident) ? (
                            <Typography role="status" variant="body2" sx={{alignSelf: 'center'}}>
                                Deletion requested. Agoge is verifying cleanup.
                            </Typography>
                        ) : (
                            <Button size="small" color="error" onClick={() => chooseCleanup(incident)}>
                                {cleanupLabel(incident)}…
                            </Button>
                        )}
                        {incident.kind !== 'cleanup_failed' && !cleanupPending(incident) &&
                            stateOf(incident) === WorkoutStates.BROKEN && (
                                <Button
                                    size="small"
                                    color="inherit"
                                    title={retryIsPaused(incident) ? quotaHoldMessage : undefined}
                                    disabled={Boolean(retrying) || retryIsPaused(incident)}
                                    onClick={() => void retryBuild(incident)}
                                >
                                    Retry build
                                </Button>
                        )}
                    </Stack>
                </Alert>
            ))}
            {retryNotice && <Alert severity="info" onClose={() => setRetryNotice(null)}>
                Build retry requested for {retryNotice}.
            </Alert>}
            {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
            {prompt && (
                <Dialog open onClose={() => setPromptId(null)} aria-labelledby={titleId}>
                    <DialogTitle id={titleId}>{incidentTitle(prompt)}</DialogTitle>
                    <DialogContent>
                        <Typography>{describeIncident(prompt)}</Typography>
                        <Typography sx={{mt: 1}}>
                            Contact {supportContact} with the report. You can keep the incomplete resources for inspection,
                            and some resources may still incur charges.
                        </Typography>
                    </DialogContent>
                    <DialogActions sx={{flexWrap: 'wrap'}}>
                        <Button onClick={() => copy(formatReport(prompt))}>Copy report</Button>
                        <Button onClick={() => setPromptId(null)}>Keep for inspection</Button>
                        {!cleanupPending(prompt) && <Button color="error" onClick={() => chooseCleanup(prompt)}>
                            {cleanupLabel(prompt)}…
                        </Button>}
                    </DialogActions>
                </Dialog>
            )}
            {confirmation && (
                <ConfirmationDialog
                    open
                    expectedText={target(confirmation)}
                    confirmLabel={cleanupLabel(confirmation)}
                    message={confirmation.workout_id
                        ? 'This permanently deletes resources and data for the selected workout. Other workouts remain available.'
                        : 'This permanently deletes this lab and all associated workouts, including their data.'}
                    onClose={() => { if (!requesting) setConfirmId(null); }}
                    handleConfirm={requestCleanup}
                    loading={requesting}
                />
            )}
        </Stack>
    );
}
