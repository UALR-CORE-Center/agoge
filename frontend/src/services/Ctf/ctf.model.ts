// Mirrors the CTF request/response models in common/models/response.py and common/models/agoge.py.
// Keys stay snake_case because the API serializes them that way. A Python Optional field with no
// default is still always present in the JSON, so it is typed `T | null`, not `?`.

export type LocationType = 'file' | 'registry' | 'env' | 'ads';
export type OperatingSystem = 'linux' | 'windows';
export type NestedGuestDriver = 'qemu-agent' | 'offline';
export type WindowsAccess = 'administrators' | 'user' | 'everyone';
export type PlantStatus = 'pending' | 'planting' | 'planted' | 'failed' | 'stale';
export type ArmStatus = 'pending' | 'arming' | 'armed' | 'failed';
// A runtime list, not just a type, so the Submissions panel can offer every verdict as a filter.
export const VERDICTS = ['correct', 'incorrect', 'duplicate', 'decoy', 'cross_submission', 'rate_limited', 'closed'] as const;
export type Verdict = typeof VERDICTS[number];
export type CtfAction = 'arm' | 'start' | 'pause' | 'resume' | 'end' | 'archive';
export type ResetMode = 'replant' | 'restart' | 'rebuild';
export type CtfServersAction = 'build' | 'start' | 'stop';
// A runtime list, not just a type, so the Event Log panel can offer every action as a filter.
export const LOG_ACTIONS = [
    'CTF_CREATE', 'CTF_UPDATE', 'CTF_ARM', 'CTF_START', 'CTF_PAUSE',
    'CTF_RESUME', 'CTF_END', 'CTF_ARCHIVE', 'CTF_DELETE',
    'FLAG_REPLANT', 'FLAG_REVEAL', 'HOST_RESET', 'SCORE_ADJUST',
    'TEAM_ADD', 'TEAM_REMOVE', 'TEAM_UPDATE', 'SPEC_UPDATE',
    'SERVERS_BUILD', 'SERVERS_START', 'SERVERS_STOP',
] as const;
export type LogAction = typeof LOG_ACTIONS[number];
export type LogResult = 'OK' | 'DENIED' | 'ERROR';

// CtfStates in common/constants/states.py. `state` is the number; `state_name` is the member name.
export const CtfStates = {
    DRAFT: 0,
    ARMING: 1,
    ARMED: 2,
    RUNNING: 3,
    PAUSED: 4,
    ENDED: 5,
    ARCHIVED: 6,
    BROKEN: 7,
} as const;
export type CtfStateName = keyof typeof CtfStates;

// ---- Specification (copied into the event) ----

export interface CtfFlagSpec {
    id: string;
    server: string;
    slot: number;
    category: string | null;
    location_type: LocationType;
    path: string;
    operating_system: OperatingSystem;
    access_level: 'user' | 'root' | 'admin';
    points: number;
    decoy: boolean;
    hint: string | null;
    hint_cost: number;
    unlocks_after: string[] | null;
    file_mode: string | null;
    file_owner: string | null;
    // Windows file and ads flags only; optional so specs saved before these existed still type-check.
    windows_access?: WindowsAccess | null;
    windows_user?: string | null;
    hidden?: boolean;
    // A CtfNestedGuestSpec.name on `server`; null = the server itself. Optional for older specs.
    guest?: string | null;
}

// A VM running inside a lab server; flags reach it through its parent `server`.
export interface CtfNestedGuestSpec {
    name: string;
    server: string;
    domain: string;
    operating_system: OperatingSystem;
    driver: NestedGuestDriver;
}

export interface CtfScoringSpec {
    flag_prefix: string;
    submission_rate_limit: number;
    reveal_decoy_penalty: boolean;
}

export interface CtfSpec {
    name: string;
    description: string | null;
    rules_url: string | null;
    flags: CtfFlagSpec[];
    scoring: CtfScoringSpec;
    // Optional so specs saved before nested guests existed still type-check.
    nested_guests?: CtfNestedGuestSpec[];
}

// ---- Stored documents returned by the instructor API ----

export interface CtfEvent {
    id: string;
    unit_id: string;
    instructor_id: string[];
    spec: CtfSpec;
    seed_version: number;
    creation_timestamp: number;
    starts_at: number | null;
    ends_at: number | null;
    paused_at: number | null;
    accumulated_pause_seconds: number;
    scoreboard_frozen_at: number | null;
    public_scoreboard_enabled: boolean;
    board_ids: string[];
    // The lab's join code; participants enter it with their roster email.
    join_code: string | null;
    boards_pending: number;
    state: number;
    state_timestamp: string;
}

export interface CtfSubmission {
    id: string;
    ctf_id: string;
    workout_id: string;
    flag_id: string | null;
    submitted_digest: string;
    verdict: Verdict;
    matched_workout_id: string | null;
    points_awarded: number;
    submitted_at: number;
    origin_ip: string | null;
}

export interface CtfLogEntry {
    id: string;
    ctf_id: string;
    action: LogAction;
    actor: string;
    target: string | null;
    result: LogResult;
    detail: Record<string, string | number | boolean> | null;
    created_at: number;
}

// ---- Instructor responses ----

export interface CtfConfigResponse {
    ctf_enabled: boolean;
}

export interface CtfIdResponse {
    build_id: string;
    exists: boolean | null;
}

export interface CtfEventSummary {
    id: string;
    name: string;
    unit_id: string;
    state: number;
    state_name: string;
    board_count: number;
    creation_timestamp: number;
    starts_at: number | null;
    ends_at: number | null;
}

