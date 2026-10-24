export const isWireGuardLab = (specification: {servers?: Array<{wireguard_gateway?: boolean}>} | null) =>
    specification?.servers?.some(server => server.wireguard_gateway === true) ?? false;

export const wireGuardDnsSuffix = (hostname: string): string =>
    hostname.replace(/\.$/, "").split(".").slice(1).join(".");

export const wireGuardReadiness = (endpointStatus: string, lease?: {
    service_ready?: boolean;
    tunnel_ready?: boolean;
    health_timestamp?: number | null;
    health_error?: string | null;
    expires?: number;
    status?: string;
} | null, now = Date.now() / 1000) => {
    const fresh = !!lease?.health_timestamp && now - lease.health_timestamp >= 0 && now - lease.health_timestamp <= 120;
    const available = endpointStatus === "active" && lease?.status !== "released"
        && (lease?.expires === undefined || lease.expires > now);
    const telemetry = available && fresh;
    return {
        available,
        telemetry,
        service: telemetry && lease?.service_ready === true,
        tunnel: telemetry && lease?.service_ready === true && lease?.tunnel_ready === true,
        fresh,
    };
};
