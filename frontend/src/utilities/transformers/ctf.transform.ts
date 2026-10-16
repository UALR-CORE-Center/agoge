import {
    CtfBoardStatus,
    CtfChallenge,
    CtfConfigResponse,
    CtfEvent,
    CtfEventSummary,
    CtfFlagBoardStatus,
    CtfFlagRevealResponse,
    CtfFlagRow,
    CtfHintResponse,
    CtfHostRow,
    CtfIdResponse,
    CtfLogEntry,
    CtfPublicScoreboardRow,
    CtfReplantResponse,
    CtfScoreAdjustResponse,
    CtfScoreboardRow,
    CtfSpec,
    CtfStateResponse,
    CtfStudentBoardResponse,
    CtfSubmission,
    CtfSubmitResponse,
    CtfTeamRow,
    CtfTemplateRow,
} from "../../services/Ctf/ctf.model";

// Each transformer copies only the modelled keys. Its input is typed as the wire shape the API
// promises, but nullable keys still fall back to null and lists to [] at runtime, so a panel never
// has to guard against undefined from an older API or a sparse Firestore document.

const orNull = <T>(value: T | undefined): T | null => value ?? null;

export const transformToCtfConfig = (data: Partial<CtfConfigResponse> | null): CtfConfigResponse => ({
    // Anything but an explicit true keeps the feature hidden.
    ctf_enabled: data?.ctf_enabled === true,
});

export const transformToCtfIdResponse = (data: CtfIdResponse): CtfIdResponse => ({
    build_id: data.build_id,
    exists: orNull(data.exists),
});

export const transformToCtfEventSummary = (data: CtfEventSummary): CtfEventSummary => ({
    id: data.id,
    name: data.name,
    unit_id: data.unit_id,
    state: data.state,
    state_name: data.state_name,
    board_count: data.board_count,
    creation_timestamp: data.creation_timestamp,
    starts_at: orNull(data.starts_at),
    ends_at: orNull(data.ends_at),
});

export const transformToCtfEventSummaryList = (data: CtfEventSummary[]): CtfEventSummary[] =>
    (data ?? []).map(transformToCtfEventSummary);

const transformToCtfSpec = (data: CtfSpec): CtfSpec => ({
    name: data.name,
    description: orNull(data.description),
    rules_url: orNull(data.rules_url),
    flags: data.flags ?? [],
    scoring: data.scoring,
});

export const transformToCtfEvent = (data: CtfEvent): CtfEvent => ({
    id: data.id,
    unit_id: data.unit_id,
    instructor_id: data.instructor_id ?? [],
    spec: transformToCtfSpec(data.spec),
    seed_version: data.seed_version,
    creation_timestamp: data.creation_timestamp,
    starts_at: orNull(data.starts_at),
    ends_at: orNull(data.ends_at),
    paused_at: orNull(data.paused_at),
    accumulated_pause_seconds: data.accumulated_pause_seconds ?? 0,
    scoreboard_frozen_at: orNull(data.scoreboard_frozen_at),
    public_scoreboard_enabled: data.public_scoreboard_enabled === true,
    board_ids: data.board_ids ?? [],
    join_code: orNull(data.join_code),
    boards_pending: data.boards_pending ?? 0,
    state: data.state,
    state_timestamp: data.state_timestamp,
});

export const transformToCtfBoardStatus = (data: CtfBoardStatus): CtfBoardStatus => ({
    workout_id: data.workout_id,
    team_name: data.team_name,
    arm_status: data.arm_status,
    arm_error: orNull(data.arm_error),
    plant_failed_count: data.plant_failed_count ?? 0,
    plant_stale_count: data.plant_stale_count ?? 0,
});

export const transformToCtfBoardStatusList = (data: CtfBoardStatus[]): CtfBoardStatus[] =>
    (data ?? []).map(transformToCtfBoardStatus);

export const transformToCtfState = (data: CtfStateResponse): CtfStateResponse => ({
    id: data.id,
    state: data.state,
    state_name: data.state_name,
    state_timestamp: data.state_timestamp,
    starts_at: orNull(data.starts_at),
    ends_at: orNull(data.ends_at),
    paused_at: orNull(data.paused_at),
    accumulated_pause_seconds: data.accumulated_pause_seconds ?? 0,
    scoreboard_frozen_at: orNull(data.scoreboard_frozen_at),
    public_scoreboard_enabled: data.public_scoreboard_enabled === true,
    budget_exceeded: data.budget_exceeded === true,
    boards: transformToCtfBoardStatusList(data.boards),
});

const transformToCtfFlagBoardStatus = (data: CtfFlagBoardStatus): CtfFlagBoardStatus => ({
    workout_id: data.workout_id,
    team_name: data.team_name,
    plant_status: data.plant_status,
    planted_at: orNull(data.planted_at),
    plant_error: orNull(data.plant_error),
    solved: data.solved === true,
});

export const transformToCtfFlagRow = (data: CtfFlagRow): CtfFlagRow => ({
    flag_id: data.flag_id,
    server: data.server,
    slot: data.slot,
    category: orNull(data.category),
    location_type: data.location_type,
    points: data.points,
    decoy: data.decoy === true,
    boards: (data.boards ?? []).map(transformToCtfFlagBoardStatus),
});

export const transformToCtfFlagRowList = (data: CtfFlagRow[]): CtfFlagRow[] =>
    (data ?? []).map(transformToCtfFlagRow);

export const transformToCtfFlagReveal = (data: CtfFlagRevealResponse): CtfFlagRevealResponse => ({
    flag_id: data.flag_id,
    workout_id: data.workout_id,
    value: data.value,
});

export const transformToCtfReplantResponse = (data: CtfReplantResponse): CtfReplantResponse => ({
    messages: data.messages ?? 0,
});

