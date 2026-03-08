import React, {useEffect, useState} from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import {useForm} from "../../../../../hooks/useForm";
import {createDefaultFormFieldMeta, FormType, IFormFieldMeta} from "../../../../../types/Form";
import {requiredValidator} from "../../../../../utilities/formValidators";
import {
    FormFields,
    FormGroup, FormGroupOutline,
    FormTextField,
    StyledFormFieldLabel,
    StyledFormGroupLabel
} from "../utils/FormFields";
import {Box, Button, IconButton, Paper, Stack, Typography, useTheme} from "@mui/material";
import {Clear, Feed} from "@mui/icons-material";
import {lighten} from "@mui/system";
import {NetworkFormKeys, SummaryFormKeys} from "../utils/EditorTypes";
import {LoadingButton} from "@mui/lab";
import SaveIcon from "@mui/icons-material/Save";
import {specificationEditService} from "../../../../../services/Specification/specificationEdit.service";

interface Props {
    onClose: (name: string | null) => void
}


const StartupScriptDialog: React.FC<Props> = ({onClose}) => {
    const [open, setOpen] = useState(true)
    const [submitting, setSubmitting] = useState(false)

    let fileInput: HTMLInputElement | null = null;

    const [filenameInput, setFilenameInput] = useState<{ value: string, error: null | string }>({
        value: '',
        error: null
    })

    const [selectedFileInput, setSelectedFileInput] = useState<{
        value: any;
        error: string | null;
        dragging: boolean;
    }>
    ({
        value: null,
        error: 'Required',
        dragging: false
    });

    useEffect(() => {
        setSelectedFileInput({...selectedFileInput, error: validateFileInput(selectedFileInput.value)})

    }, [filenameInput.value]);

    const handleSubmit = () => {
        setSubmitting(true);

        const file = selectedFileInput.value;
        const filename = filenameInput.value || file.name
        specificationEditService.uploadStartupScript(filename, file)
            .then((res) => {
                onClose(res);
                setOpen(false);
            })
            .catch(() => {
                alert("Something went wrong");
                setSubmitting(false)
            })
    }


    const gcloudFileExtensionValidator = (fileName: string): string | null => {
        // Regex to check if the filename contains only alphanumeric characters and hyphens
        const regexCharacters = /^[a-zA-Z0-9\-]+$/;
        // Regex to ensure the filename ends with a valid file extension
        const regexExtension = /^[a-zA-Z0-9\-]{1,63}\.[a-zA-Z0-9]+$/;

        if (fileName.length > 63) {
            return "File name must be 63 characters or less.";
        }

        const [namePart] = fileName.split('.');

        if (!regexCharacters.test(namePart)) {
            return "File name must contain only alphanumeric characters and hyphens.";
        }

        if (!regexExtension.test(fileName)) {
            return "File name must end with a valid file extension.";
        }

        return null;
    };


    const validateFileInput = (value: File | null) => {
        if (value == null) {
            return 'Required'
        }


        if (value && !filenameInput.value) {
            return gcloudFileExtensionValidator(value.name);
        }

        return null;
    }

    const validateFilenameInput = (value: string) => {
        if (value) {
            return gcloudFileExtensionValidator(value);
        }

        return null;
    }


    const handleDrop = (e: any) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        setSelectedFileInput({value: file, dragging: false, error: validateFileInput(file)})
    }

    const handleDragOver = (e: any) => {
        e.preventDefault();
        if (!selectedFileInput.dragging) {
            setSelectedFileInput({...selectedFileInput, dragging: true})
        }
    }

    const handleDragLeave = (e: any) => {
        e.preventDefault();
        setSelectedFileInput({...selectedFileInput, dragging: false})
    }

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files && files.length > 0) {
            setSelectedFileInput({...selectedFileInput, value: files[0], error: validateFileInput(files[0])})
        }
    };


    const theme = useTheme();
    return (
        <Dialog open={open} maxWidth={'sm'} fullWidth>
            <DialogTitle>Upload Startup Script</DialogTitle>
            <DialogContent>

                <FormFields>
                    <FormGroup>
                        <StyledFormFieldLabel>File Name</StyledFormFieldLabel>
                        <FormTextField
                            helpText={'File name can be within 63 characters, contain only alphanumeric characters and hyphens'}
                            placeholder={'File Name (Optional)'}
                            formKey={'some-key'}
                            fieldFn={(key) => filenameInput as IFormFieldMeta}
                            endAdornment={
                                !!filenameInput.value ?
                                    <IconButton size={'small'} onClick={() => setFilenameInput({
                                        ...selectedFileInput,
                                        value: ''
                                    })}>
                                        <Clear/>
                                    </IconButton> : undefined
                            }
                            onInputChange={(field, value) => {
                                setFilenameInput({value: value, error: validateFilenameInput(value)})
                            }}
                        />

                    </FormGroup>

                    <FormGroup>
                        <Stack direction={'row'} gap={1}>
                            <StyledFormFieldLabel>Startup Script</StyledFormFieldLabel>

                            {
                                selectedFileInput.value && (
                                    <StyledFormFieldLabel
                                        sx={{color: theme.palette.success.main}}>(Uploaded)</StyledFormFieldLabel>
                                )
                            }
                        </Stack>

                        <Stack gap={1}>
                            <Paper elevation={8}>


                                <Box component={Paper}
                                     onDragOver={(e: any) => handleDragOver(e)}
                                     onDragLeave={(e: any) => handleDragLeave(e)}
                                     elevation={1}
                                     onClick={() => fileInput?.click()}
                                     onDrop={(e: any) => handleDrop(e)}
                                     role="button"
                                     tabIndex={0}
                                     aria-label="Choose startup script file"
                                     onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
                                         if (e.key === 'Enter' || e.key === ' ') {
                                             e.preventDefault();
                                             fileInput?.click();
                                         }
                                     }}

                                     sx={{
                                         border: '2px dashed ' + (!(!!selectedFileInput.error) ? 'gray' : theme.palette.error.main),
                                         width: '200px%',
                                         height: '200px',
                                         cursor: 'pointer',
                                         '&:hover': {
                                             background: (theme) => lighten(theme.palette.background.default, 0.15),
                                         },
                                         display: 'flex',
                                         alignItems: 'center',
                                         justifyContent: 'center',
                                         color: selectedFileInput.dragging ? 'green' : 'black',
                                     }}
                                >
                                    {selectedFileInput.value?.name ?
                                        <Typography color={'text.secondary'} className={'overflow'}>
                                            {selectedFileInput.value.name}
                                        </Typography> :
                                        <Typography color={'text.secondary'}>
                                            Click or Drag a file here
                                        </Typography>}
                                    <input
                                        type="file"
                                        style={{display: 'none'}}
                                        ref={(input) => (fileInput = input)}
                                        onChange={(e) => handleFileChange(e)}
                                    />
                                </Box>


                            </Paper>
                            {
                                !!selectedFileInput?.error &&
                                <Typography sx={{ml: 1.5}} variant={'caption'} color={'text.secondary'}>
                                    {selectedFileInput.error}
                                </Typography>
                            }
                        </Stack>

                    </FormGroup>
                </FormFields>
            </DialogContent>

            <DialogActions>
                <Button onClick={() => {
                    onClose(null);
                    setOpen(false);
                }}>cancel</Button>
                <LoadingButton
                    size="small"
                    color="primary"
                    onClick={handleSubmit}
                    loading={submitting}
                    loadingPosition="end"
                    endIcon={<SaveIcon/>}
                    variant="contained"
                    disabled={selectedFileInput.error !== null || filenameInput.error !== null}>
                    Upload
                </LoadingButton>

            </DialogActions>
        </Dialog>
    )
}

export default StartupScriptDialog;