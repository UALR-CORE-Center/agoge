import {ErrorOutline} from "@mui/icons-material";
import Cancel from "@mui/icons-material/Cancel";
import SaveIcon from "@mui/icons-material/Save";
import {LoadingButton} from "@mui/lab";
import {Box, Container, Paper, Stack, Typography} from "@mui/material";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import {useTheme} from "@mui/material/styles";
import {useModal} from "mui-modal-provider";
import React, {useEffect, useState} from "react";
import {useNavigate, useParams} from "react-router-dom";

import {URL_TEACHER_SERVERS} from "../../../../../router/urls";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {imageService} from "../../../../../services/Server/image.service";
import {serverService} from "../../../../../services/Server/server.service";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {ImageStates} from "../../../../../types/AgogeStates";
import SimpleSnackbar from "../../../../Common/SnackBar/SnackBar";
import {IFormKeys, IServerForm} from "../FormFields";
import ServerValidationDialog from "../ServerValidationDialog";
import {HumanInteractionForm} from "./HumanInteractionForm";
import {ServerDetailsForm} from "./ServerDetailsForm";
import {useHumanInteractionForm} from "./useHumanInteractionForm";


interface MessageProps {
    message: string;
    severity?: 'info' | 'warning' | 'error' | 'success';
}


const initialForm: IServerForm = {
    [IFormKeys.DESCRIPTION]: "",
    [IFormKeys.TAGS]: [],
    [IFormKeys.MACHINE_TYPE]: "",
    [IFormKeys.HUMAN_INTERACTION]: [],
    [IFormKeys.DISK_SIZE]: 50
};


