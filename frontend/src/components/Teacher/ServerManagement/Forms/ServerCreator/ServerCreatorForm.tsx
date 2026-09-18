import {KeyboardReturn, Memory} from "@mui/icons-material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import SaveIcon from "@mui/icons-material/Save";
import LoadingButton from "@mui/lab/LoadingButton";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Checkbox,
    Container,
    Divider,
    FormControl,
    FormControlLabel,
    FormGroup,
    Link,
    Paper,
    TextField,
} from "@mui/material";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import React, { useState, FormEvent } from "react";
import { Form } from "react-router-dom";
import { useNavigate } from 'react-router-dom';

import {URL_TEACHER_SERVERS} from "../../../../../router/urls";
import { imageService } from "../../../../../services/Server/image.service";
import InputTags from "../../../../Common/FormInputs/InputTags";
import NumberInputField from "../../../../Common/FormInputs/NumberInputField";
import TextAreaField from "../../../../Common/FormInputs/TextAreaField";
import SimpleSnackbar from "../../../../Common/SnackBar/SnackBar";
import ServerValidationDialog from "../ServerValidationDialog";
import {ImageSelectTable} from "./ImageTemplateSelector/ImageSelectTable";
import MachineTypeSelector from "./MachineTypeSelector";
import {validateServerName, validateDiskSize, validateSshKey} from "./ServerFormValidators";
import {absoluteUrl} from "../../../../../utilities/appContext";
import {serverImageArchitectureError} from "../../../../../utilities/imageArchitecture";



