import {
    URL_COMPUTE_IMAGE_API_BASE,
    URL_COMPUTE_IMAGE_API_CREATE,
    URL_COMPUTE_IMAGE_API_ITEM,
} from "../../router/urls";
import {PubSub} from "../../types/PubSub";
import formatString from "../../utilities/formatString";
import {transformToAgogeImage, transformToAgogeImageList} from "../../utilities/transformers/image.transform";
import { apiService } from "../api-request.service";
import {AgogeImage} from "./image.model";

const list = async() =>{
    return await apiService.get<AgogeImage[]>(
        URL_COMPUTE_IMAGE_API_BASE,
        null,
        true,
        transformToAgogeImageList
    );
}

const get = async (imageName: string) => {
    const endpoint = formatString(URL_COMPUTE_IMAGE_API_ITEM, {"ITEM_ID": imageName})
    return await apiService.get<AgogeImage>(endpoint,null,true, transformToAgogeImage);
}

const post_action = async (images: AgogeImage[], action: string) => {
    const postData = JSON.stringify({
        "images": images,
        'action': action,
    });
    return await apiService.post<AgogeImage>(
        URL_COMPUTE_IMAGE_API_BASE,
        postData,
        true,
        transformToAgogeImage
    );
}

const create = async (image: { [p: string]: string | File }) => {
    image['action'] = PubSub.Actions.BUILD.toString();
    const postData = JSON.stringify(image);
    return await apiService.post<AgogeImage>(
        URL_COMPUTE_IMAGE_API_CREATE,
        postData,
        true,
        transformToAgogeImage
    );
}

const delete_image = async (imageId: string)=> {
    const endpoint = formatString(URL_COMPUTE_IMAGE_API_ITEM, {"ITEM_ID": imageId});
    return await apiService.del(endpoint, true,);
}

const patch = async (imageId: string, formData: {[key: string]: any}) => {
    const endpoint = formatString(URL_COMPUTE_IMAGE_API_ITEM, {"ITEM_ID": imageId});
    return await apiService.patch(endpoint, formData, true);
};

export const imageService = {
    create,
    get,
    list,
    post_action,
    delete_image,
    patch
}