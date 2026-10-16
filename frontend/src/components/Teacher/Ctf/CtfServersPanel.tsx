import DnsIcon from "@mui/icons-material/Dns";
import {Alert, Box, Button, Chip, Stack, Tooltip, Typography} from "@mui/material";
import React, {useState} from "react";
import {CtfServersAction, CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import ActionConfirmDialog from "../../Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog";
import HttpError from "../../Common/Errors/HttpError";
import {WORKOUT_NOT_BUILT, workoutStateLabel} from "./CtfTeamsPanel";

// WorkoutStates.RUNNING in common/constants/states.py; arming fails a board whose workout is not running.
export const WORKOUT_RUNNING = 50;

export interface CtfServerSummary {
    name: string;
    os: string | null;
    machine_type: string | null;
    flag_count: number;
}

interface ServerActionRule {
    label: string;
    // CtfSetup.SERVER_ACTIONS in api/core/ctf/setup.py; the API answers anything else with 409.
    legalStates: readonly number[];
    message: string;
}

const S = CtfStates;
export const SERVER_ACTION_RULES: Record<CtfServersAction, ServerActionRule> = {
    build: {
        label: 'Build all',
        legalStates: [S.DRAFT, S.ARMED, S.BROKEN, S.RUNNING, S.PAUSED],
        message: "Build every team's servers that are not built yet. VMs start as they are built and cost money while they run.",
    },
    start: {
        label: 'Start all',
        legalStates: [S.DRAFT, S.ARMED, S.BROKEN, S.RUNNING, S.PAUSED],
        message: "Start every team's servers. Running VMs cost money until they are stopped.",
    },
    stop: {
        label: 'Stop all',
        legalStates: [S.DRAFT, S.ARMED, S.BROKEN, S.PAUSED, S.ENDED],
        message: "Stop every team's servers. Arming needs them running again.",
    },
};

const ACTION_ORDER: CtfServersAction[] = ['build', 'start', 'stop'];

interface CtfServersPanelProps {
    ctfId: string;
    state: number;
    servers: CtfServerSummary[];
    teams: CtfTeamRow[];
    onChanged: () => void | Promise<void>;
}

const CtfServersPanel: React.FC<CtfServersPanelProps> = ({ctfId, state, servers, teams, onChanged}) => {
    const [selected, setSelected] = useState<CtfServersAction>('build');
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const unbuilt = teams.filter((team) => team.workout_state === WORKOUT_NOT_BUILT).length;
    const running = teams.filter((team) => team.workout_state === WORKOUT_RUNNING).length;

    const handleConfirm = async () => {
        setBusy(true);
        setError(null);
        setNotice(null);
        try {
            const {messages} = await ctfService.controlServers(ctfId, selected);
            setNotice(messages === 0
                ? "Nothing to do: no team needed this."
                : `${SERVER_ACTION_RULES[selected].label} sent for ${messages} ${messages === 1 ? "team" : "teams"}.`);
            await onChanged();
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            setError(`${status || "Unknown Status"}: ${message || "Could not control the servers."}`);
            console.error(err);
        } finally {
            setBusy(false);
            setOpen(false);
        }
    };

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{mb: 1}}>
                <DnsIcon />
                <Typography variant="h6" component="h3">Servers</Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{mb: 1}}>
                Every team gets its own copy of these servers.
            </Typography>
            <Box sx={{display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2}}>
                {servers.length === 0 && <Typography variant="body2">No servers in this lab.</Typography>}
                {servers.map((server) => (
                    <Chip
                        key={server.name}
                        variant="outlined"
                        label={[
                            server.name,
                            server.os,
                            server.machine_type,
                            `${server.flag_count} ${server.flag_count === 1 ? "flag" : "flags"}`,
                        ].filter(Boolean).join(" · ")}
                    />
                ))}
            </Box>
            <Typography variant="body2" sx={{mb: 1}}>
                {teams.length === 0
                    ? "Add teams before building servers."
                    : `${running} of ${teams.length} ${teams.length === 1 ? "team" : "teams"} running, ${unbuilt} not built.`}
            </Typography>
            {teams.length > 0 && running < teams.length && (
                <Alert severity="info" sx={{mb: 2}}>
                    Arming plants flags only on running servers. Build and start every team before you arm.
                </Alert>
            )}
            <Box role="group" aria-label="Server actions" sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                {ACTION_ORDER.map((action) => {
                    const rule = SERVER_ACTION_RULES[action];
                    const illegal = !rule.legalStates.includes(state);
                    const reason = teams.length === 0 ? "Add at least one team first." : illegal ? "Not available in this state." : "";
                    return (
                        <Tooltip key={action} title={reason}>
                            <span>
                                <Button
                                    variant="outlined"
                                    color={action === 'stop' ? 'warning' : 'primary'}
                                    disabled={busy || illegal || teams.length === 0}
                                    onClick={() => {
                                        setSelected(action);
                                        setOpen(true);
                                    }}
                                >
                                    {rule.label}
                                </Button>
                            </span>
                        </Tooltip>
                    );
                })}
            </Box>
            {teams.length > 0 && (
                <Box component="ul" sx={{pl: 2, mt: 2, mb: 0}}>
                    {teams.map((team) => (
                        <Typography component="li" variant="body2" key={team.workout_id}>
                            {team.team_name}: {workoutStateLabel(team)}
                        </Typography>
                    ))}
                </Box>
            )}
            {error && <Alert severity="error" sx={{mt: 2}} onClose={() => setError(null)}>{error}</Alert>}
            {notice && <Alert severity="success" sx={{mt: 2}} onClose={() => setNotice(null)}>{notice}</Alert>}
            <ActionConfirmDialog
                open={open}
                title={SERVER_ACTION_RULES[selected].label}
                message={SERVER_ACTION_RULES[selected].message}
                confirmLabel={SERVER_ACTION_RULES[selected].label}
                onConfirm={handleConfirm}
                onClose={() => !busy && setOpen(false)}
                loading={busy}
            />
        </Box>
    );
};

export default CtfServersPanel;
