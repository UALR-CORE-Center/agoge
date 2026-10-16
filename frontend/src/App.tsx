import { CssBaseline, ThemeProvider } from '@mui/material';
import ModalProvider from "mui-modal-provider";
import React from 'react';
import { ThemeModeProvider, useThemeMode } from "./context/ThemeModeContext";
import AppRouter from "./router/AppRouter";
import { darkTheme, lightTheme } from './styles/theme';

const ThemedApp: React.FC = () => {
    const { resolvedMode } = useThemeMode();

    return (
        <ThemeProvider theme={resolvedMode === 'dark' ? darkTheme : lightTheme}>
            {/* enableColorScheme sets the CSS color-scheme so native scrollbars/inputs match. */}
            <CssBaseline enableColorScheme />
                <ModalProvider>
                    <AppRouter />
                </ModalProvider>
        </ThemeProvider>
    );
};

const App: React.FC = () => (
    <ThemeModeProvider>
        <ThemedApp />
    </ThemeModeProvider>
);

export default App;
