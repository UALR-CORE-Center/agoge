import React from "react";
import {AssessmentFormCommonChildrenProps} from "./AssessmentForm";
import {
    FormCheckBox,
    FormGroup,
    FormGroupOutline,
    FormMuliTextField,
    FormRadioBtns,
    FormTextField,
    RequiredMark,
    StyledFormFieldLabel
} from "../utils/FormFields";
import {
    AssessmentQuestionType,
    LMSAssessmentQuestionType
} from "../../../../../services/Specification/specificationEdit.model";
import {AssessmentFormKeys, AssessmentFormQuestions} from "./AssessmentFormTypes";

interface Props extends AssessmentFormCommonChildrenProps {
    question: AssessmentFormQuestions
}

const AssessmentQuestionForm: React.FC<Props> = ({assessmentFormHook, question, qIndex, disableForm}: Props) => {
    const isInputQuestion =
        assessmentFormHook.getFormField(AssessmentFormKeys.assessmentQuestionType, qIndex)!.value === AssessmentQuestionType.input;
    return (
        <React.Fragment>

            <FormGroupOutline showOverlay={disableForm}> <FormGroup gap={2}>
                <FormRadioBtns
                    placeholder={"Question Type"}
                    options={[
                        {
                            label: 'auto',
                            value: AssessmentQuestionType.auto
                        },
                        {
                            label: 'input',
                            value: AssessmentQuestionType.input
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
                        disabled={disableForm}
                        helpText={"Answer is automatically assessed by the script"}
                        onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                        formKey={AssessmentFormKeys.assessmentQuestionScriptAssessment}
                        fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>
                }
            </FormGroup>
            </FormGroupOutline>


            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                <StyledFormFieldLabel>
                    Question Text{isInputQuestion && <RequiredMark/>}
                </StyledFormFieldLabel>
                <FormMuliTextField
                    required={isInputQuestion}
                    placeholder={"Question Text"}
                    rows={3}
                    disabled={disableForm}
                    onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                    formKey={AssessmentFormKeys.assessmentQuestionText}
                    fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>
            </FormGroup>
            </FormGroupOutline>

            {
                isInputQuestion &&
                <FormGroupOutline showOverlay={disableForm}>
                    <FormGroup>
                        <StyledFormFieldLabel>Question Answer<RequiredMark/></StyledFormFieldLabel>
                        <FormTextField
                            required
                            placeholder={"Question Answer"}
                            disabled={disableForm}
                            onInputChange={(field: AssessmentFormKeys, value) => assessmentFormHook.updateQuestionField(qIndex, field, value)}
                            formKey={AssessmentFormKeys.assessmentQuizAnswerText}
                            fieldFn={(k: AssessmentFormKeys) => assessmentFormHook.getFormField(k, qIndex)!}/>
                    </FormGroup>
                </FormGroupOutline>
            }

        </React.Fragment>
    );
}

export default AssessmentQuestionForm;
