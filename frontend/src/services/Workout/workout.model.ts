import {Dictionary, ListOfDictionaries} from "../../types/Common";

export interface Workout {
    id: string;
    action: number;
    assessment?: Dictionary;
    build_type: string;
    expires: number;
    firewall_rules?: ListOfDictionaries;
    lms_integration?: Dictionary;
    networks?: ListOfDictionaries;
    parent_build_type: string;
    parent_id: string;
    prev_state: number;
    proxy_connections?: ListOfDictionaries;
    servers?: ListOfDictionaries;
    state: string;
    student_email: string;
    student_name?: string;
    shutoff_timestamp?: number;
    unit_type: string;
    summary?: Dictionary;
    web_applications?: ListOfDictionaries;
    student_external_ip_addresses?: string[];
}

export interface WorkoutState extends Partial<Workout> {
    id: string,
    state: string,
}

export interface WorkoutId extends Partial<Workout> {
    build_id: string;
    exists: boolean
}

export interface WorkoutFull extends Partial<Workout>{
    workout: Workout;
    servers?: ListOfDictionaries;
}

export interface WorkoutAssessment extends Partial<Workout>{
    questions: Dictionary;
}
