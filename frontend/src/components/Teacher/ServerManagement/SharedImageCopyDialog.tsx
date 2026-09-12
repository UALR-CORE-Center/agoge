import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {LoadingButton} from '@mui/lab';
import {Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography} from '@mui/material';
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
}

export const SharedImageCopyDialog: React.FC<Props> = ({image, existingNames = [], action = 'edit', onClose, onCopied}) => {
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
            if (!localImage.name || localImage.name !== name || localImage.is_shared || localImage.image_exists === false) {
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
            <DialogTitle id="copy-shared-image-title">Create a local copy</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{pt: 1}}>
                    <Typography>
                        {image?.name} is a shared image{image?.source_project ? ` from ${image.source_project}` : ''}.
                        {' '}Create a copy in your project under a new name to edit it. The shared image will stay available and unchanged.
                    </Typography>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Local image name"
                        value={name}
                        onChange={(event) => {setName(event.target.value); setError('');}}
                        disabled={copying}
                        error={!!nameError}
                        helperText={nameError || 'Use this name when selecting the customized image for a lab.'}
                        inputProps={{maxLength: 54}}
                    />
                    {copying && <Alert severity="info">Copying the image into your project. This may take a few minutes.</Alert>}
                    {error && <Alert severity="error">{error}</Alert>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={copying}>Cancel</Button>
                <LoadingButton onClick={handleCopy} loading={copying} disabled={!!nameError} startIcon={<ContentCopyIcon />} loadingPosition="start" variant="contained">
                    {action === 'checkOut' ? 'Copy and check out' : 'Copy and edit'}
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};
