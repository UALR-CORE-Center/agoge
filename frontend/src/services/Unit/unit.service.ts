import {
    URL_UNIT_API_BASE,
    URL_UNIT_API_ITEM,
    URL_UNIT_API_ITEM_FULL,
    URL_UNIT_API_ITEM_ROSTER,
    URL_UNIT_API_ITEM_STATE,
    URL_UNIT_API_ITEMS,
    URL_WORKOUT_API_BASE
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformActiveExpiredUnitList,
    transformToFullUnit,
    transformToUnit,
    transformToUnitList,
    transformToUnitRoster,
    transformToUnitState,
} from "../../utilities/transformers/unit.transform";
import {transformToWorkoutList} from "../../utilities/transformers/workout.transform";
import {Workout} from "../Workout/workout.model";
import {apiService} from "../api-request.service";
import {Unit, UnitFull, UnitRoster, UnitState} from "./unit.model";


const get = async (buildId: string) => {
    const endpoint = formatString(URL_UNIT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.get<Unit>(endpoint, null, true, transformToUnit);
}

const get_state = async (buildId: string) => {
    const endpoint = formatString(URL_UNIT_API_ITEM_STATE, {"ITEM_ID": buildId});
    return await apiService.get<UnitState>(endpoint, null, true, transformToUnitState);
}

const get_roster = async(buildId: string)=>{
    const endpoint = formatString(URL_UNIT_API_ITEM_ROSTER, {"ITEM_ID": buildId});
    return await apiService.get<UnitRoster>(endpoint,null,true, transformToUnitRoster);
}

const get_full = async(buildId: string)=>{
    const endpoint = formatString(URL_UNIT_API_ITEM_FULL, {"ITEM_ID": buildId});
    return await apiService.get<UnitFull>(endpoint,null,true,transformToFullUnit);
}

const post_action = async (buildId: string) => {
    const endpoint = formatString(URL_UNIT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.post<UnitState>(endpoint, null, true, transformToUnitState);
}

export const put_action = async (buildId: string, action?: string, days?: number, workout_ids?: string[]) => {
    //const endpoint = formatString(`${URL_UNIT_API_ITEM}?action=${action}`, {"ITEM_ID": buildId});
    const endpoint = formatString(URL_UNIT_API_ITEM, {"ITEM_ID": buildId});
    const payload = {'action': action}
    if (days) {
        payload['days'] = days;
    } else if (workout_ids) {
        payload['workout_ids'] = workout_ids;
    }
    return await apiService.put<UnitState>(endpoint, payload, true, transformToUnitState);
}

const list = async () => {
    return await apiService.get<{ active: Unit[], expired: Unit[] }>(
        URL_UNIT_API_BASE,
        {active: true, expired: true, instructor: true},
        true,
        transformActiveExpiredUnitList
    );
}

const list_filtered = async (filter: "active" | "instructor" | `${number}-days` | "expired") => {
    let active, instructor, expired;
    active = instructor = expired = false;
    let days;

    if (filter === "active") {
        active = true;
    } else if (filter === "expired" ) {
        expired = true
    } else if (filter === "instructor") {
        instructor = true
    } else if (filter.endsWith("-days")) {
        days = parseInt(filter.split('-')[0], 10);
    } else {
        console.error("Invalid filter type");
        return;
    }
    const params = {
        'active': active,
        'instructor': instructor,
        'days': days,
        'expired': expired
    }
    return await apiService.get<Unit[]>(URL_UNIT_API_BASE, params,true, transformToUnitList);
}

const list_workouts = async (buildId: string) => {
    const endpoint = formatString(URL_UNIT_API_ITEMS, {"ITEM_ID": buildId});
    return await apiService.get<Workout[]>(endpoint, null, true, transformToWorkoutList);
}

const list_workouts_filtered = async (filter: "active" | "student" | `${number}-days`) => {
    let active, student, days;
    if (filter === "active") {
        active = true;
        student = false;
    } else if(filter.endsWith("-days")) {
        days = parseInt(filter.split('-')[0],10);
        active = student = false;
    } else if(filter === "student"){
        student = true;
        active = false;
    } else{
        console.error("Invalid filter type");
        return;
    }
    const params = {
        'active': active,
        'student': student,
        'days': days
    }
    return await apiService.get<Workout[]>(URL_WORKOUT_API_BASE, params, true, transformToWorkoutList);
}

const create = async (unitData: { [key: string]: any }) => {
    return await apiService.post<UnitState>(URL_UNIT_API_BASE, unitData, true, transformToUnitState);
};

const patch = async (buildId: string, formData: {[key: string]: any}) => {
    const endpoint = formatString(URL_UNIT_API_ITEM, {"ITEM_ID": buildId});
    return await apiService.patch(endpoint, formData, true);
};

export const unitService = {
    get,
    get_state,
    get_roster,
    post_action,
    get_full,
    list,
    list_filtered,
    list_workouts,
    list_workouts_filtered,
    create,
    put_action,
    patch,
}
