import {
    CommonEditorChildrenProps, NetworkFormKeys, SummaryFormKeys
} from "../utils/EditorTypes";
import React, {useState} from "react";
import {
    Accordion, AccordionDetails, AccordionSummary,
    Button, Collapse, IconButton, Stack, Typography,
    useTheme
} from "@mui/material";
import {
    FormAutocompleteField,
    FormGroup,
    FormFields,
    FormGroupOutline,
    FormSwitch,
    FormTextField,
    StyledFormFieldLabel,
} from "../utils/FormFields";
import {Add, CloudUpload, Delete, Error} from "@mui/icons-material";
import {AssessmentScript} from "../../../../../services/Specification/specification.model";
import AssessmentQuestionForm from "./AssessmentQuestionForm";
import LMSQuestionForm from "./LMSQuestionForm";
import {TransitionGroup} from "react-transition-group";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {EmptyListItem, EmptyListItemText} from "../Review/ReviewCommonStyles";
import {
    AssessmentFormField,
    AssessmentFormKeys,
    AssessmentFormQuestions,
    LmsAssessmentFormQuestions
} from "./AssessmentFormTypes";
import {useModal} from "mui-modal-provider";
import StartupScriptDialog from "./StartupScriptDialog";
import {IUseAssessmentForm} from "./useAssessmentForm";

interface Props extends CommonEditorChildrenProps {
    assessmentFormHook: IUseAssessmentForm;
    startupScripts: {
        pending: boolean,
        data: string[]
    }

    onUploadStartScript: () => void;

    localServers: string[]
    remoteServers: string[]

}

export interface AssessmentFormCommonChildrenProps {
    assessmentFormHook: IUseAssessmentForm;
    qIndex: number;
    disableForm: boolean;
}

