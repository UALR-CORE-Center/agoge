import {Clear} from "@mui/icons-material";
import {Snackbar, useTheme} from "@mui/material";
import Alert from '@mui/material/Alert'
import IconButton from "@mui/material/IconButton";
import {lighten} from "@mui/system";
import React from "react";
import Portal from "@mui/material/Portal";

interface SnackbarProps {
    message: string | React.ReactNode,
    open: boolean,
    onClose?: Function,
    disableAutoClose?: boolean,
    autoHideDuration?: number,
    vertical?: 'top' | 'bottom';
    horizontal?: 'left' | 'center' | 'right';
    severity?: 'info' | 'warning' | 'error' | 'success';
}

export default function SimpleSnackbar(props: SnackbarProps) {
    const theme = useTheme();

    const container =
        typeof document !== "undefined"
            ? (document.querySelector('[role="dialog"]') as HTMLElement | null)
            : null;

    const handleClose = (event: React.SyntheticEvent | Event, reason?: string) => {
        if (reason === 'clickaway') return;
        if (props.onClose) props.onClose();
    };

    const action = (
        <React.Fragment>
            <IconButton color="error" size="small" onClick={handleClose}>
                <Clear/>
            </IconButton>
        </React.Fragment>
    );

    const autoHide = () => {
        if (props.disableAutoClose) return null;
        return props.autoHideDuration ? props.autoHideDuration : 3000;
    };

    return (
        <Portal container={container ?? undefined}>
            <Snackbar
                open={props.open}
                anchorOrigin={{
                    vertical: props.vertical ? props.vertical : 'bottom',
                    horizontal: props.horizontal ? props.horizontal : 'center'
                }}
                autoHideDuration={autoHide()}
                onClose={handleClose}
                slotProps={{
                    content: {
                        style: {
                            fontWeight: 600,
                            letterSpacing: '.025rem',
                            color: theme.palette.text.primary,
                        }
                    }
                }}
                action={action}
            >
                <Alert
                    role="alert"
                    aria-live="assertive"
                    aria-atomic="true"
                    sx={{
                        width: '100%',
                        background: lighten(theme.palette.background.paper, .15),
                        borderLeft: `3px solid ${theme.palette.info.main}`,
                        display: 'flex',
                        alignItems: 'center'
                    }}
                    severity={props.severity ? props.severity : 'info'}
                >
                    {props.message}
                </Alert>
            </Snackbar>
        </Portal>
    );
}