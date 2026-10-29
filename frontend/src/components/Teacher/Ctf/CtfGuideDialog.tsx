import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Tooltip,
    Typography,
    useMediaQuery,
} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import React, {useState} from "react";

// A term and its explanation; a list of these reads better than a table on a phone.
const Term: React.FC<{name: string; children: React.ReactNode}> = ({name, children}) => (
    <Box component="li" sx={{mb: 1}}>
        <Typography variant="body2">
            <Box component="span" sx={{fontWeight: 600}}>{name}</Box> — {children}
        </Typography>
    </Box>
);

const Terms: React.FC<{children: React.ReactNode}> = ({children}) => (
    <Box component="ul" sx={{pl: 2.5, my: 1}}>{children}</Box>
);

const Steps: React.FC<{children: React.ReactNode}> = ({children}) => (
    <Box component="ol" sx={{pl: 2.5, my: 1, '& li': {mb: 1}}}>{children}</Box>
);

const Para: React.FC<{children: React.ReactNode}> = ({children}) => (
    <Typography variant="body2" sx={{mb: 1}}>{children}</Typography>
);

interface GuideSection {
    title: string;
    body: React.ReactNode;
}

// Condensed from docs/guides/game-master-guide.md; keep the two in step when CTF behavior changes.
export const GUIDE_SECTIONS: GuideSection[] = [
    {
        title: "Quick start: running a CTF",
        body: (
            <Steps>
                <li><Typography variant="body2"><b>Setup → Teams:</b> add every team and its members&apos; emails, or import a CSV of <code>team,email</code> lines. Share the <b>join code</b> with students; they join at <code>/join</code> with it and their roster email.</Typography></li>
                <li><Typography variant="body2"><b>Setup → Flags:</b> review the event name, rules link, scoring and flags. Flags can only be edited while the event is a DRAFT.</Typography></li>
                <li><Typography variant="body2"><b>Setup → Servers:</b> click <b>Build all</b>, then <b>Start all</b>. Wait until every team&apos;s servers are running.</Typography></li>
                <li><Typography variant="body2">Click <b>Arm</b>. Agoge plants each team&apos;s unique flags (flag-bearing VMs restart). Check the <b>Flags</b> tab and replant anything <code>failed</code>.</Typography></li>
                <li><Typography variant="body2">Under Event Control, set <b>Ends at</b> and the scoreboard switches, then click <b>Start</b> when the exercise begins.</Typography></li>
                <li><Typography variant="body2">During play, watch <b>Submissions</b>, <b>Scoreboard</b> and <b>Flags</b>; use <b>Pause</b> for breaks and <b>Hosts</b> to fix broken servers.</Typography></li>
                <li><Typography variant="body2">Click <b>End</b> when time is up, then <b>Archive</b> and <b>Stop all</b> so the VMs stop costing money.</Typography></li>
            </Steps>
        ),
    },
    {
        title: "Event states",
        body: (
            <Terms>
                <Term name="DRAFT">Created; nothing planted yet. Teams and flags can be changed.</Term>
                <Term name="ARMING">Flags are being planted on every board.</Term>
                <Term name="ARMED">At least one board planted; ready to start.</Term>
                <Term name="RUNNING">The clock is running; submissions and hints are open.</Term>
                <Term name="PAUSED">The clock is stopped and submissions are closed.</Term>
                <Term name="ENDED">The exercise is over; submissions are closed for good.</Term>
                <Term name="ARCHIVED">Retired and read-only. Boards are released so the workouts can join a new event.</Term>
                <Term name="BROKEN">Arming finished, but no board planted successfully. Fix the servers and click Arm again.</Term>
            </Terms>
        ),
    },
    {
        title: "Event Control buttons",
        body: (
            <>
                <Para>Only the buttons valid for the current state are enabled.</Para>
                <Terms>
                    <Term name="Arm">Plants flags on every board (DRAFT, ARMED or BROKEN). Needs at least one team. Re-arming replants every board with the same values.</Term>
                    <Term name="Start">ARMED → RUNNING. Opens submissions and starts the clock.</Term>
                    <Term name="Pause">RUNNING → PAUSED. Closes submissions and hints; students see &quot;(paused)&quot;.</Term>
                    <Term name="Resume">PAUSED → RUNNING. The paused time is added to the end time, so pausing never shortens the exercise.</Term>
                    <Term name="End">Closes submissions permanently. Cannot be undone; you must type the event id to confirm.</Term>
                    <Term name="Archive">Allowed from DRAFT, ARMED, ENDED or BROKEN. Releases the boards and hides the CTF banner from students. Cannot be undone.</Term>
                </Terms>
            </>
        ),
    },
    {
        title: "Scoreboard settings",
        body: (
            <>
            <Para>These controls sit under Event Control on the left of this page, not on the Scoreboard tab.</Para>
            <Terms>
                <Term name="Public scoreboard">Lets students see standings on their workout page. Teams appear as anonymous &quot;Team n&quot; and the student&apos;s own team is highlighted.</Term>
                <Term name="Freeze scoreboard">Hides solves made after the freeze from the public standings only, keeping the final minutes suspenseful. Hint costs and manual adjustments still show. Your own Scoreboard tab is never frozen.</Term>
                <Term name="Ends at">Pick a time and click <b>Save end time</b> to set or change the countdown. <b>Clear end time</b> makes the event open-ended.</Term>
            </Terms>
            </>
        ),
    },
    {
        title: "Setup tab",
        body: (
            <Terms>
                <Term name="Teams">Team names must be unique, and an email can be on only one team in any active event. Teams can be added or removed only in DRAFT (and removed only before their servers are built), but members can be changed until the event ends, so a late student can still be added. Teammates share one set of servers and one score.</Term>
                <Term name="Join code">Students enter it at /join with the email on their team. An email not on the roster is refused. The first member to join builds the team&apos;s servers if you have not.</Term>
                <Term name="Flags">Edit the event&apos;s name, description, rules link, scoring and flags (DRAFT only). Saving regenerates every team&apos;s flag values. Avoid Linux file flags under /tmp, /run or /dev/shm: a reboot erases them.</Term>
                <Term name="Servers">Build all, Start all and Stop all act on every team and need at least one team. Running VMs cost money until stopped. Stop all is disabled while the event is running (pause it first), and Build all and Start all are disabled once the event has ended.</Term>
            </Terms>
        ),
    },
    {
        title: "Flags tab",
        body: (
            <>
                <Para>Shows each flag&apos;s plant status on every board. Click <b>Replant</b> on a row, or select rows and replant them together. Replant works per server: every flag on that server is planted again on every team&apos;s board. Replanting writes the same value again, so it is always safe to repeat.</Para>
                <Terms>
                    <Term name="pending">Not planted yet; the event has not been armed.</Term>
                    <Term name="planting">A plant is in progress.</Term>
                    <Term name="planted">The server confirmed the write.</Term>
                    <Term name="failed">The plant did not confirm. Hover the row for the reason, fix it, then replant.</Term>
                    <Term name="stale">The server was rebuilt after planting, so the flag is no longer on disk. Replant it.</Term>
                </Terms>
                <Para>Common failures: <b>&quot;Server is not running&quot;</b> — start the workout, then replant. <b>&quot;Server instance not found&quot;</b> — rebuild on the Hosts tab, then replant. <b>&quot;No plant confirmation&quot;</b> — the VM did not finish booting or was built before CTF was deployed; replant, and rebuild first if it fails again.</Para>
            </>
        ),
    },
    {
        title: "Hosts tab (resetting a team's server)",
        body: (
            <>
                <Para>Click <b>Reset</b> on a team&apos;s server row and pick a mode from the menu. Resets work while the event is ARMED, RUNNING, PAUSED or BROKEN, and only affect that one team. Flag values never change, so earlier solves still count.</Para>
                <Terms>
                    <Term name="Replant">Plants this server&apos;s flags again (the VM restarts). Use when a team deleted or damaged a flag, or a flag is failed/stale.</Term>
                    <Term name="Restart">Stops and starts the VM. Flags are unchanged. Use when the server is hung but its disk is fine.</Term>
                    <Term name="Rebuild">Recreates the VM from its image and can take up to 15 minutes; you must type to confirm. Flags become stale, so follow up with a Replant. Use when the server is broken beyond repair.</Term>
                </Terms>
                <Para>A disabled mode explains why in its tooltip: nothing is offered for a server that has not been built, Replant is unavailable on a server with no flags, and Rebuild is unavailable on a server with a WireGuard endpoint.</Para>
                <Para>Nested guests (VMs inside a hypervisor server) have their own indented rows. A guest reset acts on that guest only and never restarts the parent; a guest Rebuild reverts to its <code>agoge-pristine</code> snapshot and replants.</Para>
            </>
        ),
    },
    {
        title: "Scoreboard tab and scoring",
        body: (
            <>
                <Para>A team&apos;s score is solved points, plus decoy penalties, minus hint costs, plus manual adjustments. Ties go to the team that reached the score first.</Para>
                <Para>Your Scoreboard tab always shows full, unfrozen standings including decoy penalties. Use <b>Adjust</b> to add or remove −10,000 to 10,000 points with a reason (for example, a rules violation or a bonus); every adjustment is recorded in the Event Log.</Para>
            </>
        ),
    },
    {
        title: "Event Log and Submissions",
        body: (
            <>
                <Para><b>Event Log</b> lists every game master action and its result (OK, DENIED or ERROR). <b>Submissions</b> lists every flag submission, newest first, filterable by verdict:</Para>
                <Terms>
                    <Term name="correct">First solve of a flag on the team&apos;s own board.</Term>
                    <Term name="duplicate">The team already solved this flag.</Term>
                    <Term name="decoy">An out-of-scope decoy flag; recorded as a scope violation.</Term>
                    <Term name="incorrect">Not a flag in this event.</Term>
                    <Term name="cross_submission">Another team&apos;s flag. Students just see &quot;Incorrect flag&quot;; watch for this as a sign of flag sharing.</Term>
                    <Term name="rate_limited">The team exceeded the per-minute submission limit.</Term>
                    <Term name="closed">Submitted while the event was not running.</Term>
                </Terms>
            </>
        ),
    },
    {
        title: "Cost, overnight stops and wrapping up",
        body: (
            <>
                <Para>Workouts on an ARMING, ARMED, RUNNING or PAUSED event are exempt from the overnight stop and run-timer stop, so multi-day exercises keep their flags and progress. That also means they keep costing money.</Para>
                <Para>When the exercise is over: <b>End</b>, then <b>Archive</b>, then <b>Setup → Servers → Stop all</b>. Stop all stays available after the event is archived.</Para>
                <Para>If nothing builds, arms or resets and no error appears, check for the budget warning at the top of the page; an administrator must clear it.</Para>
            </>
        ),
    },
];

