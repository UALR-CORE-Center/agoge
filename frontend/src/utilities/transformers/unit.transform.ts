import {Unit, UnitFull, UnitRoster, UnitState} from "../../services/Unit/unit.model";
import {transformToWorkout} from "./workout.transform";


export const transformToUnit = (data: any): Unit => {
    return {
        id: data.id,
        assessment: data.assessment,
        build_type: data.build_type,
        creation_timestamp: data.creation_timestamp,
        firewall_rules: data.firewall_rules,
        instructor_id: data.instructor_id,
        join_code: data.join_code,
        lms_integration: data?.lms_integration,
        networks: data.networks,
        servers: data.servers,
        state: data.state,
        summary: data.summary,
        unit_type: data.unit_type,
        workspace_settings: data.workspace_settings,
        wireguard_endpoint: data.wireguard_endpoint ?? null,
    };
};

export const transformToUnitList = (data: any[]): Unit[] => {
    return data.map(transformToUnit);
};

export const transformActiveExpiredUnitList = (
    data: { active: any[], expired: any[] }
): { active: Unit[], expired: Unit[] } => {
    const active = transformToUnitList(data.active || []);
    const expired = transformToUnitList(data.expired || []);
    return { active, expired };
};

export const transformToUnitState = (data: any): UnitState => {
    return {
        build_id: data.build_id,
        state: data?.state,
    };
};

export const transformToUnitRoster = (data:any): UnitRoster =>{
    return {
        id: data.id,
        roster: data.roster,
    };
};

export const transformToFullUnit = (data: any): UnitFull => {
    const { unit, workouts, roster, rubric_support } = data;
    return {
        ...transformToUnit(unit),
        workouts: workouts.map(transformToWorkout),
        roster: Number(roster),
        rubric_support: rubric_support
    };
};
