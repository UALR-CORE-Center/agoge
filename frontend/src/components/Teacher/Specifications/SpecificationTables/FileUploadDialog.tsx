import {Clear, CopyAll, ErrorOutline, X} from "@mui/icons-material";
import SaveIcon from "@mui/icons-material/Save";
import {LoadingButton} from "@mui/lab";
import {Box, Button, IconButton, Paper, Stack, Tooltip, Typography, useTheme} from "@mui/material";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import {lighten} from "@mui/system";
import React, {useEffect, useState} from "react";
import {useClipboard} from "../../../../hooks/useClipboard";
import {specificationService} from "../../../../services/Specification/specification.service";
import {
    FormFields,
    FormGroup,
    StyledFormFieldLabel,
} from "../NewEditor/utils/FormFields";

interface DefaultSelectedFile {
    value: any;
    error: string | null;
    dragging: boolean;
}

interface FilenameInputProps {
    value: string;
    error: null | string;
}

interface Props {
    open: boolean
    onClose?: () => void;
}

export default function FileUploadDialog(props: Props) {
    const {open, onClose} = props;
    const {copy} = useClipboard();
    const [submitting, setSubmitting] = useState(false);
    const [fileObject, setFileObject] = useState<File | null>(null);
    const [validationErrors, setValidationErrors] = useState<string>("");
    const [filenameInput, setFilenameInput] = useState<FilenameInputProps>({
        value: '',
        error: null
    });
    const [selectedFileInput, setSelectedFileInput] = useState<DefaultSelectedFile>({
        value: null,
        error: 'Required',
        dragging: false
    });
    let fileInput: HTMLInputElement | null = null;

    useEffect(() => {
        setSelectedFileInput({...selectedFileInput, error: validateFileInput(selectedFileInput.value)})
    }, [filenameInput]);

    useEffect(() => {}, [fileObject]);

    const handleSubmit = async () => {
        setSubmitting(true);

        const file = selectedFileInput.value;

        try {
            if (file) {
                const formData = new FormData();
                formData.append('file', file);
                await specificationService.upload(formData);
                if (onClose) onClose();
            }
        } catch (error) {
            setSubmitting(false);
            setSelectedFileInput((prevState) => (
                {...prevState, error: error.message}
            ));

        }
    }

    const handleClose = () => {
        setFileObject(null);
        setFilenameInput({value: "", error: null});
        setSelectedFileInput({
            value: null,
            error: 'Required',
            dragging: false
        });
        setValidationErrors("");
        setSubmitting(false);
        if (fileInput) {
            fileInput.value = "";
        }
        if (onClose) onClose();
    }

    const fileExtensionValidator = (fileName: string): string | null => {
        const regexExtension = /^[a-zA-Z0-9\-]{1,63}\.(yaml|yml|json)$/;
        if (!regexExtension.test(fileName)) {
            return "File name must end with a valid file extension.";
        }

        return null;
    };

    const validateFileInput = (value: File | null) => {
        if (value == null) return 'Required';

        if (value && !filenameInput.value) return fileExtensionValidator(value.name);

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

    const handleRemoveSelectedFile = () => {
        setFileObject(null);
        setFilenameInput({value: "", error: null});
        setSelectedFileInput({
            value: null,
            error: 'Required',
            dragging: false
        });
        setValidationErrors("");
        setSubmitting(false);

        if (fileInput) fileInput.value = "";
    }

    const theme = useTheme();

    return (
        <Dialog open={open} maxWidth={'sm'} fullWidth onClose={handleClose}>
            <DialogTitle>
                <Stack direction={'row'} gap={1}>
                    Upload Lab Specification
                    {selectedFileInput?.error && (
                        <ErrorOutline
                            fontSize={"medium"}
                            sx={{
                                marginTop: "5px"
                            }}
                            color={'error'}
                        />
                    )}
                </Stack>
            </DialogTitle>
            <DialogContent>
                <FormFields>
                    <FormGroup>
                        <Stack direction={'row'} gap={1}>
                            <StyledFormFieldLabel id={"upload-lab-field-label"}>Lab Specification</StyledFormFieldLabel>
                            {selectedFileInput.value && (
                                <>
                                    <StyledFormFieldLabel sx={{color: theme.palette.success.main}}>
                                        ({selectedFileInput.value.name})
                                    </StyledFormFieldLabel>
                                    <Tooltip title="Clear selected file">
                                        <IconButton
                                            color={"error"}
                                            size={"small"}
                                            sx={{p: 0}}
                                            onClick={handleRemoveSelectedFile}
                                            aria-label={"clear-selected-lab-file-btn"}
                                            aria-controls={"upload-lab-field-label"}
                                            aria-labelledby={"upload-lab-field-label"}
                                            aria-description={"clear selected file from form"}
                                        >
                                            <Clear fontSize={"small"} />
                                        </IconButton>
                                    </Tooltip>
                                </>
                            )}
                        </Stack>
                        <Stack gap={1}>
                            <Paper elevation={8}>
                                <Box component={Paper}
                                     onDragOver={(e: any) => handleDragOver(e)}
                                     onDragLeave={(e: any) => handleDragLeave(e)}
                                     elevation={1}
                                     onClick={() => fileInput?.click()}
                                     onDrop={(e: any) => handleDrop(e)}
                                     sx={{
                                         border: '2px dashed ' + (!selectedFileInput.error ? 'gray' : theme.palette.error.main),
                                         width: '200px%',
                                         height: '200px',
                                         cursor: "pointer",
                                         "&:hover": {
                                             background: (theme) =>
                                                 lighten(theme.palette.background.default, 0.15),
                                         },
                                         display: 'flex',
                                         alignItems: 'center',
                                         justifyContent: 'center',
                                         color: selectedFileInput.dragging ? 'green' : 'black'
                                     }}
                                     aria-description={"select a JSON file to upload into Agoge catalog"}
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
                                (
                                    <>
                                        {
                                            selectedFileInput.error !== 'Required' &&
                                            <Button
                                                onClick={() => copy(selectedFileInput.error)}
                                                startIcon={<CopyAll />}
                                                color={"secondary"}
                                                variant={"contained"}
                                                fullWidth={false}
                                            >
                                                Copy Error
                                            </Button>
                                        }
                                        <Typography sx={{ml: 1.5}} variant={'caption'} color={'text.secondary'}>
                                            {selectedFileInput.error}
                                        </Typography>
                                    </>
                                )
                            }
                        </Stack>
                    </FormGroup>
                </FormFields>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Cancel</Button>
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
