import React, {useEffect, useState} from "react";
import {Alert, Box, Button, CircularProgress, Divider, Stack, TextField, Typography} from "@mui/material";
import {WireGuardEnrollmentResult, WireGuardKit, wireguardService} from "../../../services/WireGuard/wireguard.service";
import {useClipboard} from "../../../hooks/useClipboard";

const emptyForm = {id: "", device_id: "", equipment_subnet: "", peer_public_key: "", authorized_instructors: ""};

export const WireGuardKitManager: React.FC = () => {
    const [kits, setKits] = useState<WireGuardKit[]>([]);
    const [form, setForm] = useState(emptyForm);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [enrolled, setEnrolled] = useState<WireGuardEnrollmentResult | null>(null);
    const {copy} = useClipboard();

    const load = async () => {
        setLoading(true);
        setError(null);
        try { setKits(await wireguardService.listKits()); }
        catch (err) { setError(err instanceof Error ? err.message : "Could not load registered kits."); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);

    const register = async (event: React.FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const result = await wireguardService.enrollKit({
                id: form.id.trim(),
                device_id: form.device_id.trim(),
                equipment_subnet: form.equipment_subnet.trim(),
                peer_public_key: form.peer_public_key.trim(),
                authorized_instructors: form.authorized_instructors.split(/[\s,;]+/).filter(Boolean),
            });
            setEnrolled(result);
            setForm(emptyForm);
            setKits(previous => [...previous.filter(kit => kit.id !== result.kit.id), result.kit]);
        } catch (err) { setError(err instanceof Error ? err.message : "Could not register this kit."); }
        finally { setSaving(false); }
    };

    return <Box sx={{p: {xs: 1.5, sm: 3}}}>
        <Typography variant="h5" component="h2" gutterBottom>Registered WireGuard kits</Typography>
        <Typography sx={{mb: 2}}>
            Register the Pi identity and equipment network, then authorize the instructors who may assign it to a lab.
            Keep the Pi's private key on that device; enter only its WireGuard public key here.
        </Typography>
        {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
        {enrolled && <Alert severity="success" sx={{mb: 2}}>
            <Typography sx={{fontWeight: 700}}>Kit {enrolled.kit.id} registered</Typography>
            <Typography>Save this enrollment token on the Pi now. It is shown once and grants access to this kit's assigned lab.</Typography>
            <TextField label="One-time enrollment token" value={enrolled.enrollment_token} fullWidth margin="normal"
                inputProps={{readOnly: true, autoComplete: "off"}} />
            <Stack direction={{xs: "column", sm: "row"}} spacing={1}>
                <Button onClick={() => copy(enrolled.enrollment_token)}>Copy enrollment token</Button>
                <Button onClick={() => setEnrolled(null)}>I saved the token</Button>
            </Stack>
        </Alert>}
        <Box component="form" onSubmit={register} sx={{display: "grid", gap: 2, maxWidth: 720}}>
            <Typography variant="h6" component="h3">Register a kit</Typography>
            <TextField label="Kit ID" required value={form.id}
                helperText="A stable label such as factory-kit-01."
                onChange={event => setForm({...form, id: event.target.value})} />
            <TextField label="Pi device identity" required value={form.device_id}
                helperText="Use the registered serial number or another unique device identifier."
                onChange={event => setForm({...form, device_id: event.target.value})} />
            <TextField label="Equipment IPv4 subnet" required placeholder="172.30.0.0/24" value={form.equipment_subnet}
                helperText="The factory network behind this Pi. The server validates subnet overlap before building."
                onChange={event => setForm({...form, equipment_subnet: event.target.value})} />
            <TextField label="Pi WireGuard public key" required value={form.peer_public_key}
                onChange={event => setForm({...form, peer_public_key: event.target.value})} />
            <TextField label="Authorized instructor emails" required multiline minRows={2} value={form.authorized_instructors}
                helperText="Separate emails with commas or new lines."
                onChange={event => setForm({...form, authorized_instructors: event.target.value})} />
            <Button type="submit" variant="contained" disabled={saving || !!enrolled}>
                {saving ? "Registering…" : "Register kit"}
            </Button>
        </Box>
        <Divider sx={{my: 3}} />
        <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
            <Typography variant="h6" component="h3">Kit inventory</Typography>
            <Button onClick={() => void load()} disabled={loading}>Refresh kits</Button>
            {loading && <CircularProgress size={20} aria-label="Loading kits" />}
        </Stack>
        {!loading && kits.length === 0 && <Typography>No kits have been registered.</Typography>}
        <Stack spacing={2}>
            {kits.map(kit => <Box key={kit.id} sx={{border: 1, borderColor: "divider", borderRadius: 1, p: 2, overflowWrap: "anywhere"}}>
                <Typography sx={{fontWeight: 700}}>{kit.id} — {kit.device_id}</Typography>
                <Typography>Equipment: {kit.equipment_subnet}</Typography>
                <Typography>Status: {!kit.enabled ? "Disabled" : kit.assigned_unit_id ? `Assigned to lab ${kit.assigned_unit_id}` : "Available"}</Typography>
                <Typography>Instructors: {kit.authorized_instructors.join(", ")}</Typography>
            </Box>)}
        </Stack>
    </Box>;
};
