import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Typography,
    IconButton
} from "@mui/material";
import React from "react";
import {useClipboard} from "../../../hooks/useClipboard";

interface DialogProps{
    title: string,
    message: string,
    open: boolean,
    onClose?: () => void,
}

export default function ErrorDialog(props: DialogProps) {
    const {copy} = useClipboard();

    const handleClose = () => {
        if (props.onClose) {
            props.onClose();
        }
    };

    return (
        <Dialog
            open={props.open}
            onClose={handleClose}
            aria-labelledby="error-alert-dialog-title"
            aria-describedby="error-alert-dialog-description"
        >
            <DialogTitle id="error-alert-dialog-title">{props.title}</DialogTitle>

            <DialogContent>
                <Typography id="error-alert-dialog-description" color={"textPrimary"}>
                    {props.message}
                </Typography>
                <IconButton onClick={() => copy(props.message)} aria-label="copy" color="info">
                    <ContentCopyIcon />
                </IconButton>
            </DialogContent>

            <DialogActions>
                <Button onClick={handleClose} color="primary">
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
}
