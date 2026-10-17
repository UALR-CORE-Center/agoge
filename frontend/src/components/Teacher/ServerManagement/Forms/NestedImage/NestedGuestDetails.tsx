import {
    Alert,
    Box,
    Chip,
    FormControlLabel,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from "@mui/material";
import React, {useState} from "react";
import {NestedBuildStatus, NestedHostSpec} from "../../../../../services/Server/nested.model";
import {nestedGuestDetails, nestedGuestStatusLabel, nestedPhaseLabel} from "./nestedImageStatus";

interface NestedGuestDetailsProps {
    spec: NestedHostSpec;
    build: NestedBuildStatus | null | undefined;
}

const MASK = "••••••••";

// The guest section of ImageDetailsDialog for a nested lab host image.
const NestedGuestDetails: React.FC<NestedGuestDetailsProps> = ({spec, build}) => {
    const [showPasswords, setShowPasswords] = useState(false);
    const guests = nestedGuestDetails(spec, build);
    const phase = build ? nestedPhaseLabel(build.phase) : null;

    return (
        <Stack gap={1} sx={{mt: 2}}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} flexWrap={"wrap"} gap={1}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography variant={"h6"}>Nested guests</Typography>
                    {phase && <Chip size={"small"} label={phase.label} color={phase.color} />}
                </Stack>
                <FormControlLabel
                    control={<Switch checked={showPasswords} onChange={(_, checked) => setShowPasswords(checked)} />}
                    label={"Show passwords"}
                />
            </Stack>
            {build?.message && <Alert severity={build.phase === 'failed' ? 'error' : 'info'}>{build.message}</Alert>}
            <TableContainer sx={{overflowX: 'auto'}}>
                <Table size={"small"} aria-label={"nested guests"}>
                    <TableHead>
                        <TableRow>
                            <TableCell>Guest</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>IP addresses</TableCell>
                            <TableCell>Credentials</TableCell>
                            <TableCell>Console</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {guests.map(guest => {
                            const status = nestedGuestStatusLabel(guest.status);
                            return (
                                <TableRow key={guest.name}>
                                    <TableCell>
                                        <Typography variant={"body2"} fontWeight={600}>{guest.name}</Typography>
                                        <Typography variant={"caption"} color={"text.secondary"}>{guest.os_id}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Chip size={"small"} label={status.label} color={status.color} />
                                    </TableCell>
                                    <TableCell>
                                        {guest.ips.map((nic, index) => (
                                            <Box key={`${nic.network}-${index}`}>
                                                <Typography variant={"body2"}>
                                                    {`${nic.network}: ${nic.ip ?? 'DHCP'}`}
                                                </Typography>
                                            </Box>
                                        ))}
                                        {guest.alias_slots.length > 0 && (
                                            <Typography variant={"caption"} color={"text.secondary"}>
                                                {`Exposed on alias slot ${guest.alias_slots.join(', ')}`}
                                            </Typography>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant={"body2"}>{guest.admin_username}</Typography>
                                        <Typography variant={"body2"} sx={{fontFamily: 'monospace'}}>
                                            {showPasswords ? guest.admin_password : MASK}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        {guest.console_port === null ? (
                                            <Typography variant={"body2"} color={"text.secondary"}>None</Typography>
                                        ) : (
                                            <>
                                                <Typography variant={"body2"}>{`Port ${guest.console_port}`}</Typography>
                                                <Typography variant={"body2"} sx={{fontFamily: 'monospace'}}>
                                                    {`VNC ${showPasswords ? guest.vnc_password ?? '' : MASK}`}
                                                </Typography>
                                            </>
                                        )}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        </Stack>
    );
};

export default NestedGuestDetails;
