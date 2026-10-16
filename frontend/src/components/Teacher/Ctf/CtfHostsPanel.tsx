import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import DnsIcon from "@mui/icons-material/Dns";
import {Alert, Box, Button, ListItemText, Menu, MenuItem, Tooltip, Typography} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfHostRow, CtfStates, ResetMode} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import ConfirmationDialog from "../../Common/Dialogs/ConfirmationDialog/Confirmation";
import HttpError from "../../Common/Errors/HttpError";
import {REPLANT_STATES} from "./CtfFlagsPanel";

// A rebuild can take up to 15 minutes, so server state moves slowly; no CTF poll may be faster than 10 s.
export const HOSTS_POLL_INTERVAL_MS = 15000;

// Resets share the replant states in CtfHosts.reset (api/core/ctf/hosts.py); the API answers anything else with 409.
export const RESET_STATES = REPLANT_STATES;

export const hostRowId = (row: CtfHostRow) => `${row.workout_id}-${row.server}`;

const RESET_MODES: {mode: ResetMode; label: string; description: string}[] = [
    {mode: 'replant', label: 'Replant', description: 'Plant this host\'s flags again; the VM restarts.'},
    {mode: 'restart', label: 'Restart', description: 'Stop and start the VM; flags stay on disk.'},
    {mode: 'rebuild', label: 'Rebuild', description: 'Delete and recreate the VM; its flags go stale until a replant.'},
];

// Why a mode cannot run on this host, or null when it can. The API refuses the same cases with 400.
export const resetBlocker = (row: CtfHostRow, mode: ResetMode): string | null => {
    // No server document: CtfHosts.reset answers every mode with 404.
    if (row.server_state === null) {
        return 'This server has not been built, so it cannot be reset.';
    }
    if (mode === 'replant' && row.flag_count === 0) {
        return 'This server carries no flags, so there is nothing to replant.';
    }
    if (mode === 'rebuild' && !row.rebuild_allowed) {
        // LabServerManager.nuke() deletes WireGuard servers without recreating them.
        return 'This server has a WireGuard endpoint and cannot be rebuilt.';
    }
    return null;
};

interface PendingReset {
    row: CtfHostRow;
    mode: ResetMode;
}

interface CtfHostsPanelProps {
    ctfId: string;
    state: number;
    // Polls only while the Hosts tab is showing, so hidden panels add no load.
    active: boolean;
}

