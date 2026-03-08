import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Typography
} from "@mui/material";
import React from "react";


interface ConfirmCancelProps {
    open: boolean;
    onClose: () => void;
    description: string;
    onCancel: () => void;
    title?: string;
}

export const ConfirmCancelDialog: React.FC<ConfirmCancelProps> = (props) => {
    const title = () => {
        if (props.title) {
            return `Confirm ${props.title} Cancel`;
        } else {
            return "Confirm Cancel";
        }
    }

    const handleOnClose = () => {
        if (props.onClose) {
            props.onClose();
        }
    }

    const handleConfirmCancel = () => props.onCancel();

    return (
        <>
            <Dialog
                open={props.open}
                onClose={handleOnClose}
            >
                <DialogTitle>{title()}</DialogTitle>
                <DialogContent>
                    <Typography id={"cancel-actions-description"}>
                        {props.description}
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={handleOnClose}
                    >
                        Go Back
                    </Button>
                    <Button onClick={handleConfirmCancel} color={"error"}>
                        Confirm
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    )
}