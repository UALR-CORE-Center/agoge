import {
    Alert, Box, Button, Link as MuiLink, Stack, Table, TableBody, TableCell, TableContainer,
    TableHead, TablePagination, TableRow, TableSortLabel, TextField, Typography,
} from '@mui/material';
import {FormEvent, useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import {URL_TEACHER_UNIT} from '../../router/urls';
import {
    cloudMonitoringService, WorkoutRuntimeFilters, WorkoutRuntimeMonths, WorkoutRuntimeReport as Report, WorkoutRuntimeSort,
} from '../../services/Admin/cloud-monitoring.service';
import HttpError from '../Common/Errors/HttpError';

const dateFormat = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC'});

function displayTimestamp(value: string | null) {
    return value ? dateFormat.format(new Date(value)) : '—';
}

function displayRuntime(totalSeconds: number) {
    const seconds = Math.floor(totalSeconds);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor(seconds / 60) % 60;
    if (hours) return `${hours.toLocaleString()} h ${minutes} min`;
    if (minutes) return `${minutes} min ${seconds % 60} sec`;
    return `${seconds} sec`;
}

const columns: {field: WorkoutRuntimeSort; label: string}[] = [
    {field: 'student_name', label: 'Student'},
    {field: 'lab_name', label: 'Lab'},
    {field: 'workout_id', label: 'Workout ID'},
    {field: 'build_date', label: 'Build date (UTC)'},
    {field: 'runtime_seconds', label: 'Recorded runtime'},
    {field: 'last_seen_at', label: 'Last ran (UTC)'},
    {field: 'run_count', label: 'Runs'},
];

export default function WorkoutRuntimeReport({initialMonth}: {initialMonth?: string}) {
    const today = new Date().toISOString().slice(0, 10);
    const defaultMonth = initialMonth || today.slice(0, 7);
    const [period, setPeriod] = useState<'month' | 'range'>('month');
    const [month, setMonth] = useState(defaultMonth);
    const [start, setStart] = useState(`${defaultMonth}-01`);
    const [end, setEnd] = useState(today);
    const [search, setSearch] = useState('');
    const [filters, setFilters] = useState<WorkoutRuntimeFilters>({month: defaultMonth, sort: 'build_date', direction: 'desc'});
    const [page, setPage] = useState(0);
    const [pageSize, setPageSize] = useState(25);
    const [report, setReport] = useState<Report | null>(null);
    const [loading, setLoading] = useState(true);
    const [exporting, setExporting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [exportError, setExportError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        cloudMonitoringService.listWorkoutRuntime(filters, page * pageSize, pageSize)
            .then(result => { if (active) setReport(result); })
            .catch(err => { if (active) setError(err instanceof HttpError ? err.message : 'Could not load workout runtime.'); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [filters, page, pageSize]);

    function apply(event: FormEvent) {
        event.preventDefault();
        setPage(0);
        setReport(null);
        setExportError(null);
        setFilters({
            ...(period === 'month' ? {month} : {start, end}),
            ...(search.trim() ? {q: search.trim()} : {}),
            sort: filters.sort,
            direction: filters.direction,
        });
    }

    function sortBy(sort: WorkoutRuntimeSort) {
        setPage(0);
        setFilters(current => ({...current, sort, direction: current.sort === sort && current.direction === 'desc' ? 'asc' : 'desc'}));
    }

    async function exportCsv() {
        setExporting(true);
        setExportError(null);
        try {
            const csv = await cloudMonitoringService.exportWorkoutRuntime(filters);
            const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
            const link = document.createElement('a');
            link.href = url;
            link.download = `agoge-workout-runtime-${filters.month || `${filters.start}-to-${filters.end}`}.csv`;
            document.body.append(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            setExportError(err instanceof HttpError ? err.message : 'Could not export workout runtime.');
        } finally {
            setExporting(false);
        }
    }

    const invalidPeriod = period === 'month' ? !/^\d{4}-(0[1-9]|1[0-2])$/.test(month) : !start || !end || end < start;

    return (
        <Stack component="section" spacing={2} aria-labelledby="workout-runtime-heading">
            <Typography id="workout-runtime-heading" component="h2" variant="h6">Workout runs by activity period</Typography>
            <Stack component="form" onSubmit={apply} direction="row" useFlexGap sx={{flexWrap: 'wrap', gap: 1.5, alignItems: 'center'}}>
                <TextField select label="Activity period" value={period} onChange={event => setPeriod(event.target.value as 'month' | 'range')}
                    slotProps={{select: {native: true}}} size="small">
                    <option value="month">Calendar month</option>
                    <option value="range">Custom date range</option>
                </TextField>
                {period === 'month' ? (
                    <TextField type="month" label="Month (UTC)" value={month} onChange={event => setMonth(event.target.value)}
                        slotProps={{inputLabel: {shrink: true}}} size="small" required />
                ) : (
                    <>
                        <TextField type="date" label="From (UTC)" value={start} onChange={event => setStart(event.target.value)}
                            slotProps={{inputLabel: {shrink: true}}} size="small" required />
                        <TextField type="date" label="Through (UTC)" value={end} onChange={event => setEnd(event.target.value)}
                            slotProps={{inputLabel: {shrink: true}}} size="small" required error={Boolean(start && end && end < start)} />
                    </>
                )}
                <TextField type="search" label="Search workouts" value={search} onChange={event => setSearch(event.target.value)}
                    slotProps={{htmlInput: {maxLength: 120}}} size="small" />
                <Button type="submit" variant="outlined" disabled={invalidPeriod}>Apply filters</Button>
                <Button onClick={() => void exportCsv()} disabled={exporting || loading || Boolean(error) || !report?.total}>
                    {exporting ? 'Exporting…' : 'Export CSV'}
                </Button>
            </Stack>
            {invalidPeriod && <Typography color="error" variant="body2">Enter a valid period with the start on or before the end.</Typography>}
            {error && <Alert severity="error">{error}</Alert>}
            {exportError && <Alert severity="error">{exportError}</Alert>}
            {loading && <Typography role="status">Loading workout runtime…</Typography>}
            {report && !error && (
                <>
                    <Box>
                        <Typography fontWeight="bold">
                            {report.total_workouts.toLocaleString()} {report.total_workouts === 1 ? 'workout' : 'workouts'} · {displayRuntime(report.total_runtime_seconds)} total recorded runtime
                        </Typography>
                        <Typography variant="body2" color="text.secondary">{report.start} through {report.end} UTC</Typography>
                    </Box>
                    {report.notes.map(note => <Typography key={note} variant="body2" color="text.secondary">{note}</Typography>)}
                    <TableContainer>
                        <Table size="small" aria-label="Workout runtime report">
                            <TableHead><TableRow>
                                {columns.map(({field, label}) => (
                                    <TableCell key={field} align={field === 'run_count' ? 'right' : 'left'}
                                        sortDirection={filters.sort === field ? filters.direction : false}>
                                        <TableSortLabel active={filters.sort === field} direction={filters.direction} onClick={() => sortBy(field)}>
                                            {label}
                                        </TableSortLabel>
                                    </TableCell>
                                ))}
                            </TableRow></TableHead>
                            <TableBody>
                                {report.rows.map(row => (
                                    <TableRow key={row.row_id}>
                                        <TableCell component="th" scope="row">{row.student_name || row.student_email || '—'}</TableCell>
                                        <TableCell>{row.unit_id ? (
                                            <MuiLink component={Link} to={`${URL_TEACHER_UNIT}/${encodeURIComponent(row.unit_id)}`}>
                                                {row.lab_name || row.unit_id}
                                            </MuiLink>
                                        ) : row.lab_name || '—'}</TableCell>
                                        <TableCell>{row.workout_id}</TableCell>
                                        <TableCell>{displayTimestamp(row.build_date)}</TableCell>
                                        <TableCell>{displayRuntime(row.runtime_seconds)}{row.running && ' · Running'}</TableCell>
                                        <TableCell>{displayTimestamp(row.last_seen_at)}</TableCell>
                                        <TableCell align="right">{row.run_count}</TableCell>
                                    </TableRow>
                                ))}
                                {report.rows.length === 0 && <TableRow><TableCell colSpan={columns.length}>No recorded workouts for this period.</TableCell></TableRow>}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    <TablePagination component="div" count={report.total} page={page} rowsPerPage={pageSize}
                        rowsPerPageOptions={[25, 50, 100]} onPageChange={(_, next) => setPage(next)}
                        onRowsPerPageChange={event => { setPage(0); setPageSize(Number(event.target.value)); }} />
                </>
            )}
        </Stack>
    );
}

export function WorkoutMonthlySummary({onSelectMonth}: {onSelectMonth: (month: string) => void}) {
    const [report, setReport] = useState<WorkoutRuntimeMonths | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [refreshKey, setRefreshKey] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        cloudMonitoringService.listRuntimeMonths()
            .then(result => { if (active) setReport(result); })
            .catch(err => { if (active) setError(err instanceof HttpError ? err.message : 'Could not load monthly workout totals.'); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [refreshKey]);

    return (
        <Stack component="section" spacing={2} aria-labelledby="workout-monthly-heading">
            <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap', alignItems: 'center'}}>
                <Typography component="h2" id="workout-monthly-heading" variant="h6">Monthly Summary</Typography>
                <Button onClick={() => setRefreshKey(key => key + 1)} disabled={loading}>Refresh</Button>
            </Stack>
            {error && <Alert severity="error">{error}</Alert>}
            {loading && <Typography role="status">Loading monthly workout totals…</Typography>}
            {report && (
                <>
                    <Typography variant="body2" color="text.secondary">{report.start} through {report.end} UTC</Typography>
                    <TableContainer>
                        <Table size="small" aria-label="Monthly workout totals">
                            <TableHead><TableRow>
                                <TableCell>Month (UTC)</TableCell>
                                <TableCell align="right">Workouts</TableCell>
                                <TableCell align="right">Runs</TableCell>
                                <TableCell align="right">Recorded runtime</TableCell>
                            </TableRow></TableHead>
                            <TableBody>
                                {report.months.map(row => (
                                    <TableRow key={row.month}>
                                        <TableCell component="th" scope="row">
                                            <MuiLink component="button" type="button" onClick={() => onSelectMonth(row.month)}
                                                aria-label={`View workouts for ${row.month}`}>{row.month}</MuiLink>
                                        </TableCell>
                                        <TableCell align="right">{row.workouts.toLocaleString()}</TableCell>
                                        <TableCell align="right">{row.run_count.toLocaleString()}</TableCell>
                                        <TableCell align="right">{displayRuntime(row.runtime_seconds)}</TableCell>
                                    </TableRow>
                                ))}
                                {!report.months.length && <TableRow><TableCell colSpan={4}>No monthly activity recorded.</TableCell></TableRow>}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    {report.notes.map(note => <Typography key={note} variant="body2" color="text.secondary">{note}</Typography>)}
                </>
            )}
        </Stack>
    );
}
