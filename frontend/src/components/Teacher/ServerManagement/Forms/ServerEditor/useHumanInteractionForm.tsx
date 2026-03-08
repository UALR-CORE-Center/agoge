import {useEffect, useState} from "react";
import {HumanInteraction} from "../../../../../services/Specification/specificationEdit.model";
import {FormType, IFormFieldMeta, ValidationFn} from "../../../../../types/Form";
import {createDefaultFormFieldMeta} from "../../../../../types/Form";
import {Protocols, SecurityModes} from "../../../../../types/Guacamole";
import {maxLengthValidator} from "../../../../../utilities/formValidators";
import {IHumanInteractionForm, IHumanInteractionFormKeys} from "../FormFields";

export interface IUseHumanInteractionForm {
    forms: IHumanInteractionForm[]
    handleInitialization: (hInteractions: HumanInteraction[]) => void;

    addInteraction: () => void;
    removeInteraction: (idx: number) => void;

    handleInteractionValueChange: (k: keyof IHumanInteractionForm, value: any, idx: number) => void;

    hasErrors: () => boolean;
    doesInteractionHaveErrors: (idx: number) => boolean;

    getField: (key: (keyof IHumanInteractionForm), idx: number) => IFormFieldMeta;
    isEmpty: () => boolean;

    render: () => HumanInteraction[];
}

export const useHumanInteractionForm = (
    {rawData, initialize}: { rawData?: HumanInteraction[], initialize: boolean }
): IUseHumanInteractionForm => {
    const [forms, setForms] = useState<IHumanInteractionForm[]>([]);

    useEffect(() => {
        if (initialize && !!rawData) {
            alert("Form initialized with null value");
        }

        if (initialize && rawData) {
            handleInitialization(rawData);
        }

    }, [initialize, rawData]);

    const handleInitialization = (hInteractions: HumanInteraction[]): void => {
        const initializeForms: IHumanInteractionForm[] = [];
        for (const interaction of hInteractions || []) {
            initializeForms.push(createInteraction(interaction));
        }
        setForms(initializeForms);
    }

    const createInteraction = (
        hInteraction: HumanInteraction | null = null
    ): IHumanInteractionForm => {
        const localForm: IHumanInteractionForm = {
            [IHumanInteractionFormKeys.DISPLAY]: {
                ...createDefaultFormFieldMeta(hInteraction?.display || false)
            },
            [IHumanInteractionFormKeys.PASSWORD]: {
                ...createDefaultFormFieldMeta(hInteraction?.password || '', [maxLengthValidator(200)])
            },
            [IHumanInteractionFormKeys.PROTOCOL]: {
                ...createDefaultFormFieldMeta(hInteraction?.protocol || Protocols.SSH)
            },
            [IHumanInteractionFormKeys.SECURITY_MODE]: {
                ...createDefaultFormFieldMeta(hInteraction?.security_mode || SecurityModes.ANY)
            },
            [IHumanInteractionFormKeys.SSH_KEY]: {
                ...createDefaultFormFieldMeta(hInteraction?.ssh_key || '')
            },
            [IHumanInteractionFormKeys.USERNAME]: {
                ...createDefaultFormFieldMeta(hInteraction?.username || 'pantheon', [maxLengthValidator(20), validateAuthor])
            }
        }
        for (const key of Object.keys(localForm)) {
            localForm[key].error = handleValidation(
                key as keyof IHumanInteractionForm,
                localForm[key].value,
                localForm
            );
        }

        return localForm;
    }

    const addInteraction = () => {
        const newInteraction = createInteraction();
        setForms([...forms, newInteraction]);
    }

    const removeInteraction = (idx: number) => {
        const copy = [...forms];
        copy.splice(idx, 1);
        setForms(copy);
    }

    const handleInteractionValueChange = (
        key: keyof IHumanInteractionForm,
        value: any,
        idx: number
    ): void => {
        const copyOfForms = [...forms];
        copyOfForms[idx] = {
            ...copyOfForms[idx],
            [key]: {
                ...copyOfForms[idx][key],
                value: value,
                error: handleValidation(key, value, copyOfForms[idx])
            },
        };
        setForms(copyOfForms);
    }

    const hasErrors = (): boolean => {
        return false;
    }

    const doesInteractionHaveErrors = (idx: number): boolean => {
        return Object.values(forms[idx]).some((f) => 'error' in f && f.error);
    }

    const getField = (
        key: (keyof IHumanInteractionForm),
        idx: number
    ): IFormFieldMeta => {
        const level: IHumanInteractionForm = forms[idx];

        return level[key as keyof IHumanInteractionForm] as IFormFieldMeta;
    }

    const isEmpty = (): boolean => {
        return forms.length === 0;
    }

    const handleValidation = (key: keyof IHumanInteractionForm, value: any, form: IHumanInteractionForm) => {
        let validationError: null | string = null;
        for (let validatorFn of form[key].validators) {
            validationError = validatorFn(value, key, form);

            if (validationError !== null)
                break;
        }

        return validationError;
    }

    const validateAuthor: ValidationFn = (value, k, form, ...forms: FormType[]) => {
        const usernameRegex = /^[a-zA-Z0-9_]([a-zA-Z0-9_.-]{0,18}[a-zA-Z0-9_]?)?$/;
        if (!usernameRegex.test(value)) {
            return "Invalid username. Please use only letters, numbers, underscores, " +
                "periods, or hyphens. Your username must be between 3 and 20 characters long and cannot start " +
                "or end with a period or space."
        }
        return null;
    }

    const render = (): HumanInteraction[] => {
        const interactionValues: HumanInteraction[] = [];
        for (const form of forms!) {
            const interactionValue: HumanInteraction = {
                'display': form[IHumanInteractionFormKeys.DISPLAY].value || false,
                'password': form[IHumanInteractionFormKeys.PASSWORD].value || "",
                'protocol': form[IHumanInteractionFormKeys.PROTOCOL].value,
                'security_mode': form[IHumanInteractionFormKeys.SECURITY_MODE].value,
                'username': form[IHumanInteractionFormKeys.USERNAME].value || "pantheon",
                'ssh_key': form[IHumanInteractionFormKeys.SSH_KEY].value || ""
            }
            interactionValues.push(interactionValue);
        }
        return interactionValues;
    }

    return {
        forms,
        handleInitialization,
        addInteraction,
        removeInteraction,
        handleInteractionValueChange,
        hasErrors,
        doesInteractionHaveErrors,
        getField,
        isEmpty,
        render,
    }
}