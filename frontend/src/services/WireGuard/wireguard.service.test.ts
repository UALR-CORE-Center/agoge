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

    it("authenticates remote peer inventory and retains the explicit remote LAN", async () => {
        const peer = {id: "remote-lab-01", device_id: "router-01", remote_network_cidr: "192.168.8.0/24",
            peer_public_key: "public-key", authorized_instructors: ["teacher@example.edu"], enabled: true};
        vi.mocked(axios.get).mockResolvedValue({data: {data: {items: [peer]}}});
        expect(await wireguardService.listRemotePeers()).toEqual([{...peer, assigned_unit_id: null}]);
        expect(axios.get).toHaveBeenCalledWith("wireguard/remote-peers/", expect.objectContaining({
            headers: expect.objectContaining({Authorization: "Bearer teacher-id-token"}),
        }));
    });

    it("submits the selected remote peer and lab settings with instructor authentication", async () => {
        vi.mocked(axios.post).mockResolvedValue({data: {data: {build_id: "abcdefghij"}}});
        const payload = {remote_peer_id: "remote-lab-01", build_count: 12, expires: "2027-01-15T23:59:00Z"};
        expect(await wireguardService.createLab(payload)).toEqual({build_id: "abcdefghij"});
        expect(axios.post).toHaveBeenCalledWith("wireguard/labs/", payload, expect.objectContaining({
            headers: expect.objectContaining({Authorization: "Bearer teacher-id-token"}),
        }));
    });

    it("sends the configured private LAN to the canonical enrollment route", async () => {
        const request = {id: "remote-lab-01", device_id: "router-01", remote_network_cidr: "192.168.8.0/24",
            peer_public_key: "public-key", authorized_instructors: ["teacher@example.edu"]};
        vi.mocked(axios.post).mockResolvedValue({data: {data: {
            remote_peer: {...request, enabled: true}, enrollment_token: "one-time-token",
        }}});
        expect(await wireguardService.enrollRemotePeer(request)).toMatchObject({
            remote_peer: {...request, enabled: true}, enrollment_token: "one-time-token",
        });
        expect(axios.post).toHaveBeenCalledWith("wireguard/remote-peers/", request, expect.objectContaining({
            headers: expect.objectContaining({Authorization: "Bearer teacher-id-token"}),
        }));
    });

    it("normalizes legacy stored LAN names without exposing legacy wording to the UI", async () => {
        const legacy = {id: "old-peer", device_id: "router-01", equipment_subnet: "172.30.0.0/24",
            peer_public_key: "public-key", authorized_instructors: ["teacher@example.edu"], enabled: true};
        vi.mocked(axios.get).mockResolvedValue({data: {data: {items: [legacy]}}});
        const peers = await wireguardService.listRemotePeers();
        expect(peers[0].remote_network_cidr).toBe("172.30.0.0/24");
        expect(peers[0]).not.toHaveProperty("equipment_subnet");
    });
});
