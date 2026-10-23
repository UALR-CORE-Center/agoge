import React, {useEffect, useState} from "react";
import {Alert, Box, Button, CircularProgress, Divider, Stack, TextField, Typography} from "@mui/material";
import {WireGuardRemotePeerEnrollmentResult, WireGuardRemotePeer, wireguardService} from "../../../services/WireGuard/wireguard.service";
import {useClipboard} from "../../../hooks/useClipboard";

const emptyForm = {id: "", device_id: "", remote_network_cidr: "", peer_public_key: "", authorized_instructors: ""};

export const WireGuardRemotePeerManager: React.FC = () => {
    const [remotePeers, setRemotePeers] = useState<WireGuardRemotePeer[]>([]);
    const [form, setForm] = useState(emptyForm);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [enrolled, setEnrolled] = useState<WireGuardRemotePeerEnrollmentResult | null>(null);
    const {copy} = useClipboard();

    const load = async () => {
        setLoading(true);
        setError(null);
        try { setRemotePeers(await wireguardService.listRemotePeers()); }
        catch (err) { setError(err instanceof Error ? err.message : "Could not load registered remote peers."); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);

    const register = async (event: React.FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const result = await wireguardService.enrollRemotePeer({
                id: form.id.trim(),
                device_id: form.device_id.trim(),
                remote_network_cidr: form.remote_network_cidr.trim(),
                peer_public_key: form.peer_public_key.trim(),
                authorized_instructors: form.authorized_instructors.split(/[\s,;]+/).filter(Boolean),
            });
            setEnrolled(result);
            setForm(emptyForm);
            setRemotePeers(previous => [...previous.filter(peer => peer.id !== result.remote_peer.id), result.remote_peer]);
        } catch (err) { setError(err instanceof Error ? err.message : "Could not register this remote peer."); }
        finally { setSaving(false); }
    };

    return <Box sx={{p: {xs: 1.5, sm: 3}}}>
        <Typography variant="h5" component="h2" gutterBottom>Remote labs and WireGuard peers</Typography>
        <Typography sx={{mb: 2}}>
            Register the remote peer that connects a private LAN to an Agoge lab, then authorize its instructors.
            Keep the remote peer's private key on that device; enter only its WireGuard public key here.
        </Typography>
        {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
        {enrolled && <Alert severity="success" sx={{mb: 2}}>
            <Typography sx={{fontWeight: 700}}>Remote peer {enrolled.remote_peer.id} registered</Typography>
            <Typography>Save this enrollment token on the remote device now. It is shown once and grants access to this remote peer's assigned lab configuration.</Typography>
            <TextField label="One-time enrollment token" value={enrolled.enrollment_token} fullWidth margin="normal"
                inputProps={{readOnly: true, autoComplete: "off"}} />
            <Stack direction={{xs: "column", sm: "row"}} spacing={1}>
                <Button onClick={() => copy(enrolled.enrollment_token)}>Copy enrollment token</Button>
                <Button onClick={() => setEnrolled(null)}>I saved the token</Button>
            </Stack>
        </Alert>}
        <Box component="form" onSubmit={register} sx={{display: "grid", gap: 2, maxWidth: 720}}>
            <Typography variant="h6" component="h3">Register a remote peer</Typography>
            <TextField label="Remote peer ID" required value={form.id}
                helperText="A stable identifier for this remote lab, such as remote-lab-01."
                onChange={event => setForm({...form, id: event.target.value})} />
            <TextField label="Remote device identity" required value={form.device_id}
                helperText="Use the registered serial number or another unique device identifier."
                onChange={event => setForm({...form, device_id: event.target.value})} />
            <TextField label="Remote LAN (IPv4 CIDR)" required placeholder="172.30.0.0/24" value={form.remote_network_cidr}
                helperText="Enter the private LAN behind the remote peer, such as 172.30.0.0/24. This becomes the routed remote lab network; the server checks for overlap before building."
                onChange={event => setForm({...form, remote_network_cidr: event.target.value})} />
            <TextField label="Remote peer WireGuard public key" required value={form.peer_public_key}
                onChange={event => setForm({...form, peer_public_key: event.target.value})} />
            <TextField label="Authorized instructor emails" required multiline minRows={2} value={form.authorized_instructors}
                helperText="Separate emails with commas or new lines."
                onChange={event => setForm({...form, authorized_instructors: event.target.value})} />
            <Button type="submit" variant="contained" disabled={saving || !!enrolled}>
                {saving ? "Registering…" : "Register remote peer"}
            </Button>
        </Box>
        <Divider sx={{my: 3}} />
        <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
            <Typography variant="h6" component="h3">Remote lab inventory</Typography>
            <Button onClick={() => void load()} disabled={loading}>Refresh remote peers</Button>
            {loading && <CircularProgress size={20} aria-label="Loading remote peers" />}
        </Stack>
        {!loading && remotePeers.length === 0 && <Typography>No remote peers have been registered.</Typography>}
        <Stack spacing={2}>
            {remotePeers.map(peer => <Box key={peer.id} sx={{border: 1, borderColor: "divider", borderRadius: 1, p: 2, overflowWrap: "anywhere"}}>
                <Typography sx={{fontWeight: 700}}>{peer.id} — {peer.device_id}</Typography>
                <Typography>Remote LAN (IPv4 CIDR): {peer.remote_network_cidr}</Typography>
                <Typography>Status: {!peer.enabled ? "Disabled" : peer.assigned_unit_id ? `Assigned to lab ${peer.assigned_unit_id}` : "Available"}</Typography>
                <Typography>Instructors: {peer.authorized_instructors.join(", ")}</Typography>
            </Box>)}
        </Stack>
    </Box>;
};

export {WireGuardRemotePeerManager as WireGuardKitManager};
