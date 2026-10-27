import {
    Alert,
    Box,
    FormControlLabel,
    LinearProgress,
    Paper,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Typography,
} from "@mui/material";
import React, {useState} from "react";
import {NestedMedia, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {
    capacityMeters,
    deriveConsoles,
    estimateBuildMinutes,
    meterPercent,
    reviewWarnings,
} from "./accessReview";
import {catalogEntry, NESTED_PARENT_OVERHEAD_MB, requiresProductKey} from "./guestRules";
import {effectiveDiskSize, NestedWizardState, StepErrors} from "./nestedWizardState";

interface ReviewStepProps {
    state: NestedWizardState;
    errors: StepErrors;
    machineTypes: ServerMachineTypes[];
    catalog: NestedOsCatalogEntry[];
    media: NestedMedia[];
}

const ReviewStep: React.FC<ReviewStepProps> = ({state, errors, machineTypes, catalog, media}) => {
    const [showPasswords, setShowPasswords] = useState(false);
    const context = {catalog, media};
    const meters = capacityMeters(state, machineTypes, context);
    const mediaNames = Object.fromEntries(media.map(item => [item.id, item.filename]));
    const warnings = reviewWarnings(state, catalog, mediaNames);
    const consolePorts = Object.fromEntries(deriveConsoles(state.guests).map(console => [console.guest, console.port]));
    const messages = Object.values(errors).filter((message): message is string => !!message);

    return (
        <Stack gap={3} mt={2}>
            {messages.map(message => <Alert key={message} severity="error">{message}</Alert>)}

            <Paper variant="outlined" sx={{p: 2}} component="section" aria-label="Host summary">
                <Typography variant="subtitle1" component="h3">Host</Typography>
                <Typography variant="body2">
                    {state.server_name || "—"} on {state.parent_os}; build {state.build_machine_type || "—"},
                    lab {state.machine_type || "—"}; {effectiveDiskSize(state, context)} GB disk; {state.guests.length} guest
                    {state.guests.length === 1 ? "" : "s"} on {state.networks.length} network
                    {state.networks.length === 1 ? "" : "s"}.
                </Typography>
                <Typography variant="body2" mt={1} aria-label="Estimated build time">
                    Estimated build time: about {estimateBuildMinutes(state.guests, catalog)} minutes, plus media
                    downloads. The build runs on its own; check its phase on the server list.
                </Typography>
            </Paper>

            <Paper variant="outlined" sx={{p: 2}} component="section" aria-label="Capacity">
                <Typography variant="subtitle1" component="h3" mb={1}>Capacity</Typography>
                <Stack gap={1.5}>
                    {meters.map(item => {
                        const over = item.used > item.available;
                        return (
                            <Box key={item.label}>
                                <Stack direction="row" justifyContent="space-between">
                                    <Typography variant="body2">{item.label}</Typography>
                                    <Typography variant="body2" color={over ? "error" : "text.secondary"}>
                                        {item.used} / {item.available} {item.unit}
                                    </Typography>
                                </Stack>
                                <LinearProgress
                                    variant="determinate"
                                    value={meterPercent(item)}
                                    color={over ? "error" : "primary"}
                                    aria-label={item.label}
                                />
                            </Box>
                        );
                    })}
                </Stack>
                <Typography variant="caption" color="text.secondary">
                    RAM includes {NESTED_PARENT_OVERHEAD_MB} MB for the parent. Guests may use up to twice the machine&apos;s vCPUs.
                </Typography>
            </Paper>

            {warnings.length > 0 && (
                <Stack gap={1} component="section" aria-label="Warnings">
                    {warnings.map(warning => <Alert key={warning.message} severity="warning">{warning.message}</Alert>)}
                </Stack>
            )}

            <Paper variant="outlined" sx={{p: 2}} component="section" aria-label="Credentials">
                <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap">
                    <Typography variant="subtitle1" component="h3">Credentials</Typography>
                    <FormControlLabel
                        control={<Switch checked={showPasswords} onChange={(_, checked) => setShowPasswords(checked)} />}
                        label="Show passwords"
                    />
                </Stack>
                <Typography variant="body2" color="text.secondary" mb={1}>
                    The parent accepts SSH as {state.username || "—"} with the key from the Host step. Teachers can
                    read guest passwords on the image. Product keys are used for the build and never stored.
                </Typography>
                <Table size="small" aria-label="Guest credentials">
                    <TableHead>
                        <TableRow>
                            <TableCell>Guest</TableCell>
                            <TableCell>Username</TableCell>
                            <TableCell>Password</TableCell>
                            <TableCell>Product key</TableCell>
                            <TableCell>Console</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {state.guests.map(guest => {
                            const entry = catalogEntry(catalog, guest.os_id);
                            const port = consolePorts[guest.name];
                            return (
                                <TableRow key={guest.name}>
                                    <TableCell>{guest.name}</TableCell>
                                    <TableCell>{guest.admin_username}</TableCell>
                                    <TableCell sx={{fontFamily: "monospace"}}>
                                        {showPasswords ? guest.admin_password : "••••••••"}
                                    </TableCell>
                                    <TableCell>
                                        {entry && requiresProductKey(entry) ? "Provided, not stored" : "Not needed"}
                                    </TableCell>
                                    <TableCell>{port ? `VNC ${port}, password generated` : "Off"}</TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </Paper>
        </Stack>
    );
};

export default ReviewStep;
