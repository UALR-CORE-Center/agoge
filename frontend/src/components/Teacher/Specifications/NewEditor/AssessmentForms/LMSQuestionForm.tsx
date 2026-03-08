import React, {useState} from "react";
import {AssessmentFormCommonChildrenProps} from "./AssessmentForm";
import {
    FormCheckBox,
    FormFields,
    FormGroup,
    FormGroupOutline,
    FormMuliTextField,
    FormRadioBtns,
    FormRow,
    FormTextField,
    StyledFormFieldLabel
} from "../utils/FormFields";
import {LMSAssessmentQuestionType} from "../../../../../services/Specification/specificationEdit.model";
import {Button, Collapse, IconButton, Stack, Typography, useTheme} from "@mui/material";
import {Add, Clear} from "@mui/icons-material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {AssessmentFormKeys, LmsAssessmentFormQuestions} from "./AssessmentFormTypes";
import {IUseAssessmentForm} from "./useAssessmentForm";

interface Props extends AssessmentFormCommonChildrenProps {
    question: LmsAssessmentFormQuestions
    assessmentFormHook: IUseAssessmentForm;
}

const LMSQuestionForm: React.FC<Props> = ({assessmentFormHook, disableForm, qIndex}: Props) => {
    const [answersOpened, setAnswersOpened] = useState<boolean>(true)


    const addQuestionAnswer = () => {
        assessmentFormHook.addQuestionAnswer(qIndex);
    }

    const theme = useTheme()
    const questionAnswers = assessmentFormHook.getLMSQuestionAnswers(qIndex);
    return (
        <React.Fragment>
            <FormGroupOutline showOverlay={disableForm}> <FormGroup gap={2}>
                <FormRadioBtns
                    placeholder={"Question Type"}
                    options={[
                        {
                            label: 'Auto',
                            value: LMSAssessmentQuestionType.auto
                        },
                        {
                            label: 'Short Answer',
                            value: LMSAssessmentQuestionType.shortAnswer
                        },
                    ]}
                    label={'Question Type'}
                    helpText={"Auto if the question is accessed by a web application or an application script"}
                    disabled={assessmentFormHook.hasAssessmentScript() || disableForm}
                    onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                    formKey={AssessmentFormKeys.assessmentQuestionType}
                    fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>

                {
                    assessmentFormHook.hasAssessmentScript() &&
                    <FormCheckBox
                        placeholder={"Answered By Script"}
                        label={'Script Assessment'}
                        helpText={"Answer is automatically assessed by the script"}
                        onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                        formKey={AssessmentFormKeys.assessmentQuestionScriptAssessment}
                        fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>
                }
            </FormGroup>
            </FormGroupOutline>


            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                <StyledFormFieldLabel>Question Text</StyledFormFieldLabel>
                <FormMuliTextField
                    placeholder={"Question Text"}
                    rows={3}
                    disabled={disableForm}
                    onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                    formKey={AssessmentFormKeys.assessmentQuestionText}
                    fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>
            </FormGroup>
            </FormGroupOutline>

            {
                assessmentFormHook.getFormField(AssessmentFormKeys.assessmentQuestionType, qIndex)!.value !== LMSAssessmentQuestionType.auto &&
                <FormGroupOutline showOverlay={disableForm}>
                    <Stack direction={'row'} alignItems={'center'}>
                        <StyledFormFieldLabel>Question Answers</StyledFormFieldLabel>
                        <IconButton
                            color={'primary'}
                            size={'small'}
                            onClick={() => setAnswersOpened(!answersOpened)}
                            aria-label={answersOpened ? 'Collapse answers' : 'Expand answers'}
                        >
                            {answersOpened ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                        </IconButton>

                        <Typography sx={{ml: 'auto'}} variant={'subtitle1'}
                                    color={'text.secondary'}>{questionAnswers.length} Question(s)</Typography>
                    </Stack>

                    <Collapse in={answersOpened} unmountOnExit mountOnEnter>
                        <FormFields>
                            {
                                questionAnswers?.map((answer, aIdx) => {
                                    return (
                                        <FormRow key={aIdx} gap={2}>
                                            <FormGroup width={'75%'}>
                                                <StyledFormFieldLabel>Answer #{aIdx + 1}</StyledFormFieldLabel>
                                                <FormTextField
                                                    disabled={disableForm}
                                                    placeholder={"Question Answer"}
                                                    onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionAnswer(qIndex, aIdx, field, value)}
                                                    formKey={AssessmentFormKeys.assessmentQuizAnswerText}
                                                    fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex, aIdx)!}/>

                                            </FormGroup>

                                            <FormGroup width={'20%'}>
                                                <StyledFormFieldLabel>Weight</StyledFormFieldLabel>
                                                <FormTextField
                                                    placeholder={"Weighted Points"}
                                                    disabled={disableForm}
                                                    type={'number'}
                                                    onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionAnswer(qIndex, aIdx, field, value)}
                                                    formKey={AssessmentFormKeys.assessmentQuizAnswerWeight}
                                                    fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex, aIdx)!}/>
                                            </FormGroup>

                                            <IconButton
                                                onClick={() => assessmentFormHook.removeQuestionAnswer(qIndex, aIdx)}
                                                disabled={disableForm}
                                                sx={{alignSelf: 'flex-end'}} size={'small'} color={'error'}
                                                aria-label={`Remove answer ${aIdx + 1}`}
                                            >
                                                <Clear/>
                                            </IconButton>

                                        </FormRow>
                                    )
                                })
                            }

                            <Stack sx={{width: '100%', mt: theme.spacing(2),}} alignItems={'center'}>
                                <Button disabled={disableForm} onClick={() => addQuestionAnswer()}
                                        sx={{width: '30%', minWidth: '150px'}}
                                        variant={'contained'} color={'primary'} endIcon={<Add/>}>Add Answer</Button>
                            </Stack>
                        </FormFields>
                    </Collapse>


                </FormGroupOutline>
            }


        </React.Fragment>
    );
}

export default LMSQuestionForm;