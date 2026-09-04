import {ErrorOutlined} from "@mui/icons-material";
import SaveIcon from "@mui/icons-material/Save";
import {LoadingButton} from "@mui/lab";
import {
    Box,
    Button,
    CircularProgress,
    Container,
    Modal,
    Paper,
    Stack,
    Step,
    StepButton,
    Stepper, Tooltip,
    Typography,
    useTheme
} from "@mui/material";
import {useModal} from "mui-modal-provider";
import React, { useEffect, useState } from "react";
import {useNavigate, useParams} from "react-router-dom";
import {useForm} from "../../../../hooks/useForm";
import {useForms} from "../../../../hooks/useForms";
import {URL_TEACHER_SPECIFICATIONS_BASE} from "../../../../router/urls";
import {DocSummary} from "../../../../services/Documents/docs.model";
import {docsService} from "../../../../services/Documents/docs.service";
import {AgogeImage} from "../../../../services/Server/image.model";
import {imageService} from "../../../../services/Server/image.service";
import {serverService} from "../../../../services/Server/server.service";
import {WebApplication} from "../../../../services/Specification/specification.model";
import {
    Assessment,
    LMSQuiz,
    Network, ServerMachineTypes,
    SpecificationEdit,
    Summary,
    TeachingConcept
} from "../../../../services/Specification/specificationEdit.model";
import {specificationEditService} from "../../../../services/Specification/specificationEdit.service";
import {FormType} from "../../../../types/Form";
import {UnitType} from "../../../../types/BuildConstants";
import ErrorDialog from "../../../Common/Dialogs/ErrorDialog";
import SimpleSnackbar from "../../../Common/SnackBar/SnackBar";
import AssessmentForm from "./AssessmentForms/AssessmentForm";
import {AssessmentFormKeys} from "./AssessmentForms/AssessmentFormTypes";
import StartupScriptDialog from "./AssessmentForms/StartupScriptDialog";
import {useAssessmentForm} from "./AssessmentForms/useAssessmentForm";
import NetworkForm from "./NetworkForm";
import Review from "./Review/Review";
import ServerForm from "./ServerForm/ServerForm";
import {ServerFormKeys} from "./ServerForm/ServerFormTypes";
import {useServerForm} from "./ServerForm/useServerForm";
import SummaryForm from "./SummaryForm";
import WebApplicationForm from "./WebApplicationForm";
import {EditorFormFactory} from "./utils/EditorFormFactory";
import {EditorForms, NetworkFormKeys, SummaryFormKeys, WebApplicationFormKeys} from "./utils/EditorTypes";


