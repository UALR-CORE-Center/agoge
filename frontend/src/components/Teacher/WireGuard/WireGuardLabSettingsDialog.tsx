import React, {useEffect, useState} from "react";
import {Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography} from "@mui/material";
import {WireGuardLabRemoteSettings, WireGuardRemotePeer, wireguardService} from "../../../services/WireGuard/wireguard.service";

interface Props {
    open: boolean;
    unitId: string;
    onClose: () => void;
    onSaved: (settings: WireGuardLabRemoteSettings) => void | Promise<void>;
}

export const WireGuardLabSettingsDialog: React.FC<Props> = ({open, unitId, onClose, onSaved}) => {
    const [settings, setSettings] = useState<WireGuardLabRemoteSettings | null>(null);
    const [peers, setPeers] = useState<WireGuardRemotePeer[]>([]);
    const [peerId, setPeerId] = useState("");
    const [network, setNetwork] = useState("");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        if (!open) return;
        let current = true;
        setLoading(true);
        setSettings(null);
        setError(null);
        Promise.all([wireguardService.getLabRemoteSettings(unitId), wireguardService.listRemotePeers()])
            .then(([value, inventory]) => {
                if (!current) return;
                setSettings(value);
                setPeerId(value.remote_peer_id);
                setNetwork(value.remote_network_cidr);
                // The assigned peer remains selectable only for its own lab.
                const authorized = inventory.filter(peer => peer.enabled && (!peer.assigned_unit_id || peer.assigned_unit_id === unitId));
                if (!authorized.some(peer => peer.id === value.remote_peer_id)) {
                    authorized.push(value.remote_peer);
                }
                setPeers(authorized);
            })
            .catch(failure => {
                if (current) setError(failure instanceof Error ? failure.message : "Could not load this lab's remote connection settings.");
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [open, unitId, retry]);

    const save = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!settings?.can_edit || !peerId || !network.trim() || saving) return;
        setSaving(true);
        setError(null);
        try {
            const saved = await wireguardService.saveLabRemoteSettings(unitId, {
                remote_peer_id: peerId, remote_network_cidr: network.trim(),
            });
            await onSaved(saved);
            onClose();
        } catch (failure) {
            setError(failure instanceof Error ? failure.message : "Could not save this lab's remote connection settings.");
        } finally { setSaving(false); }
    };

    return <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Remote lab settings</DialogTitle>
        <Box component="form" onSubmit={save}>
            <DialogContent>
                <Typography sx={{mb: 2}}>
                    Choose the remote lab and private LAN students will access. Saved settings are applied before the gateway next starts.
                </Typography>
                <Alert severity="info" sx={{mb: 2}}>Stop all student workouts and the shared gateway before changing this connection.</Alert>
                {loading && <CircularProgress size={24} aria-label="Loading remote lab settings" />}
                {error && <Alert severity="error" sx={{mb: 2}} action={!settings && !loading
                    ? <Button color="inherit" onClick={() => setRetry(value => value + 1)}>Retry</Button> : undefined}>{error}</Alert>}
                {settings && !settings.can_edit && <Alert severity="warning" sx={{mb: 2}}>
                    {settings.blocked_reason || "Stop all students and the gateway, then reopen these settings."}
                </Alert>}
                {settings && <>
                    <TextField select fullWidth label="Remote lab" margin="normal" value={peerId}
                        disabled={!settings.can_edit || saving}
                        onChange={event => {
                            setPeerId(event.target.value);
                            setNetwork(peers.find(peer => peer.id === event.target.value)?.remote_network_cidr || "");
                        }}>
                        {peers.map(peer => <MenuItem key={peer.id} value={peer.id} disabled={!peer.enabled}>
                            {peer.name ? `${peer.name} — ` : ""}{peer.id} ({peer.remote_network_cidr})
                        </MenuItem>)}
                    </TextField>
                    <TextField label="Remote LAN for this lab (IPv4 CIDR)" fullWidth required margin="normal"
                        value={network} disabled={!settings.can_edit || saving}
                        onChange={event => setNetwork(event.target.value)}
                        helperText="This override applies only to this Agoge lab. Registered defaults are unchanged. Networks must not overlap the student or tunnel networks." />
                    {peers.find(peer => peer.id === peerId)?.description && <Typography variant="body2">
                        {peers.find(peer => peer.id === peerId)?.description}
                    </Typography>}
                </>}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button type="submit" variant="contained" disabled={loading || saving || !settings?.can_edit || !peerId || !network.trim()}>
                    {saving ? "Saving…" : "Save remote lab settings"}
                </Button>
            </DialogActions>
        </Box>
    </Dialog>;
};
