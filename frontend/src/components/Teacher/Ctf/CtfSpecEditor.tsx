import FlagIcon from "@mui/icons-material/Flag";
import {LoadingButton} from "@mui/lab";
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    MenuItem,
    Stack,
    TextField,
    Typography,
} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useEffect, useId, useState} from "react";
import {CtfFlagSpec, CtfSpec, CtfStates, LocationType, OperatingSystem} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import HttpError from "../../Common/Errors/HttpError";

// CtfSetup.update_spec runs only in DRAFT: once arming starts the planted flags are fixed.
export const SPEC_EDIT_STATES: readonly number[] = [CtfStates.DRAFT];

const LOCATION_TYPES: {value: LocationType; label: string; example: string}[] = [
    {value: 'file', label: 'File', example: '/root/flag.txt or C:\\Users\\Public\\flag.txt'},
    {value: 'env', label: 'Environment variable', example: 'AGOGE_FLAG'},
    {value: 'registry', label: 'Registry value (Windows)', example: 'HKLM\\SOFTWARE\\Agoge Lab:Flag'},
    {value: 'ads', label: 'Alternate data stream (Windows)', example: 'C:\\Windows\\Temp\\notes.txt:hidden'},
];

// CtfFlagSpecModel.id in common/models/agoge.py.
const FLAG_ID_PATTERN = /^[a-z0-9][a-z0-9-]{1,31}$/;

export const blankFlag = (server: string): CtfFlagSpec => ({
    id: '',
    server,
    slot: 1,
    category: null,
    location_type: 'file',
    path: '',
    operating_system: 'linux',
    access_level: 'user',
    points: 100,
    decoy: false,
    hint: null,
    hint_cost: 0,
    unlocks_after: null,
    file_mode: null,
    file_owner: null,
});

/** Client-side checks that catch the common mistakes; the API re-validates every field and path. */
export const flagProblems = (flag: CtfFlagSpec, others: CtfFlagSpec[]): string[] => {
    const problems: string[] = [];
    if (!FLAG_ID_PATTERN.test(flag.id)) {
        problems.push("Id: 2-32 lowercase letters, digits or '-', not starting with '-'.");
    } else if (others.some((other) => other.id === flag.id)) {
        problems.push("Id is already used by another flag.");
    }
    if (!flag.server) problems.push("Choose a server.");
    if (others.some((other) => other.server === flag.server && other.slot === flag.slot)) {
        problems.push(`Slot ${flag.slot} is already used on ${flag.server}.`);
    }
    if (!flag.path.trim()) problems.push("Path is required.");
    if (!flag.decoy && flag.points <= 0) problems.push("Points must be greater than 0 (only a decoy may be 0 or negative).");
    if ((flag.location_type === 'registry' || flag.location_type === 'ads') && flag.operating_system !== 'windows') {
        problems.push("Registry and ADS flags must be on Windows.");
    }
    if (others.some((other) => other.server === flag.server && other.operating_system !== flag.operating_system)) {
        problems.push(`Every flag on ${flag.server} must use the same operating system.`);
    }
    return problems;
};

interface FlagDialogProps {
    initial: CtfFlagSpec;
    others: CtfFlagSpec[];
    serverNames: string[];
    onSave: (flag: CtfFlagSpec) => void;
    onClose: () => void;
}

