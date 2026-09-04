import {AssessmentScriptLanguages, Firewalls, UnitType} from "../../types/BuildConstants";
// TODO: Some of these objects are duplicates of what already exists in /types.
//  Revisit these models to ensure that they need to exist here

export enum AssessmentQuestionType {
    auto = 'auto',
    input = 'input'
}

export enum LMSAssessmentQuestionType {
    auto = 'auto',
    shortAnswer = 'short_answer_question'
}

export interface AssessmentQuestion {
    name?: string;
    type: AssessmentQuestionType;
    question: string;
    key?: string;
    answer?: string;
    script_assessment?: boolean;
}

interface AssessmentScript {
    script?: string;
    script_language?: AssessmentScriptLanguages;
    server?: string;
    operating_system?: string;
}

export interface Assessment {
    questions: AssessmentQuestion[];
    assessment_script?: AssessmentScript;
    key?: string;
}


interface FirewallRule {
    name: string;
    network: string;
    action?: Firewalls.Action;
    target_tags?: string[];
    protocol?: Firewalls.TransportProtocols;
    ports?: string[];
    ip_ranges?: string[];
    direction?: Firewalls.TrafficDirection;
    priority?: number;
}

export interface Firewall {
    name: string;
    type: Firewalls.FirewallTypes;
    gateway: string;
    networks: string[];
    allow_outbound?: boolean;
}

interface LMSQuizAnswer {
    answer_text?: string;
    weight?: number;
}

export interface LMSQuizQuestions {
    name?: string;
    question_text: string;
    question_type?: LMSAssessmentQuestionType;
    points_possible?: number;
    script_assessment?: boolean;
    bonus?: boolean;
    answers?: LMSQuizAnswer[];
}

export interface LMSQuiz {
    allowed_attempts?: number;
    assessment_script?: AssessmentScript;
    questions?: LMSQuizQuestions[];
}


interface Nic {
    network: string;
    internal_ip?: string | null;
    subnet_name?: string;
    external_nat?: boolean;
    external_ip_name?: string;
    ip_aliases?: string[];
    direct_connect?: boolean;
}

export interface Route {
    name: string;
    network: string;
    dest_range: string;
    next_hop_instance: string;
    priority?: number;
    tags?: string[];
    description?: string;
}

interface SubNetwork {
    name: string;
    ip_subnet: string;
    promiscuous_mode?: boolean;
}

export interface Network {
    name: string;
    subnets?: SubNetwork[];
    reservations?: string[];
}

export interface HumanInteraction {
    display?: boolean;
    username?: string;
    password?: string;
    protocol: string;
    ssh_key?: string;
    domain?: string;
    security_mode?: string;
}

interface ServerDetails {
    description: string;
    os: string;
    labels: string[];
}

export interface ServerMachineTypes {
    id: string;
    name: string;
    description: string;
    is_shared_core: boolean
    memory_mb: number
    guest_cpus: number
}

export interface Server {
    name: string;
    details: ServerDetails;
    image: string;
    hidden?: boolean;
    tags?: string[];
    build_type?: string;
    machine_type?: string;
    sshkey?: string;
    can_ip_forward?: boolean;
    wireguard_gateway?: boolean;
    wireguard_endpoint_id?: string;
    startup_script?: string;
    routes?: Route[];
    nics?: Nic[];
    human_interaction?: HumanInteraction[];
    community_server?: boolean;
    deny_outbound?: boolean;
    disk_size?: number;
}

export interface WebApplication {
    name: string;
    host_name: string;
    starting_directory: string;
    url?: string;
}

interface StandardMappings {
    framework: string;
    mapping: string;
}

export interface TeachingConcept {
    id: string;
    name: string;
}

export interface Summary {
    name: string;
    description: string;
    teacher_instructions_url?: string;
    student_instructions_url?: string;
    author?: string;
    hourly_cost?: number;
    standard_mappings?: StandardMappings[];
    tags?: TeachingConcept[];
}

export interface SpecificationEdit {
    assessment?: Assessment,
    lms_quiz?: LMSQuiz;

    build_type: string;
    creation_timestamp: number;
    discriminator: string;
    edit_id: string;
    firewalls?: Firewall[],
    firewall_rules?: FirewallRule[],
    id: string;
    instructor_id?: string | string[];
    networks: Network[];
    routes?: Route[];
    promiscuous_mode?: boolean;
    servers: Server[];
    status: string;
    summary: Summary;
    unit_type: UnitType;
    version: number;
    workout_duration_days?: number;
    web_applications: WebApplication[];
}

export interface SpecificationEditId {
    build_id: string;
}

export interface PublishResponse {
    build_id: string;
}
