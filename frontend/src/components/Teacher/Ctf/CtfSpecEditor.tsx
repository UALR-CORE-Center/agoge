import FlagIcon from "@mui/icons-material/Flag";
import {LoadingButton} from "@mui/lab";
import {
    Alert,
    Autocomplete,
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
    styled,
    TextField,
    Typography,
} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useEffect, useId, useState} from "react";
import {CtfFlagSpec, CtfSpec, CtfStates, LocationType, OperatingSystem, WindowsAccess} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import HttpError from "../../Common/Errors/HttpError";

/** A required TextField whose label asterisk is red, matching the template editor's required marks. */
const RequiredTextField = styled(TextField)(({theme}) => ({
    '& .MuiFormLabel-asterisk': {color: theme.palette.error.main},
}));

// CtfSetup.update_spec runs only in DRAFT: once arming starts the planted flags are fixed.
export const SPEC_EDIT_STATES: readonly number[] = [CtfStates.DRAFT];

const LOCATION_TYPES: {value: LocationType; label: string; example: string}[] = [
    {value: 'file', label: 'File', example: '/root/flag.txt or C:\\Users\\Public\\flag.txt'},
    {value: 'env', label: 'Environment variable', example: 'AGOGE_FLAG'},
    {value: 'registry', label: 'Registry value (Windows)', example: 'HKLM\\SOFTWARE\\Agoge Lab:Flag'},
    {value: 'ads', label: 'Alternate data stream (Windows)', example: 'C:\\Windows\\Temp\\notes.txt:hidden'},
];

// Common CTF categories offered in the flag dialog; any other text is accepted as a custom category.
export const STANDARD_CATEGORIES: readonly string[] = [
    'Web',
    'Crypto',
    'Forensics',
    'Reverse Engineering',
    'Binary Exploitation',
    'Privilege Escalation',
    'Linux',
    'Windows',
    'Active Directory',
    'Network',
    'OSINT',
    'Steganography',
    'Miscellaneous',
];

// CtfFlagSpecModel.id in common/models/agoge.py.
const FLAG_ID_PATTERN = /^[a-z0-9][a-z0-9-]{1,31}$/;
// CtfFlagSpecModel.windows_user in common/models/agoge.py.
const WINDOWS_USER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$/;

const WINDOWS_ACCESS_OPTIONS: {value: WindowsAccess | ''; label: string}[] = [
    {value: '', label: "Inherit from folder (default)"},
    {value: 'administrators', label: "Administrators only"},
    {value: 'user', label: "Administrators and one user"},
    {value: 'everyone', label: "Everyone can read"},
];

