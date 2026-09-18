import {ProjectSettingsModel} from "../../services/Admin/projectSettings.model";

export const transformToProjectSettings = (data: any): ProjectSettingsModel => {
    return {
        classroom_user: data?.classroom_user,
        max_workspaces: data?.max_workspaces,
        spec_bucket: data?.spec_bucket,
        student_workout_firewall: data?.student_workout_firewall,
        wireguard_dns_prefix: data?.wireguard_dns_prefix,
        wireguard_dns_suffix: data?.wireguard_dns_suffix,
        wireguard_port: data?.wireguard_port,
    }
}
