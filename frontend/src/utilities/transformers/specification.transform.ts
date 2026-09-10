import {Specification} from "../../services/Specification/specification.model";

export const transformToSpecification = (data: any) : Specification  => {
    return {
        id: data.id,
        version: data.version,
        instructor_id: data.instructor_id,
        build_type: data.build_type,
        unit_type: data?.unit_type,
        summary: data.summary,
        servers: data?.servers,
        networks: data?.networks,
        routes: data?.routes,
        web_applications: data.web_applications,
        firewalls: data?.firewalls,
        firewall_rules: data?.firewall_rules,
        assessment: data?.assessment,
        lms_integration: data?.lms_integration,
        escape_room: data?.escape_room,
        test: Boolean(data?.test),
        workout_duration_days: data?.workout_duration_days,
        accessibility_features: data?.workout_duration_days,
        discriminator: data.discriminator,
    };
}

export const transformToCatalog = (data: any) : Specification => {
    return {
        id: data.id,
        version: data.version,
        instructor_id: data.instructor_id,
        build_type: data.build_type,
        unit_type: data?.unit_type,
        summary: data.summary,
        servers: data?.servers,
        networks: data?.networks,
        routes: data?.routes,
        web_applications: data.web_applications,
        firewalls: data?.firewalls,
        firewall_rules: data?.firewall_rules,
        assessment: data?.assessment,
        lms_quiz: data?.lms_quiz,
        test: Boolean(data?.test),
        workout_duration_days: data?.workout_duration_days,
        accessibility_features: data?.workout_duration_days,
        discriminator: data.discriminator,
    };
}

export const transformToSpecificationList = (data: any[]) : Specification[] => {
    return data.map(transformToCatalog)
}
