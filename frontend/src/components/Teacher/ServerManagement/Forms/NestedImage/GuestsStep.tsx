import {Add, Delete, Refresh, Visibility, VisibilityOff} from "@mui/icons-material";
import {
    Alert,
    Autocomplete,
    Button,
    Checkbox,
    Chip,
    FormControl,
    FormControlLabel,
    FormHelperText,
    IconButton,
    InputAdornment,
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
import React, {useState} from "react";
import {NestedGuest, NestedGuestNic, NestedMedia, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import MediaUpload from "./MediaUpload";
import NetworkTopology from "./NetworkTopology";
import OsPickerDialog, {OsChips} from "./OsPickerDialog";
import {
    catalogEntry,
    dropProductKey,
    generatePassword,
    GUEST_LIMITS,
    guestErrorKey,
    NESTED_MAX_GUESTS,
    NESTED_MAX_NICS,
    newGuest,
    nicErrorKey,
    renameProductKey,
    requiresProductKey,
    supportsPackages,
} from "./guestRules";
import {NestedWizardState, StepErrors} from "./nestedWizardState";

export interface CatalogOptions {
    pending: boolean;
    data: NestedOsCatalogEntry[];
    error: string;
}

interface GuestsStepProps {
    state: NestedWizardState;
    errors: StepErrors;
    catalog: CatalogOptions;
    media: NestedMedia[];
    disabled?: boolean;
    onChange: (patch: Partial<NestedWizardState>) => void;
    onMediaUploaded: (media: NestedMedia) => void;
}

// A number field's text; an empty or partial entry becomes NaN, which the rules report.
const toNumber = (value: string): number => value.trim() === "" ? NaN : Number(value);
const numberText = (value: number): string => Number.isNaN(value) ? "" : String(value);

const PasswordField: React.FC<{
    label: string;
    value: string;
    error?: string;
    helperText: string;
    disabled?: boolean;
    onChange: (value: string) => void;
}> = ({label, value, error, helperText, disabled, onChange}) => {
    const [shown, setShown] = useState(false);
    return (
        <TextField
            fullWidth
            required
            autoComplete="new-password"
            label={label}
            type={shown ? "text" : "password"}
            disabled={disabled}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            error={!!error}
            helperText={error || helperText}
            slotProps={{
                input: {
                    endAdornment: (
                        <InputAdornment position="end">
                            <Tooltip title={shown ? "Hide password" : "Show password"}>
                                <IconButton aria-label={shown ? "Hide password" : "Show password"} onClick={() => setShown(!shown)}>
                                    {shown ? <VisibilityOff /> : <Visibility />}
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Generate a password">
                                <span>
                                    <IconButton
                                        aria-label="Generate password"
                                        disabled={disabled}
                                        onClick={() => {
                                            onChange(generatePassword());
                                            setShown(true);
                                        }}
                                    >
                                        <Refresh />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </InputAdornment>
                    ),
                },
            }}
        />
    );
};

const GuestsStep: React.FC<GuestsStepProps> = (
    {state, errors, catalog, media, disabled, onChange, onMediaUploaded}
) => {
    const {guests, networks, product_keys} = state;
    const [pickerOpen, setPickerOpen] = useState(false);

    const update = (index: number, patch: Partial<NestedGuest>) => {
        const next = guests.map((guest, position) => position === index ? {...guest, ...patch} : guest);
        if (patch.name !== undefined) {
            onChange({guests: next, product_keys: renameProductKey(product_keys, guests[index].name, patch.name)});
        } else {
            onChange({guests: next});
        }
    };
    const updateNic = (guestIndex: number, nicIndex: number, patch: Partial<NestedGuestNic>) =>
        update(guestIndex, {
            nics: guests[guestIndex].nics.map((nic, position) => position === nicIndex ? {...nic, ...patch} : nic),
        });
    const remove = (index: number) => onChange({
        guests: guests.filter((_, position) => position !== index),
        product_keys: dropProductKey(product_keys, guests[index].name),
    });
    const add = (entry: NestedOsCatalogEntry) => onChange({guests: [...guests, newGuest(entry, guests, networks)]});

    return (
        <Stack gap={3} mt={2}>
            {errors.guests && <Alert severity="error">{errors.guests}</Alert>}
            {catalog.error && <Alert severity="error">{catalog.error}</Alert>}
            <Typography color="text.secondary">
                Each guest is a VM on the parent. The builder installs it from the catalog entry and records the
                admin credentials, which instructors can see.
            </Typography>
            {guests.map((guest, index) => {
                const entry = catalogEntry(catalog.data, guest.os_id);
                const error = (field: keyof NestedGuest | 'product_key') => errors[guestErrorKey(index, field)];
                const numberField = (
                    field: 'vcpus' | 'memory_mb' | 'disk_gb' | 'start_order' | 'start_delay_seconds',
                    label: string,
                    helperText: string,
                ) => (
                    <TextField
                        fullWidth
                        required
                        type="number"
                        label={label}
                        disabled={disabled}
                        value={numberText(guest[field])}
                        onChange={(event) => update(index, {[field]: toNumber(event.target.value)})}
                        error={!!error(field)}
                        helperText={error(field) || helperText}
                    />
                );
                return (
                    <Paper key={index} variant="outlined" sx={{p: 2}} component="section" aria-label={`Guest ${index + 1}`}>
                        <Stack gap={2}>
                            <Stack direction="row" alignItems="flex-start" justifyContent="space-between" gap={1}>
                                <Stack gap={0.5}>
                                    <Typography variant="subtitle1" component="h3">
                                        {`Guest ${index + 1}: ${entry?.display_name ?? guest.os_id}`}
                                    </Typography>
                                    {entry && <OsChips entry={entry} />}
                                </Stack>
                                <Tooltip title="Remove guest">
                                    <span>
                                        <IconButton aria-label={`Remove guest ${index + 1}`} disabled={disabled} onClick={() => remove(index)}>
                                            <Delete />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Stack>
                            {error("os_id") && !catalog.pending && <Alert severity="error">{error("os_id")}</Alert>}
                            <Stack direction={{xs: "column", sm: "row"}} gap={2}>
                                <TextField
                                    fullWidth
                                    required
                                    autoComplete="off"
                                    label="Name"
                                    disabled={disabled}
                                    value={guest.name}
                                    onChange={(event) => update(index, {name: event.target.value})}
                                    error={!!error("name")}
                                    helperText={error("name") || "The guest's hostname and libvirt domain."}
                                    slotProps={{htmlInput: {maxLength: 15}}}
                                />
                                {numberField("vcpus", "vCPUs", `${GUEST_LIMITS.vcpus.min}–${GUEST_LIMITS.vcpus.max}.`)}
                                {numberField("memory_mb", "Memory (MB)", `At least ${entry?.min_memory_mb ?? GUEST_LIMITS.memory_mb.min} MB.`)}
                                {numberField("disk_gb", "Disk (GB)", `At least ${entry?.min_disk_gb ?? GUEST_LIMITS.disk_gb.min} GB.`)}
                            </Stack>
                            <Stack direction={{xs: "column", sm: "row"}} gap={2}>
                                <TextField
                                    fullWidth
                                    required
                                    autoComplete="off"
                                    label="Admin username"
                                    disabled={disabled}
                                    value={guest.admin_username}
                                    onChange={(event) => update(index, {admin_username: event.target.value.trim()})}
                                    error={!!error("admin_username")}
                                    helperText={error("admin_username") || "Created by the installer."}
                                    slotProps={{htmlInput: {maxLength: 20}}}
                                />
                                <PasswordField
                                    label="Admin password"
                                    value={guest.admin_password}
                                    error={error("admin_password")}
                                    helperText="Stored with the image; instructors can see it."
                                    disabled={disabled}
                                    onChange={(value) => update(index, {admin_password: value})}
                                />
                                {entry && requiresProductKey(entry) && (
                                    <TextField
                                        fullWidth
                                        required
                                        autoComplete="off"
                                        label="Product key"
                                        disabled={disabled}
                                        value={product_keys[guest.name] ?? ""}
                                        onChange={(event) => onChange({
                                            product_keys: {...product_keys, [guest.name]: event.target.value.toUpperCase()},
                                        })}
                                        error={!!error("product_key")}
                                        helperText={error("product_key") || "Used once for the install and never stored."}
                                    />
                                )}
                            </Stack>
                            {entry?.requires_upload && (
                                <MediaUpload
                                    guestName={guest.name}
                                    entry={entry}
                                    mediaId={guest.media_id}
                                    media={media}
                                    error={error("media_id")}
                                    disabled={disabled}
                                    onSelect={(mediaId) => update(index, {media_id: mediaId})}
                                    onUploaded={(uploaded) => {
                                        onMediaUploaded(uploaded);
                                        update(index, {media_id: uploaded.id});
                                    }}
                                />
                            )}
                            <Stack gap={1}>
                                <Typography variant="subtitle2" component="h4">NICs</Typography>
                                {error("nics") && <Alert severity="error">{error("nics")}</Alert>}
                                {guest.nics.map((nic, nicIndex) => {
                                    const nicError = (field: keyof NestedGuestNic) => errors[nicErrorKey(index, nicIndex, field)];
                                    const labelId = `nested-guest-${index}-nic-${nicIndex}`;
                                    return (
                                        <Stack
                                            key={nicIndex}
                                            direction={{xs: "column", sm: "row"}}
                                            gap={2}
                                            alignItems={{sm: "flex-start"}}
                                            aria-label={`Guest ${index + 1} NIC ${nicIndex + 1}`}
                                            role="group"
                                        >
                                            <FormControl fullWidth required disabled={disabled} error={!!nicError("network")}>
                                                <InputLabel id={`${labelId}-network`}>Network</InputLabel>
                                                <Select
                                                    labelId={`${labelId}-network`}
                                                    label="Network"
                                                    value={networks.some(network => network.name === nic.network) ? nic.network : ""}
                                                    onChange={(event) => updateNic(index, nicIndex, {network: event.target.value})}
                                                >
                                                    {networks.map(network => (
                                                        <MenuItem key={network.name} value={network.name}>
                                                            {`${network.name} (${network.cidr})`}
                                                        </MenuItem>
                                                    ))}
                                                </Select>
                                                <FormHelperText>{nicError("network") || `NIC ${nicIndex}`}</FormHelperText>
                                            </FormControl>
                                            <FormControl fullWidth disabled={disabled}>
                                                <InputLabel id={`${labelId}-addressing`}>Addressing</InputLabel>
                                                <Select
                                                    labelId={`${labelId}-addressing`}
                                                    label="Addressing"
                                                    value={nic.ip === null ? "dhcp" : "static"}
                                                    onChange={(event) => updateNic(index, nicIndex, {
                                                        ip: event.target.value === "dhcp" ? null : "",
                                                    })}
                                                >
                                                    <MenuItem value="dhcp">DHCP</MenuItem>
                                                    <MenuItem value="static">Static</MenuItem>
                                                </Select>
                                                <FormHelperText>DHCP leaves the address to the network.</FormHelperText>
                                            </FormControl>
                                            {nic.ip !== null && (
                                                <TextField
                                                    fullWidth
                                                    required
                                                    autoComplete="off"
                                                    label="IP address"
                                                    disabled={disabled}
                                                    value={nic.ip}
                                                    onChange={(event) => updateNic(index, nicIndex, {ip: event.target.value.trim()})}
                                                    error={!!nicError("ip")}
                                                    helperText={nicError("ip") || "Outside the DHCP range."}
                                                />
                                            )}
                                            <FormControl error={!!nicError("expose")} sx={{minWidth: 140}}>
                                                <FormControlLabel
                                                    control={(
                                                        <Checkbox
                                                            checked={nic.expose}
                                                            disabled={disabled}
                                                            onChange={(event) => updateNic(index, nicIndex, {expose: event.target.checked})}
                                                        />
                                                    )}
                                                    label="Expose"
                                                />
                                                <FormHelperText>{nicError("expose") || "Reachable from the lab VPC."}</FormHelperText>
                                            </FormControl>
                                            <Tooltip title={guest.nics.length === 1 ? "A guest needs at least one NIC." : "Remove NIC"}>
                                                <span>
                                                    <IconButton
                                                        aria-label={`Remove NIC ${nicIndex + 1} of guest ${index + 1}`}
                                                        disabled={disabled || guest.nics.length === 1}
                                                        onClick={() => update(index, {
                                                            nics: guest.nics.filter((_, position) => position !== nicIndex),
                                                        })}
                                                    >
                                                        <Delete />
                                                    </IconButton>
                                                </span>
                                            </Tooltip>
                                        </Stack>
                                    );
                                })}
                                <Stack direction="row">
                                    <Button
                                        size="small"
                                        startIcon={<Add />}
                                        disabled={disabled || guest.nics.length >= NESTED_MAX_NICS}
                                        onClick={() => update(index, {
                                            nics: [...guest.nics, {network: networks[0]?.name ?? "", ip: null, expose: false}],
                                        })}
                                    >
                                        Add NIC
                                    </Button>
                                </Stack>
                            </Stack>
                            {entry && supportsPackages(entry) && (
                                <Autocomplete
                                    multiple
                                    freeSolo
                                    options={[] as string[]}
                                    disabled={disabled}
                                    value={guest.packages}
                                    onChange={(_, value) => update(index, {
                                        packages: (value as string[]).map(name => name.trim()).filter(Boolean),
                                    })}
                                    renderTags={(value, getTagProps) => value.map((option, position) => {
                                        const {key, ...itemProps} = getTagProps({index: position});
                                        return <Chip key={key} size="small" label={option} {...itemProps} />;
                                    })}
                                    renderInput={(params) => (
                                        <TextField
                                            {...params}
                                            label="Packages"
                                            error={!!error("packages")}
                                            helperText={error("packages") || "Installed into the image. Press Enter after each name."}
                                        />
                                    )}
                                />
                            )}
                            {error("packages") && !(entry && supportsPackages(entry)) && (
                                <Alert severity="error">{error("packages")}</Alert>
                            )}
                            <TextField
                                fullWidth
                                multiline
                                minRows={2}
                                maxRows={10}
                                label="Post-install script"
                                disabled={disabled}
                                value={guest.post_install_script ?? ""}
                                onChange={(event) => update(index, {post_install_script: event.target.value || null})}
                                error={!!error("post_install_script")}
                                helperText={error("post_install_script")
                                    || (entry?.family === "windows" ? "PowerShell, run once after install." : "bash, run once after install.")}
                                slotProps={{htmlInput: {style: {fontFamily: "monospace"}}}}
                            />
                            <Stack direction={{xs: "column", sm: "row"}} gap={2} alignItems={{sm: "flex-start"}}>
                                <FormControlLabel
                                    sx={{minWidth: 140, mt: {sm: 1}}}
                                    control={(
                                        <Switch
                                            checked={guest.console}
                                            disabled={disabled}
                                            onChange={(event) => update(index, {console: event.target.checked})}
                                        />
                                    )}
                                    label="VNC console"
                                />
                                <FormControlLabel
                                    sx={{minWidth: 140, mt: {sm: 1}}}
                                    control={(
                                        <Switch
                                            checked={guest.autostart}
                                            disabled={disabled}
                                            onChange={(event) => update(index, {autostart: event.target.checked})}
                                        />
                                    )}
                                    label="Autostart"
                                />
                                {numberField("start_order", "Start order", "Lower starts first.")}
                                {numberField("start_delay_seconds", "Start delay (s)", "Wait before starting the next guest.")}
                            </Stack>
                        </Stack>
                    </Paper>
                );
            })}
            <Stack direction="row">
                <Button
                    variant="outlined"
                    startIcon={<Add />}
                    disabled={disabled || guests.length >= NESTED_MAX_GUESTS}
                    onClick={() => setPickerOpen(true)}
                >
                    Add guest
                </Button>
            </Stack>
            <Typography variant="h6" component="h3">Topology</Typography>
            <NetworkTopology networks={networks} guests={guests} />
            <OsPickerDialog
                open={pickerOpen}
                catalog={catalog.data}
                pending={catalog.pending}
                error={catalog.error}
                onClose={() => setPickerOpen(false)}
                onConfirm={add}
            />
        </Stack>
    );
};

export default GuestsStep;
