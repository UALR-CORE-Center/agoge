import {
    Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip,
    FormControlLabel, Stack, Switch, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Link} from 'react-router-dom';
import {useBuildAvailability} from '../../context/BuildAvailabilityContext';
import {URL_TEACHER_UNIT} from '../../router/urls';
import {BuildIncident, quotaLabel} from '../../services/BuildIncidents/build-incidents.model';
import {buildIncidentsService} from '../../services/BuildIncidents/build-incidents.service';
import HttpError, {BUILD_AVAILABILITY_REFRESH} from '../Common/Errors/HttpError';

const kindLabels: Record<BuildIncident['kind'], string> = {
    build_failure: 'Build failure',
    build_blocked: 'Build paused',
    cleanup_failed: 'Cleanup failure',
};

function groupIncidents(incidents: BuildIncident[]) {
    const groups = new Map<string, BuildIncident[]>();
    for (const incident of incidents) {
        const key = JSON.stringify([incident.project, incident.kind, incident.metric || incident.limit_name || incident.reason, incident.scope]);
        const group = groups.get(key);
        if (group) group.push(incident);
        else groups.set(key, [incident]);
    }
    return [...groups.entries()];
}

function logsUrl(incident: BuildIncident) {
    if (!incident.operation_id || !incident.project) return null;
    const operation = JSON.stringify(incident.operation_id);
    const query = `jsonPayload.operation_id=${operation} OR operation.id=${operation}`;
    return `https://console.cloud.google.com/logs/query;query=${encodeURIComponent(query)}?project=${encodeURIComponent(incident.project)}`;
}