const CtfGuideDialog: React.FC = () => {
    const [open, setOpen] = useState(false);
    const theme = useTheme();
    const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

    return (
        <>
            <Tooltip title="How to run a CTF">
                <IconButton aria-label="Open the game master guide" size="small" onClick={() => setOpen(true)}>
                    <HelpOutlineIcon fontSize="small" />
                </IconButton>
            </Tooltip>
            <Dialog
                open={open}
                onClose={() => setOpen(false)}
                fullScreen={fullScreen}
                maxWidth="md"
                fullWidth
                scroll="paper"
                aria-labelledby="ctf-guide-title"
            >
                <DialogTitle id="ctf-guide-title">Game Master Guide</DialogTitle>
                <DialogContent dividers>
                    <Para>
                        Each team gets its own board: a workout with a unique set of flags. Use this dashboard to set
                        up teams, plant flags, run the clock and keep the game fair.
                    </Para>
                    {GUIDE_SECTIONS.map((section, index) => (
                        <Accordion key={section.title} defaultExpanded={index === 0} disableGutters>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography sx={{fontWeight: 600}}>{section.title}</Typography>
                            </AccordionSummary>
                            <AccordionDetails sx={{overflowWrap: 'anywhere'}}>{section.body}</AccordionDetails>
                        </Accordion>
                    ))}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default CtfGuideDialog;
