import {LoadingButton} from "@mui/lab";
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle
} from "@mui/material";
import React, {useId} from "react";

interface ActionConfirmDialogProps {
    open: boolean;
    title: string;
    message: React.ReactNode;
    confirmLabel: string;
    onConfirm: () => void;
    onClose: () => void;
    loading: boolean;
}

// Plain confirm/cancel for reversible actions. Irreversible ones use the
// type-to-confirm ConfirmationDialog instead.
export default function ActionConfirmDialog(props: ActionConfirmDialogProps) {
    const titleId = useId();
    const messageId = useId();

    // A request is in flight: closing now would hide its result, so the
    // backdrop, Escape and Cancel are all ignored until it settles.
    const handleClose = () => {
        if (!props.loading) {
            props.onClose();
        }
    };

    return (
        <Dialog
            open={props.open}
            onClose={handleClose}
            aria-labelledby={titleId}
            aria-describedby={messageId}
        >
            <DialogTitle id={titleId}>{props.title}</DialogTitle>
            <DialogContent>
                <DialogContentText id={messageId} component="div">
                    {props.message}
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={props.loading}>
                    Cancel
                </Button>
                <LoadingButton
                    onClick={props.onConfirm}
                    loading={props.loading}
                    variant="contained"
                >
                    {props.confirmLabel}
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
}