const ServerCreatorForm: React.FC = () => {
    const [selectedImageName, setSelectedImageName] = useState("");
    const [selectedImageFamily, setSelectedImageFamily] = useState("");
    const [os, setOs] = useState('');
    const [minDiskSize, setMinDiskSize] = useState(10);
    const [serverName, setServerName] = useState('');
    const [serverNameError, setServerNameError] = useState('');
    const [imageScope, setImageScope] = useState('');
    const [diskSize, setDiskSize] = useState(10);
    const [diskSizeError, setDiskSizeError] = useState('');
    const [selectImageError, setSelectImageError] = useState(true);
    const [labels, setLabels] = useState<string[]>([]);
    const [sshKey, setSshKey] = useState('');
    const [sshKeyError, setSshKeyError] = useState('');
    const [enableDisplay, setEnableDisplay] = useState(false);
    const [validationError, setValidationError] = useState("");
    const [openDialog, setOpenDialog] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState("");
    const [selectedImageRow, setSelectedImageRow] = useState<any>(null);
    const navigate = useNavigate();

    const handleImageSelect = (selectedRow: any) => {
        if (selectedRow){
            setSelectedImageRow(selectedRow);
            setSelectedImageFamily(selectedRow.family);
            setSelectImageError(false);
            setSelectedImageName(selectedRow.name);
            setOs(selectedRow.os);
            setMinDiskSize(selectedRow.disk_size);
            setDiskSize(selectedRow.disk_size);
            if (selectedRow.project == 'custom') {
                setImageScope('project');
            } else {
                setImageScope('global');
            }
        } else {
            setSelectedImageRow(null);
            setSelectedImageFamily('');
            setSelectedImageName('');
            setOs('');
            setMinDiskSize(0);
            setDiskSize(0);
            setSelectImageError(true);
            setImageScope('');
        }

    }

    // Handlers
    const handleServerNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setServerName(value);
        setServerNameError(validateServerName(value));
    };

    const handleDiskSizeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = Number(event.target.value);
        setDiskSize(value);
        setDiskSizeError(validateDiskSize(value, diskSize));
    };

    const handleLabelChange = (updatedLabels: string[]) => {
        setLabels(updatedLabels);
    }

    const handleSshKeyChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setSshKey(value);
        setSshKeyError(validateSshKey(value, os, selectedImageFamily));
    };

    const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setEnableDisplay(event.target.checked);
    };

    const handleSnackbarClose = () => setSnackbarOpen(false);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const architectureError = selectedImageRow && serverImageArchitectureError(selectedImageRow);
        if (architectureError) {
            setValidationError(architectureError);
            setOpenDialog(true);
            return;
        }

        const serverNameValidation = validateServerName(serverName);
        const diskSizeValidation = validateDiskSize(diskSize, diskSize);
        const sshKeyValidation = validateSshKey(sshKey, os, selectedImageFamily);

        if (serverNameValidation || diskSizeValidation || sshKeyValidation || !selectedImageRow) {
            setServerNameError(serverNameValidation);
            setDiskSizeError(diskSizeValidation);
            setSshKeyError(sshKeyValidation);
            setSelectImageError(true);
        } else {
            const formData = new FormData(event.currentTarget);

            // Process remaining fields before creating formObject
            formData.set('image_template', selectedImageRow.id);
            formData.set('image_scope', imageScope);
            formData.set('enable_display', enableDisplay.toString());
            formData.set('disk_size', diskSize.toString());
            formData.set('server_name', serverName);
            formData.set('os', os);

            if ((os === 'linux') || (selectedImageFamily.includes("-core"))) {
                formData.set('ssh_key', sshKey);
            } else {
                formData.delete('ssh_key');
            }

            const formObject = Object.fromEntries(formData.entries());

            setIsLoading(true)
            setSnackbarMessage("Server creation is processing...");
            setSnackbarOpen(true);

            try {
                const resp = await imageService.create(formObject);
                navigate(URL_TEACHER_SERVERS);
            } catch (error: any) {
                console.log(error.detail);
                setValidationError(error.message);
                setIsLoading(false)
                setSnackbarOpen(false);
                setOpenDialog(true);
            }
        }
    };

    return (
        <Container sx={{mt: 10}}>
            <Box
                style={{
                    border: "none",
                    padding: "15px"
                }}
            >
                <Button
                    href={absoluteUrl(URL_TEACHER_SERVERS)}
                    startIcon={<KeyboardReturn />}
                    variant={"outlined"}
                >
                    Back to Server Manager page
                </Button>
                <Typography
                    variant={"h4"}
                    component={"h1"}
                    textAlign={"left"}
                    fontFamily={"Roboto"}
                    gutterBottom={true}
                    marginTop={2}
                >
                    Edit Server
                </Typography>
                <Typography
                    variant={"subtitle1"}
                    gutterBottom={true}
                >
                    Edit your custom compute instance
                </Typography>
            </Box>


            <Paper
                elevation={1}
                square={false}
                style={{
                    margin: "0 10px",
                    padding: "15px",
                }}
            >
                <Form onSubmit={handleSubmit}>
                    <FormGroup>
                        <FormControl margin={"normal"} required={true}>
                            <TextField
                                autoComplete="off"
                                id="server-name"
                                name="server_name"
                                label="Server Name*"
                                aria-label={"Name to call virtual machine"}
                                type={"text"}
                                helperText={
                                    serverNameError ||
                                    "Name must start with a lowercase letter followed by up to 55 " +
                                    "lowercase letters, numbers, or hyphens, and cannot end with a hyphen"
                                }
                                placeholder="sec-onion-123"
                                slotProps={{
                                    htmlInput: {maxLength: 55}
                                }}
                                onChange={handleServerNameChange}
                                error={!!serverNameError}
                            />
                        </FormControl>
                    </FormGroup>


                    <Divider style={{ margin: "20px 0" }} />


                    <FormGroup
                        style={{
                            marginTop: 10,
                            padding: "10px"
                        }}
                    >
                        <Typography
                            variant={"h5"}
                            component={"h2"}
                            paddingBottom={2}
                        >
                            Machine Configuration
                        </Typography>
                        <FormControl margin={"normal"} fullWidth>
                            <Accordion
                                sx={{
                                    backgroundColor: "initial",
                                    mb: 2
                                }}
                            >
                                <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    aria-controls={"image-select-accordion"}
                                    id={"image-select-accordion-header"}
                                >
                                    <>
                                        <Memory sx={{mr: 1}}/>
                                        <Typography mr={1}>Server Image *</Typography>
                                        (<Typography color={selectedImageName ? "info" : "error"}>
                                            {selectedImageName ? selectedImageName : "No image selected"}
                                        </Typography>)
                                    </>

                                </AccordionSummary>
                                <AccordionDetails>
                                    <ImageSelectTable onSelect={handleImageSelect} hasError={selectImageError}/>
                                </AccordionDetails>
                            </Accordion>
                            <Typography
                                variant="caption"
                                color="textSecondary"
                                margin={"5px 10px"}
                            >
                                Existing Compute image to create machine instance with.
                                Includes custom images and standard, official images provided by Google.
                            </Typography>
                        </FormControl>


                        <FormControl margin={"normal"} fullWidth>
                            {/* TODO: Replace select field with SelectMachineTypeTable */}
                            <MachineTypeSelector />
                            <Typography
                                variant="caption"
                                color="textSecondary"
                                margin={"0 10px"}
                                sx={{ mt: 1 }}
                            >
                                To learn more about machine types, refer to official documentation here:
                                <Link
                                    marginLeft={1}
                                    href="https://cloud.google.com/compute/docs/general-purpose-machines#e2_machine_types_table"
                                    target="_blank"
                                    color={"inherit"}
                                >
                                    Google Cloud Docs: E2 Machine Types
                                </Link>.
                            </Typography>
                        </FormControl>


                        <FormControl margin={"normal"}>
                            <input type="hidden" name="os" value={os.toLowerCase()} />
                            <NumberInputField
                                id={"diskSize"}
                                name={"disk_size"}
                                label={"Disk Size (GB)"}
                                min={minDiskSize}
                                max={250}
                                helperText={
                                    diskSizeError ||
                                    "Minimum instance size differs based on OS. " +
                                    "For example, Windows servers require a minimum disk size of 50GB."
                                }
                                onBlur={handleDiskSizeChange}
                                value={diskSize || minDiskSize}
                                error={!!diskSizeError}
                            />
                        </FormControl>
                        <FormGroup>
                            <FormControlLabel
                                label="Enable display"
                                control={
                                    <Checkbox
                                        name={"enable_display"}
                                        checked={enableDisplay}
                                        onChange={handleCheckboxChange}
                                    />
                                }
                            />
                            <Typography
                                variant="caption"
                                color="textSecondary"
                                margin={"0 5px"}
                            >
                                If enabled, server will be added to the list of available connections
                                in proxy server.
                            </Typography>
                        </FormGroup>
                    </FormGroup>

                    <Divider style={{ margin: "20px 0" }} />

                    <FormGroup
                        style={{
                            marginTop: 10,
                            padding: "10px"
                        }}>
                        <Typography
                            variant={"h5"}
                            component={"h2"}
                            paddingBottom={2}
                        >
                            Management
                        </Typography>
                        <FormControl required={true}>
                            <TextAreaField
                                id={"description"}
                                name={"description"}
                                label={"Server description*"}
                                helperText={
                                    "General description up to 200 characters of machine purpose, " +
                                    "installed services, and/or configuration."
                                }
                                maxLength={200}
                                required={true}
                                maxRows={4}
                            />
                        </FormControl>
                        <FormControl>
                            <Typography paddingBottom={1}>Image Labels</Typography>
                            <InputTags
                                id="imageTags"
                                name="labels"
                                tagType={"labels"}
                                ariaLabel={"Image Labels input"}
                                helperText={
                                    "Comma delimited list of services and functionality provided on this server"
                                }
                                required={false}
                                initialTags={labels} // Pass initial labels
                                onTagChanges={handleLabelChange}
                            />
                        </FormControl>
                        <Typography paddingTop={2}>Authorization</Typography>
                        <FormControl margin={"normal"}>
                            <TextField
                                required
                                name={"username"}
                                type={"text"}
                                label={"Username"}
                                placeholder={"Custom user to be added for initial access. Defaults to pantheon."}
                                helperText={
                                    "Must start with an alphabetic character, " +
                                    "cannot contains spaces or special characters, " +
                                    "and cannot exceed 20 characters in length"
                                }
                                slotProps={{
                                    htmlInput: {maxLength: 20 }
                                }}
                            />
                        </FormControl>
                        <FormControl margin={"normal"} style={{paddingTop: 5}}>
                            <TextAreaField
                                id="sshKey"
                                name="ssh_key"
                                label="SSH Public Key"
                                type="text"
                                required={os === 'linux'}
                                helperText={
                                    sshKeyError ||
                                    "Public key to authenticate custom user. Only required for Unix-based servers"
                                }
                                onInputChange={handleSshKeyChange}
                                error={!!sshKeyError}
                            />
                        </FormControl>
                    </FormGroup>
                    <LoadingButton
                        type="submit"
                        color={"primary"}
                        loading={isLoading}
                        loadingPosition={"start"}
                        variant={"contained"}
                        style={{
                            marginTop: 20,
                            alignSelf: "end",
                            color: "whitesmoke"
                        }}
                        startIcon={<SaveIcon />}
                    >
                        Create Server
                    </LoadingButton>
                    <ServerValidationDialog
                        title={"Server Create Error"}
                        open={openDialog}
                        onClose={() => setOpenDialog(false)}
                        textContent={validationError}
                    />
                </Form>

                {validationError && (
                    <ServerValidationDialog
                        title={"Server Create Error"}
                        open={openDialog}
                        onClose={() => setOpenDialog(false)}
                        textContent={validationError}
                    />
                )}

                <SimpleSnackbar
                    message={snackbarMessage}
                    open={snackbarOpen}
                    onClose={handleSnackbarClose}
                    disableAutoClose={false}
                    vertical="bottom"
                    horizontal="center"
                />
            </Paper>
        </Container>
    )
}


export default ServerCreatorForm;
