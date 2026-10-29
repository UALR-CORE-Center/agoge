import FlagIcon from "@mui/icons-material/Flag";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import {Alert, Box, Button, Chip, Tooltip, Typography} from "@mui/material";
import {GridColDef, GridRowSelectionModel} from "@mui/x-data-grid";
import React, {useCallback, useEffect, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfFlagBoardStatus, CtfFlagRow, CtfStates, PlantStatus} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import StyledDataGrid from "../../Common/DataGrid/StyledDataGrid";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import HttpError from "../../Common/Errors/HttpError";

// Plant progress moves on a minutes scale (≤ 180 s per server), and no CTF poll may be faster than 10 s.
export const FLAGS_POLL_INTERVAL_MS = 15000;

// Must match the states PUT /ctf/{id}/flags/ accepts; the API answers anything else with 409.
export const REPLANT_STATES: readonly number[] = [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN];

const PLANT_STATUS_COLOR: Record<PlantStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    pending: 'default',
    planting: 'info',
    planted: 'success',
    failed: 'error',
    stale: 'warning',
};

// A `stale` flag is absent from the host (after a rebuild) and a `failed` one never landed; both need a Replant.
export const flagProblems = (boards: CtfFlagBoardStatus[]): string | null => {
    const failed = boards.filter(board => board.plant_status === 'failed').length;
    const stale = boards.filter(board => board.plant_status === 'stale').length;
    const parts = [failed ? `${failed} failed` : null, stale ? `${stale} stale` : null].filter(Boolean);
    return parts.length ? parts.join(', ') : null;
};

// Replant works per server, so a selection of flags becomes the union of their servers, in row order.
export const selectedServers = (flags: CtfFlagRow[], selection: GridRowSelectionModel): string[] => {
    const ids = new Set(selection);
    return [...new Set(flags.filter(row => ids.has(row.flag_id)).map(row => row.server))];
};

const BoardStatuses: React.FC<{boards: CtfFlagBoardStatus[]}> = ({boards}) => (
    <Box sx={{display: 'flex', flexWrap: 'wrap', gap: 0.5, py: 1}}>
        {boards.map(board => (
            <Tooltip key={board.workout_id} title={board.plant_error ?? (board.solved ? 'Solved' : '')}>
                <Chip
                    size="small"
                    variant="outlined"
                    color={PLANT_STATUS_COLOR[board.plant_status]}
                    label={`${board.team_name}: ${board.plant_status}${board.solved ? ' ✓' : ''}`}
                />
            </Tooltip>
        ))}
    </Box>
);

interface CtfFlagsPanelProps {
    ctfId: string;
    state: number;
    // Polls only while the Flags tab is showing, so hidden panels add no load.
    active: boolean;
}

