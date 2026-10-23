// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {cleanup, render, screen} from '@testing-library/react';
import React from 'react';
import {MemoryRouter, Route, Routes} from 'react-router-dom';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {guacamoleService} from '../../services/Guacamole/guacamole.service';
import HttpError from '../Common/Errors/HttpError';
import SessionWaitDialog from './SessionWaitDialog';

vi.mock('../../services/Guacamole/guacamole.service', () => ({
    guacamoleService: {getSession: vi.fn(), tokenizedUrl: vi.fn()},
}));

const renderAt = (path: string) => render(
    <MemoryRouter initialEntries={[path]}>
        <Routes>
            <Route path="/student/workout/:buildId/guacamole/:serverIdx" element={<SessionWaitDialog/>}/>
        </Routes>
    </MemoryRouter>
);

describe('SessionWaitDialog', () => {
    afterEach(cleanup);

    it('stops and explains a 404 instead of retrying', async () => {
        vi.mocked(guacamoleService.getSession)
            .mockRejectedValue(new HttpError(404, 'No servers found with proxy connections'));

        renderAt('/student/workout/abcdefghij/guacamole/0');

        expect(await screen.findByText(/No remote connection is set up for this server/)).toBeInTheDocument();
        expect(screen.getByText(/No servers found with proxy connections/)).toBeInTheDocument();
        expect(guacamoleService.getSession).toHaveBeenCalledTimes(1);
    });
});
