// Service
import {URL_COMPUTE_IMAGE_API_BASE, URL_COMPUTE_IMAGE_API_PROJECT} from "../../router/urls";
import {ImageScopes} from "../../types/BuildConstants";
import {PubSub} from "../../types/PubSub";
import {ServerMachineTypes} from "../Specification/specificationEdit.model";
import { apiService } from "../api-request.service";
import {GlobalComputeImage, ImageSummaryLists} from "./image.model";

const list = async(): Promise<ImageSummaryLists> => {
    return await apiService.get<ImageSummaryLists>(
        URL_COMPUTE_IMAGE_API_PROJECT,
        null,
        true
    );
}

const list_global = async (): Promise<GlobalComputeImage[]> => {
    return await apiService.get<GlobalComputeImage[]>(
        URL_COMPUTE_IMAGE_API_PROJECT,
        {scope: ImageScopes['GLOBAL']},
        true
    );
}

const list_machine_types = async (): Promise<ServerMachineTypes[]> => {
    return await apiService.get<ServerMachineTypes[]>(
        `${URL_COMPUTE_IMAGE_API_BASE}machine-types/`,
        null,
        true
    );
}

const post = async (data: string[], action: string): Promise<GlobalComputeImage[]> => {
    const images = JSON.stringify({images: data, action: action});

    return await apiService.post<GlobalComputeImage[]>(
        URL_COMPUTE_IMAGE_API_PROJECT,
        images,
        true,
    );
}

const sync = async (): Promise<GlobalComputeImage[]> => {
    const action = JSON.stringify({
        action: PubSub.Actions.SYNC
    });
    return await apiService.put<GlobalComputeImage[]>(
        URL_COMPUTE_IMAGE_API_PROJECT,
        action,
        true,
    )
}

export const serverService = {
    list,
    list_global,
    list_machine_types,
    post,
    sync
}
