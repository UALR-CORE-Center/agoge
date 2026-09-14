import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {LoadingButton} from '@mui/lab';
import {Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Stack, TextField, Typography} from '@mui/material';
import React, {useEffect, useState} from 'react';
import {AgogeImage} from '../../../services/Server/image.model';
import {imageService} from '../../../services/Server/image.service';
import {localImageNameError, suggestLocalImageName} from '../../../utilities/sharedImage';

interface Props {
    image: AgogeImage | null;
    existingNames?: string[];
    action?: 'edit' | 'checkOut';
    onClose: () => void;
    onCopied: (image: AgogeImage) => void | Promise<void>;
    onEditShared?: (image: AgogeImage) => void;
}

export const SharedImageCopyDialog: React.FC<Props> = ({image, existingNames = [], action = 'edit', onClose, onCopied, onEditShared}) => {
    const [name, setName] = useState('');
    const [copying, setCopying] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (image) {
            setName(suggestLocalImageName(image.name, existingNames));
            setError('');
        }
    }, [image?.name]);

    const nameError = image ? localImageNameError(name, image.name, existingNames) : '';
    const handleCopy = async () => {
        if (!image || nameError || copying) return;
        setCopying(true);
        setError('');
        try {
            const localImage = await imageService.copy(image.name, name);
            // Never open the editor or check out a source while a copy is incomplete.
            if (!localImage.name || localImage.name !== name || localImage.is_shared !== false || localImage.image_exists !== true) {
                throw new Error('The local image is not ready. Refresh the image list before trying again.');
            }
            await onCopied(localImage);
        } catch (err: any) {
            setError(err.message || 'Could not copy the shared image. Please try again.');
        } finally {
            setCopying(false);
        }
    };

    return (
        <Dialog open={!!image} onClose={copying ? undefined : onClose} maxWidth="sm" fullWidth aria-labelledby="copy-shared-image-title">
            <DialogTitle id="copy-shared-image-title">{image?.name}: shared image</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{pt: 1}}>
                    <Alert severity="info">This server image is used by multiple sites. Only administrators can edit the shared image.</Alert>
                    <Typography>Create a copy for this site under a new name. Your changes will affect only this site's copy.</Typography>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Image name for this site"
                        value={name}
                        onChange={(event) => {setName(event.target.value); setError('');}}
                        disabled={copying}
                        error={!!nameError}
                        helperText={nameError || 'Use this name when selecting the customized image for a lab.'}
                        inputProps={{maxLength: 54}}
                    />
                    {copying && <Alert severity="info">Copying the image for this site. This may take a few minutes.</Alert>}
                    {error && <Alert severity="error">{error}</Alert>}
                    {image?.can_edit_shared && onEditShared && <>
                        <Divider />
                        <Typography variant="subtitle2">Administrator option</Typography>
                        <Typography variant="body2">Editing the shared image can affect labs across every site that uses it.</Typography>
                        <Button color="warning" variant="outlined" disabled={copying} onClick={() => onEditShared(image)}>
                            {action === 'checkOut' ? 'Check out shared image' : 'Edit shared image'}
                        </Button>
                    </>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={copying}>Cancel</Button>
                <LoadingButton onClick={handleCopy} loading={copying} disabled={!!nameError} startIcon={<ContentCopyIcon />} loadingPosition="start" variant="contained">
                    {action === 'checkOut' ? 'Copy for this site and check out' : 'Copy for this site and edit'}
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};
