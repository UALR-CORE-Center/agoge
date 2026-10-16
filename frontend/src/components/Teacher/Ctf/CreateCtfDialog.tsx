import {LoadingButton} from "@mui/lab";
import {
    Alert,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    MenuItem,
    Stack,
    TextField,
    Typography,
} from "@mui/material";
import {LocalizationProvider} from "@mui/x-date-pickers";
import {AdapterDateFns} from "@mui/x-date-pickers/AdapterDateFnsV3";
import {DateTimePicker} from "@mui/x-date-pickers/DateTimePicker";
import React, {useEffect, useId, useState} from "react";
import {useNavigate} from "react-router-dom";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {CtfTemplateRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";

// The lab behind the event stays up this long by default; long enough to set up, run and review.
export const DEFAULT_EXPIRY_DAYS = 14;

const defaultExpiry = () => new Date(Date.now() + DEFAULT_EXPIRY_DAYS * 24 * 60 * 60 * 1000);

interface CreateCtfDialogProps {
    open: boolean;
    onClose: () => void;
}

const CreateCtfDialog: React.FC<CreateCtfDialogProps> = ({open, onClose}) => {
    const navigate = useNavigate();
    const titleId = useId();
    const [templates, setTemplates] = useState<CtfTemplateRow[] | null>(null);
    const [specId, setSpecId] = useState<string>("");
    const [name, setName] = useState<string>("");
    const [expires, setExpires] = useState<Date | null>(defaultExpiry);
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        setError(null);
        ctfService.getTemplates()
            .then((fetched) => {
                if (!cancelled) setTemplates(fetched ?? []);
            })
            .catch((err) => {
                if (cancelled) return;
                const {status, message} = (err ?? {}) as Partial<HttpError>;
                setTemplates([]);
                setError(`${status || "Unknown Status"}: ${message || "Could not load CTF templates."}`);
                console.error(err);
            });
        return () => {
            cancelled = true;
        };
    }, [open]);

    const template = templates?.find((row) => row.id === specId) ?? null;
    const expiresInPast = expires !== null && expires.getTime() <= Date.now();
    const canCreate = !!template && expires !== null && !expiresInPast && !creating;

    const handleClose = () => {
        if (!creating) onClose();
    };

    const handleCreate = async () => {
        if (!canCreate || expires === null) return;
        setCreating(true);
        setError(null);
        try {
            const created = await ctfService.create({
                spec_id: specId,
                name: name.trim() || null,
                expires: Math.floor(expires.getTime() / 1000),
            });
            navigate(`${URL_TEACHER_CTF_EVENT}/${created.build_id}`);
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not create the CTF event."}`);
            console.error(err);
            setCreating(false);
        }
    };

    return (
        <Dialog open={open} onClose={handleClose} aria-labelledby={titleId} fullWidth maxWidth="sm">
            <DialogTitle id={titleId}>New CTF</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{mt: 1}}>
                    <TextField
                        select
                        label="Template"
                        value={specId}
                        onChange={(e) => setSpecId(e.target.value)}
                        disabled={templates === null || creating}
                        helperText={
                            templates === null ? "Loading templates…"
                                : templates.length === 0 ? "No lab templates have a ctf block yet."
                                    : "Lab templates with a ctf block. The event builds its own lab from it."
                        }
                        fullWidth
                    >
                        {(templates ?? []).map((row) => (
                            <MenuItem key={row.id} value={row.id}>{row.name}</MenuItem>
                        ))}
                    </TextField>
                    {template && (
                        <Box sx={{p: 1.5, borderRadius: 1, bgcolor: 'action.hover'}}>
                            <Typography variant="subtitle2" component="p">{template.ctf_name}</Typography>
                            {template.description && (
                                <Typography variant="body2" color="text.secondary">{template.description}</Typography>
                            )}
                            <Typography variant="body2" sx={{mt: 1}}>
                                {template.flag_count} {template.flag_count === 1 ? "flag" : "flags"} on{" "}
                                {template.servers.map((server) => server.name).join(", ") || "no servers"}
                            </Typography>
                        </Box>
                    )}
                    <TextField
                        label="Event name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder={template?.ctf_name ?? ""}
                        helperText="Optional. Defaults to the template's CTF name."
                        inputProps={{maxLength: 100}}
                        disabled={creating}
                        fullWidth
                    />
                    <LocalizationProvider dateAdapter={AdapterDateFns}>
                        <DateTimePicker
                            label="Lab expires"
                            value={expires}
                            onChange={(value) => setExpires(value)}
                            disabled={creating}
                            disablePast
                            slotProps={{
                                textField: {
                                    fullWidth: true,
                                    helperText: expiresInPast
                                        ? "Choose a time in the future."
                                        : "Every team's servers are deleted after this time.",
                                    error: expiresInPast,
                                },
                            }}
                        />
                    </LocalizationProvider>
                    {error && <Alert severity="error">{error}</Alert>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={creating}>Cancel</Button>
                <LoadingButton variant="contained" onClick={handleCreate} disabled={!canCreate} loading={creating}>
                    Create
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};

export default CreateCtfDialog;
