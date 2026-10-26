import {describe, expect, it} from "vitest";
import {isWireGuardLab, wireGuardDnsSuffix, wireGuardReadiness} from "./wireguard.utils";

describe("WireGuard lab readiness", () => {
    it("distinguishes allocated endpoints, configured services, and actual tunnels", () => {
        const lease = {service_ready: true, tunnel_ready: false, health_timestamp: 1000};
        expect(wireGuardReadiness("reserved", lease, 1010)).toMatchObject({service: false, tunnel: false});
        expect(wireGuardReadiness("active", lease, 1010)).toMatchObject({service: true, tunnel: false});
        expect(wireGuardReadiness("active", {...lease, tunnel_ready: true}, 1010)).toMatchObject({service: true, tunnel: true});
    });

    it("never presents stale, missing, future, or stopped health as ready", () => {
        const lease = {service_ready: true, tunnel_ready: true, health_timestamp: 1000};
        for (const now of [999, 1121]) {
            expect(wireGuardReadiness("active", lease, now)).toMatchObject({service: false, tunnel: false, fresh: false});
        }
        expect(wireGuardReadiness("reserved", lease, 1010).service).toBe(false);
        expect(wireGuardReadiness("active", null, 1010).tunnel).toBe(false);
        expect(wireGuardReadiness("active", {...lease, expires: 1005}, 1010).service).toBe(false);
        expect(wireGuardReadiness("active", {...lease, status: "released"}, 1010).service).toBe(false);
    });

    it("derives the full tenant DNS suffix while handling absolute names", () => {
        expect(wireGuardDnsSuffix("wg10000.agoge-class-a.vpn.example.edu.")).toBe("agoge-class-a.vpn.example.edu");
    });

    it("requires explicit gateway designation rather than a name match", () => {
        expect(isWireGuardLab({servers: [{wireguard_gateway: true}]})).toBe(true);
        expect(isWireGuardLab({servers: [{}]})).toBe(false);
        expect(isWireGuardLab(null)).toBe(false);
    });
});
