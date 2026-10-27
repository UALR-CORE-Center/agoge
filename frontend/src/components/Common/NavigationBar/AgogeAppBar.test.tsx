// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { URL_TEACHER_CTF_BASE } from '../../../router/urls';
import AgogeAppBar from './AgogeAppBar';

let ctfEnabled = false;
let permissions: { [key: string]: boolean } = { instructor: true };

vi.mock('../../../context/AuthContext', () => ({
    useAuthContext: () => ({
        firebaseUser: { user: { displayName: 'Game Master', email: 'gm@example.edu' } },
        agogeUser: { user: { uid: 'gm', email: 'gm@example.edu', permissions, settings: {}, timezone: 'UTC' } },
        logout: vi.fn(),
    }),
}));
vi.mock('../../../context/ThemeModeContext', () => ({
    THEME_MODE_CYCLE: ['system', 'light', 'dark'],
    useThemeMode: () => ({ mode: 'system', cycleMode: vi.fn() }),
}));
vi.mock('../InfoDrawer/InfoDrawerContext', () => ({
    useDrawer: () => ({
        showDrawerButton: false, openDrawer: vi.fn(), drawerData: null, closeDrawer: vi.fn(), isOpen: false,
    }),
}));
vi.mock('../../../hooks/useCtfEnabled', () => ({
    useCtfEnabled: () => ({ ctfEnabled, loading: false }),
}));

const openTeachersMenu = () => {
    render(<MemoryRouter><AgogeAppBar onSidebarToggle={vi.fn()} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Teachers' }));
};

describe('AgogeAppBar CTF menu item', () => {
    afterEach(() => {
        cleanup();
        ctfEnabled = false;
        permissions = { instructor: true };
    });

    it('links to the CTF events list when CTF is enabled', () => {
        ctfEnabled = true;
        openTeachersMenu();

        const item = screen.getByRole('menuitem', { name: 'CTF Events' });
        expect(item.getAttribute('href')).toBe(URL_TEACHER_CTF_BASE);
        // The existing items are untouched.
        expect(screen.getByRole('menuitem', { name: 'Manage Servers' })).toBeTruthy();
    });

    it('is absent when CTF is disabled', () => {
        openTeachersMenu();

        expect(screen.getByRole('menuitem', { name: 'Manage Servers' })).toBeTruthy();
        expect(screen.queryByRole('menuitem', { name: 'CTF Events' })).toBeNull();
    });

    it('is not offered to a non-instructor even if the flag were true', () => {
        ctfEnabled = true;
        permissions = { student: true };
        render(<MemoryRouter><AgogeAppBar onSidebarToggle={vi.fn()} /></MemoryRouter>);

        expect(screen.queryByRole('button', { name: 'Teachers' })).toBeNull();
        expect(screen.queryByText('CTF Events')).toBeNull();
    });
});