export default function BuildIncidentsPanel() {
    const hold = useBuildAvailability()?.hold;
    const [includeResolved, setIncludeResolved] = useState(false);
    const [incidents, setIncidents] = useState<BuildIncident[]>([]);
    const [cursor, setCursor] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [checkError, setCheckError] = useState<string | null>(null);
    const [checkResult, setCheckResult] = useState<string | null>(null);
    const latestRequest = useRef(0);

    const load = useCallback(async (pageCursor?: string) => {
        const request = ++latestRequest.current;
        setLoading(true);
        setLoadError(null);
        try {
            const page = await buildIncidentsService.list(includeResolved, pageCursor);
            if (request !== latestRequest.current) return;
            setIncidents(current => {
                if (!pageCursor) return page.incidents;
                const byId = new Map(current.map(incident => [incident.id, incident]));
                for (const incident of page.incidents) byId.set(incident.id, incident);
                return [...byId.values()];
            });
            setCursor(page.next_cursor ?? null);
        } catch (error) {
            if (request === latestRequest.current) setLoadError(error instanceof HttpError ? error.message : 'Could not load incidents.');
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
    }, [includeResolved]);

    useEffect(() => {
        setIncidents([]);
        setCursor(null);
        void load();
        return () => { latestRequest.current++; };
    }, [load]);

    async function recheck() {
        setChecking(true);
        setCheckResult(null);
        setCheckError(null);
        try {
            const result = await buildIncidentsService.recheckQuota();
            const usage = result.quota ? ` Google Cloud reports ${result.quota.usage} of ${result.quota.limit} networks in use.` : '';
            setCheckResult(result.hold ? `The build pause is active.${usage}` : `New network builds are available.${usage}`);
            window.dispatchEvent(new Event(BUILD_AVAILABILITY_REFRESH));
        } catch (error) {
            setCheckError(error instanceof HttpError ? error.message : 'Could not verify the network quota.');
        } finally {
            setChecking(false);
        }
    }

    return (
        <Stack spacing={2} sx={{p: {xs: 1.5, sm: 3}, width: '100%', minWidth: 0}}>
            <Typography component="h1" variant="h5">Build incidents</Typography>
            <Box>
                {hold && (
                    <Alert severity="warning" sx={{mb: 1}}>
                        Network builds are paused for {hold.project}. Quota {quotaLabel(hold)}.
                        {hold.usage != null && ` Last verified usage was ${hold.usage}.`}
                        {hold.verified_at && ` Verified at ${hold.verified_at}.`}
                    </Alert>
                )}
                <Button onClick={() => void recheck()} disabled={checking} variant="outlined">
                    {checking ? 'Checking quota…' : 'Recheck quota'}
                </Button>
                {checkResult && <Alert severity="info" sx={{mt: 1}}>{checkResult}</Alert>}
                {checkError && <Alert severity="error" sx={{mt: 1}}>{checkError}</Alert>}
            </Box>
            <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap', alignItems: 'center'}}>
                <FormControlLabel control={<Switch checked={includeResolved} onChange={(_, checked) => setIncludeResolved(checked)} />}
                    label="Include resolved incidents" />
                <Button onClick={() => void load()} disabled={loading}>Refresh</Button>
            </Stack>
            {loadError && <Alert severity="error">{loadError}</Alert>}
            {loading && <Typography role="status">Loading incidents…</Typography>}
            {!loading && !loadError && !incidents.length && <Typography>No {includeResolved ? '' : 'open '}build incidents.</Typography>}
            <Box sx={{minWidth: 0}}>
                {groupIncidents(incidents).map(([key, rows]) => {
                    const first = rows[0];
                    const firstSeen = rows.map(row => row.occurred_at).sort()[0];
                    const lastSeen = rows.map(row => row.last_seen_at || row.occurred_at).sort().at(-1);
                    const units = new Set(rows.map(row => row.unit_id).filter(Boolean)).size;
                    const workouts = new Set(rows.map(row => row.workout_id).filter(Boolean)).size;
                    return (
                        <Accordion key={key} disableGutters>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Stack sx={{minWidth: 0, overflowWrap: 'anywhere'}}>
                                    <Typography fontWeight="bold">
                                        {kindLabels[first.kind]} · {first.metric || first.limit_name || first.reason}
                                        {first.scope && ` · ${first.scope}`}
                                    </Typography>
                                    <Typography variant="body2">
                                        {first.project || 'Project unavailable'} · {units} {units === 1 ? 'lab' : 'labs'} · {workouts} {workouts === 1 ? 'workout' : 'workouts'}
                                    </Typography>
                                    <Typography variant="caption">First seen {firstSeen} · Last seen {lastSeen}</Typography>
                                </Stack>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Stack component="ul" spacing={1.5} sx={{my: 0, pl: 2}}>
                                    {rows.map(incident => {
                                        const url = logsUrl(incident);
                                        return (
                                            <Box component="li" key={incident.id} sx={{overflowWrap: 'anywhere'}}>
                                                <Typography variant="body2">
                                                    {incident.occurred_at} · {incident.stage.replace(/[_-]/g, ' ')} · {incident.reason}
                                                </Typography>
                                                <Typography variant="body2">
                                                    Incident {incident.id}
                                                    {incident.workout_id && ` · Workout ${incident.workout_id}`}
                                                    {incident.resource && ` · Resource ${incident.resource}`}
                                                    {incident.limit != null && ` · Limit ${incident.limit}`}
                                                    {incident.operation_id && ` · Operation ${incident.operation_id}`}
                                                </Typography>
                                                <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap', alignItems: 'center', mt: .5}}>
                                                    <Chip size="small" label={incident.status === 'open' ? 'Open' : 'Resolved'} />
                                                    {incident.unit_id && (
                                                        <Button size="small" component={Link} to={`${URL_TEACHER_UNIT}/${encodeURIComponent(incident.unit_id)}`}>
                                                            Lab {incident.unit_id}
                                                        </Button>
                                                    )}
                                                    {url && <Button size="small" href={url} target="_blank" rel="noopener noreferrer">View cloud logs</Button>}
                                                </Stack>
                                            </Box>
                                        );
                                    })}
                                </Stack>
                            </AccordionDetails>
                        </Accordion>
                    );
                })}
            </Box>
            {cursor && (
                <>
                    <Typography variant="caption">Group counts reflect loaded incidents.</Typography>
                    <Button onClick={() => void load(cursor)} disabled={loading}>Load more incidents</Button>
                </>
            )}
        </Stack>
    );
}
