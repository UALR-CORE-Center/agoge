import {Dictionary} from "../../types/Common";

export interface Doc {
    uid: string;
    instruction_type: string;
    modified: number;
    name: string;
    content: string | null;
}

export interface DocSummary {
    uid: string;
    instruction_type: string;
    name: string;
}

export interface ListofDocs {
    docs: Doc[]
}

export interface ListofDocSummaries {
    docs: DocSummary[]
}

export interface CreateDoc extends Doc {
    uid: string;
}

export interface ImageURL {
    image_url: string;
}