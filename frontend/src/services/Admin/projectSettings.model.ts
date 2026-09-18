export interface ProjectSettingsModel {
    classroom_user?: string | null;
    max_workspaces?: number | null;
    spec_bucket?: string | null;
    student_workout_firewall?: boolean;
    wireguard_dns_prefix?: string | null;
    wireguard_dns_suffix?: string | null;
    wireguard_port?: number | null;
}
