import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {UnitType} from "../../../../../types/BuildConstants";

// Editor-only unit type: a CTF lab is saved as a solo unit carrying a ctf block.
export const CTF_UNIT_TYPE = 'ctf';
export type EditorUnitType = UnitType | typeof CTF_UNIT_TYPE;
export const EDITOR_UNIT_TYPES: EditorUnitType[] = [...Object.values(UnitType), CTF_UNIT_TYPE];

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
    // Shown only when the unit type is CTF; after Servers so flags can pick a server.
    Ctf = "CTF",
    WebApplications = 'Web Applications',
    Assessment = 'Assessment',
    Review = 'Review'
}





