import {Doc, DocSummary, ImageURL, ListofDocs, ListofDocSummaries} from "../../services/Documents/docs.model";

export const transformToDoc = (data: any): Doc => {
    return {
        uid: data.uid,
        instruction_type: data.instructions_type,
        modified: data.modified,
        name: data.name,
        content: data.content
    };
};

export const transformToDocSummary = (data: any): DocSummary => {
    return{
        uid: data.uid,
        instruction_type: data.instructions_type,
        name: data.name
    };
};

export const transformToDocsList = (data: any): ListofDocs => {
    return {
        docs: data.map(transformToDoc)
    };
};

export const transformToDocSumList = (data: any): ListofDocSummaries => {
    return {
        docs: data.map(transformToDocSummary)
    };
};

export const transformToImageURL = (data: any): ImageURL => {
    return {
        image_url: data.image_url
    };
};