import React from "react";
import {Alert, Box, Chip, Stack, Typography} from "@mui/material";
import {WireGuardEndpoint, WireGuardLease} from "../../../services/Unit/unit.model";
import {wireGuardDnsSuffix, wireGuardReadiness} from "../../../services/WireGuard/wireguard.utils";

export const WireGuardLabStatus: React.FC<{endpoint: WireGuardEndpoint; lease?: WireGuardLease | null}> = ({endpoint, lease}) => {
    const ready = wireGuardReadiness(endpoint.status, lease);
    return <Box sx={{mt: 1.5, overflowWrap: "anywhere"}}>
        <Typography variant="body2">DNS suffix: {wireGuardDnsSuffix(endpoint.hostname)}</Typography>
        <Typography variant="body2">UDP port: {endpoint.port}</Typography>
        {lease ? <>
            <Typography sx={{mt: 1}}>Assigned kit: <strong>{lease.kit_id}</strong> ({lease.device_id})</Typography>
            <Typography variant="body2">Factory network: {lease.equipment_subnet}</Typography>
            <Typography variant="body2">Student networks: {lease.student_subnets.join(", ")}</Typography>
            <Typography variant="body2">Tunnel addresses: gateway {lease.gateway_address}, Pi {lease.peer_address}</Typography>
            <Stack direction="row" sx={{my: 1, gap: 1, flexWrap: "wrap"}}>
                <Chip label={ready.service ? "Gateway service ready" : "Gateway service not ready"}
                    color={ready.service ? "success" : "default"} size="small" />
                <Chip label={ready.tunnel ? "Factory tunnel connected" : "Factory tunnel not connected"}
                    color={ready.tunnel ? "success" : "default"} size="small" />
            </Stack>
            {lease.health_error && <Alert severity="error" sx={{my: 1}}>{lease.health_error}</Alert>}
            {lease.health_timestamp && <Typography variant="body2">
                Last gateway report: {new Date(lease.health_timestamp * 1000).toLocaleString()}{!ready.fresh ? " (stale)" : ""}
            </Typography>}
            <Typography variant="body2">
                {ready.service && !ready.tunnel
                    ? "The gateway is configured. Check that the enrolled Pi is online and its WireGuard client is running."
                    : !ready.service ? "Wait for gateway configuration to finish. If it remains unavailable, check the reported build error and gateway startup logs."
                    : "The gateway reports a recent authenticated WireGuard handshake with the assigned Pi."}
            </Typography>
        </> : <Typography variant="body2" sx={{mt: 1}}>
            This gateway has no managed kit configuration. Endpoint allocation alone does not verify tunnel connectivity.
        </Typography>}
    </Box>;
};