const FlagDialog: React.FC<FlagDialogProps> = ({initial, others, serverNames, onSave, onClose}) => {
    const titleId = useId();
    const [flag, setFlag] = useState<CtfFlagSpec>(initial);
    const set = <K extends keyof CtfFlagSpec>(key: K, value: CtfFlagSpec[K]) => setFlag((prev) => ({...prev, [key]: value}));
    const problems = flagProblems(flag, others);
    const linuxFile = flag.location_type === 'file' && flag.operating_system === 'linux';
    const example = LOCATION_TYPES.find((type) => type.value === flag.location_type)?.example;

    const handleSave = () => {
        onSave({
            ...flag,
            category: flag.category?.trim() || null,
            hint: flag.hint?.trim() || null,
            path: flag.path.trim(),
            unlocks_after: flag.unlocks_after?.length ? flag.unlocks_after : null,
            // Only Linux file placements take a mode and owner.
            file_mode: linuxFile ? flag.file_mode?.trim() || null : null,
            file_owner: linuxFile ? flag.file_owner?.trim() || null : null,
        });
    };

    return (
        <Dialog open onClose={onClose} aria-labelledby={titleId} fullWidth maxWidth="md">
            <DialogTitle id={titleId}>{initial.id ? `Edit flag ${initial.id}` : "Add flag"}</DialogTitle>
            <DialogContent>
                <Box sx={{display: 'grid', gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'}, gap: 2, mt: 1}}>
                    <TextField label="Id" value={flag.id} onChange={(e) => set('id', e.target.value.toLowerCase())}
                               helperText="Appears inside the flag value" />
                    <TextField label="Category" value={flag.category ?? ''} onChange={(e) => set('category', e.target.value)}
                               inputProps={{maxLength: 32}} />
                    <TextField select label="Server" value={flag.server} onChange={(e) => set('server', e.target.value)}>
                        {serverNames.map((name) => <MenuItem key={name} value={name}>{name}</MenuItem>)}
                    </TextField>
                    <TextField label="Slot" type="number" value={flag.slot}
                               onChange={(e) => set('slot', Number(e.target.value))}
                               inputProps={{min: 1, max: 9}} helperText="1-9, unique per server; slot 1 is the foothold" />
                    <TextField select label="Operating system" value={flag.operating_system}
                               onChange={(e) => set('operating_system', e.target.value as OperatingSystem)}>
                        <MenuItem value="linux">Linux</MenuItem>
                        <MenuItem value="windows">Windows</MenuItem>
                    </TextField>
                    <TextField select label="Location type" value={flag.location_type}
                               onChange={(e) => set('location_type', e.target.value as LocationType)}>
                        {LOCATION_TYPES.map((type) => <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>)}
                    </TextField>
                    <TextField label="Path" value={flag.path} onChange={(e) => set('path', e.target.value)}
                               helperText={example ? `e.g. ${example}` : undefined} sx={{gridColumn: {sm: '1 / -1'}}} />
                    <TextField label="Points" type="number" value={flag.points}
                               onChange={(e) => set('points', Number(e.target.value))} />
                    <TextField select label="Access level" value={flag.access_level}
                               onChange={(e) => set('access_level', e.target.value as CtfFlagSpec['access_level'])}
                               helperText="Documentation only">
                        <MenuItem value="user">User</MenuItem>
                        <MenuItem value="root">Root</MenuItem>
                        <MenuItem value="admin">Admin</MenuItem>
                    </TextField>
                    <TextField label="Hint" value={flag.hint ?? ''} onChange={(e) => set('hint', e.target.value)}
                               multiline inputProps={{maxLength: 1000}} sx={{gridColumn: {sm: '1 / -1'}}} />
                    <TextField label="Hint cost" type="number" value={flag.hint_cost}
                               onChange={(e) => set('hint_cost', Math.max(0, Number(e.target.value)))} inputProps={{min: 0}} />
                    <TextField
                        select
                        label="Unlocks after"
                        value={flag.unlocks_after ?? []}
                        onChange={(e) => {
                            const value = e.target.value as unknown as string[] | string;
                            set('unlocks_after', typeof value === 'string' ? value.split(',') : value);
                        }}
                        SelectProps={{multiple: true}}
                        helperText="Hidden from teams until these are solved"
                    >
                        {others.filter((other) => !other.decoy).map((other) => (
                            <MenuItem key={other.id} value={other.id}>{other.id}</MenuItem>
                        ))}
                    </TextField>
                    {linuxFile && (
                        <>
                            <TextField label="File mode" value={flag.file_mode ?? ''} placeholder="0600"
                                       onChange={(e) => set('file_mode', e.target.value)} />
                            <TextField label="File owner" value={flag.file_owner ?? ''} placeholder="root:root"
                                       onChange={(e) => set('file_owner', e.target.value)} />
                        </>
                    )}
                    <FormControlLabel
                        control={<Checkbox checked={flag.decoy} onChange={(e) => set('decoy', e.target.checked)} />}
                        label="Decoy (out of scope; never listed; submitting it applies its points)"
                        sx={{gridColumn: {sm: '1 / -1'}}}
                    />
                </Box>
                {problems.length > 0 && (
                    <Alert severity="warning" sx={{mt: 2}}>{problems.map((p) => <div key={p}>{p}</div>)}</Alert>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" onClick={handleSave} disabled={problems.length > 0}>Done</Button>
            </DialogActions>
        </Dialog>
    );
};

interface CtfSpecEditorProps {
    ctfId: string;
    state: number;
    spec: CtfSpec;
    serverNames: string[];
    onSaved: () => void | Promise<void>;
}

const CtfSpecEditor: React.FC<CtfSpecEditorProps> = ({ctfId, state, spec, serverNames, onSaved}) => {
    const [draft, setDraft] = useState<CtfSpec>(spec);
    const [editingIndex, setEditingIndex] = useState<number | null>(null);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saved, setSaved] = useState(false);

    // A fresh event read replaces an unchanged draft; local edits are kept until saved or reset.
    useEffect(() => setDraft(spec), [spec]);

    const editable = SPEC_EDIT_STATES.includes(state);
    const dirty = JSON.stringify(draft) !== JSON.stringify(spec);
    const setField = <K extends keyof CtfSpec>(key: K, value: CtfSpec[K]) => {
        setSaved(false);
        setDraft((prev) => ({...prev, [key]: value}));
    };
    const setScoring = <K extends keyof CtfSpec['scoring']>(key: K, value: CtfSpec['scoring'][K]) =>
        setField('scoring', {...draft.scoring, [key]: value});

    const saveFlag = (flag: CtfFlagSpec) => {
        const flags = [...draft.flags];
        if (editingIndex === null || editingIndex >= flags.length) {
            flags.push(flag);
        } else {
            const previousId = flags[editingIndex].id;
            flags[editingIndex] = flag;
            // Keep unlock references pointing at a renamed flag.
            if (previousId && previousId !== flag.id) {
                flags.forEach((other, index) => {
                    if (other.unlocks_after?.includes(previousId)) {
                        flags[index] = {...other, unlocks_after: other.unlocks_after.map((id) => id === previousId ? flag.id : id)};
                    }
                });
            }
        }
        setField('flags', flags);
        setEditingIndex(null);
    };

    const deleteFlag = (index: number) => {
        const removed = draft.flags[index].id;
        setField('flags', draft.flags
            .filter((_flag, i) => i !== index)
            .map((flag) => {
                if (!flag.unlocks_after?.includes(removed)) return flag;
                const remaining = flag.unlocks_after.filter((id) => id !== removed);
                return {...flag, unlocks_after: remaining.length ? remaining : null};
            }));
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            await ctfService.updateSpec(ctfId, {
                ...draft,
                description: draft.description?.trim() || null,
                rules_url: draft.rules_url?.trim() || null,
            });
            setSaved(true);
            await onSaved();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not save the flags."}`);
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    const columns: GridColDef<CtfFlagSpec & {index: number}>[] = [
        {field: 'id', headerName: 'Flag', flex: 1, minWidth: 130},
        {field: 'server', headerName: 'Server', flex: 1, minWidth: 120},
        {field: 'slot', headerName: 'Slot', type: 'number', width: 70, minWidth: 60},
        {field: 'location_type', headerName: 'Location', width: 100, minWidth: 90},
        {field: 'points', headerName: 'Points', type: 'number', width: 90, minWidth: 80},
        {
            field: 'decoy',
            headerName: 'Kind',
            width: 110,
            minWidth: 90,
            valueGetter: (_value, row) => row.decoy ? 'Decoy' : row.unlocks_after?.length ? 'Locked' : 'Open',
        },
        {
            field: 'actions',
            headerName: '',
            width: 170,
            minWidth: 160,
            sortable: false,
            renderCell: (params) => (
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1, height: '100%'}}>
                    <Button size="small" variant="outlined" disabled={!editable}
                            onClick={() => setEditingIndex(params.row.index)}
                            aria-label={`Edit flag ${params.row.id}`}>
                        Edit
                    </Button>
                    <Button size="small" color="error" disabled={!editable || draft.flags.length <= 1}
                            onClick={() => deleteFlag(params.row.index)}
                            aria-label={`Delete flag ${params.row.id}`}>
                        Delete
                    </Button>
                </Box>
            ),
        },
    ];

    const editingFlag = editingIndex === null ? null
        : editingIndex >= draft.flags.length ? blankFlag(serverNames[0] ?? '') : draft.flags[editingIndex];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {!editable && (
                <Alert severity="info" sx={{mb: 2}}>Flags are fixed once the event has been armed.</Alert>
            )}
            <Box sx={{display: 'grid', gridTemplateColumns: {xs: '1fr', md: '1fr 1fr'}, gap: 2, mb: 2}}>
                <TextField label="Event name" value={draft.name} disabled={!editable}
                           onChange={(e) => setField('name', e.target.value)} inputProps={{maxLength: 100}} />
                <TextField label="Rules of engagement URL" value={draft.rules_url ?? ''} disabled={!editable}
                           onChange={(e) => setField('rules_url', e.target.value)} />
                <TextField label="Description" value={draft.description ?? ''} disabled={!editable}
                           onChange={(e) => setField('description', e.target.value)} multiline
                           inputProps={{maxLength: 2000}} sx={{gridColumn: {md: '1 / -1'}}} />
                <TextField label="Flag prefix" value={draft.scoring.flag_prefix} disabled={!editable}
                           onChange={(e) => setScoring('flag_prefix', e.target.value.toLowerCase())}
                           helperText="2-16 lowercase letters or digits, starting with a letter" />
                <TextField label="Submissions per flag per minute" type="number" disabled={!editable}
                           value={draft.scoring.submission_rate_limit} inputProps={{min: 1, max: 100}}
                           onChange={(e) => setScoring('submission_rate_limit', Number(e.target.value))} />
                <FormControlLabel
                    control={<Checkbox checked={draft.scoring.reveal_decoy_penalty} disabled={!editable}
                                       onChange={(e) => setScoring('reveal_decoy_penalty', e.target.checked)} />}
                    label="Show decoy penalties to students"
                />
            </Box>
            <StyledDataGrid
                data={draft.flags.map((flag, index) => ({...flag, index}))}
                columns={columns}
                getRowId={(row: CtfFlagSpec & {index: number}) => `${row.index}-${row.id}`}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: "No flags"}}
                labelProps={{text: "Flags", icon: <FlagIcon fontSize={"large"} />}}
                density={"comfortable"}
            />
            <Stack direction="row" spacing={1} sx={{mt: 2}} flexWrap="wrap" useFlexGap>
                <Button variant="outlined" disabled={!editable || serverNames.length === 0}
                        onClick={() => setEditingIndex(draft.flags.length)}>
                    Add flag
                </Button>
                <LoadingButton variant="contained" disabled={!editable || !dirty} loading={saving} onClick={handleSave}>
                    Save flags
                </LoadingButton>
                <Button disabled={!dirty || saving} onClick={() => setDraft(spec)}>Discard changes</Button>
            </Stack>
            {dirty && editable && (
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>
                    Unsaved changes. Saving regenerates the flag values of every team.
                </Typography>
            )}
            {error && <Alert severity="error" sx={{mt: 2}} onClose={() => setError(null)}>{error}</Alert>}
            {saved && !dirty && <Alert severity="success" sx={{mt: 2}} onClose={() => setSaved(false)}>Flags saved.</Alert>}
            {editingFlag && (
                <FlagDialog
                    initial={editingFlag}
                    others={draft.flags.filter((_flag, index) => index !== editingIndex)}
                    serverNames={serverNames}
                    onSave={saveFlag}
                    onClose={() => setEditingIndex(null)}
                />
            )}
        </Box>
    );
};

export default CtfSpecEditor;
