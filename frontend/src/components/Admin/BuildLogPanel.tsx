import {
    Alert, Box, Button, Chip, Link as MuiLink, MenuItem, Stack, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, TableSortLabel, TextField, Typography,
} from '@mui/material';
import {FormEvent, useCallback, useEffect, useRef, useState} from 'react';
import {Link} from 'react-router-dom';
import {URL_TEACHER_UNIT} from '../../router/urls';
import {BuildEvent, BuildEventFilters, BuildEventKind} from '../../services/BuildIncidents/build-incidents.model';
import {buildIncidentsService} from '../../services/BuildIncidents/build-incidents.service';
import HttpError from '../Common/Errors/HttpError';

const kindLabels: Record<BuildEventKind, string> = {
    build_started: 'Build started',
    build_completed: 'Build completed',
    build_error: 'Build error',
    build_failure: 'Build failed',
    build_blocked: 'Build paused',
    cleanup_completed: 'Cleanup completed',
    cleanup_failed: 'Cleanup failed',
};

const dateFormat = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC'});
const eventLabel = (value: string) => value.replace(/[_-]/g, ' ');

function logsUrl(event: BuildEvent) {
    if (!event.project) return null;
    const operation = event.operation_id && JSON.stringify(event.operation_id);
    const delivery = event.event_id && JSON.stringify(event.event_id);
    const query = operation
        ? `jsonPayload.operation_id=${operation} OR operation.id=${operation}`
        : delivery && `jsonPayload.event_id=${delivery} OR jsonPayload.extra.event_id=${delivery}`;
    if (!query) return null;
    return `https://console.cloud.google.com/logs/query;query=${encodeURIComponent(query)}?project=${encodeURIComponent(event.project)}`;
}

function EventDetails({event}: {event: BuildEvent}) {
    const url = logsUrl(event);
    return (
        <Box component="details" sx={{minWidth: 160, overflowWrap: 'anywhere'}}>
            <Box component="summary" sx={{cursor: 'pointer'}}>
                {event.metric || event.limit_name || event.reason || 'Event details'}
            </Box>
            {[
                event.message,
                event.stage && `Stage · ${eventLabel(event.stage)}`,
                event.reason && `Reason · ${event.reason}`,
                event.metric && `Quota · ${event.metric}`,
                event.limit_name && `Quota limit name · ${event.limit_name}`,
                event.limit != null && `Limit · ${event.limit}`,
                event.scope && `Scope · ${event.scope}`,
                (event.resource || event.resource_type) && `Resource · ${[event.resource_type, event.resource].filter(Boolean).join(' ')}`,
                event.project && `Project · ${event.project}`,
                event.operation_id && `Operation · ${event.operation_id}`,
                event.event_id && `Delivery ID · ${event.event_id}`,
                `Event ID · ${event.id}`,
            ].filter(Boolean).map((line, index) => <Typography key={index} variant="body2">{line}</Typography>)}
            {url && <MuiLink href={url} target="_blank" rel="noopener noreferrer">View cloud logs</MuiLink>}
        </Box>
    );
}

