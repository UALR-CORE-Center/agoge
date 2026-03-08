import {
    URL_ADMIN_API_PROJECT_BASE,
    URL_ADMIN_MANAGE_PROJECT,
    URL_UNIT_API_ITEM,
    URL_WORKOUT_API_ITEM
} from "../../router/urls";
import {PubSub} from "../../types/PubSub";
import formatString from "../../utilities/formatString";
import {transformToProjectSettings} from "../../utilities/transformers/project.transform";
import {transformToUnit} from "../../utilities/transformers/unit.transform";
import {transformToWorkout, transformToWorkoutList} from "../../utilities/transformers/workout.transform";
import {Workout} from "../Workout/workout.model";
import {apiService} from "../api-request.service";

const build_in_place = async(buildId: string) => {
    /*Todo: Figure out what endpoint/data desired*/
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.put<Workout>(endpoint,String(PubSub.Actions.DELETE),true,transformToWorkout);
}

const patch = async (buildId: string, formData: { [key: string]: any }, buildType: "unit" | "workout", ) => {
    const url = buildType === 'unit' ? URL_UNIT_API_ITEM : URL_WORKOUT_API_ITEM;
    const endpoint = formatString(url, {"ITEM_ID": buildId});
    return await apiService.patch(endpoint, formData, true);
}

const delete_unit = async(buildId: string) => {
    const endpoint = formatString(URL_UNIT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.del(endpoint,true, transformToUnit);
};

const delete_workout = async(buildId: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.del(endpoint,true, transformToWorkoutList);
}

const restore_workout = async(buildId: string) => {
    /*Todo: No solution yet just say coming soon =)*/
    return'';
}

const get_project_settings = async () => {
    return await apiService.get(
        URL_ADMIN_API_PROJECT_BASE,
        null,
        true,
        transformToProjectSettings
    );
}

export const adminService = {
    patch,
    build_in_place,
    delete_unit,
    delete_workout,
    restore_workout,
    get_project_settings,
}
