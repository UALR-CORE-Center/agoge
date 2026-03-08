export interface APISettings {
    api?: string;
    url?: string;
    secret?: string;
}

export interface AgogeUserSettings {
    [key: string]: APISettings;
}

export interface AgogeUser {
    uid: string;
    email: string;
    name?: string;
    permissions?: { [key: string]: boolean };
    settings: AgogeUserSettings;
    timezone?: string;
}

export interface SafeAgogeUser {
    uid: string;
    email: string;
    name?: string;
    permissions: { [key: string]: boolean };
    settings: { [key: string]: boolean };
    timezone: string;
}

export interface LMSCourse {
    id: string;
    name: string;
}

export interface UserCourses {
    canvas?: LMSCourse[] | null;
    blackboard?: LMSCourse[] | null;
    classroom?: LMSCourse[] | null;
}

