import {
    URL_CTF_API_ACTION,
    URL_CTF_API_BASE,
    URL_CTF_API_BOARDS,
    URL_CTF_API_CONFIG,
    URL_CTF_API_FLAG_REVEAL,
    URL_CTF_API_FLAGS,
    URL_CTF_API_HOST_RESET,
    URL_CTF_API_HOSTS,
    URL_CTF_API_ITEM,
    URL_CTF_API_LOG,
    URL_CTF_API_SCORE,
    URL_CTF_API_SCOREBOARD,
    URL_CTF_API_SERVERS,
    URL_CTF_API_SPEC,
    URL_CTF_API_STATE,
    URL_CTF_API_SUBMISSIONS,
    URL_CTF_API_TEAM,
    URL_CTF_API_TEAMS,
    URL_CTF_API_TEMPLATES,
    URL_CTF_BOARD_API_HINT,
    URL_CTF_BOARD_API_ITEM,
    URL_CTF_BOARD_API_SCOREBOARD,
    URL_CTF_BOARD_API_SUBMIT,
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    transformToCtfBoardStatusList,
    transformToCtfConfig,
    transformToCtfEvent,
    transformToCtfEventSummaryList,
    transformToCtfFlagReveal,
    transformToCtfFlagRowList,
    transformToCtfHintResponse,
    transformToCtfHostRowList,
    transformToCtfIdResponse,
    transformToCtfLog,
    transformToCtfPublicScoreboard,
    transformToCtfReplantResponse,
    transformToCtfScoreAdjustResponse,
    transformToCtfScoreboard,
    transformToCtfState,
    transformToCtfStudentBoard,
    transformToCtfSubmissionList,
    transformToCtfSubmitResponse,
    transformToCtfTeamList,
    transformToCtfTeamRow,
    transformToCtfTemplateList,
} from "../../utilities/transformers/ctf.transform";
import {apiService} from "../api-request.service";
import {
    CtfActionRequest,
    CtfBoardStatus,
    CtfConfigResponse,
    CtfCreateRequest,
    CtfEvent,
    CtfEventSummary,
    CtfFlagRevealResponse,
    CtfFlagRow,
    CtfHintResponse,
    CtfHostResetRequest,
    CtfHostRow,
    CtfIdResponse,
    CtfLogEntry,
    CtfPublicScoreboardRow,
    CtfReplantRequest,
    CtfReplantResponse,
    CtfScoreAdjustRequest,
    CtfScoreAdjustResponse,
    CtfScoreboardRow,
    CtfServersAction,
    CtfServersResponse,
    CtfSpec,
    CtfStateResponse,
    CtfStudentBoardResponse,
    CtfSubmission,
    CtfSubmitResponse,
    CtfTeamRequest,
    CtfTeamRow,
    CtfTemplateRow,
    CtfUpdateRequest,
    LogAction,
    Verdict,
} from "./ctf.model";

// Path segments are encoded: server names come from the lab spec, not from IdGenerator.
const url = (template: string, values: Record<string, string>) => formatString(template, values, true);
const item = (ctfId: string, template: string = URL_CTF_API_ITEM, extra: Record<string, string> = {}) =>
    url(template, {ITEM_ID: ctfId, ...extra});

// ---- Instructor (/ctf) ----

const getConfig = async () =>
    await apiService.get<CtfConfigResponse>(URL_CTF_API_CONFIG, null, true, transformToCtfConfig);

const list = async () =>
    await apiService.get<CtfEventSummary[]>(URL_CTF_API_BASE, null, true, transformToCtfEventSummaryList);

const create = async (request: CtfCreateRequest) =>
    await apiService.post<CtfIdResponse>(URL_CTF_API_BASE, request, true, null, transformToCtfIdResponse);

const get = async (ctfId: string) =>
    await apiService.get<CtfEvent>(item(ctfId), null, true, transformToCtfEvent);

const remove = async (ctfId: string) =>
    await apiService.del<CtfIdResponse>(item(ctfId), true, transformToCtfIdResponse);

const getState = async (ctfId: string) =>
    await apiService.get<CtfStateResponse>(item(ctfId, URL_CTF_API_STATE), null, true, transformToCtfState);

const getFlags = async (ctfId: string) =>
    await apiService.get<CtfFlagRow[]>(item(ctfId, URL_CTF_API_FLAGS), null, true, transformToCtfFlagRowList);

const replant = async (ctfId: string, request: CtfReplantRequest = {}) =>
    await apiService.put<CtfReplantResponse>(item(ctfId, URL_CTF_API_FLAGS), request, true, transformToCtfReplantResponse);

const revealFlag = async (ctfId: string, flagId: string, workoutId: string) =>
    await apiService.get<CtfFlagRevealResponse>(
        item(ctfId, URL_CTF_API_FLAG_REVEAL, {FLAG_ID: flagId}), {workout_id: workoutId}, true, transformToCtfFlagReveal
    );

const getBoards = async (ctfId: string) =>
    await apiService.get<CtfBoardStatus[]>(item(ctfId, URL_CTF_API_BOARDS), null, true, transformToCtfBoardStatusList);

const getHosts = async (ctfId: string) =>
    await apiService.get<CtfHostRow[]>(item(ctfId, URL_CTF_API_HOSTS), null, true, transformToCtfHostRowList);

