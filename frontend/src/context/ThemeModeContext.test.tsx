// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeModeProvider, useThemeMode } from './ThemeModeContext';

const mockPrefersDark = (dark: boolean) => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: dark && query.includes('dark'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }));
};

const wrapper = ({ children }: { children: React.ReactNode }) => <ThemeModeProvider>{children}</ThemeModeProvider>;

describe('ThemeModeContext', () => {
    beforeEach(() => {
        localStorage.clear();
        mockPrefersDark(true);
    });
    afterEach(() => localStorage.clear());

    it('defaults to system and resolves from the OS preference', () => {
        const { result } = renderHook(() => useThemeMode(), { wrapper });
        expect(result.current.mode).toBe('system');
        expect(result.current.resolvedMode).toBe('dark');
    });

    it('cycles system → light → dark → system on every press', () => {
        const { result } = renderHook(() => useThemeMode(), { wrapper });
        const seen: string[] = [];
        for (let i = 0; i < 4; i++) {
            act(() => result.current.cycleMode());
            seen.push(result.current.mode);
        }
        expect(seen).toEqual(['light', 'dark', 'system', 'light']);
        expect(localStorage.getItem('themeMode')).toBe('light');
    });

    it('migrates the legacy boolean theme key', () => {
        localStorage.setItem('theme', 'false');
        const { result } = renderHook(() => useThemeMode(), { wrapper });
        expect(result.current.mode).toBe('light');
        expect(localStorage.getItem('theme')).toBeNull();
    });
});
