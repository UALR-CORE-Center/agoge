import {Box, useTheme} from "@mui/material";
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import { styled } from '@mui/material/styles';
import * as React from 'react';

interface StyledTabsProps {
    label: string;
    children?: React.ReactNode;
    value: number;
    onChange: (event: React.SyntheticEvent, newValue: number) => void;
}

export const StyledTabs = styled((props: StyledTabsProps) => (
    <Tabs
        {...props}
        TabIndicatorProps={{ children: <span className="MuiTabs-indicatorSpan" /> }}
        orientation={"horizontal"}
        variant={"scrollable"}
        scrollButtons
        allowScrollButtonsMobile
        aria-label={props.label}
    />
))(({ theme }) => ({
    backgroundColor: 'transparent',
    '& .MuiTab-root': {
        borderRadius: 2,
        lineHeight: 0,
        minHeight: 'unset',
        padding: '8px',
        color: theme.palette.text.secondary,
    },
    '& .MuiTab-root.Mui-selected': {
        backgroundColor: theme.palette.primary.main,
        borderBottom: `2px solid ${theme.palette.getContrastText(theme.palette.primary.main)}`,
        color: theme.palette.getContrastText(theme.palette.primary.main),
    },
    '& .MuiTabs-indicator': {
        display: 'flex',
        justifyContent: 'center',
        backgroundColor: 'transparent',
    },
    '& .MuiTabs-indicatorSpan': {
        maxWidth: 100,
        width: '100%',
        backgroundColor: 'transparent',
    },
}));

interface StyledTabProps {
    label: string;
}

export const StyledTab = styled((props: StyledTabProps) => (
    <Tab disableRipple {...props} />
))(({ theme }) => ({
    textTransform: 'none',
    fontWeight: theme.typography.fontWeightRegular,
    fontSize: theme.typography.pxToRem(14),
    marginRight: theme.spacing(1),
    color: theme.palette.text.disabled,
    '&.Mui-selected': {
        color: theme.palette.text.primary,
    },
    '&.Mui-focusVisible': {
        backgroundColor: 'rgba(100, 95, 228, 0.32)',
    },
}));

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

export const StyledTabPanel = (props: TabPanelProps) => {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';
    const { children, value, index, ...other } = props;

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`tabpanel-${index}`}
            aria-labelledby={`tab-${index}`}
            {...other}
            style={{
                background: isDarkMode ? "#232323" : theme.palette.background.paper,
                borderRadius: 3,
            }}
        >
            {value === index && (
                <Box sx={{ p: 3 }}>
                    {children}
                </Box>
            )}
        </div>
    );
}