import {Alert, Box, Divider, Typography} from "@mui/material";
import React, {useEffect, useState} from "react";
import {NestedBuildStatus, NestedHostSpec, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import {UserDetailField} from "../../../../Buttons/ConnectButton/UserDetailField";
import NestedConnectGuide from "./NestedConnectGuide";
import {nestedTunnels, NestedTunnel} from "./nestedImageStatus";

interface NestedTunnelHintsProps {
    spec: NestedHostSpec;
    // Carries each guest's reported addresses, so a DHCP guest gets a tunnel too.
    build: NestedBuildStatus | null | undefined;
    hostname: string | null | undefined;
    username: string | null | undefined;
}

const tunnelLabel = (tunnel: NestedTunnel, guestUser: string | undefined): string => {
    if (tunnel.kind === 'console') {
        return `${tunnel.guest} console (VNC viewer to localhost:${tunnel.local_port})`;
    }
    if (tunnel.kind === 'rdp') {
        return `${tunnel.guest} RDP (connect to localhost:${tunnel.local_port})`;
    }
    return `${tunnel.guest} SSH (ssh -p ${tunnel.local_port} ${guestUser || '<user>'}@localhost)`;
};

// Once per guest: the VNC password for its console, then the admin account the installer created, which
// logs in over RDP or SSH and at the console's login screen alike.
const GuestCredentials: React.FC<{spec: NestedHostSpec; guest: string; hasConsole: boolean}> = ({spec, guest, hasConsole}) => {
    const entry = spec.guests.find(item => item.name === guest);
    return (
        <>
            {hasConsole && <UserDetailField label={`${guest} VNC password`} value={spec.vnc_passwords[guest] ?? ""} />}
            <UserDetailField label={`${guest} username`} value={entry?.admin_username ?? ""} />
            <UserDetailField label={`${guest} password`} value={entry?.admin_password ?? ""} />
        </>
    );
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
    // In spec order, each guest once, with every way to reach it.
    const guests = spec.guests.map(item => item.name).filter(name => tunnels.some(tunnel => tunnel.guest === name));
    const guestUsers = Object.fromEntries(spec.guests.map(item => [item.name, item.admin_username]));

    return (
        <Box component={"section"} sx={{mt: 3}}>
            <Divider />
            <Typography variant={"h6"} component={"h3"} sx={{mt: 2}}>
                Nested guests
            </Typography>
            <Typography sx={{mt: 1, mb: 1}}>
                Guests are reached through an SSH tunnel to this server. Run a command below, keep it open, then
                connect to the local port with the credentials under it.
            </Typography>
            <NestedConnectGuide tunnels={tunnels} username={username || '<user>'} hostname={hostname} guestUsers={guestUsers} />
            {catalogPending && (
                <Alert severity={"info"} sx={{mb: 1}}>{"Loading the guests' operating systems for RDP and SSH tunnels…"}</Alert>
            )}
            {tunnels.length === 0 ? (
                <Alert severity={"info"}>This host has no guest consoles, and no Windows or Linux guest with an address the parent can reach.</Alert>
            ) : guests.map(guest => {
                const guestTunnels = tunnels.filter(tunnel => tunnel.guest === guest);
                const guestUser = spec.guests.find(item => item.name === guest)?.admin_username;
                return (
                    <Box key={guest} component={"section"} aria-label={`${guest} connections`} sx={{mb: 3}}>
                        <Typography variant={"subtitle1"} component={"h4"} sx={{fontWeight: 600}}>{guest}</Typography>
                        {guestTunnels.map(tunnel => (
                            <UserDetailField key={tunnel.kind} label={tunnelLabel(tunnel, guestUser)} value={tunnel.command} />
                        ))}
                        <GuestCredentials spec={spec} guest={guest} hasConsole={guestTunnels.some(tunnel => tunnel.kind === 'console')} />
                    </Box>
                );
            })}
        </Box>
    );
};

export default NestedTunnelHints;
