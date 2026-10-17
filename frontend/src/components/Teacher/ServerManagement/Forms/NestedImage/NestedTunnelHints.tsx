import {Alert, Box, Divider, Typography} from "@mui/material";
import React, {useEffect, useState} from "react";
import {NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import {UserDetailField} from "../../../../Buttons/ConnectButton/UserDetailField";
import {nestedTunnels, NestedTunnel} from "./nestedImageStatus";

interface NestedTunnelHintsProps {
    spec: NestedHostSpec;
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

// The Connect dialog section for a nested lab host: one SSH tunnel through the parent per console and
// per exposed guest. Mounted only while the dialog is open, so the catalog is fetched on open.
const NestedTunnelHints: React.FC<NestedTunnelHintsProps> = ({spec, hostname, username}) => {
    const [catalog, setCatalog] = useState<NestedOsCatalogEntry[]>([]);

    useEffect(() => {
        let active = true;
        nestedService.list_catalog()
            .then(entries => {
                if (active) {
                    setCatalog(entries);
                }
            })
            // Without the catalog a guest's family is unknown, and nestedTunnels offers both RDP and SSH.
            .catch(() => undefined);
        return () => {
            active = false;
        };
    }, []);

    if (!hostname) {
        return null;
    }
    const tunnels = nestedTunnels(spec, `${username || '<user>'}@${hostname}`, catalog);

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
            {tunnels.length === 0 ? (
                <Alert severity={"info"}>This host has no guest consoles or exposed guests.</Alert>
            ) : tunnels.map(tunnel => (
                <UserDetailField key={`${tunnel.guest}-${tunnel.kind}`} label={tunnelLabel(tunnel)} value={tunnel.command} />
            ))}
        </Box>
    );
};

export default NestedTunnelHints;
