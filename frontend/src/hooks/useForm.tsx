import {useEffect, useState} from "react";
import {FormType, IFormField, ValidationFn} from "../types/Form";


export interface IUseFormHook {
    form: FormType | undefined;
    handleInputChange: (key: keyof FormType, value: any) => void;
    handleInitialization: (localForm: FormType) => void;
    getFormField: (key: keyof FormType) => IFormField | null;
    getValue: () => object;
    hasErrors: () => boolean;
}

export const useForm = ({rawForm, initialize}: { rawForm?: FormType, initialize?: boolean }): IUseFormHook => {
    const [form, setForm] = useState(rawForm);

    useEffect(() => {
        if (initialize && !(!!rawForm)) {
            alert("Form initialized with null value")
        }

        if ((initialize == undefined || initialize) && rawForm) {
            console.log(rawForm);
            handleInitialization(rawForm);
        }

    }, []);


    const handleInitialization = (localForm: FormType) => {
        for (const key of Object.keys(localForm)) {
            localForm[key].error = handleValidation(key, localForm[key].value, localForm);
        }

        setForm(localForm)
    }


    const handleInputChange = (key: keyof FormType, value: string) => {
        if (form) {
            setForm((prevForm) => ({
                ...prevForm,
                [key]: {
                    ...prevForm![key],
                    value: value,
                    error: handleValidation(key, value, form),
                    initialized: true,
                },
            }));
        }
    }

    const getValue = (): object => {
        const obj: any = {}

        if (form) {
            for (let key of Object.keys(form)) {
                obj[key] = form[key].value
            }
        }

        return obj
    }

    const getFormField = (key: keyof FormType) => {
        if (form) {
            return form[key];
        }

        return null;
    }


    const handleValidation = (key: keyof FormType, value: any, form: FormType) => {
        let validationError: null | string = null;
        for (let validatorFn of form[key].validators) {
            validationError = validatorFn(value, key, form);

            if (validationError !== null)
                break;
        }

        return validationError;
    }


    const hasErrors = () => {
        return form ? Object.values(form).filter(v => v.error !== null).length > 0 : false
    }


    return {form, handleInputChange, handleInitialization, getValue, hasErrors, getFormField};
}