const CtfHostsPanel: React.FC<CtfHostsPanelProps> = ({ctfId, state, active}) => {
    const [hosts, setHosts] = useState<CtfHostRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    // Separate from the load error so the next successful poll does not wipe a reset failure.
    const [resetError, setResetError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
    const [menuRow, setMenuRow] = useState<CtfHostRow | null>(null);
    // Kept apart from `open` so the dialog text does not go blank while it fades out.
    const [pending, setPending] = useState<PendingReset | null>(null);
    const [open, setOpen] = useState(false);
    const [resetting, setResetting] = useState(false);

    const fetchHosts = useCallback(async () => {
        try {
            const fetched = await ctfService.getHosts(ctfId);
            setHosts(fetched ?? []);
            setError(null);
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not load the hosts."}`);
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [ctfId]);

    // An archived event's hosts cannot be reset any more; one read is enough.
    const archived = state === CtfStates.ARCHIVED;
    usePolling(fetchHosts, {enabled: active && !archived, interval: HOSTS_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) {
            fetchHosts();
        }
    }, [active, archived, fetchHosts]);
    const canReset = RESET_STATES.includes(state);

    const closeMenu = () => setMenuAnchor(null);

    const handleChoose = (mode: ResetMode) => {
        if (menuRow) {
            setPending({row: menuRow, mode});
            setOpen(true);
        }
        closeMenu();
    };

    const handleClose = () => {
        if (!resetting) {
            setOpen(false);
        }
    };

    const handleConfirm = async () => {
        if (!pending) {
            return;
        }
        const {row, mode} = pending;
        setResetting(true);
        setResetError(null);
        setNotice(null);
        try {
            await ctfService.resetHost(ctfId, row.workout_id, row.server, {mode});
            setNotice(`${mode[0].toUpperCase()}${mode.slice(1)} of ${row.server} for ${row.team_name} started.`);
            setOpen(false);
            await fetchHosts();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setResetError(`${status || "Unknown Status"}: ${message || `Could not start the ${mode}.`}`);
            setOpen(false);
            console.error(err);
        } finally {
            setResetting(false);
        }
    };

    const columns: GridColDef<CtfHostRow>[] = [
        {field: 'team_name', headerName: 'Team', flex: 1, minWidth: 140},
        {field: 'server', headerName: 'Server', flex: 1, minWidth: 140},
        {
            field: 'server_state_name',
            headerName: 'Server state',
            width: 170,
            minWidth: 130,
            // A flag-bearing server with no document is listed so the gap shows instead of hiding the host.
            valueGetter: (value?: string | null) => value ?? 'Not built',
        },
        {field: 'flag_count', headerName: 'Flags', type: 'number', width: 80, minWidth: 70},
        {
            field: 'actions',
            headerName: '',
            width: 120,
            minWidth: 110,
            sortable: false,
            renderCell: (params) => (
                <Box sx={{display: 'flex', alignItems: 'center', height: '100%'}}>
                    <Button
                        size="small"
                        variant="outlined"
                        endIcon={<ArrowDropDownIcon />}
                        disabled={!canReset || resetting}
                        aria-haspopup="menu"
                        aria-label={`Reset ${params.row.server} for ${params.row.team_name}`}
                        onClick={(e) => {
                            setMenuRow(params.row);
                            setMenuAnchor(e.currentTarget);
                        }}
                    >
                        Reset
                    </Button>
                </Box>
            ),
        },
    ];

    const pendingLabel = pending ? RESET_MODES.find(m => m.mode === pending.mode)?.label ?? pending.mode : '';
    const pendingTarget = pending ? `${pending.row.server} for ${pending.row.team_name}` : '';

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            {resetError && (
                <Alert severity="error" sx={{mb: 2}} onClose={() => setResetError(null)}>{resetError}</Alert>
            )}
            {notice && <Alert severity="success" sx={{mb: 2}} onClose={() => setNotice(null)}>{notice}</Alert>}
            <StyledDataGrid
                data={hosts}
                columns={columns}
                getRowId={hostRowId}
                disableCheckBoxes={true}
                disableRowSelectionOnClick={true}
                localeText={{noRowsLabel: "No hosts in this event"}}
                labelProps={{text: "Hosts", icon: <DnsIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
            {/* No mode is pre-selected: every reset is an explicit choice (PRD I14). */}
            <Menu anchorEl={menuAnchor} open={menuAnchor !== null} onClose={closeMenu}>
                {RESET_MODES.map(({mode, label, description}) => {
                    const blocker = menuRow ? resetBlocker(menuRow, mode) : null;
                    const item = (
                        <MenuItem key={mode} disabled={blocker !== null} onClick={() => handleChoose(mode)}>
                            <ListItemText primary={label} secondary={description} />
                        </MenuItem>
                    );
                    // A disabled item has no pointer events, so the tooltip hangs off a wrapper that does.
                    return blocker ? (
                        <Tooltip key={mode} title={blocker} placement="left">
                            <span>{item}</span>
                        </Tooltip>
                    ) : item;
                })}
            </Menu>
            <ActionConfirmDialog
                open={open && pending?.mode !== 'rebuild'}
                title={`${pendingLabel} ${pendingTarget}`}
                message={pending?.mode === 'restart'
                    ? `Stop and start ${pendingTarget}. The flags stay on disk, and the team loses access until it is back.`
                    : `Plant every flag on ${pendingTarget} again. The VM restarts; the flag values stay the same.`}
                confirmLabel={pendingLabel}
                onConfirm={handleConfirm}
                onClose={handleClose}
                loading={resetting}
            />
            {/* Rebuild deletes the instance, so it takes the type-to-confirm dialog. */}
            <ConfirmationDialog
                open={open && pending?.mode === 'rebuild'}
                onClose={handleClose}
                handleConfirm={handleConfirm}
                expectedText={pending?.row.server ?? ''}
                action="rebuild"
                confirmLabel="Rebuild"
                message={
                    <>
                        Delete and recreate {pendingTarget}. Its flags are gone until you replant them from the
                        Flags panel. This can take up to 15 minutes.
                    </>
                }
                loading={resetting}
            />
            {!canReset && !loading && hosts.length > 0 && (
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>
                    Hosts can be reset only while the event is armed, running, paused or broken.
                </Typography>
            )}
        </Box>
    );
};

export default CtfHostsPanel;
