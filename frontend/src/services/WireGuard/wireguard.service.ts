import {apiService} from "../api-request.service";

export interface WireGuardRemotePeer {
    id: string;
    device_id: string;
    remote_network_cidr: string;
    peer_public_key: string;
    authorized_instructors: string[];
    assigned_unit_id?: string | null;
    enabled: boolean;
}

export type WireGuardRemotePeerEnrollment = Pick<WireGuardRemotePeer,
    "id" | "device_id" | "remote_network_cidr" | "peer_public_key" | "authorized_instructors">;

export interface WireGuardRemotePeerEnrollmentResult {
    remote_peer: WireGuardRemotePeer;
    enrollment_token: string;
}

// Keep the legacy transport available to callers during the API migration.
export type WireGuardKit = Omit<WireGuardRemotePeer, "remote_network_cidr"> & {equipment_subnet: string};
export type WireGuardKitEnrollment = Pick<WireGuardKit,
    "id" | "device_id" | "equipment_subnet" | "peer_public_key" | "authorized_instructors">;

export interface WireGuardEnrollmentResult {
    kit: WireGuardKit;
    enrollment_token: string;
}

export type WireGuardLabRequest = {
    build_count: number;
    expires: Date | string;
    student_image?: string;
} & ({remote_peer_id: string; kit_id?: string} | {remote_peer_id?: string; kit_id: string});

const toRemotePeer = (record: any): WireGuardRemotePeer => ({
    id: record.id,
    device_id: record.device_id,
    remote_network_cidr: record.remote_network_cidr ?? record.equipment_subnet,
    peer_public_key: record.peer_public_key,
    authorized_instructors: record.authorized_instructors,
    assigned_unit_id: record.assigned_unit_id ?? null,
    enabled: record.enabled === true,
});

export const wireguardService = {
    listRemotePeers: () => apiService.get<WireGuardRemotePeer[]>("wireguard/remote-peers/", null, true,
        records => records.map(toRemotePeer)),
    enrollRemotePeer: (peer: WireGuardRemotePeerEnrollment) =>
        apiService.post<WireGuardRemotePeerEnrollmentResult>("wireguard/remote-peers/", peer, true, null,
            data => ({remote_peer: toRemotePeer(data.remote_peer ?? data.kit), enrollment_token: data.enrollment_token})),
    listKits: () => apiService.get<WireGuardKit[]>("wireguard/kits/"),
    enrollKit: (kit: WireGuardKitEnrollment) =>
        apiService.post<WireGuardEnrollmentResult>("wireguard/kits/", kit),
    createLab: (request: WireGuardLabRequest) =>
        apiService.post<{build_id: string}>("wireguard/labs/", request),
};
