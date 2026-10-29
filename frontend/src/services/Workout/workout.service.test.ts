import axios from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PubSub } from "../../types/PubSub";
import { workoutService } from "./workout.service";

vi.mock("axios", () => ({ default: { put: vi.fn() } }));
vi.mock("../../components/AgogeAuth/Firebase/firebaseConfig", () => ({
    auth: { currentUser: { getIdToken: vi.fn().mockResolvedValue("test-token") } },
}));
vi.mock("../../utilities/apiClient", () => ({ apiUrl: (endpoint: string) => endpoint }));

const headersSent = () => vi.mocked(axios.put).mock.calls[0][2]?.headers as Record<string, string>;

describe("workout put_action", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(axios.put).mockResolvedValue({ data: { data: { build_id: "abcdefghij", state: 50 } } });
    });

    it.each([PubSub.Actions.START, PubSub.Actions.STOP, PubSub.Actions.EXTEND_RUNTIME])(
        "sends student action %s without a token", async (action) => {
            await workoutService.put_action("abcdefghij", String(action));
            expect(headersSent()).not.toHaveProperty("Authorization");
        });

    it.each([PubSub.Actions.NUKE, PubSub.Actions.DELETE, PubSub.Actions.BUILD])(
        "sends instructor action %s with the signed-in token", async (action) => {
            await workoutService.put_action("abcdefghij", String(action));
            expect(headersSent()).toHaveProperty("Authorization", "Bearer test-token");
        });
});