export const ServerEditorForm: React.FC = () => {
    const theme = useTheme();
    const {showModal} = useModal();
    const navigate = useNavigate();
    const { image_id } = useParams<{ image_id: string }>();
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [initialized, setInitialized] = useState<boolean>(false);
    const [image, setImage] = useState<{ pending: boolean, data: AgogeImage | null }>({
        pending: true,
        data: null,
    });
    const [machineTypes, setMachineTypes] = useState<{ pending: boolean, data: ServerMachineTypes[] }>({
        pending: true,
        data: [],
    });
    const [imageForm, setImageForm] = useState<IServerForm>(initialForm);
    const hInteractionsForm = useHumanInteractionForm({initialize: false});
    const [formErrors, setFormErrors] = useState<string>("");
    const [openErrorDialog, setOpenErrorDialog] = useState<boolean>(false);

    useEffect(() => {
        if (!initialized) manageSnackbar({message: "Loading image details ..."});
        loadMachineTypes();
        loadImage();
    }, []);

    useEffect(() => {
        loadForm();
    }, [image.data, machineTypes.data]);

    const manageSnackbar = (snackbar: MessageProps): void => {
        showModal(SimpleSnackbar, {
            message: snackbar.message,
            severity: snackbar?.severity ?? "info",
            horizontal: "center",
            vertical: "bottom",
            autoHideDuration: 3000
        });
    }

    const loadMachineTypes = () => {
        serverService
            .list_machine_types()
            .then((resp) => setMachineTypes({ pending: false, data: resp }))
            .catch((err) => setMachineTypes({...machineTypes, pending: false}))
    }

    const loadImage = () => {
        if (image_id){
            imageService
                .get(image_id)
                .then((resp) => setImage({pending: false, data: resp}))
                .catch((err) => setImage({...image, pending: false}));
        }
    }

    const loadForm = () => {
        if (!initialized && image.data) {
            const imageData = image.data;
            const newForm: IServerForm = {
                [IFormKeys.DESCRIPTION]: imageData!.description,
                [IFormKeys.TAGS]: imageData?.labels || [],
                [IFormKeys.MACHINE_TYPE]: imageData!.machine_type,
                [IFormKeys.HUMAN_INTERACTION]: imageData!.human_interaction,
                [IFormKeys.DISK_SIZE]: parseInt(imageData!.add_disk)
            };
            setImageForm(newForm);

            hInteractionsForm.handleInitialization(imageData.human_interaction);

            setInitialized(true);
            setIsLoading(false);
        }
    }

    const updateImage = (
        formKey: IFormKeys,
        value: any,
        index: number | null
    ) => {
        const image = imageForm;
        if ((formKey === IFormKeys.HUMAN_INTERACTION) && index) {
            if (index in image[formKey]) {
                image[formKey][index] = value;
            }
        } else {
            image[formKey] = value;
        }
        setImageForm(image);
    }

    const handleSave = async () => {
        if (hInteractionsForm.isEmpty()) {
            setFormErrors("Servers must have at least one human interaction configured.");
            return;
        }
        setIsLoading(true);
        setFormErrors("");
        const formData = {
            'description': imageForm[IFormKeys.DESCRIPTION],
            'labels': imageForm[IFormKeys.TAGS],
            'machine_type': imageForm[IFormKeys.MACHINE_TYPE],
            'disk_size': imageForm[IFormKeys.DISK_SIZE],
            'human_interaction': hInteractionsForm.render()
        }

        manageSnackbar({message: "Updating image details ..."});
        await imageService
            .patch(image_id!, formData)
            .then(() => {
                navigate(URL_TEACHER_SERVERS);
            })
            .catch((err) => {
                manageSnackbar({
                    message: `Error saving changes: ${err.message}`,
                    severity: "error",
                });
                setFormErrors(err.message);
            }).finally(() => {
                setIsLoading(false);
            });
    }

    const handleCancel = () => navigate(URL_TEACHER_SERVERS);

    return (
        <>
            <Container sx={{ width: "80%", overflow: "hidden", mt: theme.spacing(9) }}>
                <Paper elevation={1} square={false} sx={{ width: "100%", paddingY: theme.spacing(1) }}>
                    <Stack sx={{ padding: theme.spacing(2), overflowY: "auto" }}>
                        <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"}>
                            <Stack gap={1} direction={"row"} alignItems={"center"}>
                                <Typography variant={"h5"} component={"h1"}>Edit {image_id} </Typography>
                                {
                                    formErrors && (
                                        <ErrorOutline color={'error'} fontSize={'small'}/>
                                    )
                                }
                            </Stack>
                        </Stack>
                        {
                            image.data?.status === ImageStates.CHECKED_OUT && (
                                <>
                                    <Stack gap={1} direction={"row"} alignItems={"center"} paddingTop={2}>
                                        <Alert severity={"warning"} variant={"outlined"}>
                                            The image is currently in a checked-out state. Modifications to the
                                            image in this state will not be reflected until after the
                                            image is checked in.
                                        </Alert>
                                    </Stack>
                                </>
                            )
                        }
                        <Box sx={{ width: "100%"}}>
                            { formErrors && (
                                <>
                                    <Stack gap={1} direction={"row"} alignItems={"center"} justifyContent={"space-around"}>
                                        <Button
                                            variant={"contained"}
                                            color={"error"}
                                            onClick={() => setOpenErrorDialog(true)}
                                        >
                                            View Errors
                                        </Button>
                                    </Stack>
                                </>
                            )}
                            <ServerDetailsForm
                                key={`detailsForm`}
                                image={image}
                                imageForm={imageForm}
                                machineTypes={machineTypes}
                                disableForm={(!initialized && machineTypes.pending && image.pending)}
                                updateFormFn={updateImage}
                            />

                            <HumanInteractionForm
                                key={`humanInteractionsForm`}
                                image={image}
                                imageForm={imageForm}
                                disableForm={!initialized && image.pending}
                                interactionsForm={hInteractionsForm}
                            />

                            <Stack gap={1} direction={"row"} alignItems={"center"} justifyContent={"end"}>
                                <LoadingButton
                                    onClick={handleCancel}
                                    variant="outlined"
                                    color="secondary"
                                    startIcon={<Cancel />}
                                    disabled={isLoading}
                                >
                                    Cancel
                                </LoadingButton>
                                <LoadingButton
                                    onClick={handleSave}
                                    variant="contained"
                                    color="primary"
                                    startIcon={<SaveIcon />}
                                    loading={isLoading}
                                    loadingPosition="start"
                                    disabled={!initialized}
                                >
                                    Save
                                </LoadingButton>
                            </Stack>

                            {formErrors && (
                                <ServerValidationDialog
                                    title={"Update Form Errors"}
                                    open={openErrorDialog}
                                    onClose={() => setOpenErrorDialog(false)}
                                    textContent={formErrors}
                                />
                            )}
                        </Box>
                    </Stack>
                </Paper>
            </Container>
        </>
    )
}