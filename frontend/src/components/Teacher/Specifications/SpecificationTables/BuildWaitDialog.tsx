import CoffeeIcon from '@mui/icons-material/Coffee';
import { Dialog, DialogTitle, DialogContent, Typography, Box } from '@mui/material';
import { styled } from '@mui/system';
import React from 'react';
import {AppUiObjectNames} from "../../../../types/AppObjectNames";

interface BuildWaitDialogModalProps {
    open: boolean;
    onClose: () => void;
}

const FloatingIcon = styled(CoffeeIcon)({
    position: 'relative',
    animation: 'cup-bounce 2s ease infinite',
    '@keyframes cup-bounce': {
        '0%, 20%, 50%, 80%, 100%': {
            transform: 'translateY(0)',
            color: 'var(--python-blue)',
            transition: 'var(--mint) 1000ms linear',
        },
        '40%': {
            transform: 'translateY(-15px)',
        },
        '60%': {
            transform: 'translateY(-8px)',
            color: 'var(--mint)',
            transition: 'var(--python-blue) 1000ms linear',
        },
    },
});

const BuildWaitDialog: React.FC<BuildWaitDialogModalProps> = ({ open, onClose }) => {
    return (
        <Dialog
            open={open}
            onClose={onClose}
            aria-labelledby="waiting-message-dialog-title"
            fullWidth
        >
            <DialogTitle id="waiting-message-dialog-title">
                <Box display="flex" justifyContent="center" alignItems="center">
                    <Typography variant="h5" align="center">
                        Please wait while your {AppUiObjectNames.UNIT.toLowerCase()} is created...
                    </Typography>
                    <FloatingIcon className="pl-2" />
                </Box>
            </DialogTitle>
            <DialogContent>
                <Box textAlign="center">
                    <Typography>
                        This page will automatically redirect when the process is complete.
                    </Typography>
                    <Typography>
                        Go grab some coffee (or tea, if you prefer).
                    </Typography>
                </Box>
            </DialogContent>
        </Dialog>
    );
};

export default BuildWaitDialog;
