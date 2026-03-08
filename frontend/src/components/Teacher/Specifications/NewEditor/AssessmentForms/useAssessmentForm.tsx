import { useEffect, useState } from "react";
import { LMSQuizAnswer } from "../../../../../services/Specification/specification.model";
import {
    Assessment,
    AssessmentQuestion,
    AssessmentQuestionType,
    LMSAssessmentQuestionType,
    LMSQuiz,
    LMSQuizQuestions
} from "../../../../../services/Specification/specificationEdit.model";
import {
    AssessmentForm,
    AssessmentFormField,
    AssessmentFormKeys,
    AssessmentFormQuestions,
    AssessmentValidationFn,
    LmsAssessmentFormQuestions,
    LMSQuestionAnswers
} from "./AssessmentFormTypes";

export interface IUseAssessmentForm {
    form: AssessmentForm | null;
    isLMS: boolean;

    hasAssessmentScript: () => boolean;
    handleInitialization: (assessment: Assessment | undefined, lmsQuiz: LMSQuiz | undefined) => void;
    render: () => Assessment | LMSQuiz;

    addQuestionAnswer: (qIndex: number) => void;
    addQuestion: () => void;
    removeQuestion: (idx: number) => void;
    removeQuestionAnswer: (qIdx: number, aIdx: number) => void;

    updateQuestionField: (qIdx: number, field: AssessmentFormKeys, value: any) => void;
    updateQuestionAnswer: (qIdx: number, aIdx: number, field: AssessmentFormKeys, value: any) => void;
    updateAssessmentField: (field: AssessmentFormKeys, value: any) => void;

    getLMSQuestionAnswers: (qIdx: number) => LMSQuestionAnswers[];
    getFormField: (field: AssessmentFormKeys, qIdx?: number, aIdx?: number) => AssessmentFormField | null;
    getQuestions: () => (LmsAssessmentFormQuestions | AssessmentFormQuestions)[];

    doesQuestionHaveAnyErrors: (qIdx: number) => boolean;
    hasErrors: () => boolean;
    isEmpty: () => boolean;
}

