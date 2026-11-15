// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { URL_ADMIN_BASE, URL_STUDENT_WORKOUT, URL_TEACHER_CTF_BASE, URL_TEACHER_UNIT } from '../../../router/urls';
import AgogeAppBar from './AgogeAppBar';

let ctfEnabled = false;
let permissions: Record<string, boolean> | null = { instructor: true };

vi.mock('../../../context/AuthContext', () => ({
    useAuthContext: () => ({
        firebaseUser: { user: permissions && { displayName: 'Game Master', email: 'gm@example.edu' } },
        agogeUser: { user: permissions && { uid: 'gm', email: 'gm@example.edu', permissions, settings: {}, timezone: 'UTC' } },
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

afterEach(() => {
    cleanup();
    ctfEnabled = false;
    permissions = { instructor: true };
});

describe('AgogeAppBar CTF menu item', () => {
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

describe('AgogeAppBar CORE branding', () => {
    it.each([
        { pathname: `${URL_TEACHER_UNIT}/12345`, permission: 'instructor' },
        { pathname: URL_ADMIN_BASE, permission: 'admin' },
        { pathname: `${URL_STUDENT_WORKOUT}/12345`, permission: 'student' },
        { pathname: `${URL_STUDENT_WORKOUT}/12345`, permission: 'instructor' },
        { pathname: `${URL_STUDENT_WORKOUT}/12345`, permission: null },
    ])('shows the same brand at $pathname (permission: $permission)', ({ pathname, permission }) => {
        permissions = permission ? { [permission]: true } : null;
        render(
            <MemoryRouter basename="/ualr" initialEntries={[`/ualr${pathname}`]}>
                <AgogeAppBar onSidebarToggle={vi.fn()} />
            </MemoryRouter>
        );

        const brand = screen.getByRole('link', { name: 'Agoge · CORE Center' });
        expect(brand.textContent).toBe('Agoge');
        expect(brand.querySelector('img')?.getAttribute('src')).toBe('/images/core-emblem.png');
    });
});
