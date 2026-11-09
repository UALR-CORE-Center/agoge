import {
    Alert, Box, Button, Chip, Stack, Tab, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, Tabs, Typography,
} from '@mui/material';
import {useState} from 'react';
import {useBuildAvailability} from '../../context/BuildAvailabilityContext';
import {usePolling} from '../../hooks/usePolling';
import {CloudQuota, CloudQuotaReport, cloudMonitoringService} from '../../services/Admin/cloud-monitoring.service';
import {quotaLabel} from '../../services/BuildIncidents/build-incidents.model';
import {buildIncidentsService} from '../../services/BuildIncidents/build-incidents.service';
import HttpError, {BUILD_AVAILABILITY_REFRESH} from '../Common/Errors/HttpError';
import WorkoutRuntimeReport, {WorkoutMonthlySummary} from './WorkoutRuntimeReport';

const quotaStatus: Record<CloudQuota['level'], {label: string; color: 'default' | 'warning' | 'error'}> = {
    normal: {label: 'Normal', color: 'default'},
    warning: {label: 'Near limit', color: 'warning'},
    critical: {label: 'Very low headroom', color: 'error'},
    exhausted: {label: 'Exhausted', color: 'error'},
};

type QuotaSnapshot = Omit<CloudQuotaReport, 'quotas'> & {
    quotas: (CloudQuota & {observedAt: string})[];
};