// The API answers with the workout id only; the reset itself runs asynchronously.
const resetHost = async (ctfId: string, workoutId: string, server: string, request: CtfHostResetRequest) =>
    await apiService.put<CtfIdResponse>(
        item(ctfId, URL_CTF_API_HOST_RESET, {WORKOUT_ID: workoutId, SERVER: server}), request, true, transformToCtfIdResponse
    );

const adjustScore = async (ctfId: string, workoutId: string, request: CtfScoreAdjustRequest) =>
    await apiService.put<CtfScoreAdjustResponse>(
        item(ctfId, URL_CTF_API_SCORE, {WORKOUT_ID: workoutId}), request, true, transformToCtfScoreAdjustResponse
    );

const getScoreboard = async (ctfId: string) =>
    await apiService.get<CtfScoreboardRow[]>(item(ctfId, URL_CTF_API_SCOREBOARD), null, true, transformToCtfScoreboard);

// Omitting the filter sends no query parameter, so the API applies none.
const getSubmissions = async (ctfId: string, verdict?: Verdict) =>
    await apiService.get<CtfSubmission[]>(
        item(ctfId, URL_CTF_API_SUBMISSIONS), verdict ? {verdict} : null, true, transformToCtfSubmissionList
    );

const getLog = async (ctfId: string, action?: LogAction) =>
    await apiService.get<CtfLogEntry[]>(item(ctfId, URL_CTF_API_LOG), action ? {action} : null, true, transformToCtfLog);

// PUT /ctf/{id}/ and PUT /ctf/{id}/action/ both answer with the updated event.
const update = async (ctfId: string, request: CtfUpdateRequest) =>
    await apiService.put<CtfEvent>(item(ctfId), request, true, transformToCtfEvent);

const processAction = async (ctfId: string, request: CtfActionRequest) =>
    await apiService.put<CtfEvent>(item(ctfId, URL_CTF_API_ACTION), request, true, transformToCtfEvent);

// ---- Setup (DRAFT): templates, teams, flags, servers ----

const getTemplates = async () =>
    await apiService.get<CtfTemplateRow[]>(URL_CTF_API_TEMPLATES, null, true, transformToCtfTemplateList);

const getTeams = async (ctfId: string) =>
    await apiService.get<CtfTeamRow[]>(item(ctfId, URL_CTF_API_TEAMS), null, true, transformToCtfTeamList);

const addTeam = async (ctfId: string, request: CtfTeamRequest) =>
    await apiService.post<CtfTeamRow>(item(ctfId, URL_CTF_API_TEAMS), request, true, null, transformToCtfTeamRow);

const setTeamMembers = async (ctfId: string, workoutId: string, members: string[]) =>
    await apiService.put<CtfTeamRow>(
        item(ctfId, URL_CTF_API_TEAM, {WORKOUT_ID: workoutId}), {members}, true, transformToCtfTeamRow
    );

const removeTeam = async (ctfId: string, workoutId: string) =>
    await apiService.del<CtfIdResponse>(item(ctfId, URL_CTF_API_TEAM, {WORKOUT_ID: workoutId}), true, transformToCtfIdResponse);

const updateSpec = async (ctfId: string, ctf: CtfSpec) =>
    await apiService.put<CtfEvent>(item(ctfId, URL_CTF_API_SPEC), {ctf}, true, transformToCtfEvent);

const controlServers = async (ctfId: string, action: CtfServersAction) =>
    await apiService.put<CtfServersResponse>(
        item(ctfId, URL_CTF_API_SERVERS), {action}, true, (data: CtfServersResponse) => ({messages: data?.messages ?? 0})
    );

// ---- Student (/ctf-board) ----
// These routes carry no auth on the API (the workout id is the capability), so no token is sent.

const board = (workoutId: string, template: string = URL_CTF_BOARD_API_ITEM, extra: Record<string, string> = {}) =>
    url(template, {WORKOUT_ID: workoutId, ...extra});

const getBoard = async (workoutId: string) =>
    await apiService.get<CtfStudentBoardResponse>(board(workoutId), null, false, transformToCtfStudentBoard);

const submitFlag = async (workoutId: string, flag: string) =>
    await apiService.post<CtfSubmitResponse>(
        board(workoutId, URL_CTF_BOARD_API_SUBMIT), {flag}, false, null, transformToCtfSubmitResponse
    );

const takeHint = async (workoutId: string, flagId: string) =>
    await apiService.post<CtfHintResponse>(
        board(workoutId, URL_CTF_BOARD_API_HINT, {FLAG_ID: flagId}), null, false, null, transformToCtfHintResponse
    );

const getPublicScoreboard = async (workoutId: string) =>
    await apiService.get<CtfPublicScoreboardRow[]>(
        board(workoutId, URL_CTF_BOARD_API_SCOREBOARD), null, false, transformToCtfPublicScoreboard
    );

export const ctfService = {
    addTeam,
    adjustScore,
    controlServers,
    create,
    get,
    getBoards,
    getConfig,
    getFlags,
    getHosts,
    getLog,
    getScoreboard,
    getState,
    getSubmissions,
    getTeams,
    getTemplates,
    list,
    processAction,
    remove,
    removeTeam,
    replant,
    resetHost,
    revealFlag,
    setTeamMembers,
    update,
    updateSpec,
};

export const ctfBoardService = {
    getBoard,
    getPublicScoreboard,
    submitFlag,
    takeHint,
};
