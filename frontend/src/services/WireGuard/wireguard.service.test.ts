import {beforeEach, describe, expect, it, vi} from "vitest";
import axios from "axios";
import {wireguardService} from "./wireguard.service";

vi.mock("axios", () => ({default: {get: vi.fn(), post: vi.fn()}}));
vi.mock("../../components/AgogeAuth/Firebase/firebaseConfig", () => ({
    auth: {currentUser: {getIdToken: vi.fn().mockResolvedValue("teacher-id-token")}},
}));
vi.mock("../../utilities/apiClient", () => ({apiUrl: (path: string) => path}));

describe("WireGuard instructor API", () => {
    beforeEach(() => vi.clearAllMocks());

    it("authenticates kit inventory and extracts only authorized API items", async () => {
        vi.mocked(axios.get).mockResolvedValue({data: {data: {items: [{id: "factory-01"}]}}});
        expect(await wireguardService.listKits()).toEqual([{id: "factory-01"}]);
        expect(axios.get).toHaveBeenCalledWith("wireguard/kits/", expect.objectContaining({
            headers: expect.objectContaining({Authorization: "Bearer teacher-id-token"}),
        }));
    });

    it("submits the selected kit and lab settings with instructor authentication", async () => {
        vi.mocked(axios.post).mockResolvedValue({data: {data: {build_id: "abcdefghij"}}});
        const payload = {kit_id: "factory-01", build_count: 12, expires: "2027-01-15T23:59:00Z"};
        expect(await wireguardService.createLab(payload)).toEqual({build_id: "abcdefghij"});
        expect(axios.post).toHaveBeenCalledWith("wireguard/labs/", payload, expect.objectContaining({
            headers: expect.objectContaining({Authorization: "Bearer teacher-id-token"}),
        }));
    });
});