function CloudQuotaPanel({active}: {active: boolean}) {
    const hold = useBuildAvailability()?.hold;
    const [report, setReport] = useState<QuotaSnapshot | null>(null);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [checkError, setCheckError] = useState<string | null>(null);
    const [checkResult, setCheckResult] = useState<string | null>(null);

    const {poll} = usePolling(async () => {
        setLoading(true);
        try {
            const current = await cloudMonitoringService.getQuotas();
            setReport(previous => ({
                ...current,
                quotas: [
                    ...current.quotas.map(quota => ({...quota, observedAt: current.observed_at})),
                    ...(previous?.quotas.filter(quota => current.unavailable_scopes?.includes(quota.scope)) ?? []),
                ],
            }));
            setLoadError(null);
        } catch (err) {
            setLoadError(err instanceof HttpError ? err.message : 'Could not read Google Cloud quotas.');
        } finally {
            setLoading(false);
        }
    }, {enabled: active, interval: 90000});

    async function recheck() {
        setChecking(true);
        setCheckResult(null);
        setCheckError(null);
        try {
            const result = await buildIncidentsService.recheckQuota();
            const usage = result.quota ? ` Google Cloud reports ${result.quota.usage} of ${result.quota.limit} networks in use.` : '';
            setCheckResult(result.hold ? `The build pause is active.${usage}` : `New network builds are available.${usage}`);
            window.dispatchEvent(new Event(BUILD_AVAILABILITY_REFRESH));
            void poll();
        } catch (err) {
            setCheckError(err instanceof HttpError ? err.message : 'Could not verify the network quota.');
        } finally {
            setChecking(false);
        }
    }

    const lowQuota = report?.quotas.filter(quota => quota.level !== 'normal') ?? [];
    const veryLowQuota = lowQuota.some(quota => quota.level === 'critical' || quota.level === 'exhausted');

    return (
        <Stack component="section" spacing={2} aria-labelledby="cloud-quotas-heading">
            <Typography component="h2" id="cloud-quotas-heading" variant="h6">Cloud quotas</Typography>
            {hold && (
                <Alert severity="warning">
                    Network builds are paused for {hold.project}. Quota {quotaLabel(hold)}.
                    {hold.usage != null && ` Last verified usage was ${hold.usage}.`}
                    {hold.verified_at && ` Verified at ${hold.verified_at}.`}
                </Alert>
            )}
            <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap'}}>
                <Button onClick={() => void poll()} disabled={loading} variant="outlined">
                    {loading ? 'Refreshing…' : 'Refresh cloud quotas'}
                </Button>
                <Button onClick={() => void recheck()} disabled={checking}>
                    {checking ? 'Checking…' : 'Recheck network quota'}
                </Button>
            </Stack>
            {checkResult && <Alert severity="info">{checkResult}</Alert>}
            {checkError && <Alert severity="error">{checkError}</Alert>}
            {loadError && <Alert severity={report ? 'warning' : 'error'}>{loadError}{report && ' Showing the last available reading.'}</Alert>}
            {loading && !report && <Typography role="status">Loading cloud quotas…</Typography>}
            {report && (
                <>
                    <Typography variant="body2" color="text.secondary">
                        {report.project} · {report.region} · Checked {report.observed_at}
                    </Typography>
                    {Boolean(report.unavailable_scopes?.length) && (
                        <Alert severity="warning">Current quota readings unavailable for {report.unavailable_scopes?.join(', ')}.</Alert>
                    )}
                    {lowQuota.length > 0 && (
                        <Alert severity={veryLowQuota ? 'error' : 'warning'}>
                            The latest available readings show {lowQuota.length} {lowQuota.length === 1 ? 'quota' : 'quotas'} at or near the limit.
                        </Alert>
                    )}
                    <TableContainer>
                        <Table size="small" aria-label="Cloud quota usage">
                            <TableHead><TableRow>
                                <TableCell>Quota</TableCell>
                                <TableCell>Scope</TableCell>
                                <TableCell align="right">In use</TableCell>
                                <TableCell align="right">Limit</TableCell>
                                <TableCell align="right">Remaining</TableCell>
                                <TableCell align="right">Utilization</TableCell>
                                <TableCell>Status</TableCell>
                            </TableRow></TableHead>
                            <TableBody>
                                {report.quotas.map(quota => (
                                    <TableRow key={`${quota.metric}/${quota.scope}`}>
                                        <TableCell component="th" scope="row">{quota.metric}</TableCell>
                                        <TableCell>{quota.scope}</TableCell>
                                        <TableCell align="right">{quota.usage.toLocaleString()}</TableCell>
                                        <TableCell align="right">{quota.limit.toLocaleString()}</TableCell>
                                        <TableCell align="right">{quota.remaining.toLocaleString()}</TableCell>
                                        <TableCell align="right">{quota.utilization == null ? '—' : quota.utilization.toLocaleString(undefined, {style: 'percent', maximumFractionDigits: 1})}</TableCell>
                                        <TableCell>
                                            <Chip size="small" {...quotaStatus[quota.level]} />
                                            {quota.observedAt !== report.observed_at && (
                                                <Typography variant="caption" display="block">
                                                    Last observed {quota.observedAt}
                                                </Typography>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {report.quotas.length === 0 && <TableRow><TableCell colSpan={7}>No quota readings available.</TableCell></TableRow>}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </>
            )}
        </Stack>
    );
}

type MonitoringTab = 'quotas' | 'workouts' | 'monthly';

export default function CloudMonitoringPanel() {
    const [tab, setTab] = useState<MonitoringTab>('quotas');
    const [visited, setVisited] = useState<MonitoringTab[]>(['quotas']);
    const [monthSelection, setMonthSelection] = useState<{month?: string; revision: number}>({revision: 0});

    function changeTab(next: MonitoringTab) {
        setTab(next);
        setVisited(current => current.includes(next) ? current : [...current, next]);
    }

    function viewMonth(month: string) {
        setMonthSelection(current => ({month, revision: current.revision + 1}));
        changeTab('workouts');
    }

    return (
        <Stack spacing={2} sx={{p: {xs: 1.5, sm: 3}, width: '100%', minWidth: 0}}>
            <Typography component="h1" variant="h5">Cloud Monitoring</Typography>
            <Tabs value={tab} onChange={(_, value) => changeTab(value)} aria-label="Cloud monitoring views"
                variant="scrollable" scrollButtons="auto">
                <Tab value="quotas" label="Quotas" id="cloud-quotas-tab" aria-controls="cloud-quotas-panel" />
                <Tab value="workouts" label="Workout Runs" id="cloud-workouts-tab" aria-controls="cloud-workouts-panel" />
                <Tab value="monthly" label="Monthly Summary" id="cloud-monthly-tab" aria-controls="cloud-monthly-panel" />
            </Tabs>
            <Box id="cloud-quotas-panel" role="tabpanel" aria-labelledby="cloud-quotas-tab" hidden={tab !== 'quotas'}>
                <CloudQuotaPanel active={tab === 'quotas'} />
            </Box>
            <Box id="cloud-workouts-panel" role="tabpanel" aria-labelledby="cloud-workouts-tab" hidden={tab !== 'workouts'}>
                {visited.includes('workouts') && <WorkoutRuntimeReport key={monthSelection.revision} initialMonth={monthSelection.month} />}
            </Box>
            <Box id="cloud-monthly-panel" role="tabpanel" aria-labelledby="cloud-monthly-tab" hidden={tab !== 'monthly'}>
                {visited.includes('monthly') && <WorkoutMonthlySummary onSelectMonth={viewMonth} />}
            </Box>
        </Stack>
    );
}
