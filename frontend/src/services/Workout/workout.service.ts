import {
    URL_WORKOUT_API_BASE,
    URL_WORKOUT_API_ITEM, URL_WORKOUT_API_ITEM_FULL,
    URL_WORKOUT_API_ITEM_STATE,
    URL_WORKOUT_QUESTION_API_ITEM
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformToFullWorkout, transformToWorkoutId,
    transformToWorkout, transformToWorkoutAssessment,
    transformToWorkoutList,
    transformToWorkoutState
} from "../../utilities/transformers/workout.transform";
import { apiService } from "../api-request.service";
import {
    Workout,WorkoutId, WorkoutFull,
    WorkoutState, WorkoutAssessment
} from "./workout.model";


const get = async (buildId: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.get<Workout>(endpoint, null, false, transformToWorkout);
}

const get_full = async (buildId: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM_FULL, {"ITEM_ID": buildId});
    return await apiService.get<WorkoutFull>(endpoint, null, true, transformToFullWorkout);
}

const get_state = async (buildId: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM_STATE, {"ITEM_ID": buildId});
    return await apiService.get<WorkoutState>(endpoint, null, false, transformToWorkoutState);
}

const list = async (buildId: string) => {
    const url = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    const endpoint = `${url}workouts/`;
    return await apiService.get<Workout[]>(endpoint, null, true, transformToWorkoutList);
}

export const post = async (data: { [k: string]: FormDataEntryValue }) => {
    const postData = JSON.stringify(data);
    return await apiService.post<WorkoutId>(
        URL_WORKOUT_API_BASE,
        postData,
        false,
        transformToWorkoutId
    );
}

const post_action = async (buildId: string, action:string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.post<Workout>(endpoint, action, true, transformToWorkout);
}

export const put_action = async (buildId: string, action: string, duration?: number, extIp?: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    let payload;
    if (duration) {
        payload = {'action': action, 'duration': duration}
    } else if (extIp){
        payload = {'ip_address': String(extIp)}
    } else {
        payload = {'action': action}
    }
    return await apiService.put<WorkoutState>(endpoint, payload, false, transformToWorkoutState);
}

export const configure = async (buildId: string, extIp: string) => {
    const endpoint = formatString(URL_WORKOUT_API_ITEM, {"ITEM_ID": buildId});
    const payload = {'ip_address': String(extIp)};
    return await apiService.put(`${endpoint}access/`, payload, false, null);
}

export const answer_question = async (buildId: string, question_key:string, action:string) => {
    const endpoint = formatString(
        URL_WORKOUT_QUESTION_API_ITEM,
        {"ITEM_ID": buildId, "Q_KEY": question_key}
    );
    return await apiService.put<WorkoutAssessment>(endpoint, action,false, transformToWorkoutAssessment);
}

export const workoutService = {
    get,
    get_state,
    get_full,
    list,
    post,
    post_action,
    put_action,
    configure,
    answer_question
}
