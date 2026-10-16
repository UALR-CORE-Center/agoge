import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import GroupsIcon from "@mui/icons-material/Groups";
import {LoadingButton} from "@mui/lab";
import {
    Alert,
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useId, useState} from "react";
import {URL_STUDENT_JOIN} from "../../../router/urls";
import {CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import HttpError from "../../Common/Errors/HttpError";
import {MAX_TEAM_MEMBERS, parseEmails, parseRosterCsv} from "./ctfRoster";

// CtfSetup.SETUP_STATES / MEMBER_STATES in api/core/ctf/setup.py; the API answers anything else with 409.
export const TEAM_EDIT_STATES: readonly number[] = [CtfStates.DRAFT];
export const MEMBER_EDIT_STATES: readonly number[] = [
    CtfStates.DRAFT, CtfStates.ARMING, CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN,
];
// WorkoutStates.NOT_BUILT: only a team whose servers were never built can be removed.
export const WORKOUT_NOT_BUILT = -1;

export const workoutStateLabel = (row: CtfTeamRow): string => {
    if (row.workout_state === null) return 'Missing';
    if (row.workout_state === WORKOUT_NOT_BUILT) return 'Not built';
    return row.workout_state_name ?? String(row.workout_state);
};

const errorText = (err: unknown, fallback: string) => {
    const {status, message} = (err ?? {}) as Partial<HttpError>;
    return `${status || "Unknown Status"}: ${message || fallback}`;
};

interface MembersDialogProps {
    open: boolean;
    title: string;
    // Shown only when adding a team; editing keeps the team's name.
    withName: boolean;
    initialName?: string;
    initialMembers?: string[];
    onSubmit: (teamName: string, members: string[]) => Promise<void>;
    onClose: () => void;
}

const MembersDialog: React.FC<MembersDialogProps> = ({open, title, withName, initialName = "", initialMembers = [], onSubmit, onClose}) => {
    const titleId = useId();
    const [name, setName] = useState(initialName);
    const [text, setText] = useState(initialMembers.join("\n"));
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const {emails, invalid} = parseEmails(text);
    const tooMany = emails.length > MAX_TEAM_MEMBERS;
    const canSave = !saving && emails.length > 0 && invalid.length === 0 && !tooMany && (!withName || name.trim() !== "");

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            await onSubmit(name.trim(), emails);
        } catch (err) {
            setError(errorText(err, "Could not save the team."));
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    const helper = invalid.length > 0
        ? `Not email addresses: ${invalid.join(", ")}`
        : tooMany ? `A team can have at most ${MAX_TEAM_MEMBERS} members.`
            : `${emails.length} ${emails.length === 1 ? "member" : "members"}. Separate emails with commas or new lines.`;

    return (
        <Dialog open={open} onClose={() => !saving && onClose()} aria-labelledby={titleId} fullWidth maxWidth="sm">
            <DialogTitle id={titleId}>{title}</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{mt: 1}}>
                    {withName && (
                        <TextField
                            label="Team name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            inputProps={{maxLength: 64}}
                            disabled={saving}
                            fullWidth
                            autoFocus
                        />
                    )}
                    <TextField
                        label="Member emails"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        multiline
                        minRows={4}
                        disabled={saving}
                        error={invalid.length > 0 || tooMany}
                        helperText={helper}
                        fullWidth
                    />
                    {error && <Alert severity="error">{error}</Alert>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <LoadingButton variant="contained" onClick={handleSave} disabled={!canSave} loading={saving}>
                    Save
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};

interface ImportDialogProps {
    open: boolean;
    ctfId: string;
    onDone: () => void;
    onClose: () => void;
}

const ImportDialog: React.FC<ImportDialogProps> = ({open, ctfId, onDone, onClose}) => {
    const titleId = useId();
    const [text, setText] = useState("");
    const [importing, setImporting] = useState(false);
    const [results, setResults] = useState<string[]>([]);
    const parsed = parseRosterCsv(text);
    const canImport = !importing && parsed.teams.length > 0 && parsed.errors.length === 0;

    const handleFile = async (file: File | undefined) => {
        if (file) setText(await file.text());
    };

    // One request per team, in order, so a failure names its team and the rest still go through.
    const handleImport = async () => {
        setImporting(true);
        const failures: string[] = [];
        for (const team of parsed.teams) {
            try {
                await ctfService.addTeam(ctfId, team);
            } catch (err) {
                failures.push(`${team.team_name}: ${errorText(err, "Could not add the team.")}`);
                console.error(err);
            }
        }
        setImporting(false);
        setResults(failures);
        onDone();
        if (failures.length === 0) {
            setText("");
            onClose();
        }
    };

    return (
        <Dialog open={open} onClose={() => !importing && onClose()} aria-labelledby={titleId} fullWidth maxWidth="sm">
            <DialogTitle id={titleId}>Import teams</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{mt: 1}}>
                    <Typography variant="body2" color="text.secondary">
                        One <code>team,email</code> line per member. Lines with the same team name make one team.
                    </Typography>
                    <Button variant="outlined" component="label" disabled={importing} sx={{alignSelf: 'flex-start'}}>
                        Choose CSV file
                        <input hidden type="file" accept=".csv,text/csv,text/plain" onChange={(e) => handleFile(e.target.files?.[0])} />
                    </Button>
                    <TextField
                        label="Roster"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder={"team,email\nRed Team,ana@example.edu\nRed Team,ben@example.edu"}
                        multiline
                        minRows={6}
                        disabled={importing}
                        fullWidth
                    />
                    {parsed.errors.length > 0 && (
                        <Alert severity="error">{parsed.errors.map((e) => <div key={e}>{e}</div>)}</Alert>
                    )}
                    {parsed.errors.length === 0 && parsed.teams.length > 0 && (
                        <Alert severity="info">
                            {parsed.teams.length} {parsed.teams.length === 1 ? "team" : "teams"},{" "}
                            {parsed.teams.reduce((sum, t) => sum + t.members.length, 0)} members
                        </Alert>
                    )}
                    {results.length > 0 && (
                        <Alert severity="warning">{results.map((r) => <div key={r}>{r}</div>)}</Alert>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={importing}>Close</Button>
                <LoadingButton variant="contained" onClick={handleImport} disabled={!canImport} loading={importing}>
                    Import
                </LoadingButton>
            </DialogActions>
        </Dialog>
    );
};

interface CtfTeamsPanelProps {
    ctfId: string;
    state: number;
    joinCode: string | null;
    teams: CtfTeamRow[];
    loading: boolean;
    // Re-reads the team list after any change.
    onChanged: () => void | Promise<void>;
}

const CtfTeamsPanel: React.FC<CtfTeamsPanelProps> = ({ctfId, state, joinCode, teams, loading, onChanged}) => {
    const [adding, setAdding] = useState(false);
    const [importing, setImporting] = useState(false);
    // Kept apart from the dialog's open flag so its text does not go blank while it fades out.
    const [editing, setEditing] = useState<CtfTeamRow | null>(null);
    const [removing, setRemoving] = useState<CtfTeamRow | null>(null);
    const [removeOpen, setRemoveOpen] = useState(false);
    const [removeBusy, setRemoveBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    const canEditTeams = TEAM_EDIT_STATES.includes(state);
    const canEditMembers = MEMBER_EDIT_STATES.includes(state);

    const handleAdd = async (teamName: string, members: string[]) => {
        await ctfService.addTeam(ctfId, {team_name: teamName, members});
        setAdding(false);
        await onChanged();
    };

    const handleEdit = async (_teamName: string, members: string[]) => {
        if (!editing) return;
        await ctfService.setTeamMembers(ctfId, editing.workout_id, members);
        setEditing(null);
        await onChanged();
    };

    const handleRemove = async () => {
        if (!removing) return;
        setRemoveBusy(true);
        setError(null);
        try {
            await ctfService.removeTeam(ctfId, removing.workout_id);
            await onChanged();
        } catch (err) {
            setError(errorText(err, "Could not remove the team."));
            console.error(err);
        } finally {
            setRemoveBusy(false);
            setRemoveOpen(false);
        }
    };

    const handleCopy = async () => {
        if (!joinCode) return;
        try {
            await navigator.clipboard.writeText(joinCode);
            setCopied(true);
        } catch (err) {
            console.error(err);
        }
    };

    const columns: GridColDef<CtfTeamRow>[] = [
        {field: 'team_name', headerName: 'Team', flex: 1, minWidth: 140},
        {
            field: 'members',
            headerName: 'Members',
            flex: 2,
            minWidth: 220,
            sortable: false,
            renderCell: (params) => (
                <Box sx={{display: 'flex', flexWrap: 'wrap', gap: 0.5, py: 1}}>
                    {params.row.members.map((member) => <Chip key={member} label={member} size="small" />)}
                </Box>
            ),
        },
        {
            field: 'workout_state',
            headerName: 'Servers',
            width: 150,
            minWidth: 120,
            valueGetter: (_value, row) => workoutStateLabel(row),
        },
        {
            field: 'actions',
            headerName: '',
            width: 200,
            minWidth: 180,
            sortable: false,
            renderCell: (params) => {
                const built = params.row.workout_state !== WORKOUT_NOT_BUILT && params.row.workout_state !== null;
                const removeBlocked = !canEditTeams ? "Teams can only be removed before arming."
                    : built ? "This team's servers are built; only an unbuilt team can be removed." : null;
                return (
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1, height: '100%'}}>
                        <Button
                            size="small"
                            variant="outlined"
                            disabled={!canEditMembers}
                            onClick={() => setEditing(params.row)}
                            aria-label={`Edit members of ${params.row.team_name}`}
                        >
                            Members
                        </Button>
                        <Tooltip title={removeBlocked ?? ""}>
                            <span>
                                <Button
                                    size="small"
                                    color="error"
                                    disabled={removeBlocked !== null || removeBusy}
                                    onClick={() => {
                                        setRemoving(params.row);
                                        setRemoveOpen(true);
                                    }}
                                    aria-label={`Remove ${params.row.team_name}`}
                                >
                                    Remove
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>
                );
            },
        },
    ];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {joinCode && (
                <Alert severity="info" sx={{mb: 2}}>
                    Participants go to <strong>{URL_STUDENT_JOIN}</strong> and enter join code{" "}
                    <strong>{joinCode}</strong>
                    <Tooltip title={copied ? "Copied" : "Copy join code"}>
                        <IconButton size="small" onClick={handleCopy} aria-label="Copy join code" sx={{ml: 0.5}}>
                            <ContentCopyIcon fontSize="inherit" />
                        </IconButton>
                    </Tooltip>
                    {" "}with the email on their team. Teammates share one set of servers and one score; anyone
                    not on a team is turned away.
                </Alert>
            )}
            {error && <Alert severity="error" sx={{mb: 2}} onClose={() => setError(null)}>{error}</Alert>}
            <Box sx={{display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap'}}>
                <Button variant="contained" onClick={() => setAdding(true)} disabled={!canEditTeams}>Add team</Button>
                <Button variant="outlined" onClick={() => setImporting(true)} disabled={!canEditTeams}>Import CSV</Button>
            </Box>
            <StyledDataGrid
                data={teams}
                columns={columns}
                getRowId={(row: CtfTeamRow) => row.workout_id}
                getRowHeight={() => 'auto'}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: "No teams yet. Add a team or import a roster."}}
                labelProps={{text: "Teams", icon: <GroupsIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
            {adding && (
                <MembersDialog open title="Add team" withName onSubmit={handleAdd} onClose={() => setAdding(false)} />
            )}
            {editing && (
                <MembersDialog
                    open
                    title={`Members of ${editing.team_name}`}
                    withName={false}
                    initialMembers={editing.members}
                    onSubmit={handleEdit}
                    onClose={() => setEditing(null)}
                />
            )}
            <ImportDialog open={importing} ctfId={ctfId} onDone={onChanged} onClose={() => setImporting(false)} />
            <ActionConfirmDialog
                open={removeOpen}
                title="Remove team"
                message={removing ? `Remove ${removing.team_name}? Its members will no longer be able to join.` : ""}
                confirmLabel="Remove"
                onConfirm={handleRemove}
                onClose={() => !removeBusy && setRemoveOpen(false)}
                loading={removeBusy}
            />
        </Box>
    );
};

export default CtfTeamsPanel;
