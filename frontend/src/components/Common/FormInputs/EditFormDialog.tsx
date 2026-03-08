import {CancelRounded} from "@mui/icons-material";
import SaveIcon from "@mui/icons-material/Save";
import {
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
} from '@mui/material';
import {LoadingButton} from "@mui/lab";
import React from 'react';
import Button from "@mui/material/Button";


interface EditDialogProps {
    title: string;
    open: boolean;
    onClose: () => void;
    onSave: () => void;
    loading: boolean;
    formComponent: React.ComponentType<any>;
    formProps: any;
}

const EditFormDialog: React.FC<EditDialogProps> = (
    {
        title,
        open,
        onClose,
        onSave,
        formComponent: FormComponent,
        formProps,
        loading
    }
) => {

    return (
        <Dialog
            open={open}
            onClose={onClose}
            disableEnforceFocus
        >
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <FormComponent {...formProps} />
            </DialogContent>
            <DialogActions>
                <Button
                    variant="contained"
                    color="error"
                    onClick={onClose}
                    endIcon={<CancelRounded />}
                >
                    Cancel
                </Button>
                <LoadingButton
                    variant="contained"
                    color="success"
                    onClick={onSave}
                    loading={loading}
                    loadingPosition="end"
                    endIcon={<SaveIcon />}
                >
                    Save
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};

export default EditFormDialog;
