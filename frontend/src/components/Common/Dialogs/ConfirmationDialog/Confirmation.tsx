import DeleteIcon from "@mui/icons-material/Delete";
import {LoadingButton} from "@mui/lab";
import {CircularProgress, TextField, useTheme} from '@mui/material';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import React, {useEffect, useState} from 'react';
import {capitalizeString} from "../../../../utilities/formatString";

interface Props {
    open: boolean;
    onClose: () => void;
    handleConfirm: () => void;
    expectedText: string;
    action?: "rebuild" | "delete" | "cancel"
    loading: boolean;
}

export default function ConfirmationDialog(props: Props) {
    const theme = useTheme();
    const [inputValue, setInputValue] = useState('');
    const action = props.action ? props.action : "delete";

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setInputValue(event.target.value);
    };

    const isConfirmEnabled = inputValue === props.expectedText;

    useEffect(() => {
        if (props.open) {
            setInputValue('');
        }
    }, [props.open]);

    return (
        <Dialog open={props.open} onClose={props.onClose}>
            <DialogTitle sx={{ color: theme.palette.text.primary }}>
                Confirm {capitalizeString(String(action))}
            </DialogTitle>
            <DialogContent>
                <DialogContentText sx={{ color: theme.palette.text.primary }}>
                    Are you sure you want to {action} the selected items? This action cannot be undone.
                </DialogContentText>
                <DialogContentText sx={{ color: theme.palette.text.primary }}>
                    Please type <strong>{props.expectedText}</strong> to confirm.
                </DialogContentText>
                <TextField
                    autoFocus
                    autoComplete="off"
                    margin="dense"
                    label="Confirmation"
                    type="text"
                    fullWidth
                    variant="standard"
                    value={inputValue}
                    onChange={handleInputChange}
                    slotProps={{
                        htmlInput: {
                            autoComplete: 'off'
                        }
                    }}
                    sx={{
                        '& .MuiInputLabel-root': {
                            color: theme.palette.text.primary,
                        },
                        '& .MuiInputBase-input': {
                            color: theme.palette.text.primary,
                        },
                        '& .MuiInput-underline:before': {
                            borderBottomColor: theme.palette.text.primary,
                        },
                    }}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={props.onClose} sx={{ color: theme.palette.text.primary }}>Cancel</Button>
                <LoadingButton
                    onClick={props.handleConfirm}
                    sx={{
                        color: isConfirmEnabled ? theme.palette.error.main : theme.palette.text.primary,
                        '&.Mui-disabled': {
                            color: theme.palette.text.disabled,
                        },
                    }}
                    disabled={!isConfirmEnabled}
                    loading={props.loading}
                    loadingPosition={"start"}
                    startIcon={props.loading ? <CircularProgress /> : <DeleteIcon /> }
                >
                    Delete
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
}
