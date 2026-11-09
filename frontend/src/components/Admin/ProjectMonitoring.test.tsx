// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import {cloudMonitoringService} from '../../services/Admin/cloud-monitoring.service';
import {buildIncidentsService} from '../../services/BuildIncidents/build-incidents.service';
import ProjectOverviewTabs from './ProjectOverviewTabs';

vi.mock('./UnitManager', () => ({default: () => null}));
vi.mock('./WorkoutManager', () => ({default: () => null}));
vi.mock('./WireGuard/WireGuardKitManager', () => ({WireGuardRemotePeerManager: () => null}));
vi.mock('../../services/BuildIncidents/build-incidents.service', () => ({
    buildIncidentsService: {listEvents: vi.fn(), recheckQuota: vi.fn()},
}));
vi.mock('../../services/Admin/cloud-monitoring.service', () => ({
    cloudMonitoringService: {
        getQuotas: vi.fn(), listWorkoutRuntime: vi.fn(), listRuntimeMonths: vi.fn(), exportWorkoutRuntime: vi.fn(),
    },
}));

const observedAt = '2026-11-09T12:00:00Z';
const quotaReport = {
    project: 'test-project', region: 'us-central1', observed_at: observedAt,
    quotas: [{metric: 'NETWORKS', scope: 'global', usage: 29, limit: 30, remaining: 1, utilization: 29 / 30, level: 'critical' as const}],
};
const runtimeReport = {
    start: '2026-11-01', end: '2026-11-30', total: 1, total_workouts: 1, total_runtime_seconds: 5400,
    notes: ['Recorded activity only.'],
    rows: [{
        row_id: 'row-1', workout_id: 'workout-1', unit_id: 'lab-1', lab_name: 'Routing', student_name: 'Avery Student',
        student_email: 'test@example.edu', runtime_seconds: 5400, run_count: 2, build_date: observedAt,
        started_at: observedAt, last_seen_at: observedAt, running: false,
    }],
};

const renderPage = (view: string) => render(
    <MemoryRouter initialEntries={[`/admin?view=${view}`]}>
        <ProjectOverviewTabs />
    </MemoryRouter>
);

beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(cloudMonitoringService.getQuotas).mockResolvedValue(quotaReport);
    vi.mocked(cloudMonitoringService.listWorkoutRuntime).mockResolvedValue(runtimeReport);
    vi.mocked(cloudMonitoringService.listRuntimeMonths).mockResolvedValue({
        start: '2025-12-01', end: '2026-11-30', notes: [],
        months: [{month: '2026-11', workouts: 1, runtime_seconds: 5400, run_count: 2}],
    });
});
afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
});

it('opens the Build Log from a legacy incident link and keeps scanning filtered pages', async () => {
    vi.mocked(buildIncidentsService.listEvents)
        .mockResolvedValueOnce({events: []})
        .mockResolvedValueOnce({events: [], next_cursor: 'next'})
        .mockResolvedValueOnce({events: [{
            id: 'event-1', kind: 'build_error', occurred_at: observedAt, unit_id: 'lab-1', project: 'test-project',
            reason: 'TimeoutError', stage: 'network', event_id: 'delivery-1',
        }]})
        .mockResolvedValue({events: []});
    renderPage('incidents');
    expect(screen.getByRole('heading', {name: 'Build Log'})).toBeInTheDocument();
    expect(cloudMonitoringService.getQuotas).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('searchbox', {name: 'Search build events'}), {target: {value: 'TimeoutError'}});
    fireEvent.click(screen.getByRole('button', {name: 'Apply filters'}));
    expect(await screen.findByText(/load more to continue searching/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Load more events'}));
    expect(await screen.findByRole('link', {name: 'lab-1'})).toHaveAttribute('href', '/teacher/lab/lab-1');
    expect(buildIncidentsService.listEvents).toHaveBeenLastCalledWith({search: 'TimeoutError', sort: 'desc'}, 'next');
    const logs = screen.getByRole('link', {name: 'View cloud logs', hidden: true});
    expect(decodeURIComponent(logs.getAttribute('href') || '')).toContain('jsonPayload.extra.event_id="delivery-1"');

    fireEvent.click(screen.getByRole('button', {name: /event time/i}));
    await waitFor(() => expect(buildIncidentsService.listEvents).toHaveBeenLastCalledWith({search: 'TimeoutError', sort: 'asc'}, undefined));
});

it('retains the last quota reading when its scope cannot be refreshed', async () => {
    renderPage('cloudMonitoring');
    const table = await screen.findByRole('table', {name: 'Cloud quota usage'});
    expect(within(table).getByRole('rowheader', {name: 'NETWORKS'})).toBeInTheDocument();
    expect(within(table).getByText('Very low headroom')).toBeInTheDocument();
    vi.mocked(cloudMonitoringService.getQuotas).mockResolvedValueOnce({
        ...quotaReport, observed_at: '2026-11-09T12:01:00Z', quotas: [], unavailable_scopes: ['global'],
    });
    fireEvent.click(screen.getByRole('button', {name: 'Refresh cloud quotas'}));
    expect(await screen.findByText(/current quota readings unavailable for global/i)).toBeInTheDocument();
    expect(within(table).getByText(`Last observed ${observedAt}`)).toBeInTheDocument();
});

it('filters runtime by activity month, sorts by build date, and exports the active report', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', class extends URL {
        static createObjectURL = vi.fn(() => 'blob:test');
        static revokeObjectURL = revokeObjectURL;
    });
    vi.mocked(cloudMonitoringService.exportWorkoutRuntime).mockResolvedValue('Student,Workout\nAvery Student,workout-1');

    renderPage('cloudMonitoring');
    expect(cloudMonitoringService.listWorkoutRuntime).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('tab', {name: 'Monthly Summary'}));
    const monthly = await screen.findByRole('table', {name: 'Monthly workout totals'});
    expect(cloudMonitoringService.listWorkoutRuntime).not.toHaveBeenCalled();
    fireEvent.click(within(monthly).getByRole('button', {name: 'View workouts for 2026-11'}));
    expect(screen.getByRole('tab', {name: 'Workout Runs'})).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByRole('rowheader', {name: 'Avery Student'})).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Build date (UTC)'}));
    await waitFor(() => expect(cloudMonitoringService.listWorkoutRuntime)
        .toHaveBeenLastCalledWith({month: '2026-11', sort: 'build_date', direction: 'asc'}, 0, 25));
    fireEvent.click(screen.getByRole('tab', {name: 'Monthly Summary'}));
    fireEvent.click(screen.getByRole('tab', {name: 'Workout Runs'}));
    expect(screen.getByRole('columnheader', {name: 'Build date (UTC)'})).toHaveAttribute('aria-sort', 'ascending');
    const download = await screen.findByRole('button', {name: 'Export CSV'});
    await waitFor(() => expect(download).toBeEnabled());
    fireEvent.click(download);
    await waitFor(() => expect(click).toHaveBeenCalledOnce());
    expect(cloudMonitoringService.exportWorkoutRuntime).toHaveBeenCalledWith({month: '2026-11', sort: 'build_date', direction: 'asc'});
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:test'), {timeout: 2000});
});
