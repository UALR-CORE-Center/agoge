import {
    URL_DOCS_INSTRUCTIONS_API_BASE,
    URL_DOCS_INSTRUCTIONS_API_ITEM, URL_DOCS_INSTRUCTIONS_IMAGES
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformToDoc, transformToDocsList,
    transformToDocSumList,
    transformToImageURL
} from "../../utilities/transformers/docs.transform";
import {apiService} from "../api-request.service";
import {CreateDoc, Doc, ImageURL, ListofDocs, ListofDocSummaries} from "./docs.model";


export const create = async (filename:string,instruction_type:string) => {
    const formData = new FormData();
    formData.append('filename',filename);
    formData.append('instructions_type',instruction_type);
    return await apiService.post<CreateDoc>(URL_DOCS_INSTRUCTIONS_API_BASE,formData,true,transformToDoc);
}

export const save = async (uid: string, file_content: string, instructions_type: string, file_name?: string) => {
    const endpoint = formatString(URL_DOCS_INSTRUCTIONS_API_ITEM, {"ITEM_ID": uid});
    const payload = {
        'uid': uid,
        'file':file_content,
        'filename': file_name,
        'instructions_type': instructions_type
    }
    return await apiService.post<Doc>(endpoint,payload,true, transformToDoc);
}

export const get_list_full = async () => {
    return await apiService.get<ListofDocs>(`${URL_DOCS_INSTRUCTIONS_API_BASE}full`, null, true, transformToDocsList);
}

export const get_list = async () => {
    return await apiService.get<ListofDocSummaries>(URL_DOCS_INSTRUCTIONS_API_BASE, null, true, transformToDocSumList);
}

export const get_instruction = async(uid: string) => {
    const endpoint = formatString(URL_DOCS_INSTRUCTIONS_API_ITEM, {"ITEM_ID": uid});
    return await apiService.get<Doc>(endpoint,null,true,transformToDoc);
}

export const post_image = async (image: File, instructionsType: "student" | "teacher") => {
    const formData = new FormData();
    formData.append('file', image);
    formData.append('instructions_type', instructionsType);
    const headers = {
        'Content-Type': 'multipart/form-data',
    };
    return await apiService.post<ImageURL>(URL_DOCS_INSTRUCTIONS_IMAGES, formData, true, headers, transformToImageURL);
}
export const docsService = {
    create,
    get_instruction,
    get_list,
    get_list_full,
    post_image,
    save
}