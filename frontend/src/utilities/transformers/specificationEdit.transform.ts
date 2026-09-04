import {
    PublishResponse,
    SpecificationEdit, SpecificationEditId
} from "../../services/Specification/specificationEdit.model";

export const transformToSpecificationEdit = (data: any) : SpecificationEdit => {
    return {
        assessment: data?.assessment,
        build_type: data?.build_type,
        creation_timestamp: data.creation_timestamp,
        discriminator: data.discriminator,
        edit_id: data.edit_id,
        firewalls: data?.firewalls,
        firewall_rules: data?.firewall_rules,
        id: data.id,
        instructor_id: data?.instructor_id,
        lms_quiz: data?.lms_quiz,
        networks: data?.networks,
        routes: data?.routes,
        promiscuous_mode: data?.promiscuous_mode,
        servers: data?.servers,
        status: data.status,
        summary: data?.summary,
        version: data?.version,
        unit_type: data?.unit_type,
        web_applications: data?.web_applications,
        workout_duration_days: data?.workout_duration_days,
    };
}

export const transformToSpecificationEditId = (data: any) : SpecificationEditId => {
    return {
        build_id: data.build_id,
    }
}

export const transformToSpecificationPublish = (data: any) : PublishResponse => {
    return {
        build_id: data.build_id
    }
}

export const transformToSpecificationEditList = (data: any[]) : SpecificationEdit[] => {
    return data.map(transformToSpecificationEdit);
}
