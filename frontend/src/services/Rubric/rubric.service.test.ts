import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import { rubricService } from "./rubric.service";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));
vi.mock("../../components/AgogeAuth/Firebase/firebaseConfig", () => ({
    auth: { currentUser: { getIdToken: vi.fn().mockResolvedValue("test-token") } },
}));
vi.mock("../../utilities/apiClient", () => ({ apiUrl: (endpoint: string) => endpoint }));

const rubric = {
    build_id: "abcdefghij",
    categories: ["Configuration"],
    headers: ["Proficient"],
    criteria: [{ category: "Configuration", index: 0, description: "Complete." }],
};

describe("rubric service", () => {
    beforeEach(() => vi.clearAllMocks());

    it("returns null for an expected missing rubric", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: null, redirect: null } });
        expect(await rubricService.get(rubric.build_id)).toBeNull();
    });

    it("loads an existing rubric", async () => {
        vi.mocked(axios.get).mockResolvedValue({ data: { data: rubric } });
        expect(await rubricService.get(rubric.build_id)).toEqual(rubric);
    });

    it("transforms the generation response into an editable rubric", async () => {
        const { build_id, ...content } = rubric;
        vi.mocked(axios.post).mockResolvedValue({ data: { data: { content, id: build_id } } });

        expect(await rubricService.generate_rubric(build_id, { id: build_id })).toEqual(rubric);
        expect(axios.post).toHaveBeenCalledWith(
            expect.any(String), { id: build_id },
            { headers: { "Content-Type": "application/json", Authorization: "Bearer test-token" } }
        );
    });

    it("preserves the API's actionable error message", async () => {
        vi.mocked(axios.post).mockRejectedValue({
            response: { status: 503, data: { detail: "Ask an administrator to add API credits." } },
        });

        await expect(rubricService.generate_rubric(rubric.build_id, {})).rejects.toMatchObject({
            status: 503, message: "Ask an administrator to add API credits.",
        });
    });
});