export const transformToCtfHostRow = (data: CtfHostRow): CtfHostRow => ({
    workout_id: data.workout_id,
    team_name: data.team_name,
    server: data.server,
    server_state: orNull(data.server_state),
    server_state_name: orNull(data.server_state_name),
    flag_count: data.flag_count ?? 0,
    // Fail closed: a missing value must not offer a rebuild that would drop a wireguard endpoint.
    rebuild_allowed: data.rebuild_allowed === true,
});

export const transformToCtfHostRowList = (data: CtfHostRow[]): CtfHostRow[] =>
    (data ?? []).map(transformToCtfHostRow);

export const transformToCtfScoreAdjustResponse = (data: CtfScoreAdjustResponse): CtfScoreAdjustResponse => ({
    workout_id: data.workout_id,
    score: data.score,
});

export const transformToCtfScoreboardRow = (data: CtfScoreboardRow): CtfScoreboardRow => ({
    rank: data.rank,
    workout_id: data.workout_id,
    team_name: data.team_name,
    score: data.score,
    solve_count: data.solve_count ?? 0,
    decoy_count: data.decoy_count ?? 0,
    last_solve_at: orNull(data.last_solve_at),
});

export const transformToCtfScoreboard = (data: CtfScoreboardRow[]): CtfScoreboardRow[] =>
    (data ?? []).map(transformToCtfScoreboardRow);

export const transformToCtfSubmission = (data: CtfSubmission): CtfSubmission => ({
    id: data.id,
    ctf_id: data.ctf_id,
    workout_id: data.workout_id,
    flag_id: orNull(data.flag_id),
    submitted_digest: data.submitted_digest,
    verdict: data.verdict,
    matched_workout_id: orNull(data.matched_workout_id),
    points_awarded: data.points_awarded ?? 0,
    submitted_at: data.submitted_at,
    origin_ip: orNull(data.origin_ip),
});

export const transformToCtfSubmissionList = (data: CtfSubmission[]): CtfSubmission[] =>
    (data ?? []).map(transformToCtfSubmission);

export const transformToCtfLogEntry = (data: CtfLogEntry): CtfLogEntry => ({
    id: data.id,
    ctf_id: data.ctf_id,
    action: data.action,
    actor: data.actor,
    target: orNull(data.target),
    result: data.result,
    detail: orNull(data.detail),
    created_at: data.created_at,
});

export const transformToCtfLog = (data: CtfLogEntry[]): CtfLogEntry[] =>
    (data ?? []).map(transformToCtfLogEntry);

// ---- Student ----

const transformToCtfChallenge = (data: CtfChallenge): CtfChallenge => ({
    flag_id: data.flag_id,
    category: orNull(data.category),
    points: data.points,
    solved: data.solved === true,
    solved_at: orNull(data.solved_at),
    hint_available: data.hint_available === true,
    hint_cost: data.hint_cost ?? 0,
    hint: orNull(data.hint),
});

export const transformToCtfStudentBoard = (data: Partial<CtfStudentBoardResponse> | null): CtfStudentBoardResponse => ({
    enrolled: data?.enrolled === true,
    ctf_id: orNull(data?.ctf_id),
    name: orNull(data?.name),
    description: orNull(data?.description),
    rules_url: orNull(data?.rules_url),
    state_name: orNull(data?.state_name),
    remaining_seconds: orNull(data?.remaining_seconds),
    flag_format: orNull(data?.flag_format),
    score: orNull(data?.score),
    challenges: (data?.challenges ?? []).map(transformToCtfChallenge),
    public_scoreboard_enabled: data?.public_scoreboard_enabled === true,
});

export const transformToCtfSubmitResponse = (data: CtfSubmitResponse): CtfSubmitResponse => ({
    verdict: data.verdict,
    correct: data.correct === true,
    points_awarded: data.points_awarded ?? 0,
    message: data.message,
});

export const transformToCtfHintResponse = (data: CtfHintResponse): CtfHintResponse => ({
    flag_id: data.flag_id,
    hint: data.hint,
    hint_cost: data.hint_cost,
    score: data.score,
});

export const transformToCtfPublicScoreboardRow = (data: CtfPublicScoreboardRow): CtfPublicScoreboardRow => ({
    rank: data.rank,
    team_label: data.team_label,
    score: data.score,
    solve_count: data.solve_count ?? 0,
    is_you: data.is_you === true,
});

export const transformToCtfPublicScoreboard = (data: CtfPublicScoreboardRow[]): CtfPublicScoreboardRow[] =>
    (data ?? []).map(transformToCtfPublicScoreboardRow);

export const transformToCtfTeamRow = (data: CtfTeamRow): CtfTeamRow => ({
    workout_id: data.workout_id,
    team_name: data.team_name,
    members: data.members ?? [],
    workout_state: orNull(data.workout_state),
    workout_state_name: orNull(data.workout_state_name),
    arm_status: data.arm_status ?? 'pending',
});

export const transformToCtfTeamList = (data: CtfTeamRow[]): CtfTeamRow[] =>
    (data ?? []).map(transformToCtfTeamRow);

export const transformToCtfTemplateRow = (data: CtfTemplateRow): CtfTemplateRow => ({
    id: data.id,
    name: data.name,
    description: orNull(data.description),
    ctf_name: data.ctf_name,
    flag_count: data.flag_count ?? 0,
    servers: (data.servers ?? []).map((server) => ({
        name: server.name,
        os: orNull(server.os),
        machine_type: orNull(server.machine_type),
    })),
});

export const transformToCtfTemplateList = (data: CtfTemplateRow[]): CtfTemplateRow[] =>
    (data ?? []).map(transformToCtfTemplateRow);
