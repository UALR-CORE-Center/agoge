import {Alert, Box, Divider, Skeleton, Typography} from "@mui/material";
import React, {useCallback, useEffect, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfEvent, CtfStates, CtfTeamRow} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import {unitService} from "../../../services/Unit/unit.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfServersPanel, {CtfServerSummary} from "./CtfServersPanel";
import CtfSpecEditor from "./CtfSpecEditor";
import CtfTeamsPanel from "./CtfTeamsPanel";

// Workout state moves slowly while servers build; no CTF poll may be faster than 10 s.
export const TEAMS_POLL_INTERVAL_MS = 15000;

const errorText = (err: unknown, fallback: string) => {
    const {status, message} = (err ?? {}) as Partial<HttpError>;
    return `${status || "Unknown Status"}: ${message || fallback}`;
};

interface UnitServer {
    name?: string;
    machine_type?: string;
    details?: {os?: string} | null;
}

interface CtfSetupPanelProps {
    ctfId: string;
    state: number;
    // Polls only while the Setup tab is showing, so hidden panels add no load.
    active: boolean;
    // Lets the dashboard refresh its state (team count gates Arm) after a roster change.
    onTeamsChanged: () => void | Promise<void>;
}

const CtfSetupPanel: React.FC<CtfSetupPanelProps> = ({ctfId, state, active, onTeamsChanged}) => {
    const [event, setEvent] = useState<CtfEvent | null>(null);
    const [unitServers, setUnitServers] = useState<UnitServer[]>([]);
    const [teams, setTeams] = useState<CtfTeamRow[]>([]);
    const [teamsLoading, setTeamsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchEvent = useCallback(async () => {
        try {
            const fetched = await ctfService.get(ctfId);
            setEvent(fetched);
            return fetched;
        } catch (err) {
            setError(errorText(err, "Could not load the CTF event."));
            console.error(err);
            return null;
        }
    }, [ctfId]);

    const fetchTeams = useCallback(async () => {
        try {
            setTeams(await ctfService.getTeams(ctfId) ?? []);
        } catch (err) {
            setError(errorText(err, "Could not load the teams."));
            console.error(err);
        } finally {
            setTeamsLoading(false);
        }
    }, [ctfId]);

    // The event and its lab change only through this panel, so they are read once, not polled.
    useEffect(() => {
        let cancelled = false;
        fetchEvent().then(async (fetched) => {
            if (!fetched || cancelled) return;
            try {
                const unit = await unitService.get(fetched.unit_id);
                if (!cancelled) setUnitServers((unit?.servers ?? []) as UnitServer[]);
            } catch (err) {
                // The flag editor still works without the server list; it only loses the server choices.
                console.error(err);
            }
        });
        return () => {
            cancelled = true;
        };
    }, [fetchEvent]);

    const archived = state === CtfStates.ARCHIVED;
    usePolling(fetchTeams, {enabled: active && !archived, interval: TEAMS_POLL_INTERVAL_MS});
    useEffect(() => {
        if (active && archived) fetchTeams();
    }, [active, archived, fetchTeams]);

    const handleTeamsChanged = async () => {
        await fetchTeams();
        await onTeamsChanged();
    };

    if (event === null) {
        return error
            ? <Alert severity="error">{error}</Alert>
            : <Skeleton variant="rectangular" width="100%" height={240} animation="wave" />;
    }

    const flagCounts = new Map<string, number>();
    for (const flag of event.spec.flags) {
        flagCounts.set(flag.server, (flagCounts.get(flag.server) ?? 0) + 1);
    }
    const servers: CtfServerSummary[] = unitServers
        .filter((server): server is UnitServer & {name: string} => !!server.name)
        .map((server) => ({
            name: server.name,
            os: server.details?.os ?? null,
            machine_type: server.machine_type ?? null,
            flag_count: flagCounts.get(server.name) ?? 0,
        }));
    // Fall back to the flags' servers so the editor still offers choices if the lab read failed.
    const serverNames = servers.length > 0 ? servers.map((server) => server.name) : Array.from(flagCounts.keys());

    return (
        <Box sx={{width: '100%', minWidth: 0}}>
            {error && <Alert severity="error" sx={{mb: 2}} onClose={() => setError(null)}>{error}</Alert>}
            {state === CtfStates.DRAFT && (
                <Alert severity="info" sx={{mb: 2}}>
                    Set up the event before arming: add teams, review the flags, then build and start every
                    team&apos;s servers. Arm plants the flags on running servers.
                </Alert>
            )}
            <Typography variant="h6" component="h2" sx={{mb: 1}}>1. Teams</Typography>
            <CtfTeamsPanel
                ctfId={ctfId}
                state={state}
                joinCode={event.join_code}
                teams={teams}
                loading={teamsLoading}
                onChanged={handleTeamsChanged}
            />
            <Divider sx={{my: 3}} />
            <Typography variant="h6" component="h2" sx={{mb: 1}}>2. Flags</Typography>
            <CtfSpecEditor
                ctfId={ctfId}
                state={state}
                spec={event.spec}
                serverNames={serverNames}
                onSaved={async () => {
                    await fetchEvent();
                }}
            />
            <Divider sx={{my: 3}} />
            <Typography variant="h6" component="h2" sx={{mb: 1}}>3. Servers</Typography>
            <CtfServersPanel ctfId={ctfId} state={state} servers={servers} teams={teams} onChanged={fetchTeams} />
        </Box>
    );
};

export default CtfSetupPanel;
