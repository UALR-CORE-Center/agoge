import { CssBaseline, ThemeProvider } from '@mui/material';
import ModalProvider from "mui-modal-provider";
import React, {useState, useEffect, ChangeEvent} from 'react';
import {useLocalStorage} from "./hooks/useLocalStorage";
import AppRouter from "./router/AppRouter";
import { darkTheme, lightTheme } from './styles/theme';

const App: React.FC = () => {
    const {setItem, getItem} = useLocalStorage();
    const [isDarkMode, setIsDarkMode] = useState(() => {
        const savedTheme = getItem('theme');
        return savedTheme ? JSON.parse(savedTheme) : true;
    });

    useEffect(() => {
        setItem('theme', JSON.stringify(isDarkMode));
    }, [isDarkMode]);

    const toggleTheme = (event: ChangeEvent<HTMLInputElement>, checked: boolean) => {
        setIsDarkMode(checked);
    };

    return (
        <ThemeProvider theme={isDarkMode ? darkTheme : lightTheme}>
            <CssBaseline />
                <ModalProvider>
                    <AppRouter toggleTheme={toggleTheme} isDarkMode={isDarkMode} />
                </ModalProvider>
        </ThemeProvider>
    );
};

export default App;
