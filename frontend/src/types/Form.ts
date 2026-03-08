export type FormType = {
    [key: string]: IFormField;
};

export interface IFormField extends IFormFieldMeta {
    validators: ValidationFn[];
}


export interface IFormFieldMeta {
    value: any;
    error: null | string;
    initialized: boolean;
    extra?: any;
}


export type ValidationFn = (
    v: any,
    k: keyof FormType,
    form: FormType,
    ...forms: FormType[]
) => null | string;

export const createDefaultFormFieldMeta = (
    defaultValue: any,
    validators: ValidationFn[] = []
): IFormField => ({
    value: defaultValue,
    error: null,
    initialized: false,
    validators: validators
});