const AssessmentForm: React.FC<Props> = (
    {
        assessmentFormHook,
        startupScripts,
        remoteServers,
        specification,
        disableForm,
        localServers,
        onUploadStartScript
    }: Props
) => {
    const theme = useTheme();

    const {showModal} = useModal();

    // default toggle first network service
    const [accordionStates, setAccordionStates] = useState<number[]>([0])

    const toggleAccordion = (index: number) => {
        if (accordionStates.includes(index)) {
            setAccordionStates(accordionStates.filter(idx => idx !== index));
        } else {
            setAccordionStates([...accordionStates, index]);
        }
    }


    const removeQuestion = (index: number) => {
        assessmentFormHook.removeQuestion(index);

        const indexOfIndex = accordionStates.findIndex(idx => idx == index)
        setAccordionStates(accordionStates.filter(idx => idx !== indexOfIndex));
    }

    const addQuestion = () => {
        assessmentFormHook.addQuestion()

        // Looks strange without .length - 1, but required to work
        setAccordionStates([assessmentFormHook.form![AssessmentFormKeys.assessmentQuestions].length])
    }

    return (
        <FormFields alignItems={'center'}>

            <FormGroupOutline showOverlay={disableForm} sx={{width: '100%'}}>
                <FormGroup>
                    <Stack direction={'row'} alignItems={'center'} justifyContent={'space-between'}>
                        <StyledFormFieldLabel>Assessment Script</StyledFormFieldLabel>
                        <Button
                            disabled={disableForm}
                            onClick={onUploadStartScript}
                            sx={(theme) => ({
                                color: theme.palette.mode === 'light'
                                    ? '#D5014B'
                                    : '#FE2571',
                            })}
                            size={'small'}
                            endIcon={<CloudUpload/>}
                        >
                            Upload Script
                        </Button>
                    </Stack>
                    <FormAutocompleteField
                        placeholder={"Assessment Script (Optional)"}
                        options={startupScripts.data}
                        disabled={disableForm}
                        loading={startupScripts.pending}
                        onInputChange={(field, value) => assessmentFormHook.updateAssessmentField(field as AssessmentFormKeys, value)}
                        formKey={AssessmentFormKeys.assessmentScript}
                        fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k)!}/>
                </FormGroup>
            </FormGroupOutline>

            {
                assessmentFormHook.hasAssessmentScript() &&
                <FormGroupOutline showOverlay={disableForm} sx={{width: '100%'}}>
                    <FormGroup>
                        <StyledFormFieldLabel>Install Server</StyledFormFieldLabel>
                        <FormAutocompleteField
                            placeholder={"Install Server"}
                            helpText={"Server where the Assessment Script will be hosted"}
                            options={remoteServers}
                            disabled={disableForm}
                            noOptionsTextFn={(input: string) => {
                                const matches = localServers.filter(v => v.toLowerCase().startsWith(input.toLowerCase()));
                                if (!!input && matches.length) {
                                    if (matches.length === 1) {
                                        return `Server '${matches[0]}' exists locally, but must be saved to use it.`;
                                    } else {
                                        return `One or more local servers exist locally but must be saved before they can be used.`;
                                    }
                                }
                            }}
                            onInputChange={(field, value) => assessmentFormHook.updateAssessmentField(field as AssessmentFormKeys, value)}
                            formKey={AssessmentFormKeys.assessmentInstallServer}
                            fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k)!}/>
                    </FormGroup>
                </FormGroupOutline>
            }

            <TransitionGroup style={{width: '100%'}}>
                {
                    assessmentFormHook.getQuestions().map((question: (LmsAssessmentFormQuestions | AssessmentFormQuestions), qIdx: number) => {
                        return (
                            <Collapse key={qIdx} unmountOnExit>
                                <Accordion disableGutters expanded={accordionStates.includes(qIdx)} key={qIdx}>
                                    <AccordionSummary
                                        sx={{
                                            background: theme.palette.action.hover,
                                        }}

                                        onClick={() => toggleAccordion(qIdx)}
                                        id={`assessment-panel-${qIdx}-header`}
                                        aria-controls={`assessment-panel-${qIdx}-content`}
                                        aria-expanded={accordionStates.includes(qIdx)}
                                        aria-label={
                                            accordionStates.includes(qIdx)
                                                ? `Collapse Question ${qIdx+1}`
                                                : `Expand Question ${qIdx+1}`
                                        }
                                    >
                                        <Stack width={'100%'} direction={'row'} alignItems={'center'}
                                               justifyContent={'space-between'}>
                                            <Stack direction={'row'} alignItems={'center'} gap={1}>
                                                <Stack direction={'row'} alignItems={'center'}>
                                                    <Typography variant={'h6'}>Question {qIdx + 1}</Typography>
                                                    {
                                                        assessmentFormHook.doesQuestionHaveAnyErrors(qIdx) &&
                                                        <Error
                                                            color={'error'}
                                                            fontSize={'small'}
                                                            role="img"
                                                            aria-label="This question has validation errors"
                                                        />
                                                    }
                                                </Stack>


                                                <IconButton
                                                    color={'primary'}
                                                    size={'small'}
                                                    aria-label={accordionStates.includes(qIdx) ? "Collapse question" : "Expand question"}
                                                >
                                                    {
                                                        accordionStates.includes(qIdx) ?
                                                            <ExpandLessIcon/> : <ExpandMoreIcon/>
                                                    }
                                                </IconButton>
                                            </Stack>

                                            <IconButton
                                                disabled={disableForm}
                                                color={'error'}
                                                size={'small'}
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    removeQuestion(qIdx);
                                                }}
                                                aria-label={`Remove Question ${qIdx + 1}`}
                                            >
                                                <Delete/>
                                            </IconButton>
                                        </Stack>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <FormFields>

                                            {
                                                assessmentFormHook.isLMS ?
                                                    <LMSQuestionForm key={qIdx} assessmentFormHook={assessmentFormHook}
                                                                     question={question as LmsAssessmentFormQuestions}
                                                                     disableForm={disableForm}
                                                                     qIndex={qIdx}/> :
                                                    <AssessmentQuestionForm key={qIdx}
                                                                            assessmentFormHook={assessmentFormHook}
                                                                            disableForm={disableForm}
                                                                            question={question as AssessmentFormQuestions}
                                                                            qIndex={qIdx}/>
                                            }

                                        </FormFields>
                                    </AccordionDetails>
                                </Accordion>
                            </Collapse>
                        )
                    })
                }

            </TransitionGroup>


            {
                (assessmentFormHook.getQuestions()).length == 0 &&
                <EmptyListItem sx={{padding: theme.spacing(2)}}>
                    <EmptyListItemText>
                        {
                            specification.pending ? 'Loading...' : 'No Questions'
                        }
                    </EmptyListItemText>
                </EmptyListItem>
            }


            <Button disabled={disableForm} onClick={addQuestion} variant={'contained'}
                    sx={{width: '70%', backgroundColor:'secondary.dark'}}
                    endIcon={<Add/>}>
                Add Question
            </Button>
        </FormFields>
    );

}


export default AssessmentForm;