import {ErrorOutlined} from "@mui/icons-material";
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Paper,
    Stack,
    Step,
    StepButton,
    StepLabel,
    Stepper,
    Tooltip,
    Typography,
    useMediaQuery,
    useTheme,
} from "@mui/material";
import React, {useEffect, useMemo, useState} from "react";
import {useNavigate} from "react-router-dom";
import {URL_TEACHER_SERVERS} from "../../../../../router/urls";
import {NestedMedia} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import AccessStep from "./AccessStep";
import GuestsStep, {CatalogOptions} from "./GuestsStep";
import HostStep, {MachineTypeOptions} from "./HostStep";
import NetworksStep from "./NetworksStep";
import ReviewStep from "./ReviewStep";
import {toCreateRequest} from "./accessReview";
import {GuestRuleContext} from "./guestRules";
import {
    hasErrors,
    initialNestedWizardState,
    NESTED_WIZARD_STEPS,
    NestedWizardState,
    NestedWizardSteps,
    resolveNavigation,
    StepErrors,
    validateStep,
} from "./nestedWizardState";

const NestedImageWizard: React.FC = () => {
    const navigate = useNavigate();
    const theme = useTheme();
    const compactStepper = useMediaQuery(theme.breakpoints.down('md'));
    const [state, setState] = useState<NestedWizardState>(initialNestedWizardState);
    const [activeStep, setActiveStep] = useState(0);
    // Errors appear for a step once the instructor has tried to move past it, not while they first type.
    const [checkedSteps, setCheckedSteps] = useState<Set<number>>(new Set());
    const [machineTypes, setMachineTypes] = useState<MachineTypeOptions>({pending: true, data: [], error: ""});
    const [catalog, setCatalog] = useState<CatalogOptions>({pending: true, data: [], error: ""});
    const [media, setMedia] = useState<NestedMedia[]>([]);
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState("");
    const guestContext: GuestRuleContext = useMemo(() => ({catalog: catalog.data, media}), [catalog.data, media]);

    useEffect(() => {
        let active = true;
        nestedService.list_machine_types()
            .then(types => {
                if (!active) return;
                setMachineTypes({pending: false, data: types, error: ""});
                // Drop the default build type when this project does not offer it, so the select starts empty.
                setState(prev => types.some(type => type.name === prev.build_machine_type)
                    ? prev
                    : {...prev, build_machine_type: ""});
            })
            .catch((error) => {
                if (!active) return;
                setMachineTypes({
                    pending: false,
                    data: [],
                    error: `Could not load machine types: ${error?.message || "unknown error"}`,
                });
            });
        nestedService.list_catalog()
            .then(entries => {
                if (active) setCatalog({pending: false, data: entries, error: ""});
            })
            .catch((error) => {
                if (active) {
                    setCatalog({pending: false, data: [], error: `Could not load the OS catalog: ${error?.message || "unknown error"}`});
                }
            });
        // The library only feeds the media pickers; without it, uploads still work.
        nestedService.list_media()
            .then(items => {
                if (active) setMedia(items);
            })
            .catch(() => undefined);
        return () => {
            active = false;
        };
    }, []);

    const handleMediaUploaded = (uploaded: NestedMedia) =>
        setMedia(prev => [...prev.filter(item => item.id !== uploaded.id), uploaded]);

    const errorsFor = (index: number): StepErrors =>
        validateStep(NESTED_WIZARD_STEPS[index], state, machineTypes.data, guestContext);
    const shownErrors = (index: number): StepErrors => checkedSteps.has(index) ? errorsFor(index) : {};

    const handleChange = (patch: Partial<NestedWizardState>) => setState(prev => ({...prev, ...patch}));

    const goTo = (target: number) => {
        const destination = resolveNavigation(activeStep, target, state, machineTypes.data, guestContext);
        if (target > activeStep) {
            // Moving forward submits every step before the target; the target itself is not checked on arrival.
            setCheckedSteps(prev => {
                const next = new Set(prev);
                for (let index = 0; index < target; index++) {
                    next.add(index);
                }
                return next;
            });
        }
        setActiveStep(destination);
    };

    const handleSubmit = async () => {
        const reviewIndex = NESTED_WIZARD_STEPS.length - 1;
        setCheckedSteps(prev => new Set(prev).add(reviewIndex));
        if (hasErrors(errorsFor(reviewIndex))) {
            return;
        }
        setSubmitting(true);
        setSubmitError("");
        try {
            await nestedService.create(toCreateRequest(state, catalog.data));
            navigate(URL_TEACHER_SERVERS);
        } catch (error) {
            // The API names the network, guest, or field it refused; keep the wizard state so it can be fixed.
            setSubmitError((error as Error)?.message || "The image could not be created.");
            setSubmitting(false);
        }
    };

    const step = NESTED_WIZARD_STEPS[activeStep];
    const currentErrors = shownErrors(activeStep);

    return (
        <Paper elevation={1} square={false} sx={{width: "100%", paddingY: theme.spacing(1)}}>
            <Stepper
                nonLinear
                activeStep={activeStep}
                alternativeLabel={compactStepper}
                sx={{overflowX: {xs: "auto", sm: "visible"}, pb: {xs: 0.5, sm: 0}}}
            >
                {NESTED_WIZARD_STEPS.map((name, index) => (
                    <Step key={name} sx={{minWidth: {xs: 72, sm: 0}}}>
                        <StepButton color="inherit" onClick={() => goTo(index)}>
                            <StepLabel error={hasErrors(shownErrors(index))}>{name}</StepLabel>
                        </StepButton>
                    </Step>
                ))}
            </Stepper>

            <Stack sx={{padding: {xs: 1, sm: 2}}}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                    <Stack gap={1} direction="row" alignItems="center">
                        <Typography variant="h6" component="h2">{step}</Typography>
                        {hasErrors(currentErrors) && (
                            <Tooltip title={`Form ${step} is invalid`}>
                                <ErrorOutlined color="error" aria-label={`${step} has errors`} />
                            </Tooltip>
                        )}
                        {machineTypes.pending && <CircularProgress thickness={5} size={20} color="primary" />}
                    </Stack>
                    <Stack direction="row" gap={{xs: 1, sm: 2}} flexWrap="wrap">
                        <Button size="small" color="error" variant="outlined" onClick={() => navigate(URL_TEACHER_SERVERS)}>
                            Cancel
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            disabled={activeStep === 0}
                            onClick={() => goTo(activeStep - 1)}
                        >
                            Back
                        </Button>
                        {activeStep < NESTED_WIZARD_STEPS.length - 1 ? (
                            <Button size="small" variant="contained" onClick={() => goTo(activeStep + 1)}>
                                Next
                            </Button>
                        ) : (
                            <Button
                                size="small"
                                variant="contained"
                                disabled={submitting || catalog.pending || machineTypes.pending}
                                onClick={handleSubmit}
                                startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
                            >
                                Create image
                            </Button>
                        )}
                    </Stack>
                </Stack>
                <Box>
                    {step === NestedWizardSteps.Host && (
                        <HostStep
                            state={state}
                            errors={currentErrors}
                            machineTypes={machineTypes}
                            context={guestContext}
                            onChange={handleChange}
                        />
                    )}
                    {step === NestedWizardSteps.Networks && (
                        <NetworksStep state={state} errors={currentErrors} onChange={handleChange} />
                    )}
                    {step === NestedWizardSteps.Guests && (
                        <GuestsStep
                            state={state}
                            errors={currentErrors}
                            catalog={catalog}
                            media={media}
                            onChange={handleChange}
                            onMediaUploaded={handleMediaUploaded}
                        />
                    )}
                    {step === NestedWizardSteps.Access && (
                        <AccessStep state={state} disabled={submitting} onChange={handleChange} />
                    )}
                    {step === NestedWizardSteps.Review && (
                        <>
                            {submitError && <Alert severity="error" sx={{mt: 2}}>{submitError}</Alert>}
                            <ReviewStep
                                state={state}
                                errors={currentErrors}
                                machineTypes={machineTypes.data}
                                catalog={catalog.data}
                                media={media}
                            />
                        </>
                    )}
                </Box>
            </Stack>
        </Paper>
    );
};

export default NestedImageWizard;
