// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {BuildIncident} from '../../../services/BuildIncidents/build-incidents.model';
import {unitService} from '../../../services/Unit/unit.service';
import {workoutService} from '../../../services/Workout/workout.service';
import {PubSub} from '../../../types/PubSub';
import UnitBuildIncidents from './UnitBuildIncidents';

const {copy} = vi.hoisted(() => ({copy: vi.fn()}));
vi.mock('../../../hooks/useClipboard', () => ({useClipboard: () => ({copy})}));
vi.mock('../../../services/Unit/unit.service', () => ({unitService: {delete_unit: vi.fn(), put_action: vi.fn()}}));
vi.mock('../../../services/Workout/workout.service', () => ({workoutService: {put_action: vi.fn()}}));

const incident: BuildIncident = {
    id: 'incident-1',
    unit_id: 'unit-1',
    project: 'agoge-test',
    kind: 'build_failure',
    status: 'open',
    occurred_at: '2026-11-07T12:24:18Z',
    stage: 'network_creation',
    reason: 'QUOTA_EXCEEDED',
    metric: 'NETWORKS',
    scope: 'global',
    limit: 30,
};

beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
});
afterEach(cleanup);

it('copies the exact quota and preserves the warning after keeping the lab and returning', async () => {
    const page = <UnitBuildIncidents incidents={[incident]} unitId="unit-1" workouts={[]} onChanged={vi.fn()} />;
    const {unmount} = render(page);
    const prompt = await screen.findByRole('dialog', {name: 'Lab build failed'});
    fireEvent.click(within(prompt).getByRole('button', {name: 'Copy report'}));
    expect(copy).toHaveBeenCalledWith(expect.stringContaining('Quota: NETWORKS\nLimit: 30\nScope: global'));
    fireEvent.click(within(prompt).getByRole('button', {name: 'Keep for inspection'}));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent('Lab build failed');
    unmount();
    render(page);
    expect(screen.getByRole('alert')).toHaveTextContent('Lab build failed');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('confirms and requests cleanup only for an affected workout', async () => {
    const onChanged = vi.fn();
    vi.mocked(workoutService.put_action).mockResolvedValue({id: 'workout-1', state: '62'});
    render(<UnitBuildIncidents incidents={[{...incident, workout_id: 'workout-1'}]} unitId="unit-1"
        workouts={[]} onChanged={onChanged} />);
    const prompt = await screen.findByRole('dialog', {name: 'Workout build failed'});
    fireEvent.click(within(prompt).getByRole('button', {name: 'Clean up failed workout…'}));
    const confirmation = await screen.findByRole('textbox', {name: 'Confirmation'});
    const remove = screen.getByRole('button', {name: 'Clean up failed workout'});
    expect(remove).toBeDisabled();
    fireEvent.change(confirmation, {target: {value: 'workout-1'}});
    fireEvent.click(remove);
    await waitFor(() => expect(workoutService.put_action).toHaveBeenCalledWith('workout-1', String(PubSub.Actions.DELETE)));
    expect(unitService.delete_unit).not.toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent('Deletion requested');
    expect(onChanged).toHaveBeenCalled();
});
