import {WebApplication} from "../../../../../services/Specification/specification.model";
import {
    Network,
    Summary
} from "../../../../../services/Specification/specificationEdit.model";
import {UnitType} from "../../../../../types/BuildConstants";
import {createDefaultFormFieldMeta, FormType} from "../../../../../types/Form";
import {maxLengthValidator, requiredValidator} from "../../../../../utilities/formValidators";

import {
    NetworkFormKeys,
    SummaryFormKeys,
    WebApplicationFormKeys
} from "./EditorTypes";


export class EditorFormFactory {


    static generateSummaryForm(
        summary: Summary | null = null,
        unitType: UnitType = UnitType.SOLO
    ): FormType {
        return {
            [SummaryFormKeys.summaryName]: {
                ...createDefaultFormFieldMeta(
                    summary?.name || '', [requiredValidator, EditorFormFactory.summaryNameValidator])
            },
            [SummaryFormKeys.summaryDescription]: {
                ...createDefaultFormFieldMeta(summary?.description || '', [requiredValidator, maxLengthValidator(200)])
            },
            [SummaryFormKeys.summaryAuthor]: {
                ...createDefaultFormFieldMeta(summary?.author || '', [EditorFormFactory.summaryAuthorValidator])
            },
            [SummaryFormKeys.summaryTeacherInstructions]: {
                ...createDefaultFormFieldMeta(summary?.teacher_instructions_url || '')
            },
            [SummaryFormKeys.summaryStudentInstructions]: {
                ...createDefaultFormFieldMeta(summary?.student_instructions_url || '')
            },
            [SummaryFormKeys.summaryUnitType]: {
                ...createDefaultFormFieldMeta(unitType, [requiredValidator])
            },
            [SummaryFormKeys.summaryTeachingConcepts]: {
                ...createDefaultFormFieldMeta(summary?.tags || [])
            },
        }
    }

    static generateNetworkForm(networkService: Network | null = null): FormType {
        const subnet = !!networkService?.subnets?.length ? networkService.subnets[0] : null
        return {
            [NetworkFormKeys.networkName]: {
                ...createDefaultFormFieldMeta(networkService?.name || '', [requiredValidator, EditorFormFactory.networkNameValidator])
            },
            [NetworkFormKeys.networkSubnets]: {
                ...createDefaultFormFieldMeta(subnet?.ip_subnet || '', [requiredValidator, EditorFormFactory.networkIPValidator])
            },
            [NetworkFormKeys.networkPromiscuous]: {
                ...createDefaultFormFieldMeta(subnet?.promiscuous_mode || false, [])
            },
        }
    }

    static generateWebAppForm(webApplication: WebApplication | null = null): FormType {
        return {
            [WebApplicationFormKeys.webAppName]: {
                ...createDefaultFormFieldMeta(webApplication?.name || '', [requiredValidator, maxLengthValidator(60)]),
                // because we have a unique validator
            },
            [WebApplicationFormKeys.webAppHostName]: {
                ...createDefaultFormFieldMeta(webApplication?.host_name || '', [requiredValidator, EditorFormFactory.urlValidator, EditorFormFactory.webAppHostNameSlash])
            },
            [WebApplicationFormKeys.webAppStartingDirectory]: {
                ...createDefaultFormFieldMeta(webApplication?.starting_directory || '', [EditorFormFactory.webAppStartingDirectorySlash])
            }
        }
    }


    private static summaryNameValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        const pattern = /^[a-zA-Z0-9][a-zA-Z0-9: -]{0,98}[a-zA-Z0-9]$/;
        if (value?.trim() !== "")
            return pattern.test(value) ? null : "Name must start with a letter or number up to 100 letters, numbers, " +
                "dashes ('-'), colons (`:`) or spaces, and cannot end in a special character"

        return null;
    }

    private static summaryAuthorValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        const pattern = /^[a-zA-Z0-9]([a-zA-Z0-9 ]{0,48}[a-zA-Z0-9])?$/;
        if (value?.trim() !== "")
            return pattern.test(value) ? null : "Author must start and end with a letter or number, and can only contain " +
                "letters, numbers, and spaces. The total length must be between 1 and 50 characters."

        return null;
    }

    private static networkNameValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        const pattern = /^[a-z0-9-]{1,52}$/;

        if (value?.trim() !== "")
            return pattern.test(value) ? null : "Name must start with a lowercase letter followed by up to 52 lowercase letters, numbers, or hyphens, and cannot end with a hyphen"

        return null;
    }

    private static urlValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        const pattern = new RegExp('^(https?:\\/\\/)?' + // protocol
            '((([a-zA-Z\\d]([a-zA-Z\\d-]*[a-zA-Z\\d])*)\\.)+[a-zA-Z]{2,}|' + // domain name
            '((\\d{1,3}\\.){3}\\d{1,3}))' + // OR ip (v4) address
            '(\\:\\d+)?' + // port
            '(\\/[-a-zA-Z\\d%_.~+]*)*' + // path
            '(\\?[;&a-zA-Z\\d%_.~+=-]*)?' + // query string
            '(\\#[-a-zA-Z\\d_]*)?$', 'i'); // fragment locator

        if (value?.trim() !== "")
            return pattern.test(value) ? null : 'Invalid URL';

        return null;
    }

    private static networkIPValidator = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        // Define regex patterns for the valid GCP VPC IP ranges
        const privateRanges = [
            /^10\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/(?:[8-9]|[12][0-9]|3[0-2])$/,
            /^172\.(?:1[6-9]|2[0-9]|3[0-1])\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/(?:[12][0-9]|3[0-2])$/,
            /^192\.168\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.(?:[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/(?:1[6-9]|2[0-9]|3[0-2])$/
        ];

        if (value?.trim() !== "") {
            // Test the value against all the valid ranges
            const isValid = privateRanges.some(pattern => pattern.test(value));
            return isValid ? null : "Invalid IPv4 address range. Use CIDR notation and enter the lowest IPv4 address in the subnet.";
        }

        return null;
    }



    private static webAppStartingDirectorySlash = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        if (value?.trim() !== "" && !value.startsWith('/'))
            return "Must start with a /"

        return null;
    }

    private static webAppHostNameSlash = (value: string, k: keyof FormType, form: FormType, ...forms: FormType[]): string | null => {
        if (value?.trim() !== "" && value.endsWith('/'))
            return "Host name cannot end with a /"

        return null;
    }
}
