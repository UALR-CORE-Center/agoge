import { createTheme, useTheme } from "@mui/material/styles";
import { PaletteMode } from "@mui/material";

export const getDesignTokens = (mode: PaletteMode) => ({
    typography: {
        fontFamily: [
            'Roboto',
            'Montserrat',
            'sans-serif',
        ].join(','),
    },
    palette: {
        mode,
        ...(mode === 'light')
            ? {
                primary: {
                    main: '#1c2538',
                    contrastText: '#fff'
                },
                secondary: {
                    main: '#f50057',
                },
                background: {
                    default: '#ffffff',
                    paper: '#ffffff',
                },
                text: {
                    primary: '#000000',
                    secondary: '#ffffff',
                },
            }
            : {
                primary: {
                    main: '#1c2538',
                    contrastText: '#fff'
                },
                background: {
                    default: '#121212',
                    paper: '#1c2538',
                },
                text: {
                    primary: '#ffffff',
                    secondary: '#b0bec5',
                },
            }
    }
});

export const darkTheme = createTheme({
    palette: {
        mode: 'dark',
        text: {
            primary: '#ffffff',
            secondary: '#b0bec5',
        },
    },
    components: {
        MuiAppBar: {
            styleOverrides: {
                colorPrimary: {
                    backgroundColor: "#1c2538",
                },
                colorSecondary: {
                    backgroundColor: "#1c2538",
                    color: "#ffffff",
                }
            }
        },
        MuiTabs: {
            styleOverrides: {
                root:{
                    '& .MuiTabs-indicator': {
                        backgroundColor: "cornflowerblue",
                    }
                }
            }
        },
        MuiTab: {
            styleOverrides: {
                root: {
                    "&.Mui-selected": {
                        color: "white",
                        borderRadius: "2px",
                    }
                }
            }
        },
        MuiButton: {
            styleOverrides: {
                colorPrimary: {
                    backgroundColor: "cornflowerblue",
                },
            }
        }
    }
});

export const lightTheme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#1c2538',
        },
        secondary: {
            main: '#f50057',
        },
        background: {
            default: '#f5f5f5',
        },
        text: {
            primary: '#000000',
        },
    },
    components: {
        MuiTabs: {
            styleOverrides: {
                root:{
                    '& .MuiTabs-indicator': {
                        backgroundColor: "cornflowerblue",
                    }
                }
            }
        }
    }
});
