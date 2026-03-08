import {useCallback, useEffect, useMemo, useState} from "react";
import {IFormFieldMeta, FormType, ValidationFn} from "../types/Form";


export interface UseFormsHook {
    forms: FormType[] | null;
    handleInputChange: (key: keyof FormType, value: any, formIndex: number) => void;
    handleInitialization: (localForm: FormType[]) => void;
    getValue: () => object[];
    setErrors: (key: keyof FormType, errorMsgs: (string | null)[], formIndexes: number[]) => void;
    addForm: (form: FormType) => void;
    replaceForms: (forms: FormType[]) => void;
    removeForm: (formIndex: number) => void;

    doesFormHaveErrors: (formIndex: number) => boolean;

    hasErrors: () => boolean;
}

export const useForms = ({rawForm, initialize}: { rawForm?: FormType[], initialize: boolean }): UseFormsHook => {
    const [forms, setForms] = useState(rawForm || []);


    useEffect(() => {
        if (initialize && !!rawForm) {
            alert("Form initialized with null value")
        }

        if (initialize && rawForm) {
            handleInitialization(rawForm);
        }

    }, []);


    const handleInitialization = (localForms: FormType[]) => {
        for (let localForm of localForms) {
            for (const key of Object.keys(localForm)) {
                localForm[key].error = handleValidation(key, localForm[key].value, localForm, localForms);
            }
        }

        setForms(localForms)
    }


    const handleInputChange = (key: keyof FormType, value: string, formIndex: number) => {
        // todo I think that weird bug is happening here
        // right on refresh - when any form field is changed it gets cleared
        if (forms) {
            const copyOfForms = [...forms];
            const updatedForm = {
                ...copyOfForms[formIndex],
                [key]: {
                    ...copyOfForms[formIndex][key],
                    value: value,
                    initialized: true
                }
            }

            copyOfForms.splice(formIndex, 1, updatedForm);
            updatedForm[key].error = handleValidation(key, value, updatedForm, copyOfForms);
            setForms(copyOfForms)
        }
    }

    const handleValidation = (key: keyof FormType, value: any, form: FormType, updatedForms: FormType[]) => {
        let validationError: null | string = null;
        for (let validatorFn of form[key].validators) {
            validationError = validatorFn(value, key, form, ...(updatedForms || []));
            if (validationError !== null)
                break;
        }

        return validationError;
    }


    const getValue = () => {
        return [];
    }


    const addForm = (localForm: FormType, validate = true) => {
        if (validate) {
            handleInitialization([...forms, localForm])
        } else {
            setForms([...forms, localForm])
        }
    }

    const replaceForms = (localForms: FormType[]) => {
        setForms(localForms);
    }

    const removeForm = (formIndex: number) => {
        setForms(forms.filter((f, i) => i !== formIndex));
    }

    const setErrors = (key: keyof FormType, errorMsgs: (string | null)[], formIndexes: number[]): void => {
        if (errorMsgs.length !== formIndexes.length) {
            throw Error("Error Messages and FormIndexes must be the same size");
        }


        if (formIndexes.length == 0)
            return;

        const copyOfForms = [...forms];
        if (formIndexes.length) {
            for (const formIndex of formIndexes) {
                const copyOfForm = {...copyOfForms[formIndex]};
                copyOfForm[key].error = errorMsgs[formIndex]
            }
        }

        setForms(copyOfForms);
    }


    const doesFormHaveErrors = (index: number) => {
        return Object.values(forms[index]).filter(f => f.error !== null).length > 0;
    }


    const hasErrors = () => {
        for (let i = 0; i < forms.length - 1; i++) {
            if (doesFormHaveErrors(i)) {
                return true;
            }
        }

        return false;
    }


    return {
        forms,
        handleInputChange,
        handleInitialization,
        getValue,
        addForm,
        removeForm,
        replaceForms,
        setErrors,
        doesFormHaveErrors,
        hasErrors
    };
}

