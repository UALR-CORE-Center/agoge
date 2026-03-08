import {LMSQuiz} from "./specificationEdit.model";

export interface TeachingConcepts {
    id: string;
    name: string;
}

export interface StandardMappings {
    framework: string;
    mapping: string;
}

export interface SubNetwork {
    name: string;
    ip_subnet: string;
    promiscuous_mode?: boolean;
}

export interface Network {
    name: string;
    subnets?: SubNetwork[];
    reservations?: string[];
}

export interface Nic {
    network: string;
    internal_ip?: string;
    subnet_name?: string;
    external_nat?: boolean;
    ip_aliases?: string[];
    direct_connect?: boolean;
}

export interface HumanInteraction {
    display?: boolean;
    protocol: string;
    username?: string;
    password?: string;
    domain?: string;
    security_mode?: string;
}

export interface ServerDetails {
    description?: string;
    os?: string;
    labels?: string[];
}

export interface Server {
    name: string;
    details?: ServerDetails;
    image: string;
    hidden?: boolean;
    machine_type?: string;
    add_disk?: number;
    tags?: string[];
    build_type?: string;
    metadata?: string;
    sshkey?: string;
    can_ip_forward?: boolean;
    min_cpu_platform?: string;
    nics?: Nic[];
    human_interaction?: HumanInteraction[];
    community_server?: boolean;
}

export interface WebApplication {
    name: string;
    host_name: string;
    starting_directory: string;
    url?: string;
}

export interface Firewall {
    name: string;
    type: string;
    gateway: string;
    networks: string[];
    allow_outbound?: boolean;
}

export interface FirewallRule {
    name: string;
    network: string;
    action?: string;
    target_tags?: string[];
    protocol?: string;
    ports?: string[];
    ip_ranges?: string[];
    direction?: string;
    priority?: number;
}

export interface ProxyConnection {
    username: string;
    internal_ip_address: string;
    password: string;
    server: string;
}

export interface AgogeSummary {
    name: string;
    description: string;
    teacher_instructions_url?: string;
    student_instructions_url?: string;
    hourly_cost?: number;
    author?: string;
    standard_mappings?: StandardMappings[];
    tags?: TeachingConcepts[];
}

export interface AgogeWorkoutSummary {
    name: string;
    description: string;
    student_instructions_url?: string;
}

export interface WorkspaceSettings {
    count: number;
    registration_required?: boolean;
    student_emails?: string[];
    student_names?: string[];
    expires: number;
}

export interface AssessmentQuestion {
    id?: string;
    name?: string;
    type: string;
    question: string;
    key?: string;
    answer?: string;
    script_assessment?: boolean;
    complete?: boolean;
}

export interface AssessmentScript {
    script?: string;
    script_language?: string;
    server?: string;
    operating_system?: string;
}

export interface Assessment {
    questions?: AssessmentQuestion[];
    assessment_script?: AssessmentScript;
    key?: string;
}

export interface LMSQuizAnswer {
    answer_text?: string;
    weight?: number;
}

export interface LMSQuizQuestions {
    name?: string;
    question_text: string;
    question_type?: string;
    points_possible?: number;
    script_assessment?: boolean;
    bonus?: boolean;
    answers?: LMSQuizAnswer[];
    complete?: boolean;
}

export interface LMSConnection {
    lms_type: string;
    api_key?: string;
    url?: string;
    course_code: number;
    name?: string;
}

export interface LMSIntegration {
    lms_connection?: LMSConnection;
    course_work?: string;
    due_at?: number;
    description?: string;
    allowed_attempts?: number;
    assessment_script?: AssessmentScript;
    questions?: LMSQuizQuestions[];
}

export interface EscapeRoom {
    question: string;
    answer?: string;
    responses?: string[];
    escaped?: boolean;
    time_limit?: number;
    start_time?: number;
    remaining_time?: number;
    puzzles?: Puzzle[];
}

export interface Puzzle {
    id?: string;
    instructions_url?: string;
    entry_type?: string;
    entry_name?: string;
    type?: string;
    summary?: string;
    question: string;
    name: string;
    answer?: string;
    script?: string;
    script_language?: string;
    server?: string;
    operating_system?: string;
    responses?: string[];
    correct?: boolean;
    reveal?: string;
}

export interface Unit {
    id: string;
    creation_timestamp?: number;
    version: string;
    class_id?: string;
    instructor_id: string | string[];
    workspace_settings?: WorkspaceSettings;
    build_type: string;
    unit_type?: string;
    summary: AgogeSummary;
    networks?: Network[];
    servers?: Server[];
    web_applications?: WebApplication[];
    firewalls?: Firewall[];
    firewall_rules?: FirewallRule[];
    assessment?: Assessment;
    lms_integration?: LMSIntegration;
    escape_room?: EscapeRoom;
    test?: boolean;
    join_code?: string;
    workout_duration_days?: number;
    accessibility_features?: boolean;
}

export interface Specification extends Unit {
    discriminator: string,
    lms_quiz?: LMSQuiz
}