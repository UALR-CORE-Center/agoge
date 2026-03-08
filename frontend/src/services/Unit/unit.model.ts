import {Dictionary, ListOfDictionaries} from "../../types/Common";
import {Workout} from "../Workout/workout.model";

export interface Unit {
    id: string;
    summary: Dictionary;
    workspace_settings: Dictionary;
    networks: ListOfDictionaries;
    servers: ListOfDictionaries;
    assessment?: ListOfDictionaries;
    instructor_id: string;
    firewall_rules?: ListOfDictionaries;
    state: string;
    unit_type: string;
    build_type: string;
    join_code: number;
    creation_timestamp: number;
    lms_integration?: Dictionary;
    rubric_support?: boolean;
}

export interface UnitSummary extends Partial<Unit> {
    id: string;
    summary: Dictionary,
}

export interface UnitRoster extends Partial<Unit> {
    id: string,
    roster: number
}

export interface UnitState extends Partial<Unit> {
    build_id: string,
    state?: string
}

export interface UnitFull extends Partial<Unit> {
    workouts?: Workout[];
    roster:number;
}