const CtfFlagsPanel: React.FC<CtfFlagsPanelProps> = ({ctfId, state, active}) => {
    const [flags, setFlags] = useState<CtfFlagRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    // Separate from the load error so the next successful poll does not wipe a replant failure.
    const [replantError, setReplantError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    // Kept apart from `open` so the dialog text does not go blank while it fades out.
    const [targets, setTargets] = useState<string[]>([]);
    const [selection, setSelection] = useState<GridRowSelectionModel>([]);
    const [open, setOpen] = useState(false);
    const [replanting, setReplanting] = useState(false);

    const fetchFlags = useCallback(async () => {
        try {
            const fetched = await ctfService.getFlags(ctfId);
            setFlags(fetched ?? []);
            setError(null);
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not load the flags."}`);
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [ctfId]);

    // An archived event's plant status cannot change any more; one read is enough.
    const archived = state === CtfStates.ARCHIVED;
    usePolling(fetchFlags, {enabled: active && !archived, interval: FLAGS_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) {
            fetchFlags();
        }
    }, [active, archived, fetchFlags]);
    const canReplant = REPLANT_STATES.includes(state);

    const bulkServers = selectedServers(flags, selection);

    const handleOpen = (servers: string[]) => {
        setTargets(servers);
        setOpen(true);
    };

    const handleClose = () => {
        if (!replanting) {
            setOpen(false);
        }
    };

    const handleConfirm = async () => {
        if (targets.length === 0) {
            return;
        }
        setReplanting(true);
        setReplantError(null);
        setNotice(null);
        try {
            // Replant is per server, not per flag: every flag on that host is planted again, on every board.
            // One scoped PUT for the whole selection, so the audit log records a single FLAG_REPLANT.
            const {messages} = await ctfService.replant(ctfId, {servers: targets});
            setNotice(`Replant of ${targets.join(', ')} started (${messages} plant ${messages === 1 ? 'request' : 'requests'}).`);
            setOpen(false);
            setSelection([]);
            await fetchFlags();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setReplantError(`${status || "Unknown Status"}: ${message || "Could not start the replant."}`);
            setOpen(false);
            console.error(err);
        } finally {
            setReplanting(false);
        }
    };

    const columns: GridColDef<CtfFlagRow>[] = [
        {field: 'flag_id', headerName: 'Flag', width: 140, minWidth: 110},
        {field: 'server', headerName: 'Server', width: 140, minWidth: 110},
        {field: 'guest', headerName: 'Guest', width: 110, minWidth: 90, valueGetter: (_value, row) => row.guest ?? ''},
        {field: 'slot', headerName: 'Slot', type: 'number', width: 70, minWidth: 60},
        {field: 'points', headerName: 'Points', type: 'number', width: 80, minWidth: 70},
        {
            field: 'decoy',
            headerName: 'Decoy',
            width: 80,
            minWidth: 70,
            valueFormatter: (value?: boolean) => (value ? 'Yes' : 'No'),
        },
        {
            field: 'problems',
            headerName: 'Status',
            width: 150,
            minWidth: 120,
            sortable: false,
            valueGetter: (_value, row) => flagProblems(row.boards),
            renderCell: (params) => params.value ? (
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, height: '100%', color: 'warning.dark'}}>
                    <WarningAmberIcon fontSize="small" aria-hidden />
                    <Typography variant="body2" component="span">{params.value}</Typography>
                </Box>
            ) : (
                <Typography variant="body2" component="span" color="text.secondary">OK</Typography>
            ),
        },
        {
            field: 'boards',
            headerName: 'Plant status by team',
            flex: 1,
            minWidth: 220,
            sortable: false,
            renderCell: (params) => <BoardStatuses boards={params.row.boards} />,
        },
        {
            field: 'actions',
            headerName: '',
            width: 110,
            minWidth: 100,
            sortable: false,
            renderCell: (params) => (
                <Box sx={{display: 'flex', alignItems: 'center', height: '100%'}}>
                    <Button
                        size="small"
                        variant="outlined"
                        disabled={!canReplant || replanting}
                        onClick={() => handleOpen([params.row.server])}
                        aria-label={`Replant ${params.row.server} for flag ${params.row.flag_id}`}
                    >
                        Replant
                    </Button>
                </Box>
            ),
        },
    ];

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            {replantError && (
                <Alert severity="error" sx={{mb: 2}} onClose={() => setReplantError(null)}>{replantError}</Alert>
            )}
            {notice && <Alert severity="success" sx={{mb: 2}} onClose={() => setNotice(null)}>{notice}</Alert>}
            <StyledDataGrid
                data={flags}
                columns={columns}
                getRowId={(row: CtfFlagRow) => row.flag_id}
                getRowHeight={() => 'auto'}
                disableRowSelectionOnClick={true}
                rowSelectionModel={selection}
                onSelection={(model: GridRowSelectionModel) => setSelection(model)}
                buttonsConfig={[{
                    label: bulkServers.length ? `Replant selected (${bulkServers.length})` : 'Replant selected',
                    variant: 'contained',
                    color: 'primary',
                    onClick: () => handleOpen(bulkServers),
                    addTooltip: true,
                    tooltip: 'Replant the servers of the selected flags, on every board',
                    isDisabled: !canReplant || replanting || bulkServers.length === 0,
                }]}
                localeText={{noRowsLabel: "No flags in this event"}}
                labelProps={{text: "Flags", icon: <FlagIcon fontSize={"large"} />}}
                density={"comfortable"}
                loading={loading}
            />
            <ActionConfirmDialog
                open={open}
                title={targets.length > 1 ? `Replant ${targets.length} servers` : `Replant ${targets[0] ?? ''}`}
                message={
                    `Plant every flag on ${targets.join(', ') || 'this server'} again, on every board. ` +
                    // A nested lab host's plant watcher plants without a restart (FlagPlanter); other servers restart.
                    `A server restarts to plant, except a nested lab host, which keeps running. The flag values stay the same.`
                }
                confirmLabel="Replant"
                onConfirm={handleConfirm}
                onClose={handleClose}
                loading={replanting}
            />
        </Box>
    );
};

export default CtfFlagsPanel;