const Editor: React.FC = () => {
    const { showModal } = useModal();
    const navigate = useNavigate();
    const initialStep = 0;
    const { edit_id } = useParams<{ edit_id: string }>();
    const [initialized, setInitialized] = useState(false);
    const [startupScripts, setStartupScripts] = useState<{
        pending: boolean;
        data: string[];
    }>({ pending: true, data: [] });
    const [images, setImages] = useState<{ pending: boolean; data: AgogeImage[] }>({
        pending: true,
        data: [],
    });
    const [machineTypes, setMachineTypes] = useState<{pending: boolean; data: ServerMachineTypes[] }>({
        pending: true,
        data: [],
    });
    const [specification, setSpecification] = useState<{
        pending: boolean;
        data: SpecificationEdit | null;
    }>({ pending: true, data: null });
    const [activeStep, setActiveStep] = useState(initialStep);
    const [submitting, setSubmitting] = useState(false);
    const [openCancelModal, setOpenCancelModal] = useState(false);
    const [canceling, setCanceling] = useState(false);
    const summaryForm = useForm({ initialize: false });
    const networkForms = useForms({ initialize: false });
    const webApplicationForms = useForms({ initialize: false });
    const serverForm = useServerForm({ initialize: false });
    const assessmentForm = useAssessmentForm({ initialize: false });
    const [erroredStep, setErroredStep] = useState<EditorForms | null>(null);
    const [openDialog, setOpenDialog] = useState(false);
    const [dialogMessage, setDialogMessage] = useState("");
    const [files, setFiles] = useState<DocSummary[]>([]);
    const [teacherFiles, setTeacherFiles] = useState<DocSummary[]>([]);
    const [studentFiles, setStudentFiles] = useState<DocSummary[]>([]);

    const onUploadStartScript = () => {
        showModal(StartupScriptDialog, {
            onClose: (newFile) => {
                if (newFile) {
                    assessmentForm.updateAssessmentField(
                        AssessmentFormKeys.assessmentScript,
                        newFile
                    );
                    setStartupScripts((prevState) => {
                        const fileExists = prevState.data.some(
                            (file) => file === newFile
                        );
                        if (!fileExists) {
                            return {
                                ...prevState,
                                data: [...prevState.data, newFile],
                            };
                        }
                        return prevState;
                    });
                    showModal(SimpleSnackbar, {
                        message: "Successfully added Start Script!",
                        severity: "success",
                    });
                }
            },
        });
    };

    useEffect(() => {
        if (edit_id) {
            loadSpecification();
        }
    }, [edit_id]);

    useEffect(() => {
        loadFiles();
        loadImages();
        loadStartupScripts();
        loadMachineTypes();
        const hash = window.location.hash;
        if (hash) {
            const step = parseInt(hash.substring(1), 10);
            if (!isNaN(step)) {
                setActiveStep(step);
            }
        }
    }, []);

    useEffect(() => {
        // There may be a better way of doing this, but I'm not entirely sure. This listens to the
        // network forms and server forms, specifically
        //
        // network.name
        // server.nics.network & server.nics.network_ip
        //
        // Whenever network changes, we revalidate the server nics to make sure we are still valid. When
        // server nics changes, we'll revalidate to make sure we align with networks.
        //

        const copyOfNetworkForms = [...(networkForms.forms || [])];
        const networks = (copyOfNetworkForms || []).reduce(
            (acc: { [key: string]: string }, form: FormType) => {
                const networkField = form[NetworkFormKeys.networkName];
                const subnetField = form[NetworkFormKeys.networkSubnets];

                if (
                    networkField &&
                    networkField.error == null &&
                    subnetField &&
                    subnetField.error == null
                ) {
                    acc[networkField.value] = subnetField.value;
                }
                return acc;
            },
            {}
        );

        const isCommunityBuild =
            summaryForm.form?.[SummaryFormKeys.summaryUnitType]?.value === UnitType.COMMUNITY;
        serverForm.validateNetworkAndServerNics(networks, isCommunityBuild);
    }, [
        networkForms.forms?.map(
            (field) => field[NetworkFormKeys.networkName].value
        ),
        serverForm.forms.map((field) =>
            field[ServerFormKeys.serverNetworks].map(
                (f) =>
                    f[ServerFormKeys.serverNicNetwork].value +
                    f[ServerFormKeys.serverNicIPv4Addr].value
            )
        ),
        summaryForm.form?.[SummaryFormKeys.summaryUnitType]?.value,
        serverForm.forms.map(
            (field) => field[ServerFormKeys.serverSettingCommunity].value
        ),
    ]);

    useEffect(() => {
        if (summaryForm.form) {
            const teacherUid = summaryForm.form![SummaryFormKeys.summaryTeacherInstructions].value;
            const studentUid = summaryForm.form![SummaryFormKeys.summaryStudentInstructions].value;

            if (teacherUid && teacherFiles.length > 0) {
                const matchingTeacherFile = teacherFiles.find(file => file.uid === teacherUid);
                if (matchingTeacherFile) {
                    summaryForm.handleInputChange(SummaryFormKeys.summaryTeacherInstructions, matchingTeacherFile);
                }
            }

            if (studentUid && studentFiles.length > 0) {
                const matchingStudentFile = studentFiles.find(file => file.uid === studentUid);
                if (matchingStudentFile) {
                    summaryForm.handleInputChange(SummaryFormKeys.summaryStudentInstructions, matchingStudentFile);
                }
            }
        }
    }, [teacherFiles, studentFiles, summaryForm.form]);

    const loadFiles = () => {
        docsService
            .get_list()
            .then((fetchedFiles) => {
                const docs = fetchedFiles.docs;
                setFiles(docs);
                setTeacherFiles(docs.filter((doc) => doc.instruction_type === "teacher"));
                setStudentFiles(docs.filter((doc) => doc.instruction_type === "student"));
            })
            .catch((error) => {
                console.error("Error fetching files:", error);
            });
    };

    const loadImages = () => {
        imageService
            .list()
            .then((res) => setImages({ pending: false, data: res }))
            .catch((err) => setImages({ ...images, pending: false }));
    };

    const loadStartupScripts = () => {
        specificationEditService
            .getStartupScripts()
            .then((res) => setStartupScripts({ pending: false, data: res }))
            .catch((err) => setStartupScripts({ ...startupScripts, pending: false }));
    };

    const loadMachineTypes = () => {
        serverService
            .list_machine_types()
            .then((resp) => setMachineTypes({ pending: false, data: resp }))
            .catch((err) => setMachineTypes({...machineTypes, pending: false}))
    }

    const loadSpecification = () => {
        specificationEditService
            .get(edit_id!)
            .then((res: SpecificationEdit) => {
                setSpecification({ pending: false, data: res });
                initializeForms(res);
            })
            .catch((err: any) => setSpecification({ ...specification, pending: false }));

    };

    const initializeForms = (specification: SpecificationEdit) => {
        const localNetworkForms = [];
        for (const networkService of specification.networks || []) {
            localNetworkForms.push(EditorFormFactory.generateNetworkForm(networkService));
        }

        const localWebAppForms = [];
        for (const webApp of specification?.web_applications || []) {
            localWebAppForms.push(EditorFormFactory.generateWebAppForm(webApp));
        }


        assessmentForm.handleInitialization(specification.assessment, specification.lms_quiz);
        serverForm.handleInitialization(specification.servers);

        const legacyUnitType = (specification?.summary as Summary & {unit_type?: UnitType})?.unit_type;
        summaryForm.handleInitialization(
            EditorFormFactory.generateSummaryForm(
                specification?.summary,
                (specification?.unit_type || legacyUnitType || UnitType.SOLO) as UnitType
            )
        );
        networkForms.handleInitialization(localNetworkForms);
        webApplicationForms.handleInitialization(localWebAppForms);

        setInitialized(true);
    };

    const handleNavigation = async (newStep: number) => {
        const currentForm = Object.values(EditorForms)[activeStep];
        const nextForm = Object.values(EditorForms)[newStep];

        if (currentForm === EditorForms.Review) {
            // Directly navigate without submission if moving away from Review form
            setActiveStep(newStep);
            window.location.hash = `#${newStep}`;
            return;
        }

        if (
            currentForm === EditorForms.WebApplications &&
            (webApplicationForms.forms === null || webApplicationForms.forms.length === 0)
        ) {
            setActiveStep(newStep);
            window.location.hash = `#${newStep}`;
            return;
        }

        if (
            currentForm === EditorForms.Assessment &&
            (assessmentForm.isEmpty())
        ) {
            setActiveStep(newStep);
            window.location.hash = `#${newStep}`;
            return;
        }

        if (
            currentForm === EditorForms.Servers &&
            (serverForm.isEmpty())
        ) {
            setActiveStep(newStep);
            window.location.hash = `#${newStep}`;
            return
        }

        if (
            nextForm === EditorForms.Servers &&
            (networkForms.forms === null || networkForms.forms.length === 0)
        ) {
            showModal(SimpleSnackbar, {
                message: "You must add a network before adding servers.",
                severity: "error",
            });
            return;
        }

        if (!doesCurrentStepHaveErrors(currentForm)) {
            await handleOnSubmit().then(resp => {
                if (newStep !== initialStep) {
                    window.location.hash = `#${newStep}`;
                }
                setActiveStep(newStep);
            }).catch((error) => {
                console.log(error);
                showModal(SimpleSnackbar, {
                    message: "Validation failed. Please correct any errors before proceeding.",
                    severity: "error",
                });
            });
        } else {
            showModal(SimpleSnackbar, {
                message: "Please correct any errors before proceeding.",
                severity: "error",
            });
        }
    };

    const handleNext = () => {
        handleNavigation(activeStep + 1);
    };

    const handleBack = () => {
        handleNavigation(activeStep - 1);
    };

    const handleNavigateTo = (form: EditorForms) => {
        const stepIndex = Object.values(EditorForms).indexOf(form);
        handleNavigation(stepIndex);
    };

    const handleOnSubmit = (): Promise<void> => {
        return new Promise((resolve, reject) => {
            setSubmitting(true);

            const formToKeyMap: { [key in EditorForms]: string } = {
                [EditorForms.Summary]: "summary",
                [EditorForms.Networks]: "networks",
                [EditorForms.Servers]: "servers",
                [EditorForms.WebApplications]: "web_applications",
                [EditorForms.Assessment]: assessmentForm?.isLMS
                    ? "lms_quiz"
                    : "assessment",
                [EditorForms.Review]: "review",
            };

            const key: string = formToKeyMap[Object.values(EditorForms)[activeStep]];
            const body = generateSpecification();
            const dataToPost =
                key !== "review" ? body![key as keyof SpecificationEdit] : body;
            let postBody: Record<string, any> = {
                form_type: key === "lms_quiz" ? "assessment" : key,
            };
            if (Array.isArray(dataToPost)) {
                postBody[key as keyof typeof postBody] = dataToPost;
            } else {
                postBody = {
                    ...(dataToPost as object),
                    ...postBody,
                };
            }
            if (key === "summary") {
                postBody = {
                    ...postBody,
                    unit_type: body!.unit_type,
                };
            }

            specificationEditService
                .post(postBody, edit_id!)
                .then((res) => {
                    setSubmitting(false);
                    setSpecification({ ...specification, data: res });

                    // Clear dialog message and make sure it's closed
                    setDialogMessage("");
                    handleCloseDialog();

                    if (key === EditorForms.Review.toLowerCase()) {
                        navigate(URL_TEACHER_SPECIFICATIONS_BASE);
                    }

                    resolve();
                })
                .catch((error) => {
                    console.log(error)

                    // Populate dialog with error message and open it.
                    setDialogMessage(error.toString());
                    handleOpenDialog();

                    setSubmitting(false);
                    showModal(SimpleSnackbar, {
                        message: "Failed to update Specification!",
                        severity: "error",
                    });
                    reject();
                });
        });
    };

    const handleOpenCancelModal = () => {
        setOpenCancelModal(true);
    }

    const handleCloseCancelModal = () => {
        setOpenCancelModal(false);
    }

    const handleConfirmCancel = async() => {
        setCanceling(true);
        try{
            if(edit_id){
                await specificationEditService.del(edit_id);
                navigate(URL_TEACHER_SPECIFICATIONS_BASE);
            }
        } catch (error){
            console.error(error);
        }
        setCanceling(false);
        setOpenCancelModal(false);
    }

    const handleOpenDialog = () => {
        setOpenDialog(true);
    }

    const handleCloseDialog = () => {
        setOpenDialog(false);
    }

    const generateSpecification = (): SpecificationEdit | undefined => {
        // this converts the forms to a specification object

        if (!specification.pending) {
            const summaryValues: Summary = {
                ...specification.data!.summary,
                name: summaryForm.form![SummaryFormKeys.summaryName].value,
                description: summaryForm.form![SummaryFormKeys.summaryDescription].value,
                teacher_instructions_url: summaryForm.form![SummaryFormKeys.summaryTeacherInstructions].value.uid,
                student_instructions_url: summaryForm.form![SummaryFormKeys.summaryStudentInstructions].value.uid,
                author: summaryForm.form![SummaryFormKeys.summaryAuthor].value,
                tags: ((summaryForm.form![SummaryFormKeys.summaryTeachingConcepts].value as TeachingConcept[])
                    .map((t) => t.id) as unknown as TeachingConcept[]),
            }
            const unitType = summaryForm.form![SummaryFormKeys.summaryUnitType].value as UnitType;

            const networkValues: Network[] = [];
            for (const form of networkForms.forms!) {
                const networkName = form[NetworkFormKeys.networkName].value;
                networkValues.push({
                    name: networkName,
                    reservations: specification.data?.networks?.find(
                        network => network.name === networkName
                    )?.reservations || [],
                    subnets: [
                        {
                            name: "default",
                            ip_subnet: form[NetworkFormKeys.networkSubnets].value,
                            promiscuous_mode: form[NetworkFormKeys.networkPromiscuous].value,
                        },
                    ],
                });
            }

            const webAppValues: WebApplication[] = [];
            for (const form of webApplicationForms.forms || []) {
                webAppValues.push({
                    name: form[WebApplicationFormKeys.webAppName].value,
                    host_name: form[WebApplicationFormKeys.webAppHostName].value,
                    starting_directory: form[WebApplicationFormKeys.webAppStartingDirectory].value
                });
            }

            const assessment = assessmentForm.render();
            const selectedServerName =
                assessmentForm.form?.[AssessmentFormKeys.assessmentInstallServer]?.value;

            const serverMatch = specification.data?.servers?.find(
                s => s.name === selectedServerName
            );

            const serverOS = serverMatch?.details?.os;

            if (assessment?.assessment_script) {
                assessment.assessment_script.operating_system = serverOS;
            }
            return {
                ...specification.data!,
                id: specification.data!.id,
                unit_type: unitType,
                build_type: specification.data!.build_type,
                edit_id: specification.data!.edit_id,
                status: "",
                discriminator: "",
                lms_quiz: assessmentForm.isLMS ? (assessment as LMSQuiz) : undefined,
                assessment: assessmentForm.isLMS ? undefined : (assessment as Assessment),
                web_applications: webAppValues,
                summary: summaryValues,
                networks: networkValues,
                servers: serverForm.render(images.data),
            };
        }
    };

    const doesCurrentStepHaveErrors = (
        step: EditorForms,
        reviewAll = false
    ): boolean => {
        const validateEntireForm = () => {
            for (const form of Object.values(EditorForms)) {
                if (form !== EditorForms.Review && doesCurrentStepHaveErrors(form, true)) {
                    if (erroredStep !== form) {
                        setErroredStep(form);
                    }
                    return true;
                }
            }
            return false;
        };

        if (!specification.pending) {
            let hasError = false;
            switch (step) {
                case EditorForms.Summary:
                    hasError = summaryForm.hasErrors();
                    break;
                case EditorForms.Networks:
                    hasError = networkForms.hasErrors();
                    break;
                case EditorForms.WebApplications:
                    hasError = webApplicationForms.hasErrors();
                    break;
                case EditorForms.Servers:
                    hasError = serverForm.hasErrors();
                    break;
                case EditorForms.Assessment:
                    hasError = assessmentForm.hasErrors();
                    break;
                case EditorForms.Review:
                    hasError = validateEntireForm();
                    break;
                default:
                    break;
            }

            return hasError;
        }

        return false;
    };

    const theme = useTheme();
    const steps = Object.values(EditorForms);

    const hasError = doesCurrentStepHaveErrors(steps[activeStep]);
    return (
        <Container sx={{ width: "80%", overflow: "hidden", mt: theme.spacing(9) }}>
            <Paper elevation={1} square={false} sx={{ width: "100%", paddingY: theme.spacing(1) }}>
                <Stepper nonLinear activeStep={activeStep}>
                    {steps.map((step, index) => (
                        <Step key={index}>
                            <StepButton color="inherit" onClick={() => handleNavigateTo(step as EditorForms)}>
                                {step}
                            </StepButton>
                        </Step>
                    ))}
                </Stepper>

                <Stack sx={{ padding: theme.spacing(2), overflowY: "auto" }}>
                    <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"}>
                        <Stack gap={1} direction={"row"} alignItems={"center"}>
                            <Typography variant={"h6"}>{steps[activeStep]}</Typography>

                            {hasError && (
                                <Tooltip
                                    title={
                                        steps[activeStep] === EditorForms.Review
                                            ? "Form " + erroredStep + " is invalid"
                                            : "Form " + steps[activeStep] + " is invalid"
                                    }
                                >
                                    <ErrorOutlined color={"error"} />
                                </Tooltip>
                            )}

                            {specification.pending && (
                                <CircularProgress thickness={5} size={20} color="primary" />
                            )}
                        </Stack>
                        <Stack direction="row" spacing={2}>
                            {dialogMessage !== "" && (
                                <Button
                                    size="small"
                                    color="error"
                                    variant="outlined"
                                    onClick={handleOpenDialog}
                                >
                                    Errors
                                </Button>
                            )}
                            <Button
                                size="small"
                                color="error"
                                variant="outlined"
                                onClick={handleOpenCancelModal}
                            >
                                Cancel
                            </Button>
                            {activeStep === 5 && (
                                <LoadingButton
                                    size="small"
                                    color="primary"
                                    onClick={handleOnSubmit}
                                    loading={submitting}
                                    loadingPosition="end"
                                    endIcon={<SaveIcon />}
                                    variant="contained"
                                    disabled={specification.pending || hasError}
                                >
                                    Publish
                                </LoadingButton>
                            )}
                        </Stack>
                    </Stack>

                    <Box>
                        {
                            Object.values(EditorForms).map((form, index) => {
                                if (form === EditorForms.Summary && index === activeStep)
                                    return (
                                        <SummaryForm
                                            key={`summary-${index}`}
                                            disableForm={specification.pending || submitting}
                                            formHook={summaryForm}
                                            specification={specification}
                                            teacherFiles={teacherFiles}
                                            studentFiles={studentFiles}
                                        />
                                    );
                                else if (form === EditorForms.Networks && index === activeStep)
                                    return (
                                        <NetworkForm
                                            key={`network-${index}`}
                                            disableForm={specification.pending || submitting}
                                            formHooks={networkForms}
                                            specification={specification}
                                            serverForms={serverForm}
                                        />
                                    );
                                else if (form === EditorForms.Servers && index === activeStep)
                                    return (
                                        <ServerForm
                                            key={`server-${index}`}
                                            disableForm={specification.pending || submitting}
                                            serverForm={serverForm}
                                            specification={specification}
                                            images={images}
                                            remoteNetworkInterfaces={specification.data?.networks || []}
                                            localNetworkInterfaces={(networkForms.forms || []).map((f => f[NetworkFormKeys.networkName].value))}
                                            machineTypes={machineTypes}
                                        />
                                    );
                                else if (form === EditorForms.WebApplications && index === activeStep)
                                    return (
                                        <WebApplicationForm
                                            key={`webapp-${index}`}
                                            disableForm={specification.pending || submitting}
                                            formHooks={webApplicationForms}
                                            specification={specification}
                                        />
                                    );
                                else if (form === EditorForms.Assessment && index === activeStep)
                                    return (
                                        <AssessmentForm
                                            key={`assessment-${index}`}
                                            disableForm={specification.pending || submitting}
                                            assessmentFormHook={assessmentForm}
                                            specification={specification}
                                            startupScripts={startupScripts}
                                            onUploadStartScript={onUploadStartScript}
                                            remoteServers={(specification.data?.servers || []).map((server => server.name))}
                                            localServers={serverForm.forms.map((f => f[ServerFormKeys.serverName].value))}
                                        />
                                    );
                                else if (form === EditorForms.Review && index === activeStep)
                                    return (
                                        <Review
                                            key={`review-${index}`}
                                            specification={generateSpecification()}
                                            onNavigateToStep={handleNavigateTo}
                                        />
                                    );
                            })

                        }
                    </Box>
                </Stack>
                {activeStep !== steps.length - 1 && (
                    <Stack direction={"row"} sx={{ pt: 2 }}>
                        <Button disabled={activeStep === 0} onClick={handleBack} sx={{ mr: 1 }}>
                            Back {activeStep !== 0 && "(" + steps[activeStep - 1] + ")"}
                        </Button>

                        <Button onClick={handleNext} sx={{ ml: "auto", mr: 1 }}>
                            Next ({steps[activeStep + 1]})
                        </Button>
                    </Stack>
                )}
            </Paper>
            <Modal
                open={openCancelModal}
                onClose={handleCloseCancelModal}
                aria-labelledby="modal-title"
                aria-describedby="cancel specification creation changes"
            >
                <Box
                    sx={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: 400,
                        bgcolor: 'background.paper',
                        boxShadow: 24,
                        p: 4,
                    }}
                >
                    <Typography id="modal-title" variant="h6" component="h2">
                        Confirm Cancel
                    </Typography>
                    <Typography id="modal-description" sx={{ mt: 2 }}>
                        Are you sure you want to cancel? This action cannot be undone.
                    </Typography>
                    <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mt: 2 }}>
                        <Button onClick={handleCloseCancelModal} disabled={canceling}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleConfirmCancel}
                            variant="contained"
                            color="primary"
                            disabled={canceling}
                            startIcon={canceling ? <CircularProgress size={20} /> : null}
                        >
                            {canceling ? "Processing..." : "Confirm"}
                        </Button>
                    </Stack>
                </Box>
            </Modal>
            <ErrorDialog
                title="Error"
                message={dialogMessage}
                open={openDialog}
                onClose={handleCloseDialog}
            />
        </Container>
    );
};

export default Editor;
