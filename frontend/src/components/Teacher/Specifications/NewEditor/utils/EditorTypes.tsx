import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";

export enum SummaryFormKeys {
    summaryName,
    summaryDescription,
    summaryTeacherInstructions,
    summaryStudentInstructions,

    summaryAuthor,
    summaryUnitType,
    summaryTeachingConcepts
}

export enum NetworkFormKeys {
    networkName,
    networkSubnets,
    networkPromiscuous
}

export enum WebApplicationFormKeys {
    webAppName,
    webAppHostName,
    webAppStartingDirectory
}


export interface CommonEditorChildrenProps {
    specification: { pending: boolean, data: SpecificationEdit | null }
    disableForm: boolean;
}


// Change the order of these to change
// the order the forms are rendered
export enum EditorForms {
    Summary = "Lab Summary",
    Networks = "Networks",
    Servers = "Servers",
    WebApplications = 'Web Applications',
    Assessment = 'Assessment',
    Review = 'Review'
}





