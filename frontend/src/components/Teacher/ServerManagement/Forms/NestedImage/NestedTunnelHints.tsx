import {Alert, Box, Divider, Typography} from "@mui/material";
import React, {useEffect, useState} from "react";
import {NestedBuildStatus, NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import {UserDetailField} from "../../../../Buttons/ConnectButton/UserDetailField";
import {nestedTunnels, NestedTunnel} from "./nestedImageStatus";

interface NestedTunnelHintsProps {
    spec: NestedHostSpec;
    // Carries each guest's reported addresses, so a DHCP guest gets a tunnel too.
    build: NestedBuildStatus | null | undefined;
    hostname: string | null | undefined;
    username: string | null | undefined;
}

const tunnelLabel = (tunnel: NestedTunnel): string => {
    if (tunnel.kind === 'console') {
        return `${tunnel.guest} console (VNC viewer to localhost:${tunnel.local_port})`;
    }
    if (tunnel.kind === 'rdp') {
        return `${tunnel.guest} RDP (connect to localhost:${tunnel.local_port})`;
    }
    return `${tunnel.guest} SSH (ssh -p ${tunnel.local_port} <user>@localhost)`;
};

// The Connect dialog section for a nested lab host: one SSH tunnel through the parent per console, and RDP
// or SSH per Windows or Linux guest. Mounted only while the dialog is open, so the catalog is fetched on open.
const NestedTunnelHints: React.FC<NestedTunnelHintsProps> = ({spec, build, hostname, username}) => {
    const [catalog, setCatalog] = useState<NestedOsCatalogEntry[]>([]);
    const [catalogPending, setCatalogPending] = useState(true);

    useEffect(() => {
        let active = true;
        nestedService.list_catalog()
            .then(entries => {
                if (active) {
                    setCatalog(entries);
                }
            })
            // Without the catalog a guest's family is unknown, and nestedTunnels offers only its console.
            .catch(() => undefined)
            .finally(() => {
                if (active) {
                    setCatalogPending(false);
                }
            });
        return () => {
            active = false;
        };
    }, []);

    if (!hostname) {
        return null;
    }
    const tunnels = nestedTunnels(spec, `${username || '<user>'}@${hostname}`, catalog, build?.guest_addresses);

    return (
        <Box component={"section"} sx={{mt: 3}}>
            <Divider />
            <Typography variant={"h6"} component={"h3"} sx={{mt: 2}}>
                Nested guests
            </Typography>
            <Typography sx={{mt: 1, mb: 1}}>
                Guests are reached through an SSH tunnel to this server. Run a command below, keep it open, then
                connect to the local port. Guest credentials and VNC passwords are in View Details.
            </Typography>
            {catalogPending && (
                <Alert severity={"info"} sx={{mb: 1}}>{"Loading the guests' operating systems for RDP and SSH tunnels…"}</Alert>
            )}
            {tunnels.length === 0 ? (
                <Alert severity={"info"}>This host has no guest consoles, and no Windows or Linux guest with an address the parent can reach.</Alert>
            ) : tunnels.map(tunnel => (
                <UserDetailField key={`${tunnel.guest}-${tunnel.kind}`} label={tunnelLabel(tunnel)} value={tunnel.command} />
            ))}
        </Box>
    );
};

export default NestedTunnelHints;
