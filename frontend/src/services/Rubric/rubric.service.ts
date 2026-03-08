import {URL_RUBRIC_API_GENERATE, URL_RUBRIC_API_ITEM} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {transformToRubric} from "../../utilities/transformers/rubric.transform";
import {apiService} from "../api-request.service";
import {Rubric} from "./rubric.model";


const get = async (buildId: string) => {
    const endpoint = formatString(URL_RUBRIC_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.get<Rubric>(endpoint,null,true,transformToRubric);
}

const patch = async (buildId: string, formData: { [key: string]: any }) => {
    const endpoint = formatString(URL_RUBRIC_API_ITEM, { "ITEM_ID": buildId });
    return await apiService.patch(endpoint, formData, true);
};

const generate_rubric = async (buildId: string, rubricParams: any) => {
    const endpoint = formatString(URL_RUBRIC_API_GENERATE, { "BUILD_ID": buildId });
    return await apiService.post<Rubric>(endpoint, rubricParams, true, transformToRubric);
};

export const rubricService = {
    get,
    generate_rubric,
    patch
}