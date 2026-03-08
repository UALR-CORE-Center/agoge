import {apiService} from "../api-request.service";
import {PublishResponse, SpecificationEdit, SpecificationEditId} from "./specificationEdit.model";
import {
    transformToSpecificationEdit,
    transformToSpecificationEditId, transformToSpecificationEditList,
    transformToSpecificationPublish
} from "../../utilities/transformers/specificationEdit.transform";
import {
    URL_SPEC_API_BASE, URL_SPEC_API_EDIT,
    URL_SPEC_API_EDIT_ITEM,
    URL_SPEC_API_ITEM,
    URL_SPEC_STARTUP_SCRIPTS
} from "../../router/urls";
import {SpecificationStates} from "../../types/AgogeStates";
import formatString from "../../utilities/formatString";

const get = async (editId: string) => {
    const endpoint = formatString(URL_SPEC_API_EDIT_ITEM, {"ITEM_ID": editId});
    return await apiService.get<SpecificationEdit>(
        endpoint,
        null,
        true,
        transformToSpecificationEdit
    )
};

const list = async () => {
    return await apiService.get<SpecificationEdit[]>(
        URL_SPEC_API_EDIT,
        null,
        true,
        transformToSpecificationEditList
    )
}

const post = async (specData: { [key: string]: any }, editId: string) => {
    const endpoint = formatString(URL_SPEC_API_EDIT_ITEM, {"ITEM_ID": editId});
    return await apiService.post<SpecificationEdit>(
        endpoint,
        specData,
        true,
        transformToSpecificationEdit
    );
}

const create = async (type: SpecificationStates, specId?: string) => {
    let endpoint;
    if (type === SpecificationStates.CREATE) {
        endpoint = URL_SPEC_API_BASE;
        return await apiService.post<SpecificationEditId>(
            endpoint,
            null,
            true,
            transformToSpecificationEditId
        );
    } else if ([SpecificationStates.COPY, SpecificationStates.EDIT].includes(type)) {
        const encode = Boolean(type === SpecificationStates.COPY)
        endpoint = formatString(URL_SPEC_API_ITEM, {"ITEM_ID": specId}, encode);
        return await apiService.post<SpecificationEditId>(
            endpoint,
            {'spec_action': type.toString()},
            true,
            transformToSpecificationEditId
        );
    }
    throw new Error("Create request made with invalid type")

}


const getStartupScripts = (): Promise<string[]> => {
    return apiService.get(URL_SPEC_STARTUP_SCRIPTS);
}

const uploadStartupScript = (filename: string, file: File): Promise<string> => {
    const formData = new FormData();

    formData.append('file', file);
    formData.append('filename', filename);

    const headers = {
        'content-type': 'multipart/form-data',
    }

    return apiService.post(URL_SPEC_STARTUP_SCRIPTS, formData, true, headers);
}


const publish = async (editId: string) => {
    const endpoint = formatString(URL_SPEC_API_EDIT_ITEM, {"ITEM_ID": editId});
    return await apiService.post<PublishResponse>(
        endpoint,
        null,
        true,
        transformToSpecificationPublish
    );
}

const del = async (specId: string) => {
    const endpoint = formatString(URL_SPEC_API_EDIT_ITEM, {"ITEM_ID": specId});
    return await apiService.del(endpoint, true);
}


export const specificationEditService = {
    get,
    post,
    create,
    publish,
    getStartupScripts,
    uploadStartupScript,
    list,
    del
}