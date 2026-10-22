import React, {useEffect, useState} from "react";
import {Alert, Box, Button, FormControl, FormHelperText, InputLabel, MenuItem, Select, Typography} from "@mui/material";
import {WireGuardKit, wireguardService} from "../../../services/WireGuard/wireguard.service";

interface Props {
    open: boolean;
    value: string;
    onChange: (id: string) => void;
    onAvailabilityChange: (available: boolean) => void;
}

export const WireGuardKitSelector: React.FC<Props> = ({open, value, onChange, onAvailabilityChange}) => {
    const [kits, setKits] = useState<WireGuardKit[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        if (!open) return;
        let current = true;
        setLoading(true);
        setError(null);
        onAvailabilityChange(false);
        wireguardService.listKits().then(items => {
            if (!current) return;
            const available = items.filter(kit => kit.enabled && !kit.assigned_unit_id);
            setKits(available);
            if (!available.some(kit => kit.id === value)) onChange("");
            onAvailabilityChange(available.length > 0);
        }).catch(err => {
            if (current) setError(err instanceof Error ? err.message : "Could not load registered kits.");
        }).finally(() => {
            if (current) setLoading(false);
        });
        return () => { current = false; };
        // A selection does not reload the inventory. Reopening or retrying does.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, retry]);

    const selectedKit = kits.find(kit => kit.id === value);
    return <Box sx={{my: 2}}>
        <Typography variant="subtitle1" component="h3">Assigned factory kit</Typography>
        <Typography variant="body2" sx={{mb: 1}}>
            One registered kit is assigned exclusively to this lab. The Ubuntu gateway,
            WireGuard configuration, and student routes are set up automatically.
        </Typography>
        {error && <Alert severity="error" action={<Button color="inherit" onClick={() => setRetry(n => n + 1)}>Retry</Button>}>
            {error}
        </Alert>}
        {!loading && !error && kits.length === 0 && <Alert severity="info">
            No available kits are assigned to your account. Ask an administrator to register a kit
            or release its previous lab before building.
        </Alert>}
        <FormControl fullWidth required margin="normal" disabled={loading || !!error || kits.length === 0}>
            <InputLabel id="wireguard-kit-label">Registered kit</InputLabel>
            <Select labelId="wireguard-kit-label" label="Registered kit" value={selectedKit ? value : ""}
                onChange={event => onChange(event.target.value)}>
                {kits.map(kit => <MenuItem key={kit.id} value={kit.id}>
                    {kit.id} — {kit.device_id} ({kit.equipment_subnet})
                </MenuItem>)}
            </Select>
            <FormHelperText>{loading ? "Loading authorized kits…" : selectedKit
                ? `Equipment network: ${selectedKit.equipment_subnet}. Only this kit's routes will be permitted.`
                : "Choose the kit whose factory the students will access."}</FormHelperText>
        </FormControl>
    </Box>;
};
