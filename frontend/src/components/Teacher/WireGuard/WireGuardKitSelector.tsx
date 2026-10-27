import React, {useEffect, useState} from "react";
import {Alert, Box, Button, FormControl, FormHelperText, InputLabel, MenuItem, Select, Typography} from "@mui/material";
import {WireGuardRemotePeer, wireguardService} from "../../../services/WireGuard/wireguard.service";

interface Props {
    open: boolean;
    value: string;
    onChange: (id: string) => void;
    onAvailabilityChange: (available: boolean) => void;
    onPeerChange?: (peer: WireGuardRemotePeer | undefined) => void;
}

export const WireGuardRemotePeerSelector: React.FC<Props> = ({open, value, onChange, onAvailabilityChange, onPeerChange}) => {
    const [remotePeers, setRemotePeers] = useState<WireGuardRemotePeer[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        if (!open) return;
        let current = true;
        setLoading(true);
        setError(null);
        onAvailabilityChange(false);
        wireguardService.listRemotePeers().then(items => {
            if (!current) return;
            const available = items.filter(peer => peer.enabled && !peer.assigned_unit_id);
            setRemotePeers(available);
            if (!available.some(peer => peer.id === value)) {
                onChange("");
                onPeerChange?.(undefined);
            }
            onAvailabilityChange(available.length > 0);
        }).catch(err => {
            if (current) setError(err instanceof Error ? err.message : "Could not load registered remote peers.");
        }).finally(() => {
            if (current) setLoading(false);
        });
        return () => { current = false; };
        // A selection does not reload the inventory. Reopening or retrying does.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, retry]);

    const selectedPeer = remotePeers.find(peer => peer.id === value);
    return <Box sx={{my: 2}}>
        <Typography variant="subtitle1" component="h3">Remote lab connection</Typography>
        <Typography variant="body2" sx={{mb: 1}}>
            Select the remote peer whose private LAN the students will access. It is assigned exclusively
            to this Agoge lab; the gateway, WireGuard configuration, and remote LAN routes are set up automatically.
        </Typography>
        {error && <Alert severity="error" action={<Button color="inherit" onClick={() => setRetry(n => n + 1)}>Retry</Button>}>
            {error}
        </Alert>}
        {!loading && !error && remotePeers.length === 0 && <Alert severity="info">
            No available remote peers are authorized for your account. Ask an administrator to register
            or authorize a remote peer, or release its previous lab before building.
        </Alert>}
        <FormControl fullWidth required margin="normal" disabled={loading || !!error || remotePeers.length === 0}>
            <InputLabel id="wireguard-remote-peer-label">Remote peer</InputLabel>
            <Select labelId="wireguard-remote-peer-label" label="Remote peer" value={selectedPeer ? value : ""}
                onChange={event => {
                    onChange(event.target.value);
                    onPeerChange?.(remotePeers.find(peer => peer.id === event.target.value));
                }}>
                {remotePeers.map(peer => <MenuItem key={peer.id} value={peer.id}>
                    {peer.name ? `${peer.name} — ` : ""}{peer.id} — {peer.device_id} ({peer.remote_network_cidr})
                </MenuItem>)}
            </Select>
            <FormHelperText>{loading ? "Loading authorized remote peers…" : selectedPeer
                ? `Remote LAN (IPv4 CIDR): ${selectedPeer.remote_network_cidr}. Student access is limited to this remote lab network.`
                : "Choose the remote peer for the lab the students will access."}</FormHelperText>
        </FormControl>
    </Box>;
};

export {WireGuardRemotePeerSelector as WireGuardKitSelector};
