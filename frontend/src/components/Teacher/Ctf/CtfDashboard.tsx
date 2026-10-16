import {Alert, Box, Paper, Skeleton, Tab, Tabs, Typography} from '@mui/material';
import React, {useCallback, useEffect, useState} from 'react';
import {useNavigate, useParams} from "react-router-dom";
import {usePolling} from "../../../hooks/usePolling";
import {URL_ERROR} from "../../../router/urls";
import {CtfStateResponse, CtfStates} from "../../../services/Ctf/ctf.model";
import {ctfService} from "../../../services/Ctf/ctf.service";
import HttpError from "../../Common/Errors/HttpError";
import CtfEventControl from "./CtfEventControl";
import CtfStateChip from "./CtfStateChip";
import {formatDuration, remainingSeconds} from "./ctfTime";

// PRD performance budget: the dashboard polls `state` every 10 s, and no CTF poll is faster.
export const STATE_POLL_INTERVAL_MS = 10000;

export const DASHBOARD_TABS = ['Flags', 'Hosts', 'Scoreboard', 'Event Log', 'Submissions'] as const;
export type DashboardTab = typeof DASHBOARD_TABS[number];

const tabId = (index: number) => `ctf-dashboard-tab-${index}`;
const panelId = (index: number) => `ctf-dashboard-tabpanel-${index}`;

const RemainingTime: React.FC<{event: CtfStateResponse}> = ({event}) => {
    const [now, setNow] = useState(() => Date.now() / 1000);

    // Ticks locally between 10 s polls; the countdown is derived, never fetched per second.
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
        return () => clearInterval(timer);
    }, []);

    const remaining = remainingSeconds(event, now);
    const paused = event.state === CtfStates.PAUSED;

    return (
        <Box sx={{mt: 2}}>
            <Typography variant="overline" component="h2" color="text.secondary">Time remaining</Typography>
            <Typography variant="h5" component="p" sx={{fontVariantNumeric: 'tabular-nums'}}>
                {remaining === null ? 'No end time' : formatDuration(remaining)}
                {paused && remaining !== null ? ' (paused)' : ''}
            </Typography>
        </Box>
    );
};

const CtfDashboard: React.FC = () => {
    const {ctf_id} = useParams<{ctf_id: string}>();
    const navigate = useNavigate();
    const [event, setEvent] = useState<CtfStateResponse | null>(null);
    const [pollError, setPollError] = useState<string | null>(null);
    const [selectedTab, setSelectedTab] = useState<number>(0);

    const fetchState = useCallback(async () => {
        try {
            const fetched = await ctfService.getState(String(ctf_id));
            setEvent(fetched);
            setPollError(null);
        } catch (err) {
            const {status, message} = (err ?? {}) as Partial<HttpError>;
            // A missing event (or CTF disabled, SC-19) will not recover by polling; anything else might.
            if (status === 404) {
                navigate(URL_ERROR, {state: {status, message: message || "CTF event not found"}});
                return;
            }
            setPollError(`${status || "Unknown Status"}: ${message || "Could not load the CTF event state."}`);
            console.error(err);
        }
    }, [ctf_id, navigate]);

    // An archived event is read-only, so its state cannot change any more.
    const archived = event?.state === CtfStates.ARCHIVED;
    usePolling(fetchState, {enabled: !!ctf_id && !archived, interval: STATE_POLL_INTERVAL_MS});

    return (
        <Box
            id="ctfDashboard"
            sx={{
                height: '100%', width: '100%',
                display: 'flex', flexDirection: {xs: 'column', md: 'row'},
                justifyContent: 'center', alignItems: {xs: 'stretch', md: 'flex-start'},
                minWidth: 0
            }}
        >
            <Box
                sx={{
                    width: {xs: '100%', md: '25%'},
                    minWidth: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    mr: {xs: 0, md: 4},
                    mb: {xs: 2, md: 0}
                }}
            >
                {event === null ? (
                    <Skeleton variant="rectangular" width="100%" height={150} animation="wave" />
                ) : (
                    <Paper elevation={2} component="section" aria-labelledby="ctf-event-control-heading" sx={{width: '100%', p: 2}}>
                        <Typography id="ctf-event-control-heading" variant="h6" component="h1" sx={{mb: 1}}>
                            Event Control
                        </Typography>
                        <CtfStateChip state={event.state} />
                        <RemainingTime event={event} />
                        <CtfEventControl ctfId={event.id} state={event.state} onActionComplete={fetchState} />
                    </Paper>
                )}
            </Box>
            <Box sx={{width: {xs: '100%', md: '75%'}, minWidth: 0, display: 'flex', flexDirection: 'column'}}>
                {event?.budget_exceeded && (
                    // BudgetManager halts every Cloud Function invocation silently; this is the only place it shows.
                    <Alert severity="warning" sx={{mb: 2}}>
                        The project budget has been exceeded. Arming, planting and host resets will not run until an
                        administrator clears the budget halt.
                    </Alert>
                )}
                {pollError && (
                    <Alert severity="error" sx={{mb: 2}}>{pollError}</Alert>
                )}
                <Paper elevation={1} sx={{width: '100%', minWidth: 0, p: {xs: 1, sm: 2}}}>
                    <Tabs
                        variant="scrollable"
                        allowScrollButtonsMobile
                        value={selectedTab}
                        onChange={(_e, value: number) => setSelectedTab(value)}
                        aria-label="CTF dashboard panels"
                    >
                        {DASHBOARD_TABS.map((label, index) => (
                            <Tab key={label} label={label} id={tabId(index)} aria-controls={panelId(index)} />
                        ))}
                    </Tabs>
                    {/* Each panel's content is its own PRD item (I12-I17); the shell owns only the tab wiring. */}
                    {DASHBOARD_TABS.map((label, index) => (
                        <Box
                            key={label}
                            role="tabpanel"
                            id={panelId(index)}
                            aria-labelledby={tabId(index)}
                            hidden={selectedTab !== index}
                            sx={{pt: 2}}
                        />
                    ))}
                </Paper>
            </Box>
        </Box>
    );
};

export default CtfDashboard;