export interface CtfBoardStatus {
    workout_id: string;
    team_name: string;
    arm_status: ArmStatus;
    arm_error: string | null;
    plant_failed_count: number;
    plant_stale_count: number;
}

export interface CtfStateResponse {
    id: string;
    state: number;
    state_name: string;
    state_timestamp: string;
    starts_at: number | null;
    ends_at: number | null;
    paused_at: number | null;
    accumulated_pause_seconds: number;
    scoreboard_frozen_at: number | null;
    public_scoreboard_enabled: boolean;
    budget_exceeded: boolean;
    boards: CtfBoardStatus[];
}

export interface CtfFlagBoardStatus {
    workout_id: string;
    team_name: string;
    plant_status: PlantStatus;
    planted_at: number | null;
    plant_error: string | null;
    solved: boolean;
}

export interface CtfFlagRow {
    flag_id: string;
    server: string;
    // The nested guest holding the flag; null (or absent from older APIs) for the server itself.
    guest?: string | null;
    slot: number;
    category: string | null;
    location_type: LocationType;
    points: number;
    decoy: boolean;
    boards: CtfFlagBoardStatus[];
}

export interface CtfFlagRevealResponse {
    flag_id: string;
    workout_id: string;
    value: string;
}

export interface CtfHostRow {
    workout_id: string;
    team_name: string;
    server: string;
    server_state: number | null;
    server_state_name: string | null;
    flag_count: number;
    // False when the server has a wireguard_endpoint_id.
    rebuild_allowed: boolean;
    // Set on a nested guest's row, which follows its parent's row; null for the server itself.
    guest?: string | null;
}

export interface CtfScoreboardRow {
    rank: number;
    workout_id: string;
    team_name: string;
    score: number;
    solve_count: number;
    decoy_count: number;
    last_solve_at: number | null;
}

export interface CtfTeamRow {
    workout_id: string;
    team_name: string;
    members: string[];
    // WorkoutStates value; null while the workout record is missing.
    workout_state: number | null;
    workout_state_name: string | null;
    arm_status: ArmStatus;
}

export interface CtfTemplateServer {
    name: string;
    os: string | null;
    machine_type: string | null;
}

export interface CtfTemplateRow {
    id: string;
    name: string;
    description: string | null;
    ctf_name: string;
    // Decoys excluded: the flags teams can score.
    flag_count: number;
    servers: CtfTemplateServer[];
}

// PUT /ctf/{id}/servers/ answers with the number of workout messages published.
export interface CtfServersResponse {
    messages: number;
}

// PUT /ctf/{id}/flags/ answers with the number of plant messages published.
export interface CtfReplantResponse {
    messages: number;
}

// PUT /ctf/{id}/boards/{wid}/score/ answers with the board's new score.
export interface CtfScoreAdjustResponse {
    workout_id: string;
    score: number;
}

// ---- Student responses ----

export interface CtfPublicScoreboardRow {
    rank: number;
    // "Team <n>", n by board order; the student view never carries team names or workout ids.
    team_label: string;
    score: number;
    solve_count: number;
    is_you: boolean;
}

export interface CtfChallenge {
    flag_id: string;
    category: string | null;
    points: number;
    solved: boolean;
    solved_at: number | null;
    hint_available: boolean;
    hint_cost: number;
    // Only set once the hint has been taken.
    hint: string | null;
}

export interface CtfStudentBoardResponse {
    enrolled: boolean;
    ctf_id: string | null;
    name: string | null;
    description: string | null;
    rules_url: string | null;
    state_name: string | null;
    remaining_seconds: number | null;
    flag_format: string | null;
    score: number | null;
    challenges: CtfChallenge[];
    public_scoreboard_enabled: boolean;
}

export interface CtfSubmitResponse {
    // cross_submission is answered as 'incorrect'; rate_limited and closed arrive as 429/409 errors.
    verdict: 'correct' | 'incorrect' | 'duplicate' | 'decoy';
    correct: boolean;
    points_awarded: number;
    message: string;
}

export interface CtfHintResponse {
    flag_id: string;
    hint: string;
    hint_cost: number;
    score: number;
}

// ---- Requests ----

export interface CtfCreateRequest {
    spec_id: string;
    name?: string | null;
    // UTC epoch seconds when the event's lab and workouts expire.
    expires: number;
}

export interface CtfTeamMembersRequest {
    members: string[];
}

export interface CtfTeamRequest extends CtfTeamMembersRequest {
    team_name: string;
}

export interface CtfSpecUpdateRequest {
    ctf: CtfSpec;
}

export interface CtfServersRequest {
    action: CtfServersAction;
}

// Only keys present are applied; `scoreboard_frozen_at: null` unfreezes, so omit a key to leave it alone.
export interface CtfUpdateRequest {
    ends_at?: number | null;
    scoreboard_frozen_at?: number | null;
    public_scoreboard_enabled?: boolean | null;
}

export interface CtfActionRequest {
    action: CtfAction;
}

// null (or omitted) means every board / every flag-bearing server.
export interface CtfReplantRequest {
    workout_ids?: string[] | null;
    servers?: string[] | null;
}

export interface CtfHostResetRequest {
    mode: ResetMode;
    // Reset this nested guest of the server instead of the server itself.
    guest?: string | null;
}

export interface CtfScoreAdjustRequest {
    delta: number;
    reason: string;
}

export interface CtfSubmitRequest {
    flag: string;
}
