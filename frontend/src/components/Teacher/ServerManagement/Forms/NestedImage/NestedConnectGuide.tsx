import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    IconButton,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
    useMediaQuery,
} from "@mui/material";
import {blue} from "@mui/material/colors";
import {Theme, useTheme} from "@mui/material/styles";
import React, {useState} from "react";
import {useClipboard} from "../../../../../hooks/useClipboard";
import {NestedTunnel} from "./nestedImageStatus";

export type ConnectPlatform = 'unix' | 'powershell' | 'putty';

interface NestedConnectGuideProps {
    tunnels: NestedTunnel[];
    // The parent's SSH user and address, as in the tunnel commands.
    username: string;
    hostname: string;
    // guest -> admin username, for the SSH login through the tunnel.
    guestUsers: Record<string, string>;
}

const PLATFORMS: {value: ConnectPlatform; label: string}[] = [
    {value: 'unix', label: 'macOS / Linux'},
    {value: 'powershell', label: 'Windows (PowerShell)'},
    {value: 'putty', label: 'Windows (PuTTY)'},
];

// The dark theme's primary (#00518c) is about 2:1 on dark paper; blue[200] clears 4.5:1 there, as the
// primary does on light paper, so the collapsed section reads as a control in both modes.
const accent = (theme: Theme): string => theme.palette.mode === 'dark' ? blue[200] : theme.palette.primary.main;

const defaultPlatform = (): ConnectPlatform =>
    typeof navigator !== 'undefined' && /Windows/i.test(navigator.userAgent) ? 'powershell' : 'unix';

// The walkthrough uses one real tunnel: a Linux guest's SSH when there is one, since that is the case with
// two terminals, then RDP, then a console.
const exampleTunnel = (tunnels: NestedTunnel[]): NestedTunnel | undefined =>
    tunnels.find(item => item.kind === 'ssh') ?? tunnels.find(item => item.kind === 'rdp') ?? tunnels[0];

const Command: React.FC<{value: string}> = ({value}) => {
    const {copy} = useClipboard();
    return (
        <Box sx={{display: "flex", alignItems: "center", gap: 1, my: 1, p: 1, border: 1, borderColor: "divider", borderRadius: 1}}>
            <Typography component={"code"} sx={{fontFamily: "monospace", wordBreak: "break-all", minWidth: 0, flex: 1}}>
                {value}
            </Typography>
            <Tooltip title={"Copy command"}>
                <IconButton aria-label={`Copy ${value}`} size={"small"} onClick={() => copy(value)}>
                    <ContentCopyIcon fontSize={"small"} />
                </IconButton>
            </Tooltip>
        </Box>
    );
};

// overflowWrap keeps a long hostname inside an inline <code> from widening the dialog on a phone.
const Step: React.FC<{title: string; children?: React.ReactNode}> = ({title, children}) => (
    <Box component={"li"} sx={{mb: 2, overflowWrap: "anywhere"}}>
        <Typography sx={{fontWeight: 600}}>{title}</Typography>
        {children}
    </Box>
);

// How to reach the guest once the tunnel is up, per kind and platform.
const ClientStep: React.FC<{tunnel: NestedTunnel; platform: ConnectPlatform; guestUser: string}> = ({tunnel, platform, guestUser}) => {
    const port = tunnel.local_port;
    if (tunnel.kind === 'ssh') {
        if (platform === 'putty') {
            return (
                <Step title={`Log in to ${tunnel.guest} with a second PuTTY window`}>
                    <Typography>
                        Start PuTTY again. Set Host Name to <code>localhost</code> and Port to <code>{port}</code>, then
                        Open. Log in as <code>{guestUser}</code> with the {tunnel.guest} password below.
                    </Typography>
                </Step>
            );
        }
        return (
            <Step title={`Log in to ${tunnel.guest} from a second ${platform === 'unix' ? 'terminal' : 'PowerShell window'}`}>
                <Command value={`ssh -p ${port} ${guestUser}@localhost`} />
                <Typography>
                    {`Enter the ${tunnel.guest} password below. The first time, answer yes to trust ${tunnel.guest}'s host key.`}
                </Typography>
            </Step>
        );
    }
    if (tunnel.kind === 'rdp') {
        return (
            <Step title={`Open Remote Desktop to ${tunnel.guest}`}>
                {platform === 'unix' ? (
                    <Typography>
                        On a Mac, add a PC in Microsoft&apos;s Windows App at <code>localhost:{port}</code>; on Linux, use
                        Remmina or <code>xfreerdp /v:localhost:{port}</code>. Sign in with the {tunnel.guest} username and
                        password below.
                    </Typography>
                ) : (
                    <>
                        <Command value={`mstsc /v:localhost:${port}`} />
                        <Typography>Sign in with the {tunnel.guest} username and password below.</Typography>
                    </>
                )}
            </Step>
        );
    }
    return (
        <Step title={`Open ${tunnel.guest}'s console in a VNC viewer`}>
            {platform === 'unix' ? (
                <>
                    <Command value={`open vnc://localhost:${port}`} />
                    <Typography>That opens Screen Sharing on a Mac; on Linux, point any VNC viewer at localhost:{port}.</Typography>
                </>
            ) : (
                <Typography>
                    Point a VNC viewer such as TigerVNC or RealVNC Viewer at <code>localhost:{port}</code>.
                </Typography>
            )}
            <Typography>Use the {tunnel.guest} VNC password below.</Typography>
        </Step>
    );
};

