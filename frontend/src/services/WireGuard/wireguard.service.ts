import {apiService} from "../api-request.service";

export interface WireGuardKit {
    id: string;
    device_id: string;
    equipment_subnet: string;
    peer_public_key: string;
    authorized_instructors: string[];
    assigned_unit_id?: string | null;
    enabled: boolean;
}

export type WireGuardKitEnrollment = Pick<WireGuardKit,
    "id" | "device_id" | "equipment_subnet" | "peer_public_key" | "authorized_instructors">;

export interface WireGuardEnrollmentResult {
    kit: WireGuardKit;
    enrollment_token: string;
}

export interface WireGuardLabRequest {
    kit_id: string;
    build_count: number;
    expires: Date | string;
    student_image?: string;
}

export const wireguardService = {
    listKits: () => apiService.get<WireGuardKit[]>("wireguard/kits/"),
    enrollKit: (kit: WireGuardKitEnrollment) =>
        apiService.post<WireGuardEnrollmentResult>("wireguard/kits/", kit),
    createLab: (request: WireGuardLabRequest) =>
        apiService.post<{build_id: string}>("wireguard/labs/", request),
};
