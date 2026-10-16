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
