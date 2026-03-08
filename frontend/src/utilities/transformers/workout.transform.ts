import {Workout, WorkoutId, WorkoutAssessment, WorkoutFull, WorkoutState} from "../../services/Workout/workout.model";

export const transformToWorkout = (data: any): Workout => {
    return {
        id: data.id,
        action: data.action,
        assessment: data?.assessment,
        build_type: data.build_type,
        expires: data.expires,
        firewall_rules: data?.firewall_rules,
        lms_integration: data?.lms_integration,
        networks: data?.networks,
        parent_build_type: data.parent_build_type,
        parent_id: data.parent_id,
        prev_state: data.prev_state,
        proxy_connections: data?.proxy_connections,
        servers: data?.servers,
        state: data.state,
        student_email: data.student_email,
        student_name: data?.student_name,
        shutoff_timestamp: data?.shutoff_timestamp,
        unit_type: data.unit_type,
        summary: data?.summary,
        web_applications: data?.web_applications
    };
};

export const transformToWorkoutList = (data: any[]): Workout[] => {
    return data.map(transformToWorkout);
};

export const transformToWorkoutState = (data: any): WorkoutState => {
    return {
        id: data.id,
        state: data.state,
    };
};

export const transformToWorkoutId = (data: any): WorkoutId => {
    return {
        build_id: data.build_id,
        exists: data.exists
    }
}

export const transformToFullWorkout = (data: any): WorkoutFull =>{
    return {
        workout: transformToWorkout(data.workout),
        servers: data.servers
    }
}

export const transformToWorkoutAssessment = (data:any): WorkoutAssessment =>{
    return{
        questions: data.questions,
    };
}