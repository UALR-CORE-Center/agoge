import {
    URL_SPEC_API_BASE,
    URL_SPEC_API_UPLOAD,
    URL_SPEC_API_ITEM,
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformToSpecificationList,
    transformToSpecification,
} from "../../utilities/transformers/specification.transform";
import { apiService } from "../api-request.service";
import { Specification } from "./specification.model";

const get = async (specId: string) => {
    const endpoint = formatString(URL_SPEC_API_ITEM, {"ITEM_ID": specId}, true);
    return await apiService.post<Specification>(
        endpoint,
        null,
        true,
        transformToSpecification
    )
};

const list = async () => {
    return await apiService.get<Specification[]>(
        URL_SPEC_API_BASE,
        null,
        true,
        transformToSpecificationList
    );
};

const upload = async (file: any) => {
    const headers = {
        'content-type': 'multipart/form-data',
    }
    return await apiService.post(URL_SPEC_API_UPLOAD, file,  true, headers);
}

const del = async (specId: string) => {
    const endpoint = formatString(URL_SPEC_API_ITEM, {"ITEM_ID": specId}, true);
    return await apiService.del(endpoint, true);
}

export const specificationService = {
    get,
    list,
    upload,
    del
}