export const useAssessmentForm = ({
    lmsQuiz,
    assessment,
    initialize
}: {
    assessment?: Assessment;
    lmsQuiz?: LMSQuiz;
    initialize: boolean;
}): IUseAssessmentForm => {
    const [form, setForm] = useState<AssessmentForm | null>(null);
    const [isLMS, setisLMS] = useState<boolean>(false);

    useEffect(() => {
        if (initialize && !!lmsQuiz && !!assessment) {
            alert("Form initialized with null value");
        }

        if (initialize && (lmsQuiz || assessment)) {
            handleInitialization(assessment, lmsQuiz);
        }
    }, [initialize, lmsQuiz, assessment]);

    const handleInitialization = (assessment: Assessment | undefined, lmsQuiz: LMSQuiz | undefined) => {
        let rawData;
        if (assessment) {
            rawData = assessment;
            setisLMS(false);
        } else if (lmsQuiz) {
            rawData = lmsQuiz;
            setisLMS(true);
        } else {
            alert("INVALID FORM");
            return;
        }

        const thisForm: AssessmentForm = {
            [AssessmentFormKeys.assessmentScript]: createDefaultFormFieldMeta(rawData.assessment_script?.script || "", []),
            [AssessmentFormKeys.assessmentInstallServer]: createDefaultFormFieldMeta(rawData.assessment_script?.server || "", [assessmentServerRequired]),
            [AssessmentFormKeys.assessmentQuestions]: []
        };

        for (let question of (rawData?.questions || [])) {
            if (lmsQuiz) {
                thisForm[AssessmentFormKeys.assessmentQuestions].push(addLMSQuestion(question as LMSQuizQuestions));
            } else {
                question = question as AssessmentQuestion;
                thisForm[AssessmentFormKeys.assessmentQuestions].push(addAssessmentQuestion(question as AssessmentQuestion));
            }
        }

        validateEntireForm(thisForm);
        setForm(thisForm);
    };

    const validateEntireForm = (thisForm: AssessmentForm) => {
        const validateAnswerFields = (answerFields: any[], questionIndex: number) => {
            answerFields.forEach((answerField, answerIndex) => {
                Object.entries(answerField).forEach(([answerFieldKey, answerFieldMeta]) => {
                    validateFormField(answerFieldKey, answerFieldMeta as AssessmentFormField, thisForm, questionIndex, answerIndex);
                });
            });
        };

        const validateQuestionFields = (question: any, questionIndex: number) => {
            Object.entries(question).forEach(([key, field]) => {
                if (Array.isArray(field)) {
                    validateAnswerFields(field, questionIndex);
                } else {
                    validateFormField(key, field as AssessmentFormField, thisForm, questionIndex, -1);
                }
            });
        };

        const validateFields = () => {
            Object.entries(thisForm).forEach(([key, field]) => {
                if (!Array.isArray(field)) {
                    validateFormField(key, field, thisForm, -1, -1);
                } else {
                    const questions = thisForm[AssessmentFormKeys.assessmentQuestions];
                    questions.forEach((question, questionIndex) => {
                        validateQuestionFields(question, questionIndex);
                    });
                }
            });
        };

        validateFields();
    };

    const validateFormField = (
        key: any,
        formField: AssessmentFormField,
        thisForm: AssessmentForm,
        qIdx: number,
        aIdx: number
    ): void => {
        formField.error = null;

        // Check if the question index exists before proceeding
        if (qIdx < 0 || qIdx >= thisForm[AssessmentFormKeys.assessmentQuestions].length) {
            return;
        }

        const question = thisForm[AssessmentFormKeys.assessmentQuestions][qIdx];
        const questionType = question[AssessmentFormKeys.assessmentQuestionType].value;

        // Skip validation for question answer if the question type is 'auto'
        if (questionType === AssessmentQuestionType.auto || questionType === LMSAssessmentQuestionType.auto) {
            return;
        }

        // Run through validators if necessary
        for (const validatorFn of formField.validators) {
            const error = validatorFn(formField.value, key, thisForm, qIdx, aIdx);
            if (error !== null) {
                formField.error = error;
                break;
            }
        }
    };

    const addAssessmentQuestion = (question: AssessmentQuestion | null = null): AssessmentFormQuestions => {
        return {
            [AssessmentFormKeys.assessmentQuestionText]: createDefaultFormFieldMeta(question?.question || "", [questionAnswerRequiredValidator]),
            [AssessmentFormKeys.assessmentQuizAnswerText]: createDefaultFormFieldMeta(question?.answer || "", [requiredValidator]),
            [AssessmentFormKeys.assessmentQuestionScriptAssessment]: createDefaultFormFieldMeta(question?.script_assessment || false, []),
            [AssessmentFormKeys.assessmentQuestionType]: createDefaultFormFieldMeta((question?.type || "") as AssessmentQuestionType, [])
        };
    };

    const addLMSQuestion = (question: LMSQuizQuestions | null = null): LmsAssessmentFormQuestions => {
        const formQuestion: LmsAssessmentFormQuestions = {
            [AssessmentFormKeys.assessmentQuestionText]: createDefaultFormFieldMeta(question?.question_text || "", [requiredValidator]),
            [AssessmentFormKeys.assessmentQuestionType]: createDefaultFormFieldMeta((question?.question_type || "") as LMSAssessmentQuestionType, []),
            [AssessmentFormKeys.assessmentQuestionBonus]: createDefaultFormFieldMeta(question?.bonus || false, []),
            [AssessmentFormKeys.assessmentQuestionScriptAssessment]: createDefaultFormFieldMeta(question?.script_assessment || false, []),
            [AssessmentFormKeys.assessmentQuestionPointsPossible]: createDefaultFormFieldMeta(question?.points_possible || 0, []),
            [AssessmentFormKeys.assessmentQuestionAnswer]: []
        };

        for (let answer of (question?.answers || [])) {
            formQuestion[AssessmentFormKeys.assessmentQuestionAnswer].push(
                addLMSQuestionAnswer(answer)
            );
        }

        return formQuestion;
    };

    const addLMSQuestionAnswer = (answer: LMSQuizAnswer | null = null, validate = false) => {
        const qa = {
            [AssessmentFormKeys.assessmentQuizAnswerText]: createDefaultFormFieldMeta(answer?.answer_text || "", [questionAnswerRequiredValidator]),
            [AssessmentFormKeys.assessmentQuizAnswerWeight]: createDefaultFormFieldMeta(answer?.weight || 0, [questionAnswerRequiredValidator])
        };

        if (validate) {
            let qIndex = 0;
            for (const [k, v] of Object.entries(qa)) {
                validateFormField(k, v, form!, qIndex, -1);
            }
        }

        return qa;
    };

    const removeQuestion = (questionIndex: number) => {
        const copyOfQ = [...form![AssessmentFormKeys.assessmentQuestions]];
        copyOfQ.splice(questionIndex, 1);
        setForm({
            ...form!,
            [AssessmentFormKeys.assessmentQuestions]: copyOfQ
        });
    };

    const removeQuestionAnswer = (questionIdx: number, answerIdx: number) => {
        if (isLMS) {
            const copyOfQ = [...form![AssessmentFormKeys.assessmentQuestions]];
            const thisFormQ = copyOfQ[questionIdx] as LmsAssessmentFormQuestions;
            const answers = [...thisFormQ[AssessmentFormKeys.assessmentQuestionAnswer]];

            answers.splice(answerIdx, 1);
            thisFormQ[AssessmentFormKeys.assessmentQuestionAnswer] = answers;
            setForm({
                ...form!,
                [AssessmentFormKeys.assessmentQuestions]: copyOfQ
            });
        }
    };

    const addQuestion = () => {
        let newQ = isLMS ? addLMSQuestion() : addAssessmentQuestion();
        const copyOfQs = [...form![AssessmentFormKeys.assessmentQuestions], newQ];

        if (hasAssessmentScript()) {
            newQ[AssessmentFormKeys.assessmentQuestionType].value =
                isLMS ? LMSAssessmentQuestionType.auto : AssessmentQuestionType.auto;
        } else {
            const values = Object.values(isLMS ? LMSAssessmentQuestionType : AssessmentQuestionType).filter(
                (v) => v !== (isLMS ? LMSAssessmentQuestionType.auto : AssessmentQuestionType.auto)
            );

            newQ[AssessmentFormKeys.assessmentQuestionType].value = values[0];
            if (isLMS) {
                newQ = newQ as LmsAssessmentFormQuestions;
                newQ[AssessmentFormKeys.assessmentQuestionAnswer] = [addLMSQuestionAnswer(null, true)];
            }
        }

        const copyOfForm = {
            ...form!,
            [AssessmentFormKeys.assessmentQuestions]: copyOfQs
        };

        reValidateQuestion(newQ, copyOfQs.length - 1, copyOfForm);
        setForm(copyOfForm);
    };

    const reValidateQuestion = (
        question: LmsAssessmentFormQuestions | AssessmentFormQuestions,
        qIdx: number,
        thisForm?: AssessmentForm
    ) => {
        let hasError = false;
        if (isLMS) {
            for (const answer of (question as LmsAssessmentFormQuestions)[AssessmentFormKeys.assessmentQuestionAnswer]) {
                for (const [ak, av] of Object.entries(answer)) {
                    validateFormField(ak, av, (thisForm || form)!, qIdx, -1);
                    if (av.error !== null) {
                        hasError = true;
                    }
                }
            }
        } else {
            validateFormField(
                AssessmentFormKeys.assessmentQuizAnswerText,
                (question as AssessmentFormQuestions)[AssessmentFormKeys.assessmentQuizAnswerText],
                (thisForm || form)!,
                qIdx,
                -1
            );

            if ((question as AssessmentFormQuestions)[AssessmentFormKeys.assessmentQuizAnswerText].error !== null) {
                hasError = true;
            }
        }

        return hasError;
    };

    const updateQuestionField = (qIdx: number, field: AssessmentFormKeys, value: any): void => {
        const copyOfQs = [...form![AssessmentFormKeys.assessmentQuestions]];
        const question = { ...copyOfQs[qIdx] };
        copyOfQs[qIdx] = question;

        if (field in question && field !== AssessmentFormKeys.assessmentQuestionAnswer) {
            // Update the form field value
            question[field as keyof typeof question] = {
                ...question[field as keyof typeof question],
                value: value
            } as AssessmentFormField;

            // Update question type based on script assessment checkbox
            if (field === AssessmentFormKeys.assessmentQuestionScriptAssessment && hasAssessmentScript()) {
                const questionTypeValue = value
                    ? (isLMS ? LMSAssessmentQuestionType.auto : AssessmentQuestionType.auto)
                    : (isLMS ? LMSAssessmentQuestionType.shortAnswer : AssessmentQuestionType.input);

                question[AssessmentFormKeys.assessmentQuestionType] = {
                    ...question[AssessmentFormKeys.assessmentQuestionType],
                    value: questionTypeValue
                };
            }

            // Update form state
            const updatedForm = {
                ...form!,
                [AssessmentFormKeys.assessmentQuestions]: copyOfQs
            };
            setForm(updatedForm);

            // Validate the form field after updating the form state
            validateFormField(field, question[field as keyof typeof question], updatedForm, qIdx, -1);

            // Revalidate the entire question if necessary
            if (
                field === AssessmentFormKeys.assessmentQuestionType ||
                field === AssessmentFormKeys.assessmentQuestionScriptAssessment
            ) {
                reValidateQuestion(question, qIdx, updatedForm);
            }
        } else {
            throw new Error("Unknown field on object: " + field);
        }
    };

    const doesQuestionHaveAnyErrors = (qIdx: number): boolean => {
        return reValidateQuestion({ ...form![AssessmentFormKeys.assessmentQuestions][qIdx] }, qIdx);
    };

    const updateQuestionAnswer = (qIdx: number, aIdx: number, field: number, value: any): void => {
        const copyOfQs = [...form![AssessmentFormKeys.assessmentQuestions]] as LmsAssessmentFormQuestions[];
        const copyOfQAs = [...copyOfQs[qIdx][AssessmentFormKeys.assessmentQuestionAnswer]] as LMSQuestionAnswers[];
        const copyOfAnswer: LMSQuestionAnswers = { ...copyOfQAs[aIdx] };

        if (field === AssessmentFormKeys.assessmentQuizAnswerText || field === AssessmentFormKeys.assessmentQuizAnswerWeight) {
            const errors = copyOfAnswer[field].validators
                .map((validatorFn: AssessmentValidationFn) =>
                    validatorFn(value, field as keyof LMSQuestionAnswers, form!, qIdx, aIdx)
                )
                .filter((err) => err !== null);

            copyOfAnswer[field].value = value;
            copyOfAnswer[field].error = errors.length > 0 ? errors[0] : null;

            copyOfQAs[aIdx] = copyOfAnswer;
            copyOfQs[qIdx][AssessmentFormKeys.assessmentQuestionAnswer] = copyOfQAs;
            setForm({
                ...form!,
                [AssessmentFormKeys.assessmentQuestions]: copyOfQs
            });
        }
    };

    const updateAssessmentField = (field: AssessmentFormKeys, value: string): void => {
        if (field == AssessmentFormKeys.assessmentScript) {
            const copyOfQs = [...form![AssessmentFormKeys.assessmentQuestions]];
            for (let qIdx in copyOfQs) {
                let copy = { ...copyOfQs[qIdx] };

                // just in-case the naming changes in the future
                if (isLMS) {
                    copy = copy as LmsAssessmentFormQuestions;
                    copy[AssessmentFormKeys.assessmentQuestionType].value = !!value
                        ? LMSAssessmentQuestionType.auto
                        : LMSAssessmentQuestionType.shortAnswer;
                    copy[AssessmentFormKeys.assessmentQuestionScriptAssessment].value = !!value;

                    reValidateQuestion(copy, parseInt(qIdx));
                } else {
                    copy = copy as AssessmentFormQuestions;
                    copy[AssessmentFormKeys.assessmentQuestionType].value = !!value
                        ? AssessmentQuestionType.auto
                        : AssessmentQuestionType.input;
                    copy[AssessmentFormKeys.assessmentQuestionScriptAssessment].value = !!value;

                    reValidateQuestion(copy, parseInt(qIdx));
                }
                copyOfQs[qIdx] = copy;
            }

            const updatedForm = {
                ...form!,
                [AssessmentFormKeys.assessmentQuestions]: copyOfQs,
                [AssessmentFormKeys.assessmentScript]: {
                    ...form![AssessmentFormKeys.assessmentScript],
                    value: value
                },
                [AssessmentFormKeys.assessmentInstallServer]: {
                    ...form![AssessmentFormKeys.assessmentInstallServer]
                }
            };

            validateFormField(
                AssessmentFormKeys.assessmentInstallServer,
                updatedForm[AssessmentFormKeys.assessmentInstallServer],
                updatedForm,
                -1,
                -1
            );
            setForm(updatedForm);
        } else {
            const updateField = {
                ...form![field as AssessmentFormKeys.assessmentInstallServer],
                value: value
            };

            validateFormField(AssessmentFormKeys.assessmentInstallServer, updateField, form!, -1, -1);
            setForm({
                ...form!,
                [field]: updateField
            });
        }
    };

    const getFormField = (
        field: AssessmentFormKeys,
        qIdx: number = -1,
        aIdx: number = -1
    ): AssessmentFormField | null => {
        let level: any = form!;
        if (level) {
            if (qIdx !== -1) {
                level = level[AssessmentFormKeys.assessmentQuestions][qIdx];
                if (aIdx !== -1) {
                    level = level as LmsAssessmentFormQuestions;
                    return level[AssessmentFormKeys.assessmentQuestionAnswer][aIdx][field];
                }
            }

            return level[field];
        }

        return null;
    };

    const getQuestions = (): (LmsAssessmentFormQuestions | AssessmentFormQuestions)[] => {
        if (form) {
            return form[AssessmentFormKeys.assessmentQuestions];
        }

        return [];
    };

    const getLMSQuestionAnswers = (qIdx: number): LMSQuestionAnswers[] => {
        return (form![AssessmentFormKeys.assessmentQuestions][qIdx] as LmsAssessmentFormQuestions)[AssessmentFormKeys.assessmentQuestionAnswer];
    };

    const render = (): Assessment | LMSQuiz => {
        const serialized: Assessment | LMSQuiz = {
            assessment_script: {
                script: form![AssessmentFormKeys.assessmentScript].value,
                server: form![AssessmentFormKeys.assessmentInstallServer].value
            },
            questions: []
        };

        for (let questionField of form![AssessmentFormKeys.assessmentQuestions]) {
            if (isLMS) {
                questionField = questionField as LmsAssessmentFormQuestions;
                const questionType: LMSAssessmentQuestionType = questionField[AssessmentFormKeys.assessmentQuestionType].value;
                const serializedQ: LMSQuizQuestions = {
                    question_text: questionField[AssessmentFormKeys.assessmentQuestionText].value,
                    question_type: questionType,
                    points_possible: questionField[AssessmentFormKeys.assessmentQuestionPointsPossible].value,
                    script_assessment: hasAssessmentScript() && questionType === LMSAssessmentQuestionType.auto,
                    bonus: questionField[AssessmentFormKeys.assessmentQuestionBonus].value,
                    answers: []
                };

                if (questionType !== LMSAssessmentQuestionType.auto) {
                    for (const answerField of questionField[AssessmentFormKeys.assessmentQuestionAnswer]) {
                        serializedQ.answers!.push({
                            answer_text: answerField[AssessmentFormKeys.assessmentQuizAnswerText].value,
                            weight: answerField[AssessmentFormKeys.assessmentQuizAnswerWeight].value
                        });
                    }
                }

                (serialized as LMSQuiz).questions!.push(serializedQ);
            } else {
                questionField = questionField as AssessmentFormQuestions;
                const questionType: AssessmentQuestionType = questionField[AssessmentFormKeys.assessmentQuestionType].value;
                (serialized as Assessment).questions!.push({
                    type: questionType,
                    question: questionField[AssessmentFormKeys.assessmentQuestionText].value,
                    script_assessment: hasAssessmentScript() && questionType === AssessmentQuestionType.auto,
                    answer: questionType === AssessmentQuestionType.auto ? null : questionField[AssessmentFormKeys.assessmentQuizAnswerText].value
                });
            }
        }

        return serialized;
    };

    const addQuestionAnswer = (qIndex: number) => {
        const copyOfQs = [...form![AssessmentFormKeys.assessmentQuestions]];
        const newAnswer = addLMSQuestionAnswer(null, true);

        copyOfQs[qIndex] = {
            ...(copyOfQs[qIndex] as LmsAssessmentFormQuestions),
            [AssessmentFormKeys.assessmentQuestionAnswer]: [
                ...(copyOfQs[qIndex] as LmsAssessmentFormQuestions)[AssessmentFormKeys.assessmentQuestionAnswer],
                newAnswer
            ]
        };

        // Update the form state
        setForm({
            ...form!,
            [AssessmentFormKeys.assessmentQuestions]: copyOfQs
        });
    };

    const createDefaultFormFieldMeta = (defaultValue: any, validators: AssessmentValidationFn[] = []): AssessmentFormField => ({
        value: defaultValue,
        error: null,
        initialized: false,
        validators: validators
    });

    const questionAnswerRequiredValidator = (
        v: any,
        k: keyof AssessmentForm,
        form: AssessmentForm,
        qIdx?: number,
        answerIndex?: number
    ): string | null => {
        const question = form[AssessmentFormKeys.assessmentQuestions][qIdx!];
        const qType = question[AssessmentFormKeys.assessmentQuestionType].value;

        // If the question is of type auto, question answer is not required
        if (qType === AssessmentQuestionType.auto || qType === LMSAssessmentQuestionType.auto) {
            return null;
        }

        // If the question is of type input or short answer, validate the answer as normal
        if (qType === AssessmentQuestionType.input || qType === LMSAssessmentQuestionType.shortAnswer) {
            if (typeof v === "string" && v.trim() === "") {
                return "Required";
            }
        }

        return null;
    };

    const requiredValidator = (
        v: string,
        k: keyof AssessmentForm,
        form: AssessmentForm,
        questionIndex?: number,
        answerIndex?: number
    ): string | null => {
        if (v.trim() === "") {
            return "Required";
        }

        return null;
    };

    const assessmentServerRequired = (
        v: string,
        k: keyof AssessmentForm,
        thisForm: AssessmentForm,
        questionIndex?: number,
        answerIndex?: number
    ): string | null => {
        if (hasAssessmentScript(thisForm) && !(!!v)) {
            return "Required";
        }

        return null;
    };

    const hasAssessmentScript = (localForm: AssessmentForm | null = null): boolean => {
        let thisForm = localForm || form;
        return !!(thisForm ? thisForm![AssessmentFormKeys.assessmentScript].value : null);
    };

    const hasErrors = () => {
        const scriptField = getFormField(AssessmentFormKeys.assessmentScript);
        const serverField = getFormField(AssessmentFormKeys.assessmentInstallServer);

        if (scriptField?.error !== null || serverField?.error !== null) {
            return true;
        }

        const qs = getQuestions();
        for (let i = 0; i < qs.length; i++) {
            if (doesQuestionHaveAnyErrors(i)) {
                return true;
            }
        }

        return false;
    };

    const isEmpty = () => {
        return getQuestions().length === 0;
    }

    return {
        form,
        handleInitialization,
        render,
        addQuestion,
        removeQuestion,
        removeQuestionAnswer,
        updateQuestionField,
        updateQuestionAnswer,
        updateAssessmentField,
        getFormField,
        isLMS,
        getLMSQuestionAnswers,
        addQuestionAnswer,
        doesQuestionHaveAnyErrors,
        hasAssessmentScript,
        getQuestions,
        hasErrors,
        isEmpty,
    };
};
