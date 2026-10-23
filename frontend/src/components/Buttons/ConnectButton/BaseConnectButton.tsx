import {
    Box,
    Button,
    Modal,
    Paper,
    Typography,
} from '@mui/material';
import React, { useRef, useState } from 'react';


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
    // The centering Box covers the backdrop, so a click beside the Paper lands on it rather than the backdrop.
    // Press and release must both land there: a drag between the Paper and the Box (selecting a command, say)
    // fires click on the Box, their common ancestor, and is not a click out.
    const pressedOutside = useRef(false);
    const releasedOutside = useRef(false);

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
                    data-testid="connect-modal-outside"
                    onMouseDown={(event) => {
                        pressedOutside.current = event.target === event.currentTarget;
                    }}
                    onMouseUp={(event) => {
                        releasedOutside.current = event.target === event.currentTarget;
                    }}
                    onClick={(event) => {
                        if (pressedOutside.current && releasedOutside.current && event.target === event.currentTarget) {
                            handleClose();
                        }
                        pressedOutside.current = false;
                        releasedOutside.current = false;
                    }}
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100vh',
                        p: 2,
                        boxSizing: 'border-box',
                    }}
                >
                    <Paper
                        sx={{
                            padding: { xs: 2, sm: 4 },
                            minWidth: { xs: 0, sm: 300 },
                            width: { xs: '100%', sm: 'auto' },
                            // Long tunnel commands would stretch it across the screen; two thirds is wide
                            // enough for them to wrap legibly. Phones keep the full width.
                            maxWidth: { xs: '100%', md: '66.667%' },
                            maxHeight: '100%',
                            overflowY: 'auto',
                            boxSizing: 'border-box',
                        }}
                    >
                        <Typography id="connect-modal-title" variant="h4" component="h2" sx={{ overflowWrap: 'anywhere' }}>
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