const OpenSshSteps: React.FC<{tunnel: NestedTunnel; platform: 'unix' | 'powershell'; target: string; guestUser: string}> = ({tunnel, platform, target, guestUser}) => (
    <Box component={"ol"} sx={{pl: 3, m: 0}}>
        <Step title={platform === 'unix' ? "Open Terminal and start the tunnel" : "Open PowerShell and start the tunnel"}>
            <Command value={`ssh -N -L ${tunnel.local_port}:${tunnel.destination} ${target}`} />
            <Typography>
                Keep this window open: the tunnel lasts as long as it runs, and Ctrl+C closes it. -N holds the tunnel
                without a shell; the commands below work the same without it, but that window then shows a shell on the
                server. The server accepts the SSH key from the image&apos;s Host step; if it is not your default key,
                add <code>-i {platform === 'unix' ? '~/.ssh/<key>' : '$HOME\\.ssh\\<key>'}</code>.
            </Typography>
            {platform === 'powershell' && (
                <Typography sx={{mt: 1}}>
                    Windows 10 and 11 include this ssh. If PowerShell does not recognize it, add OpenSSH Client under
                    Settings, Optional features, or use PuTTY.
                </Typography>
            )}
        </Step>
        <ClientStep tunnel={tunnel} platform={platform} guestUser={guestUser} />
    </Box>
);

const PuttySteps: React.FC<{tunnel: NestedTunnel; username: string; hostname: string; guestUser: string}> = ({tunnel, username, hostname, guestUser}) => (
    <Box component={"ol"} sx={{pl: 3, m: 0}}>
        <Step title={"Convert your SSH key for PuTTY (once)"}>
            <Typography>
                Open PuTTYgen, Load the private key that matches the image&apos;s SSH key, then Save private key as a
                .ppk file.
            </Typography>
        </Step>
        <Step title={"Set up a PuTTY session to the server"}>
            <Typography>
                In Session, set Host Name to <code>{username}@{hostname}</code> and Port to <code>22</code>. In
                Connection, SSH, Auth, Credentials, browse to the .ppk file.
            </Typography>
        </Step>
        <Step title={"Add the tunnel"}>
            <Typography>
                In Connection, SSH, Tunnels, set Source port to <code>{tunnel.local_port}</code> and Destination
                to <code>{tunnel.destination}</code>, leave Local selected, and click Add. Add one forward per
                command above to open several at once.
            </Typography>
        </Step>
        <Step title={"Save and open the session"}>
            <Typography>
                Back in Session, name it and Save so you can Load it next time, then Open. Keep this window open: the
                tunnel lasts as long as the session does.
            </Typography>
        </Step>
        <ClientStep tunnel={tunnel} platform={'putty'} guestUser={guestUser} />
    </Box>
);

// A collapsed walkthrough under the tunnel commands: the same steps on macOS or Linux, Windows' own OpenSSH,
// and PuTTY, filled in with one of this host's tunnels.
const NestedConnectGuide: React.FC<NestedConnectGuideProps> = ({tunnels, username, hostname, guestUsers}) => {
    const [platform, setPlatform] = useState<ConnectPlatform>(defaultPlatform);
    const [expanded, setExpanded] = useState(false);
    // Attached toggle buttons that wrap lose their joined borders, so a phone stacks them instead.
    const narrow = useMediaQuery(useTheme().breakpoints.down('sm'));
    const tunnel = exampleTunnel(tunnels);
    if (!tunnel) {
        return null;
    }
    const target = `${username}@${hostname}`;
    const guestUser = guestUsers[tunnel.guest] || '<user>';

    return (
        <Accordion
            disableGutters
            expanded={expanded}
            onChange={(_event, value) => setExpanded(value)}
            sx={{
                mb: 2,
                border: 1,
                borderColor: accent,
                borderRadius: 1,
                // The Accordion's divider line would read as a second, fainter border.
                '&::before': {display: 'none'},
            }}
        >
            <AccordionSummary
                expandIcon={<ExpandMoreIcon sx={{color: accent}} />}
                sx={{
                    color: accent,
                    borderRadius: 1,
                    '&:hover': {bgcolor: 'action.hover'},
                    '&.Mui-focusVisible': {bgcolor: 'action.focus', outline: '2px solid', outlineColor: accent, outlineOffset: '2px'},
                    '& .MuiAccordionSummary-content': {alignItems: 'center', gap: 1, flexWrap: 'wrap'},
                }}
            >
                <HelpOutlineIcon fontSize={"small"} aria-hidden />
                <Typography sx={{fontWeight: 600}}>How to connect from Windows, macOS, or Linux</Typography>
                {/* Says what a click does, so the affordance does not rest on color and the chevron alone. Hidden from
                    screen readers, which get aria-expanded and keep a stable name. */}
                <Typography variant={"body2"} aria-hidden sx={{textDecoration: 'underline'}}>
                    {expanded ? 'Hide steps' : 'Show steps'}
                </Typography>
            </AccordionSummary>
            <AccordionDetails>
                <ToggleButtonGroup
                    exclusive
                    size={"small"}
                    orientation={narrow ? "vertical" : "horizontal"}
                    fullWidth={narrow}
                    value={platform}
                    onChange={(_event, value: ConnectPlatform | null) => value && setPlatform(value)}
                    aria-label={"Your computer"}
                    sx={{mb: 2}}
                >
                    {PLATFORMS.map(item => (
                        <ToggleButton key={item.value} value={item.value}>{item.label}</ToggleButton>
                    ))}
                </ToggleButtonGroup>
                <Typography sx={{mb: 2}}>
                    {`This example reaches ${tunnel.guest}; every connection below works the same way with its own ports and address.`}
                </Typography>
                {platform === 'putty'
                    ? <PuttySteps tunnel={tunnel} username={username} hostname={hostname} guestUser={guestUser} />
                    : <OpenSshSteps tunnel={tunnel} platform={platform} target={target} guestUser={guestUser} />}
            </AccordionDetails>
        </Accordion>
    );
};

export default NestedConnectGuide;
