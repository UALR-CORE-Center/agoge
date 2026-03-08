import { createTheme, darken } from "@mui/material/styles";
import "@mui/lab/themeAugmentation";

declare module "@mui/material/styles" {
    interface Palette {
        ready: Palette["primary"];
        neutral: Palette["primary"];
        infoDecorative: Palette["primary"];
    }
    interface PaletteOptions {
        ready?: PaletteOptions["primary"];
        neutral?: PaletteOptions["primary"];
        infoDecorative?: PaletteOptions["primary"];
    }
}

declare module "@mui/material/Chip" {
    interface ChipPropsColorOverrides {
        ready: true;
        neutral: true;
        infoDecorative: true;
    }
}

// Define the colors
const primaryMain = '#00518c';
const primaryLight = '#2B7ABF';
const primaryDark = '#01477b';
const secondaryMain = '#f50057';
const secondaryDark = '#E90152';
const infoDark = '#01579b';
const containedErrorDark = '#D22D2D';
const containedSuccessDark = '#2e7d32';


export const darkTheme = createTheme({
    palette: {
        mode: "dark",
        contrastThreshold: 4.5,
        primary: {
            main: primaryMain,
            light: primaryLight,
            dark: primaryDark,
            contrastText: "#fff",
        },
        secondary: {
            main: secondaryMain,
            dark: secondaryDark,
            contrastText: "#fff",
        },
        ready: { main: primaryLight, contrastText: "#fff" },
        neutral: { main: "#B6BEC9", contrastText: "#0F141A" },
        infoDecorative: { main: "#424242", contrastText: "#fff" },

        text: {
            primary: "#ffffff",
            secondary: "#b0bec5",
        },
        success: { main: containedSuccessDark, contrastText: "#fff" },
        error: { main: containedErrorDark, contrastText: "#fff" },
        warning: { main: "#CA710C" },
    },

    components: {
        MuiCssBaseline: {
            styleOverrides: {
                '*:focus-visible, .Mui-focusVisible': {
                    outline: '2px solid #82B6E3 !important',
                    outlineOffset: '2px',
                    borderRadius: '4px',
                },
                'main:focus-visible, [role="main"]:focus-visible': {
                    outline: 'none !important',
                },
            },
        },
        MuiButtonBase: {
            styleOverrides: {
                root: {
                    '&:focus-visible, &.Mui-focusVisible': {
                        outline: '2px solid #82B6E3 !important',
                        outlineOffset: '2px',
                        borderRadius: '4px',
                    },
                },
            },
        },
        MuiDialog: {
            styleOverrides: {
                paper: ({ theme }) => ({
                    backgroundColor:
                        theme.palette.mode === "dark"
                            ? "#242424"
                            : theme.palette.background.paper,
                    backgroundImage: "none",
                }),
            },
        },

        MuiButton: {
            defaultProps: { color: "inherit" },
            variants: [
                {
                    props: { variant: "contained", color: "primary" },
                    style: ({ theme }) => {
                        const bg = theme.palette.primary.light;
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            "&:hover": { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
                {
                    props: { variant: "contained", color: "secondary" },
                    style: ({ theme }) => {
                        const bg = theme.palette.secondary.main;
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            "&:hover": { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
                {
                    props: { variant: "contained", color: "success" },
                    style: ({ theme }) => {
                        const bg = containedSuccessDark;
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            "&:hover": { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
                {
                    props: { variant: "contained", color: "error" },
                    style: ({ theme }) => {
                        const bg = containedErrorDark;
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            "&:hover": { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
            ],
        },

        MuiChip: {
            styleOverrides: {
                root: {
                    fontSize: "0.75rem",
                    minWidth: 75,
                    height: 24,
                },
            },
            variants: [
                {
                    props: { color: "ready", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.ready.main,
                        color: theme.palette.ready.contrastText,
                    }),
                },
                {
                    props: { color: "neutral", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.neutral.main,
                        color: theme.palette.neutral.contrastText,
                    }),
                },
                {
                    props: { color: "success", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.success.main,
                        color: theme.palette.success.contrastText,
                    }),
                },
                {
                    props: { color: "warning", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.warning.main,
                        color: theme.palette.getContrastText(theme.palette.warning.main),
                    }),
                },
                {
                    props: { color: "error", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.error.main,
                        color: theme.palette.error.contrastText,
                    }),
                },
                {
                    props: { color: "infoDecorative", variant: "filled" },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.infoDecorative.main,
                        color: theme.palette.infoDecorative.contrastText,
                    }),
                },
            ],
        },

        MuiCheckbox: { defaultProps: { color: "info" } },

        MuiAppBar: {
            styleOverrides: {
                colorPrimary: { backgroundColor: primaryMain },
                colorSecondary: { backgroundColor: primaryMain, color: "#ffffff" },
            },
        },

        MuiTabs: {
            styleOverrides: {
                root: { "& .MuiTabs-indicator": { backgroundColor: primaryLight } },
            },
        },

        MuiTab: {
            styleOverrides: {
                root: { "&.Mui-selected": { color: "white", borderRadius: "2px" } },
            },
        },

        MuiLink: { styleOverrides: { root: { color: "rgb(5, 119, 203)" } } },

        MuiTextField: {
            styleOverrides: {
                root: {
                    "input:-webkit-autofill": {
                        WebkitBoxShadow:
                            "0 0 0px 1000px rgb(51 50 50 / 98%) inset",
                        WebkitTextFillColor: "#ffffff",
                    },
                },
            },
        },

        MuiOutlinedInput: {
            styleOverrides: {
                root: {
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                        borderColor: "#90caf9",
                    },
                },
            },
        },

        MuiInputLabel: {
            styleOverrides: {
                root: { "&.Mui-focused": { color: "#90caf9" } },
            },
        },

        MuiStepIcon: {
            styleOverrides: {
                root: ({ theme }) => ({
                    color: theme.palette.grey[400],
                    "&.Mui-active": { color: theme.palette.primary.light },
                }),
                text: ({ theme }) => ({
                    fill: "#1E1E1E",
                    "&.Mui-active": {
                        fill: theme.palette.getContrastText(theme.palette.primary.light),
                    },
                }),
            },
        },
    },
});

export const lightTheme = createTheme({
    palette: {
        mode: "light",
        contrastThreshold: 4.5,
        primary: {
            main: primaryMain,
            light: primaryLight,
            dark: primaryDark,
        },
        secondary: {
            main: secondaryMain,
            dark: secondaryDark,
        },
        ready: { main: primaryLight, contrastText: "#fff" },
        neutral: { main: "#6B7280", contrastText: "#FFFFFF" },
        info: { main: infoDark },
        infoDecorative: { main: "#DCDADA", contrastText: "#000" },
        background: { default: "#dad6d6", paper: "#f0eded" },
        success: { main: "#357939", contrastText: "#fff" },
        error: { main: "#CA2B2B", dark: "#D3302F", contrastText: "#fff" },
        warning: { main: "#CA710C" },
        text: { primary: "#000000" },
    },

    components: {
        MuiButton: {
            defaultProps: { color: 'inherit' },
            variants: [
                {
                    // Save
                    props: { variant: 'contained', color: 'success' },
                    style: ({ theme }) => {
                        const bg = '#2b6e2e';
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            '&:hover': { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
                {
                    // Cancel
                    props: { variant: 'contained', color: 'error' },
                    style: ({ theme }) => {
                        const bg = '#b02525';
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            '&:hover': { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
            ],
        },
        MuiCssBaseline: {
            styleOverrides: {
                '*:focus-visible, .Mui-focusVisible': {
                    outline: '2px solid #82B6E3 !important',
                    outlineOffset: '2px',
                    borderRadius: '4px',
                },
                'main:focus-visible, [role="main"]:focus-visible': {
                    outline: 'none !important',
                },
            },
        },
        MuiButtonBase: {
            styleOverrides: {
                root: {
                    '&:focus-visible, &.Mui-focusVisible': {
                        outline: '2px solid #82B6E3 !important',
                        outlineOffset: '2px',
                        borderRadius: '4px',
                    },
                },
            },
        },
        MuiChip: {
            styleOverrides: {
                root: { fontSize: '0.75rem', minWidth: 75, height: 24 },
            },
            variants: [
                {
                    props: { color: 'ready', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.ready.main,
                        color: theme.palette.ready.contrastText,
                    }),
                },
                {
                    props: { color: 'neutral', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.neutral.main,
                        color: theme.palette.neutral.contrastText,
                    }),
                },
                {
                    props: { color: 'success', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.success.main,
                        color: theme.palette.success.contrastText,
                    }),
                },
                {
                    props: { color: 'error', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.error.main,
                        color: theme.palette.error.contrastText,
                    }),
                },
                {
                    props: { color: 'warning', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.warning.main,
                        color: theme.palette.getContrastText(theme.palette.warning.main),
                    }),
                },
                {
                    props: { color: 'infoDecorative', variant: 'filled' },
                    style: ({ theme }) => ({
                        backgroundColor: theme.palette.infoDecorative.main,
                        color: theme.palette.infoDecorative.contrastText,
                    }),
                },
            ],
        },
        MuiLoadingButton: {
            variants: [
                {
                    props: { variant: 'contained', color: 'success' },
                    style: ({ theme }) => {
                        const bg = '#2b6e2e';
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            '&:hover': { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
                {
                    props: { variant: 'contained', color: 'error' },
                    style: ({ theme }) => {
                        const bg = '#b02525';
                        return {
                            backgroundColor: bg,
                            color: theme.palette.getContrastText(bg),
                            '&:hover': { backgroundColor: darken(bg, 0.12) },
                        };
                    },
                },
            ],
        },

        // Make dialogs a bit darker in light mode for extra separation
        MuiDialog: {
            styleOverrides: {
                paper: ({ theme }) => ({
                    backgroundColor:
                        theme.palette.mode === 'dark'
                            ? '#1a1a1a'
                            : theme.palette.background.default,
                    backgroundImage: 'none',
                }),
            },
        },

        MuiAppBar: {
            styleOverrides: {
                colorPrimary: { backgroundColor: primaryDark },
                colorSecondary: { backgroundColor: primaryDark, color: '#ffffff' },
            },
        },

        MuiTabs: {
            styleOverrides: {
                root: { '& .MuiTabs-indicator': { backgroundColor: primaryLight } },
            },
        },
        MuiStepIcon: {
            styleOverrides: {
                root: ({ theme }) => ({
                    color: theme.palette.grey[700],
                    '&.Mui-active': { color: theme.palette.primary.main },
                }),
            },
        },
        MuiTextField: {
            styleOverrides: {
                root: {
                    'input:-webkit-autofill': {
                        // fixed stray quotes
                        WebkitBoxShadow: '0 0 0px 1000px rgba(232, 240, 254, 1) inset',
                        WebkitTextFillColor: 'black',
                    },
                },
            },
        },
    },
});