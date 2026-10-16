import axios from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ctfBoardService, ctfService } from "./ctf.service";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));
vi.mock("../../components/AgogeAuth/Firebase/firebaseConfig", () => ({
    auth: { currentUser: { getIdToken: vi.fn().mockResolvedValue("test-token") } },
}));
vi.mock("../../utilities/apiClient", () => ({ apiUrl: (endpoint: string) => endpoint }));

const authHeaders = { headers: { "Content-Type": "application/json", Authorization: "Bearer test-token" } };
const noAuthHeaders = { headers: { "Content-Type": "application/json" } };

const event = {
    id: "abcdefghij",
    unit_id: "klmnopqrst",
    instructor_id: ["gm@example.edu"],
    spec: {
        name: "Spring CTF",
        flags: [],
        scoring: { flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false },
    },
    seed_version: 1,
    creation_timestamp: 1700000000,
    accumulated_pause_seconds: 0,
    public_scoreboard_enabled: false,
    board_ids: ["uvwxyzabcd"],
    boards_pending: 0,
    state: 2,
    state_timestamp: "2026-10-16T00:00:00Z",
};

describe("ctf service", () => {
    beforeEach(() => vi.clearAllMocks());

    it("unwraps the items envelope of a list and fills missing nullable keys", async () => {
        vi.mocked(axios.get).mockResolvedValue({
            data: { data: { items: [{
                id: "abcdefghij", name: "Spring CTF", unit_id: "klmnopqrst", state: 0,
                state_name: "DRAFT", board_count: 3, creation_timestamp: 1700000000,
            }] } },
        });

        expect(await ctfService.list()).toEqual([{
            id: "abcdefghij", name: "Spring CTF", unit_id: "klmnopqrst", state: 0,
            state_name: "DRAFT", board_count: 3, creation_timestamp: 1700000000,
            starts_at: null, ends_at: null,
        }]);
        expect(axios.get).toHaveBeenCalledWith("ctf/", { ...authHeaders, params: null });
    });

    it("sends a list filter as a query parameter and omits it when unset", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [] } } });

        expect(await ctfService.getSubmissions("abcdefghij", "decoy")).toEqual([]);
        expect(axios.get).toHaveBeenCalledWith("ctf/abcdefghij/submissions/", { ...authHeaders, params: { verdict: "decoy" } });

        await ctfService.getLog("abcdefghij");
        expect(axios.get).toHaveBeenLastCalledWith("ctf/abcdefghij/log/", { ...authHeaders, params: null });
    });

    it("treats a config without an explicit true as disabled", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { ctf_enabled: "yes" } } });
        expect(await ctfService.getConfig()).toEqual({ ctf_enabled: false });
    });

    it("puts an action and returns the transformed event", async () => {
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { ...event, state: 3, starts_at: 1700000100 } } });

        const updated = await ctfService.processAction("abcdefghij", { action: "start" });

        expect(axios.put).toHaveBeenCalledWith("ctf/abcdefghij/action/", { action: "start" }, authHeaders);
        expect(updated.state).toBe(3);
        expect(updated.starts_at).toBe(1700000100);
        expect(updated.ends_at).toBeNull();
        expect(updated.spec.description).toBeNull();
    });

    it("encodes the server name in a host reset path", async () => {
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { build_id: "uvwxyzabcd", exists: null } } });

        await ctfService.resetHost("abcdefghij", "uvwxyzabcd", "web server/1", { mode: "replant" });

        expect(axios.put).toHaveBeenCalledWith(
            "ctf/abcdefghij/boards/uvwxyzabcd/hosts/web%20server%2F1/reset/", { mode: "replant" }, authHeaders
        );
    });

    it("never offers a rebuild when a host row omits rebuild_allowed", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [{
            workout_id: "uvwxyzabcd", team_name: "Red", server: "web", flag_count: 2,
        }] } } });

        const [host] = await ctfService.getHosts("abcdefghij");
        expect(host.rebuild_allowed).toBe(false);
        expect(host.server_state).toBeNull();
    });

    it("lists templates from the items envelope", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [{
            id: "spec1", name: "Lab", ctf_name: "Spring", flag_count: 2, servers: [{ name: "web" }],
        }] } } });

        expect(await ctfService.getTemplates()).toEqual([{
            id: "spec1", name: "Lab", description: null, ctf_name: "Spring", flag_count: 2,
            servers: [{ name: "web", os: null, machine_type: null }],
        }]);
        expect(axios.get).toHaveBeenCalledWith("ctf/templates/", { ...authHeaders, params: null });
    });

    it("posts the create body unchanged", async () => {
        vi.mocked(axios.post).mockResolvedValue({ data: { data: { build_id: "abcdefghij", exists: null } } });

        const body = { spec_id: "spec1", name: null, expires: 1800000000 };
        expect(await ctfService.create(body)).toEqual({ build_id: "abcdefghij", exists: null });
        expect(axios.post).toHaveBeenCalledWith("ctf/", body, authHeaders);
    });

    it("reads the team list", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [{
            workout_id: "wwwwwwwwww", team_name: "Red", members: ["a@x.io"], workout_state: -1,
        }] } } });

        const [team] = await ctfService.getTeams("abcdefghij");
        expect(axios.get).toHaveBeenCalledWith("ctf/abcdefghij/teams/", { ...authHeaders, params: null });
        expect(team).toMatchObject({ team_name: "Red", workout_state: -1, workout_state_name: null, arm_status: "pending" });
    });

    it("adds a team with a post", async () => {
        vi.mocked(axios.post).mockResolvedValue({ data: { data: {
            workout_id: "wwwwwwwwww", team_name: "Red", members: ["a@x.io"],
        } } });

        const body = { team_name: "Red", members: ["a@x.io"] };
        const team = await ctfService.addTeam("abcdefghij", body);
        expect(axios.post).toHaveBeenCalledWith("ctf/abcdefghij/teams/", body, authHeaders);
        expect(team.workout_id).toBe("wwwwwwwwww");
    });

    it("replaces a team's members with a put wrapped in {members}", async () => {
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { workout_id: "wwwwwwwwww", team_name: "Red", members: ["b@x.io"] } } });

        await ctfService.setTeamMembers("abcdefghij", "wwwwwwwwww", ["b@x.io"]);
        expect(axios.put).toHaveBeenCalledWith("ctf/abcdefghij/teams/wwwwwwwwww/", { members: ["b@x.io"] }, authHeaders);
    });

    it("removes a team with a delete", async () => {
        vi.mocked(axios.delete).mockResolvedValue({ data: { data: { build_id: "wwwwwwwwww", exists: null } } });

        expect(await ctfService.removeTeam("abcdefghij", "wwwwwwwwww")).toEqual({ build_id: "wwwwwwwwww", exists: null });
        expect(axios.delete).toHaveBeenCalledWith("ctf/abcdefghij/teams/wwwwwwwwww/", authHeaders);
    });

    it("wraps the spec as {ctf} when updating it and returns the event", async () => {
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { ...event, join_code: "JOIN42" } } });
        const spec = { ...event.spec, description: null, rules_url: null };

        const updated = await ctfService.updateSpec("abcdefghij", spec as never);
        expect(axios.put).toHaveBeenCalledWith("ctf/abcdefghij/spec/", { ctf: spec }, authHeaders);
        expect(updated.join_code).toBe("JOIN42");
    });

    it("sends a server action and defaults a missing message count to 0", async () => {
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { messages: 3 } } });
        expect(await ctfService.controlServers("abcdefghij", "build")).toEqual({ messages: 3 });
        expect(axios.put).toHaveBeenCalledWith("ctf/abcdefghij/servers/", { action: "build" }, authHeaders);

        vi.mocked(axios.put).mockResolvedValue({ data: { data: {} } });
        expect(await ctfService.controlServers("abcdefghij", "stop")).toEqual({ messages: 0 });
    });

    it("preserves the API's error status and message", async () => {
        vi.mocked(axios.put).mockRejectedValue({
            response: { status: 409, data: { detail: "Cannot start an event in DRAFT." } },
        });

        await expect(ctfService.processAction("abcdefghij", { action: "start" })).rejects.toMatchObject({
            status: 409, message: "Cannot start an event in DRAFT.",
        });
    });
});

