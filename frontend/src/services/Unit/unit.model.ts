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
    // True when the unit carries a `ctf` block; the block itself stays server-side.
    ctf_capable?: boolean;
    wireguard_endpoint?: WireGuardEndpoint | null;
    wireguard_lease?: WireGuardLease | null;
}

export interface WireGuardLease {
    unit_id: string;
    kit_id: string;
    device_id: string;
    endpoint_id: string;
    equipment_subnet: string;
    student_subnets: string[];
    gateway_public_key: string;
    peer_public_key: string;
    gateway_address: string;
    peer_address: string;
    expires: number;
    status: "reserved" | "released";
    service_ready: boolean;
    tunnel_ready: boolean;
    health_timestamp?: number | null;
    latest_handshake?: number;
    health_error?: string | null;
}

export interface WireGuardEndpoint {
    id: string;
    hostname: string;
    server_name: string;
    port: number;
    external_ip_name?: string | null;
    public_ip?: string | null;
    status: "reserved" | "active" | "releasing" | "released" | "error";
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
