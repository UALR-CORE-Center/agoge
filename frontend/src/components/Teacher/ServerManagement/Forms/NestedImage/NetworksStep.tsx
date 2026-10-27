import {Add, Delete} from "@mui/icons-material";
import {
    Alert,
    Button,
    FormControl,
    FormControlLabel,
    FormHelperText,
    IconButton,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from "@mui/material";
import React from "react";
import {NestedNetwork, NestedNetworkMode} from "../../../../../services/Server/nested.model";
import NetworkTopology from "./NetworkTopology";
import {NestedWizardState, StepErrors} from "./nestedWizardState";
import {guestsOnNetwork, NESTED_MAX_NETWORKS, networkErrorKey, nextNestedNetwork, renameNetworkInGuests} from "./networkRules";

interface NetworksStepProps {
    state: NestedWizardState;
    errors: StepErrors;
    disabled?: boolean;
    onChange: (patch: Partial<NestedWizardState>) => void;
}

const NetworksStep: React.FC<NetworksStepProps> = ({state, errors, disabled, onChange}) => {
    const {networks, guests} = state;

    const update = (index: number, patch: Partial<NestedNetwork>) => {
        const next = networks.map((network, position) => position === index ? {...network, ...patch} : network);
        if (patch.name !== undefined) {
            onChange({networks: next, guests: renameNetworkInGuests(guests, networks, networks[index].name, patch.name)});
        } else {
            onChange({networks: next});
        }
    };
    // Empty address fields are sent as null, which the API reads as "not set".
    const address = (value: string): string | null => value.trim() === "" ? null : value.trim();

    return (
        <Stack gap={3} mt={2}>
            {errors.networks && <Alert severity="error">{errors.networks}</Alert>}
            <Typography color="text.secondary">
                Each network is a libvirt bridge on the parent. NAT networks reach the internet through the parent;
                isolated networks do not. Leave the parent address empty for a pure layer-2 segment.
            </Typography>
            {networks.map((network, index) => {
                const error = (field: keyof NestedNetwork) => errors[networkErrorKey(index, field)];
                const users = guestsOnNetwork(guests, network.name);
                const removeBlocked = networks.length === 1
                    ? "The host needs at least one network."
                    : users.length > 0 ? `Used by ${users.join(", ")}. Move their NICs first.` : "";
                return (
                    <Paper key={index} variant="outlined" sx={{p: 2}} component="section" aria-label={`Network ${index + 1}`}>
                        <Stack gap={2}>
                            <Stack direction="row" alignItems="center" justifyContent="space-between">
                                <Typography variant="subtitle1" component="h3">{`Network ${index + 1}`}</Typography>
                                <Tooltip title={removeBlocked || "Remove network"}>
                                    <span>
                                        <IconButton
                                            aria-label={`Remove network ${index + 1}`}
                                            disabled={disabled || !!removeBlocked}
                                            onClick={() => onChange({networks: networks.filter((_, position) => position !== index)})}
                                        >
                                            <Delete />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Stack>
                            <Stack direction={{xs: "column", sm: "row"}} gap={2}>
                                <TextField
                                    fullWidth
                                    autoComplete="off"
                                    label="Name"
                                    required
                                    disabled={disabled}
                                    value={network.name}
                                    onChange={(event) => update(index, {name: event.target.value})}
                                    error={!!error("name")}
                                    helperText={error("name") || "Guest NICs refer to the network by this name."}
                                    slotProps={{htmlInput: {maxLength: 15}}}
                                />
                                <TextField
                                    fullWidth
                                    autoComplete="off"
                                    label="CIDR"
                                    required
                                    disabled={disabled}
                                    value={network.cidr}
                                    onChange={(event) => update(index, {cidr: event.target.value.trim()})}
                                    error={!!error("cidr")}
                                    helperText={error("cidr") || "A private range from /16 to /29."}
                                />
                                <FormControl fullWidth required disabled={disabled}>
                                    <InputLabel id={`nested-network-${index}-mode-label`}>Mode</InputLabel>
                                    <Select
                                        labelId={`nested-network-${index}-mode-label`}
                                        label="Mode"
                                        value={network.mode}
                                        onChange={(event) => update(index, {mode: event.target.value as NestedNetworkMode})}
                                    >
                                        <MenuItem value="nat">NAT</MenuItem>
                                        <MenuItem value="isolated">Isolated</MenuItem>
                                    </Select>
                                    <FormHelperText>
                                        {network.mode === "nat" ? "Internet through the parent." : "No route off the network."}
                                    </FormHelperText>
                                </FormControl>
                            </Stack>
                            <Stack direction={{xs: "column", sm: "row"}} gap={2} alignItems={{sm: "flex-start"}}>
                                <TextField
                                    fullWidth
                                    autoComplete="off"
                                    label="Parent address"
                                    required={network.mode === "nat" || network.dhcp}
                                    disabled={disabled}
                                    value={network.parent_address ?? ""}
                                    onChange={(event) => update(index, {parent_address: address(event.target.value)})}
                                    error={!!error("parent_address")}
                                    helperText={error("parent_address") || "The parent's address on this network; it is the guests' gateway."}
                                />
                                <FormControlLabel
                                    sx={{minWidth: 120, mt: {sm: 1}}}
                                    control={(
                                        <Switch
                                            checked={network.dhcp}
                                            disabled={disabled}
                                            onChange={(event) => update(index, {dhcp: event.target.checked})}
                                        />
                                    )}
                                    label="DHCP"
                                />
                                {network.dhcp && (
                                    <>
                                        <TextField
                                            fullWidth
                                            autoComplete="off"
                                            label="DHCP start"
                                            required
                                            disabled={disabled}
                                            value={network.dhcp_start ?? ""}
                                            onChange={(event) => update(index, {dhcp_start: address(event.target.value)})}
                                            error={!!error("dhcp_start")}
                                            helperText={error("dhcp_start") || "First leased address."}
                                        />
                                        <TextField
                                            fullWidth
                                            autoComplete="off"
                                            label="DHCP end"
                                            required
                                            disabled={disabled}
                                            value={network.dhcp_end ?? ""}
                                            onChange={(event) => update(index, {dhcp_end: address(event.target.value)})}
                                            error={!!error("dhcp_end")}
                                            helperText={error("dhcp_end") || "Last leased address."}
                                        />
                                    </>
                                )}
                            </Stack>
                            {/* Hidden range fields still go to the API, which checks them, so surface their errors. */}
                            {!network.dhcp && (error("dhcp_start") || error("dhcp_end")) && (
                                <Alert severity="error">{error("dhcp_start") || error("dhcp_end")}</Alert>
                            )}
                        </Stack>
                    </Paper>
                );
            })}
            <Stack direction="row">
                <Button
                    variant="outlined"
                    startIcon={<Add />}
                    disabled={disabled || networks.length >= NESTED_MAX_NETWORKS}
                    onClick={() => onChange({networks: [...networks, nextNestedNetwork(networks)]})}
                >
                    Add network
                </Button>
            </Stack>
            <Typography variant="h6" component="h3">Topology</Typography>
            <NetworkTopology networks={networks} guests={guests} />
        </Stack>
    );
};

export default NetworksStep;
