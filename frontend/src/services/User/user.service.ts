import {
    URL_USER_API_BASE, URL_USER_API_COURSES,
    URL_USER_API_SETTINGS, URL_USER_API_UID, URL_WHO_AM_I
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformToAgogeUser,
    transformToCoursesList,
    transformToUserList,
} from "../../utilities/transformers/user.transform";
import { apiService } from "../api-request.service";
import {AgogeUser, UserCourses} from "./user.model";

const get = async (uid: string) => {
    const endpoint = formatString(URL_USER_API_UID, {"ITEM_ID": uid});
    return await apiService.get<AgogeUser>(endpoint, null, true, transformToAgogeUser);
}

const get_courses = async (uid: string) => {
    const endpoint = formatString(URL_USER_API_COURSES, {"ITEM_ID": uid});
    return await apiService.get<UserCourses>(endpoint, null, true, transformToCoursesList);
}

const update_settings = async (uid: string, userData: { [key: string]: any }) => {
    const endpoint = formatString(URL_USER_API_SETTINGS, {"ITEM_ID": uid});
    return await apiService.post<AgogeUser>(endpoint, userData, true, transformToAgogeUser);
}

const list = async () => {
    return await apiService.get<AgogeUser[]>(URL_USER_API_BASE, null, true, transformToUserList);
}

const create = async (userData: any) => {
    return await apiService.post<AgogeUser>(URL_USER_API_BASE, userData, true, transformToAgogeUser);
}

const delete_user = async (uid: string)=> {
    const endpoint = formatString(URL_USER_API_UID, {"ITEM_ID": uid});
    return await apiService.del<AgogeUser>(endpoint, true,);
}

const update_permissions = async (uid: string, userData: { [key: string]: any})=> {
    const endpoint = formatString(URL_USER_API_UID, {"ITEM_ID": uid});
    return await apiService.post<AgogeUser>(endpoint, userData, true, transformToAgogeUser);
}

const whoami = async () => {
    return await apiService.get(URL_WHO_AM_I, null, false, null);
}


export const userService = {
    get,
    get_courses,
    update_settings,
    list,
    create,
    delete_user,
    update_permissions,
    whoami,
}