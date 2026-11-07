// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import {BuildAvailabilityProvider} from '../../provider/BuildAvailabilityProvider';
import {buildIncidentsService} from '../../services/BuildIncidents/build-incidents.service';
import {BUILD_AVAILABILITY_REFRESH} from './Errors/HttpError';
import ProjectQuotaBanner from './ProjectQuotaBanner';

const {auth, copy} = vi.hoisted(() => ({
    auth: {permissions: {admin: false, instructor: true, student: true}},
    copy: vi.fn(),
}));
vi.mock('../../context/AuthContext', () => ({
    useAuthContext: () => ({firebaseUser: {user: {uid: 'firebase-user'}}, agogeUser: {user: auth}}),
}));
vi.mock('../../hooks/useClipboard', () => ({useClipboard: () => ({copy})}));
vi.mock('../../services/BuildIncidents/build-incidents.service', () => ({
    buildIncidentsService: {getAvailability: vi.fn()},
}));

const hold = {id: 'hold-1', project: 'agoge-test', metric: 'NETWORKS', scope: 'global', limit: 30};

function renderBanner() {
    return render(<MemoryRouter><BuildAvailabilityProvider><ProjectQuotaBanner /></BuildAvailabilityProvider></MemoryRouter>);
}

beforeEach(() => {
    vi.resetAllMocks();
    auth.permissions = {admin: false, instructor: true, student: true};
    vi.mocked(buildIncidentsService.getAvailability).mockResolvedValue({hold});
});
afterEach(cleanup);

it('retains a verified hold after a failed refresh and clears it only after a successful refresh', async () => {
    renderBanner();
    expect(await screen.findByRole('alert')).toHaveTextContent('global NETWORKS (limit 30)');
    fireEvent.click(screen.getByRole('button', {name: 'Copy quota report'}));
    expect(copy).toHaveBeenCalledWith(expect.stringContaining('Hold ID: hold-1'));
    vi.mocked(buildIncidentsService.getAvailability).mockRejectedValueOnce(new Error('Unavailable'));
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(screen.getByRole('alert')).toBeInTheDocument();
    vi.mocked(buildIncidentsService.getAvailability).mockResolvedValueOnce({hold: null});
    window.dispatchEvent(new Event(BUILD_AVAILABILITY_REFRESH));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
});

it('links administrators directly to the Incidents tab', async () => {
    auth.permissions = {admin: true, instructor: false, student: true};
    renderBanner();
    expect(await screen.findByRole('link', {name: 'View incidents'})).toHaveAttribute('href', '/admin?view=incidents');
});

it('does not request or display project quota information to learners', () => {
    auth.permissions = {admin: false, instructor: false, student: true};
    renderBanner();
    expect(buildIncidentsService.getAvailability).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
