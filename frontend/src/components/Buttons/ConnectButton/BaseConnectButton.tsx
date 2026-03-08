import {
    Box,
    Button,
    Modal,
    Paper,
    Typography,
} from '@mui/material';
import React, { useState } from 'react';


export interface ConnectButtonProps {
    item: any;
    addGuacamole?: boolean;
    buildId?: string;
    serverIdx?: string;
}

interface BaseConnectButtonProps extends ConnectButtonProps{
    isDisabled: () => boolean;
    renderDetails: (item: any) => React.ReactNode;
}


export const BaseConnectButton: React.FC<BaseConnectButtonProps> = ({ item, isDisabled, renderDetails }) => {
    const [open, setOpen] = useState(false);

    const handleOpen = () => setOpen(true);
    const handleClose = () => setOpen(false);

    return (
        <>
            <Button
                variant="contained"
                color="primary"
                onClick={handleOpen}
                disabled={isDisabled()}
            >
                Connect
            </Button>
            <Modal
                open={open}
                onClose={(event, reason) => {
                    if (
                        reason === "escapeKeyDown" &&
                        document.body.hasAttribute("data-any-tooltip-open")
                    ) {
                        return;
                    }
                    handleClose();
                }}
                aria-labelledby="connect-modal-title"
                aria-describedby="connect-modal-description"
            >
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100vh'
                    }}
                >
                    <Paper sx={{ padding: 4, minWidth: 300 }}>
                        <Typography id="connect-modal-title" variant="h4" component="h2">
                            Connect to {item.name}
                        </Typography>
                        {renderDetails(item)}
                        <Box sx={{ mt: 4, textAlign: 'right' }}>
                            <Button variant="contained" color="primary" onClick={handleClose}>
                                Close
                            </Button>
                        </Box>
                    </Paper>
                </Box>
            </Modal>
        </>
    );
};