export default function BuildLogPanel() {
    const [search, setSearch] = useState('');
    const [kind, setKind] = useState<BuildEventKind | ''>('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [filters, setFilters] = useState<BuildEventFilters>({sort: 'desc'});
    const [events, setEvents] = useState<BuildEvent[]>([]);
    const [cursor, setCursor] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const requestId = useRef(0);

    const load = useCallback(async (next?: string) => {
        const request = ++requestId.current;
        setLoading(true);
        setError(null);
        try {
            const page = await buildIncidentsService.listEvents(filters, next);
            if (request !== requestId.current) return;
            setEvents(current => next
                ? [...new Map([...current, ...page.events].map(event => [event.id, event])).values()]
                : page.events);
            setCursor(page.next_cursor ?? null);
        } catch (err) {
            if (request === requestId.current) setError(err instanceof HttpError ? err.message : 'Could not load the build log.');
        } finally {
            if (request === requestId.current) setLoading(false);
        }
    }, [filters]);

    useEffect(() => {
        setEvents([]);
        setCursor(null);
        void load();
        return () => { requestId.current++; };
    }, [load]);

    function apply(event: FormEvent) {
        event.preventDefault();
        setFilters({
            sort: filters.sort,
            ...(kind ? {kind} : {}),
            ...(dateFrom ? {date_from: dateFrom} : {}),
            ...(dateTo ? {date_to: dateTo} : {}),
            ...(search.trim() ? {search: search.trim()} : {}),
        });
    }

    const invalidDates = Boolean(dateFrom && dateTo && dateTo < dateFrom);

    return (
        <Stack spacing={2} sx={{p: {xs: 1.5, sm: 3}, width: '100%', minWidth: 0}}>
            <Typography component="h1" variant="h5">Build Log</Typography>
            <Stack component="form" onSubmit={apply} direction="row" useFlexGap sx={{flexWrap: 'wrap', gap: 1.5, alignItems: 'center'}}>
                <TextField type="search" label="Search build events" value={search} onChange={event => setSearch(event.target.value)}
                    slotProps={{htmlInput: {maxLength: 160}}} size="small" />
                <TextField select label="Event type" value={kind} onChange={event => setKind(event.target.value as BuildEventKind | '')}
                    slotProps={{inputLabel: {shrink: true}}} size="small" sx={{minWidth: 165}}>
                    <MenuItem value="">All events</MenuItem>
                    {Object.entries(kindLabels).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
                </TextField>
                <TextField type="date" label="From (UTC)" value={dateFrom} onChange={event => setDateFrom(event.target.value)}
                    slotProps={{inputLabel: {shrink: true}}} size="small" />
                <TextField type="date" label="Through (UTC)" value={dateTo} onChange={event => setDateTo(event.target.value)}
                    slotProps={{inputLabel: {shrink: true}}} size="small" error={invalidDates} />
                <Button type="submit" variant="outlined" disabled={invalidDates}>Apply filters</Button>
                <Button onClick={() => void load()} disabled={loading}>Refresh</Button>
            </Stack>
            {invalidDates && <Typography variant="body2" color="error">Enter an end date on or after the start date.</Typography>}
            {error && <Alert severity="error">{error}</Alert>}
            {loading && <Typography role="status">Loading build events…</Typography>}
            <TableContainer>
                <Table aria-label="Build Log" size="small">
                    <TableHead><TableRow>
                        <TableCell sortDirection={filters.sort}>
                            <TableSortLabel active direction={filters.sort}
                                onClick={() => setFilters(current => ({...current, sort: current.sort === 'asc' ? 'desc' : 'asc'}))}>
                                Event time (UTC)
                            </TableSortLabel>
                        </TableCell>
                        <TableCell>Event</TableCell>
                        <TableCell>Lab</TableCell>
                        <TableCell>Workout ID</TableCell>
                        <TableCell>Details</TableCell>
                    </TableRow></TableHead>
                    <TableBody>
                        {events.map(event => (
                            <TableRow key={event.id} sx={{'& > th, & > td': {verticalAlign: 'top'}}}>
                                <TableCell component="th" scope="row">{dateFormat.format(new Date(event.occurred_at))}</TableCell>
                                <TableCell>
                                    <Stack spacing={.5} sx={{alignItems: 'flex-start'}}>
                                        <Typography variant="body2">{kindLabels[event.kind] || eventLabel(event.kind)}</Typography>
                                        {event.status && <Chip size="small" label={event.status === 'open' ? 'Open' : 'Resolved'} />}
                                    </Stack>
                                </TableCell>
                                <TableCell>{event.unit_id ? (
                                    <MuiLink component={Link} to={`${URL_TEACHER_UNIT}/${encodeURIComponent(event.unit_id)}`}>{event.unit_id}</MuiLink>
                                ) : '—'}</TableCell>
                                <TableCell>{event.workout_id || '—'}</TableCell>
                                <TableCell><EventDetails event={event} /></TableCell>
                            </TableRow>
                        ))}
                        {!loading && !error && !events.length && (
                            <TableRow><TableCell colSpan={5}>{cursor
                                ? 'No matching events on this page. Load more to continue searching.'
                                : 'No build events match these filters.'}</TableCell></TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
            {cursor && <Button onClick={() => void load(cursor)} disabled={loading}>Load more events</Button>}
        </Stack>
    );
}