/** Windows access and Hidden apply to Windows file flags and to the host file of an ADS flag. */
export const isWindowsFile = (flag: CtfFlagSpec): boolean =>
    flag.operating_system === 'windows' && (flag.location_type === 'file' || flag.location_type === 'ads');

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
    windows_access: null,
    windows_user: null,
    hidden: false,
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
    if (isWindowsFile(flag) && flag.windows_access === 'user' && !WINDOWS_USER_PATTERN.test(flag.windows_user?.trim() ?? '')) {
        problems.push("Windows user: 1-20 letters, digits, '.', '_' or '-' (the local account name).");
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
    const windowsFile = isWindowsFile(flag);
    const example = LOCATION_TYPES.find((type) => type.value === flag.location_type)?.example;
    // Custom categories already used in this spec are offered too, so teams see one consistent spelling.
    const categoryOptions = Array.from(new Set([
        ...STANDARD_CATEGORIES,
        ...others.map((other) => other.category?.trim()).filter((category): category is string => !!category),
    ]));

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
            // Only Windows file and ADS placements take access and Hidden; the user only with 'user' access.
            windows_access: windowsFile ? flag.windows_access || null : null,
            windows_user: windowsFile && flag.windows_access === 'user' ? flag.windows_user?.trim() || null : null,
            hidden: windowsFile ? !!flag.hidden : false,
        });
    };

    return (
        <Dialog open onClose={onClose} aria-labelledby={titleId} fullWidth maxWidth="md">
            <DialogTitle id={titleId}>{initial.id ? `Edit flag ${initial.id}` : "Add flag"}</DialogTitle>
            <DialogContent>
                <Box sx={{display: 'grid', gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'}, gap: 2, mt: 1}}>
                    <RequiredTextField required label="Id" value={flag.id} onChange={(e) => set('id', e.target.value.toLowerCase())}
                               helperText="Appears inside the flag value" />
                    <Autocomplete
                        freeSolo
                        options={categoryOptions}
                        inputValue={flag.category ?? ''}
                        onInputChange={(_event, value) => set('category', value)}
                        renderInput={(params) => (
                            <TextField {...params} label="Category"
                                       inputProps={{...params.inputProps, maxLength: 32}}
                                       helperText="Pick one or type your own" />
                        )}
                    />
                    <RequiredTextField required select label="Server" value={flag.server} onChange={(e) => set('server', e.target.value)}>
                        {serverNames.map((name) => <MenuItem key={name} value={name}>{name}</MenuItem>)}
                    </RequiredTextField>
                    <RequiredTextField required label="Slot" type="number" value={flag.slot}
                               onChange={(e) => set('slot', Number(e.target.value))}
                               inputProps={{min: 1, max: 9}} helperText="1-9, unique per server; slot 1 is the foothold" />
                    <RequiredTextField required select label="Operating system" value={flag.operating_system}
                               onChange={(e) => set('operating_system', e.target.value as OperatingSystem)}>
                        <MenuItem value="linux">Linux</MenuItem>
                        <MenuItem value="windows">Windows</MenuItem>
                    </RequiredTextField>
                    <RequiredTextField required select label="Location type" value={flag.location_type}
                               onChange={(e) => set('location_type', e.target.value as LocationType)}>
                        {LOCATION_TYPES.map((type) => <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>)}
                    </RequiredTextField>
                    <RequiredTextField required label="Path" value={flag.path} onChange={(e) => set('path', e.target.value)}
                               helperText={example ? `e.g. ${example}` : undefined} sx={{gridColumn: {sm: '1 / -1'}}} />
                    <RequiredTextField required label="Points" type="number" value={flag.points}
                               onChange={(e) => set('points', Number(e.target.value))} />
                    <RequiredTextField required select label="Access level" value={flag.access_level}
                               onChange={(e) => set('access_level', e.target.value as CtfFlagSpec['access_level'])}
                               helperText="Documentation only">
                        <MenuItem value="user">User</MenuItem>
                        <MenuItem value="root">Root</MenuItem>
                        <MenuItem value="admin">Admin</MenuItem>
                    </RequiredTextField>
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
                    {windowsFile && (
                        <>
                            <TextField select label="Windows access" value={flag.windows_access ?? ''}
                                       onChange={(e) => set('windows_access', (e.target.value || null) as WindowsAccess | null)}
                                       helperText={flag.location_type === 'ads'
                                           ? "Applied to the file that holds the stream"
                                           : "Who can read the file; SYSTEM and Administrators always can"}>
                                {WINDOWS_ACCESS_OPTIONS.map((option) => (
                                    <MenuItem key={option.value || 'inherit'} value={option.value}>{option.label}</MenuItem>
                                ))}
                            </TextField>
                            {flag.windows_access === 'user' ? (
                                <RequiredTextField required label="Windows user" value={flag.windows_user ?? ''} placeholder="student"
                                           onChange={(e) => set('windows_user', e.target.value)}
                                           helperText="Local account given read access; it must exist on the image" />
                            ) : <Box />}
                            <FormControlLabel
                                control={<Checkbox checked={!!flag.hidden} onChange={(e) => set('hidden', e.target.checked)} />}
                                label="Hidden file (set the Windows Hidden attribute)"
                                sx={{gridColumn: {sm: '1 / -1'}}}
                            />
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

// CtfScoringSpecModel.flag_prefix in common/models/agoge.py.
const FLAG_PREFIX_PATTERN = /^[a-z][a-z0-9]{1,15}$/;

export const blankCtfSpec = (name = ''): CtfSpec => ({
    name,
    description: null,
    rules_url: null,
    flags: [],
    scoring: {flag_prefix: 'agoge', submission_rate_limit: 10, reveal_decoy_penalty: false},
});

/** Whole-spec checks mirroring CtfSpecModel and CtfValidator; the API re-validates on save. */
export const ctfSpecProblems = (spec: CtfSpec, serverNames: string[]): string[] => {
    const problems: string[] = [];
    if (!spec.name.trim()) problems.push("Event name is required.");
    if (!FLAG_PREFIX_PATTERN.test(spec.scoring.flag_prefix)) {
        problems.push("Flag prefix: 2-16 lowercase letters or digits, starting with a letter.");
    }
    const rate = spec.scoring.submission_rate_limit;
    if (!Number.isInteger(rate) || rate < 1 || rate > 100) {
        problems.push("Submissions per flag per minute must be between 1 and 100.");
    }
    if (spec.flags.length === 0) problems.push("Add at least one flag.");
    spec.flags.forEach((flag, index) => {
        const label = flag.id || `#${index + 1}`;
        if (!serverNames.includes(flag.server)) {
            problems.push(`Flag ${label}: server "${flag.server}" is not in this lab.`);
        }
        flagProblems(flag, spec.flags.filter((_other, i) => i !== index))
            .forEach((problem) => problems.push(`Flag ${label}: ${problem}`));
    });
    return problems;
};

interface CtfSpecFieldsProps {
    value: CtfSpec;
    onChange: (spec: CtfSpec) => void;
    serverNames: string[];
    editable?: boolean;
}

/** The ctf block's settings and flag table, shared by the event Setup tab and the lab template editor. */
export const CtfSpecFields: React.FC<CtfSpecFieldsProps> = ({value, onChange, serverNames, editable = true}) => {
    const [editingIndex, setEditingIndex] = useState<number | null>(null);

    const setField = <K extends keyof CtfSpec>(key: K, fieldValue: CtfSpec[K]) =>
        onChange({...value, [key]: fieldValue});
    const setScoring = <K extends keyof CtfSpec['scoring']>(key: K, scoringValue: CtfSpec['scoring'][K]) =>
        setField('scoring', {...value.scoring, [key]: scoringValue});

    const saveFlag = (flag: CtfFlagSpec) => {
        const flags = [...value.flags];
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
        const removed = value.flags[index].id;
        setField('flags', value.flags
            .filter((_flag, i) => i !== index)
            .map((flag) => {
                if (!flag.unlocks_after?.includes(removed)) return flag;
                const remaining = flag.unlocks_after.filter((id) => id !== removed);
                return {...flag, unlocks_after: remaining.length ? remaining : null};
            }));
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
                    <Button size="small" color="error" disabled={!editable || value.flags.length <= 1}
                            onClick={() => deleteFlag(params.row.index)}
                            aria-label={`Delete flag ${params.row.id}`}>
                        Delete
                    </Button>
                </Box>
            ),
        },
    ];

    const editingFlag = editingIndex === null ? null
        : editingIndex >= value.flags.length ? blankFlag(serverNames[0] ?? '') : value.flags[editingIndex];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            <Box sx={{display: 'grid', gridTemplateColumns: {xs: '1fr', md: '1fr 1fr'}, gap: 2, mb: 2}}>
                <RequiredTextField required label="Event name" value={value.name} disabled={!editable}
                           onChange={(e) => setField('name', e.target.value)} inputProps={{maxLength: 100}} />
                <TextField label="Rules of engagement URL" value={value.rules_url ?? ''} disabled={!editable}
                           onChange={(e) => setField('rules_url', e.target.value)} />
                <TextField label="Description" value={value.description ?? ''} disabled={!editable}
                           onChange={(e) => setField('description', e.target.value)} multiline
                           inputProps={{maxLength: 2000}} sx={{gridColumn: {md: '1 / -1'}}} />
                <RequiredTextField required label="Flag prefix" value={value.scoring.flag_prefix} disabled={!editable}
                           onChange={(e) => setScoring('flag_prefix', e.target.value.toLowerCase())}
                           helperText="2-16 lowercase letters or digits, starting with a letter" />
                <RequiredTextField required label="Submissions per flag per minute" type="number" disabled={!editable}
                           value={value.scoring.submission_rate_limit} inputProps={{min: 1, max: 100}}
                           onChange={(e) => setScoring('submission_rate_limit', Number(e.target.value))} />
                <FormControlLabel
                    control={<Checkbox checked={value.scoring.reveal_decoy_penalty} disabled={!editable}
                                       onChange={(e) => setScoring('reveal_decoy_penalty', e.target.checked)} />}
                    label="Show decoy penalties to students"
                />
            </Box>
            <StyledDataGrid
                data={value.flags.map((flag, index) => ({...flag, index}))}
                columns={columns}
                getRowId={(row: CtfFlagSpec & {index: number}) => `${row.index}-${row.id}`}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: "No flags"}}
                labelProps={{text: "Flags", icon: <FlagIcon fontSize={"large"} />}}
                density={"comfortable"}
            />
            <Button variant="outlined" sx={{mt: 2}} disabled={!editable || serverNames.length === 0}
                    onClick={() => setEditingIndex(value.flags.length)}>
                Add flag
            </Button>
            {editingFlag && (
                <FlagDialog
                    initial={editingFlag}
                    others={value.flags.filter((_flag, index) => index !== editingIndex)}
                    serverNames={serverNames}
                    onSave={saveFlag}
                    onClose={() => setEditingIndex(null)}
                />
            )}
        </Box>
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
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saved, setSaved] = useState(false);

    // A fresh event read replaces an unchanged draft; local edits are kept until saved or reset.
    useEffect(() => setDraft(spec), [spec]);

    const editable = SPEC_EDIT_STATES.includes(state);
    const dirty = JSON.stringify(draft) !== JSON.stringify(spec);

    const handleChange = (next: CtfSpec) => {
        setSaved(false);
        setDraft(next);
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

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {!editable && (
                <Alert severity="info" sx={{mb: 2}}>Flags are fixed once the event has been armed.</Alert>
            )}
            <CtfSpecFields value={draft} onChange={handleChange} serverNames={serverNames} editable={editable} />
            <Stack direction="row" spacing={1} sx={{mt: 2}} flexWrap="wrap" useFlexGap>
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
        </Box>
    );
};

export default CtfSpecEditor;
