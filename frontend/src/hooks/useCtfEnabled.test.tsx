// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ctfService } from '../services/Ctf/ctf.service';
import { SafeAgogeUser } from '../services/User/user.model';
import { resetCtfEnabledCache, useCtfEnabled } from './useCtfEnabled';

let currentUser: SafeAgogeUser | null = null;

vi.mock('../context/AuthContext', () => ({
    useAuthContext: () => ({ agogeUser: { user: currentUser } }),
}));
vi.mock('../services/Ctf/ctf.service', () => ({ ctfService: { getConfig: vi.fn() } }));

const makeUser = (uid: string, permissions: { [key: string]: boolean }): SafeAgogeUser => ({
    uid, email: `${uid}@example.edu`, permissions, settings: {}, timezone: 'UTC',
});

describe('useCtfEnabled', () => {
    beforeEach(() => {
        resetCtfEnabledCache();
        vi.mocked(ctfService.getConfig).mockReset();
    });
    afterEach(() => {
        currentUser = null;
    });

    it('reports enabled for an instructor when the config says so', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: true });

        const { result } = renderHook(() => useCtfEnabled());
        expect(result.current).toEqual({ ctfEnabled: false, loading: true });
        await waitFor(() => expect(result.current).toEqual({ ctfEnabled: true, loading: false }));
    });

    it('reports disabled when the config says so', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: false });

        const { result } = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.ctfEnabled).toBe(false);
    });

    it('also asks for an admin', async () => {
        currentUser = makeUser('root', { admin: true });
        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: true });

        const { result } = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(result.current.ctfEnabled).toBe(true));
    });

    // The route is teacher_required; a student or anonymous request would only 403.
    it.each([
        ['a student', makeUser('kid', { student: true })],
        ['a pending user', makeUser('new', {})],
        ['nobody signed in', null],
    ])('never calls the API for %s', async (_label, user) => {
        currentUser = user;

        const { result } = renderHook(() => useCtfEnabled());
        expect(result.current).toEqual({ ctfEnabled: false, loading: false });
        await Promise.resolve();
        expect(ctfService.getConfig).not.toHaveBeenCalled();
    });

    it('reads the config only once per session across many consumers', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: true });

        const first = renderHook(() => useCtfEnabled());
        const second = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(first.result.current.ctfEnabled).toBe(true));
        await waitFor(() => expect(second.result.current.ctfEnabled).toBe(true));

        first.unmount();
        const third = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(third.result.current.ctfEnabled).toBe(true));
        expect(ctfService.getConfig).toHaveBeenCalledTimes(1);
    });

    it('fails closed on an error and retries on a later mount', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockRejectedValueOnce(new Error('boom'));

        const failed = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(failed.result.current.loading).toBe(false));
        expect(failed.result.current.ctfEnabled).toBe(false);

        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: true });
        const retried = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(retried.result.current.ctfEnabled).toBe(true));
        expect(ctfService.getConfig).toHaveBeenCalledTimes(2);
    });

    it('asks again for a different user and never shows the previous answer', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockResolvedValueOnce({ ctf_enabled: true });

        const { result, rerender } = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(result.current.ctfEnabled).toBe(true));

        let release: (value: { ctf_enabled: boolean }) => void = () => undefined;
        vi.mocked(ctfService.getConfig).mockReturnValueOnce(new Promise((resolve) => { release = resolve; }));
        currentUser = makeUser('other', { instructor: true });
        rerender();
        expect(result.current).toEqual({ ctfEnabled: false, loading: true });

        release({ ctf_enabled: false });
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.ctfEnabled).toBe(false);
        expect(ctfService.getConfig).toHaveBeenCalledTimes(2);
    });

    it('hides the feature as soon as the user signs out', async () => {
        currentUser = makeUser('gm', { instructor: true });
        vi.mocked(ctfService.getConfig).mockResolvedValue({ ctf_enabled: true });

        const { result, rerender } = renderHook(() => useCtfEnabled());
        await waitFor(() => expect(result.current.ctfEnabled).toBe(true));

        currentUser = null;
        rerender();
        expect(result.current).toEqual({ ctfEnabled: false, loading: false });
    });
});
