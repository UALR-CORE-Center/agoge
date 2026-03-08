import {CancelOutlined} from "@mui/icons-material";
import DeleteIcon from "@mui/icons-material/Delete";
import { LoadingButton } from "@mui/lab";
import { ListItem, ListItemText, TextField, useTheme } from '@mui/material';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import React, { useState, useEffect } from 'react';
import { FixedSizeList, ListChildComponentProps } from "react-window";

interface ConfirmationDialogProps {
    open: boolean;
    handleClose: () => void;
    handleConfirm: () => void;
    items: string[];
    confirmText: string;
    confirmType: "delete" | "disable";
    loading?: boolean;
}

const ConfirmationListDialog: React.FC<ConfirmationDialogProps> = (props) => {
    const [inputValue, setInputValue] = useState('');
    const theme = useTheme();

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setInputValue(event.target.value);
    };

    const isConfirmEnabled = inputValue.toLowerCase() === props.confirmText;
    const confirmType = props.confirmType === "disable" ? "Disable" : "Delete";

    const confirmWarning = () => {
        if (props.confirmType === 'disable') {
            return `Are you sure you want to disable the following ${props.items.length} items? ` +
                "This will prevent future use until enabled again!";
        } else if (props.confirmType === 'delete') {
            return `Are you sure you want to delete the following ${props.items.length} items? ` +
                "This action cannot be undone!";
        }
    }

    useEffect(() => {
        if (!props.open) {
            setInputValue('');
        }
    }, [props.open]);

    const renderListRow = (rowProps: ListChildComponentProps) => {
        const { index, style } = rowProps;

        return (
            <ListItem
                sx={{
                    paddingLeft: 2
                }}
                style={style}
                key={index}
                component="div"
                disablePadding
            >
                <ListItemText primary={`* ${props.items[index]},`} />
            </ListItem>
        );
    }

    const buttonIcon = () => {
        if (props.confirmType === "delete") {
            return <DeleteIcon />;
        } else {
            return <CancelOutlined />;
        }
    }

    return (
        <Dialog open={props.open} onClose={props.handleClose}>
            <DialogTitle
                sx={{
                    color: theme.palette.text.primary
                }}
            >
                Confirm {confirmType}
            </DialogTitle>
            <DialogContent>
                <DialogContentText
                    sx={{
                        color: theme.palette.text.primary,
                        mb: 1
                    }}
                >
                    {confirmWarning()}
                </DialogContentText>
                <FixedSizeList
                    height={200}
                    width={"100%"}
                    itemSize={46}
                    overscanCount={5}
                    itemCount={props.items.length}
                    style={{
                        padding: "2px",
                        marginBottom: 5,
                        backgroundColor: theme.palette.mode === 'dark' ?
                            theme.palette.grey["900"]
                            : theme.palette.grey["300"],
                        borderRadius: 4
                    }}
                >
                    {renderListRow}
                </FixedSizeList>
                <DialogContentText
                    sx={{
                        color: theme.palette.text.primary,
                        my: 2
                    }}
                >
                    Please type <strong>{props.confirmText}</strong> to confirm.
                </DialogContentText>
                <TextField
                    autoFocus
                    margin="dense"
                    label="Confirmation"
                    type="text"
                    fullWidth
                    variant="standard"
                    value={inputValue}
                    onChange={handleInputChange}
                    inputProps={{
                        autoComplete: 'off'
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
                <Button
                    onClick={props.handleClose}
                    sx={{ color: theme.palette.text.primary }}
                >
                    Cancel
                </Button>
                <LoadingButton
                    onClick={props.handleConfirm}
                    color={"secondary"}
                    sx={{
                        color: isConfirmEnabled ? theme.palette.error.main : theme.palette.text.primary,
                        '&.Mui-disabled': {
                            color: theme.palette.text.disabled,
                        },
                    }}
                    disabled={!isConfirmEnabled}
                    loading={props.loading}
                    startIcon={buttonIcon()}
                    loadingPosition={"start"}
                    variant={"outlined"}
                >
                    {confirmType}
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
}

export default ConfirmationListDialog