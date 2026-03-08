import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import {
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Button,
    Typography,
    IconButton,
    Paper
} from '@mui/material';
import React from 'react';
import {useClipboard} from "../../../../hooks/useClipboard";

interface Props {
    title: string;
    open: boolean;
    onClose: () => void;
    textContent: string;
}

const ValidationDialog: React.FC<Props> = (
    {
        title,
        open,
        onClose,
        textContent,
    }
) => {
    const {copy} = useClipboard();

    return (
        <Dialog open={open} onClose={onClose} disableEnforceFocus>
            <DialogTitle color={"error"}>
                {title}
                <IconButton onClick={() => copy(textContent)} sx={{ ml: 1 }}>
                    <ContentCopyIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent>
                <Paper
                    elevation={1}
                    sx={{p: 1}}
                >
                    <Typography>{textContent}</Typography>
                </Paper>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} color="info">Close</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ValidationDialog;
