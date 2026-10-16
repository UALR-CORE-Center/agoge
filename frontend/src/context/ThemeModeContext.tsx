import { useMediaQuery } from '@mui/material';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export type ThemeMode = 'system' | 'light' | 'dark';
export type ResolvedThemeMode = Exclude<ThemeMode, 'system'>;

// Order the toggle button cycles through.
export const THEME_MODE_CYCLE: ThemeMode[] = ['system', 'light', 'dark'];

const STORAGE_KEY = 'themeMode';
// Pre-tri-state key that stored a JSON boolean (true = dark).
const LEGACY_STORAGE_KEY = 'theme';

const isThemeMode = (value: unknown): value is ThemeMode =>
    THEME_MODE_CYCLE.includes(value as ThemeMode);

const readStoredMode = (): ThemeMode => {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (isThemeMode(stored)) return stored;

        const legacy = localStorage.getItem(LEGACY_STORAGE_KEY);
        if (legacy === 'true') return 'dark';
        if (legacy === 'false') return 'light';
    } catch {
        // Storage can be unavailable (private mode, blocked site data).
    }
    return 'system';
};

interface ThemeModeContextValue {
    mode: ThemeMode;
    resolvedMode: ResolvedThemeMode;
    setMode: (mode: ThemeMode) => void;
    cycleMode: () => void;
}

const ThemeModeContext = createContext<ThemeModeContextValue | undefined>(undefined);

export const ThemeModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [mode, setMode] = useState<ThemeMode>(readStoredMode);
    const prefersDark = useMediaQuery('(prefers-color-scheme: dark)', { noSsr: true });
    const resolvedMode: ResolvedThemeMode = mode === 'system' ? (prefersDark ? 'dark' : 'light') : mode;

    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, mode);
            localStorage.removeItem(LEGACY_STORAGE_KEY);
        } catch {
            // Non-fatal: the choice just won't persist.
        }
    }, [mode]);

    // Keep other open tabs in sync.
    useEffect(() => {
        const onStorage = (event: StorageEvent) => {
            if (event.key === STORAGE_KEY && isThemeMode(event.newValue)) setMode(event.newValue);
        };
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
    }, []);

    const cycleMode = useCallback(() => {
        setMode(current => THEME_MODE_CYCLE[(THEME_MODE_CYCLE.indexOf(current) + 1) % THEME_MODE_CYCLE.length]);
    }, []);

    const value = useMemo(
        () => ({ mode, resolvedMode, setMode, cycleMode }),
        [mode, resolvedMode, cycleMode],
    );

    return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>;
};

export const useThemeMode = (): ThemeModeContextValue => {
    const context = useContext(ThemeModeContext);
    if (!context) throw new Error('useThemeMode must be used within a ThemeModeProvider');
    return context;
};
