import {LoadingButton} from '@mui/lab';
import {Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack, Typography} from '@mui/material';
import React, {useEffect, useState} from 'react';

interface Props {
    open: boolean;
    imageName: string;
    action: 'edit' | 'checkOut' | 'checkIn' | 'save';
    onClose: () => void;
    onConfirm: () => void | Promise<void>;
    loading?: boolean;
}

const actionLabels = {
    edit: 'Edit shared image',
    checkOut: 'Check out shared image',
    checkIn: 'Save shared image',
    save: 'Save settings',
};

export const SharedImageWarningDialog: React.FC<Props> = ({open, imageName, action, onClose, onConfirm, loading = false}) => {
    const [acknowledged, setAcknowledged] = useState(false);
    useEffect(() => setAcknowledged(false), [open, imageName, action]);

    return (
        <Dialog open={open} onClose={loading ? undefined : onClose} maxWidth="sm" fullWidth aria-labelledby="shared-image-warning-title">
            <DialogTitle id="shared-image-warning-title">{actionLabels[action]}?</DialogTitle>
            <DialogContent>
                <Stack spacing={2}>
                    <Alert severity="warning">This image is shared across multiple sites.</Alert>
                    <Typography>
                        Checking in server changes to <strong>{imageName}</strong> updates the shared image used by other sites and applications.
                        Labs that use this image may receive those changes when their servers are built or rebuilt.
                    </Typography>
                    {(action === 'edit' || action === 'save') && <Typography variant="body2">
                        Template settings such as the description, machine type, and connection details apply to this site.
                    </Typography>}
                    <Typography>To customize it only for this site, cancel and choose to copy the image.</Typography>
                    <FormControlLabel
                        control={<Checkbox checked={acknowledged} disabled={loading} onChange={event => setAcknowledged(event.target.checked)} />}
                        label="I understand that my changes can affect multiple sites."
                    />
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={loading}>Cancel</Button>
                <LoadingButton color="warning" variant="contained" disabled={!acknowledged} loading={loading} onClick={onConfirm}>
                    {actionLabels[action]}
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};
