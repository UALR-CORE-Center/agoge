import {ArrowDownward, ArrowUpward} from "@mui/icons-material";
import {
    Alert,
    IconButton,
    Paper,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import React from "react";
import {canMoveExposure, deriveConsoles, deriveExposures, moveExposure} from "./accessReview";
import {NestedWizardState} from "./nestedWizardState";

interface AccessStepProps {
    state: NestedWizardState;
    disabled?: boolean;
    onChange: (patch: Partial<NestedWizardState>) => void;
}

// Plain buttons rather than drag-to-reorder: row drag is an MUI X Pro feature and stays out of the app.
const AccessStep: React.FC<AccessStepProps> = ({state, disabled, onChange}) => {
    const exposures = deriveExposures(state.guests);
    const consoles = deriveConsoles(state.guests);

    const move = (index: number, delta: -1 | 1) =>
        onChange({guests: moveExposure(state.guests, exposures, index, delta)});

    const moveButton = (index: number, delta: -1 | 1) => {
        const direction = delta < 0 ? "up" : "down";
        const allowed = canMoveExposure(exposures, index, delta);
        const label = `Move ${exposures[index].guest} NIC ${exposures[index].nic} ${direction}`;
        // A disabled button fires no events, so the tooltip wraps a span.
        return (
            <Tooltip title={allowed ? label : ""}>
                <span>
                    <IconButton
                        size="small"
                        aria-label={label}
                        disabled={disabled || !allowed}
                        onClick={() => move(index, delta)}
                    >
                        {delta < 0 ? <ArrowUpward fontSize="small" /> : <ArrowDownward fontSize="small" />}
                    </IconButton>
                </span>
            </Tooltip>
        );
    };

    return (
        <Stack gap={3} mt={2}>
            <Paper variant="outlined" sx={{p: 2}} component="section" aria-label="Exposures">
                <Typography variant="subtitle1" component="h3">Exposed NICs</Typography>
                <Typography color="text.secondary" variant="body2" mb={1}>
                    Each exposed NIC gets a 1:1 NAT from one alias IP on the lab server&apos;s first NIC, in slot order.
                    Moving a NIC moves its guest, so the guest&apos;s other exposures and its console port move too.
                </Typography>
                {exposures.length === 0 ? (
                    <Alert severity="info">
                        No NIC is exposed, so lab servers built from this image reach the guests only through the
                        consoles. Expose a NIC with a static IP on the Guests step to reach a guest directly.
                    </Alert>
                ) : (
                    <>
                        <Table size="small" aria-label="Exposure slots">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Alias slot</TableCell>
                                    <TableCell>Guest</TableCell>
                                    <TableCell>NIC</TableCell>
                                    <TableCell>Network</TableCell>
                                    <TableCell>Guest IP</TableCell>
                                    <TableCell align="right">Order</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {exposures.map((exposure, index) => (
                                    <TableRow key={`${exposure.guest}-${exposure.nic}`}>
                                        <TableCell>{index}</TableCell>
                                        <TableCell>{exposure.guest}</TableCell>
                                        <TableCell>{exposure.nic}</TableCell>
                                        <TableCell>{exposure.network}</TableCell>
                                        <TableCell>{exposure.ip ?? "—"}</TableCell>
                                        <TableCell align="right" sx={{whiteSpace: "nowrap"}}>
                                            {moveButton(index, -1)}
                                            {moveButton(index, 1)}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                        <Typography variant="body2" mt={1}>
                            Lab servers using this image need {exposures.length} alias
                            IP{exposures.length === 1 ? "" : "s"} on NIC 0.
                        </Typography>
                    </>
                )}
            </Paper>
            <Paper variant="outlined" sx={{p: 2}} component="section" aria-label="Consoles">
                <Typography variant="subtitle1" component="h3">Consoles</Typography>
                <Typography color="text.secondary" variant="body2" mb={1}>
                    VNC consoles listen on the parent. Reach them through an SSH tunnel to the parent; the API
                    generates each console&apos;s password when the image is created.
                </Typography>
                {consoles.length === 0 ? (
                    <Alert severity="info">No guest has a console.</Alert>
                ) : (
                    <Table size="small" aria-label="Console ports">
                        <TableHead>
                            <TableRow>
                                <TableCell>Guest</TableCell>
                                <TableCell>Port</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {consoles.map(console => (
                                <TableRow key={console.guest}>
                                    <TableCell>{console.guest}</TableCell>
                                    <TableCell>{console.port}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </Paper>
        </Stack>
    );
};

export default AccessStep;