describe("ctf board service", () => {
    beforeEach(() => vi.clearAllMocks());

    it("reads an unenrolled board without a token and defaults its fields", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: { enrolled: false } } });

        const result = await ctfBoardService.getBoard("uvwxyzabcd");

        expect(axios.get).toHaveBeenCalledWith("ctf-board/uvwxyzabcd/", { ...noAuthHeaders, params: null });
        expect(result).toMatchObject({ enrolled: false, ctf_id: null, challenges: [], public_scoreboard_enabled: false });
    });

    it("posts a flag submission without a token", async () => {
        vi.mocked(axios.post).mockResolvedValue({ data: { data: {
            verdict: "correct", correct: true, points_awarded: 100, message: "Correct.",
        } } });

        expect(await ctfBoardService.submitFlag("uvwxyzabcd", "agoge{x}")).toEqual({
            verdict: "correct", correct: true, points_awarded: 100, message: "Correct.",
        });
        expect(axios.post).toHaveBeenCalledWith("ctf-board/uvwxyzabcd/submit/", { flag: "agoge{x}" }, noAuthHeaders);
    });

    it("surfaces a rate limit as a 429 error", async () => {
        vi.mocked(axios.post).mockRejectedValue({ response: { status: 429, data: { detail: "Slow down." } } });

        await expect(ctfBoardService.submitFlag("uvwxyzabcd", "agoge{x}")).rejects.toMatchObject({ status: 429 });
    });
});
