import {FormType, ValidationFn} from "../types/Form";

export const maxLengthValidator = (maxLength: number = 255): ValidationFn => (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
    if (value.trim().length > maxLength) {
        return 'Must be less than ' + maxLength + ' characters'
    }
    return null;
};

export const minLengthValidator = (minLength: number = 0): ValidationFn => (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
    if (value.trim().length < minLength) {
        return 'Must be at least ' + minLength + ' characters'
    }
    return null;
};


export const requiredValidator: ValidationFn = (value, k, form, ...forms: FormType[]) => {
    if (!(!!value)) {
        return 'Required';
    }

    return null;
}



export const websiteValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
    const pattern = /^(ftp|http|https):\/\/[^ "]+$/;
    if (value?.trim() !== "")
        return pattern.test(value) ? null : "Invalid URL"

    return null;
}

export const requiredDateValidator: ValidationFn = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
    return value?.trim() === '' || value === '00/00/0000' ? 'Required' : null
}


export const emailValidator: ValidationFn = (value, key, form, ...forms: FormType[]) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(value)) {
        return 'Invalid email format';
    }

    return null;
};