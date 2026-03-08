import {IFormFieldMeta} from "../../../../../types/Form";

export enum AssessmentFormKeys {
    assessmentScript,
    assessmentInstallServer,
    assessmentQuestions,
    assessmentQuestionText,
    assessmentQuestionType,
    assessmentQuestionPointsPossible,
    assessmentQuestionAnswer,
    assessmentQuestionBonus,
    assessmentQuestionScriptAssessment,
    assessmentQuizAnswerText,
    assessmentQuizAnswerWeight
}

export type AssessmentValidationFn = (v: any, k: number, form: AssessmentForm, questionIndex: number, answerIndex: number) => null | string;

export interface AssessmentFormField extends IFormFieldMeta {
    validators: AssessmentValidationFn[];
}

export interface AssessmentForm {
    [AssessmentFormKeys.assessmentScript]: AssessmentFormField;
    [AssessmentFormKeys.assessmentInstallServer]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestions]: (LmsAssessmentFormQuestions | AssessmentFormQuestions)[]
}

export interface LmsAssessmentFormQuestions {
    [AssessmentFormKeys.assessmentQuestionText]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionType]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionBonus]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionPointsPossible]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionScriptAssessment]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionAnswer]: LMSQuestionAnswers[]
}

export interface LMSQuestionAnswers {
    [AssessmentFormKeys.assessmentQuizAnswerText]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuizAnswerWeight]: AssessmentFormField;
}

export interface AssessmentFormQuestions {
    [AssessmentFormKeys.assessmentQuestionText]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuizAnswerText]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionType]: AssessmentFormField;
    [AssessmentFormKeys.assessmentQuestionScriptAssessment]: AssessmentFormField;
}

