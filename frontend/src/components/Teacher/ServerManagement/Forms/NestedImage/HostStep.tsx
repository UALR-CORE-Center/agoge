import {
    Alert,
    FormControl,
    FormHelperText,
    InputLabel,
    MenuItem,
    Select,
    Stack,
    TextField,
    Typography,
} from "@mui/material";
import React, {useState} from "react";
import {NestedParentOs} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import InputTags from "../../../../Common/FormInputs/InputTags";
import {GuestRuleContext} from "./guestRules";
import {
    effectiveDiskSize,
    NESTED_MAX_DISK_GB,
    NESTED_PARENT_OS_OPTIONS,
    nestedMinDiskSize,
    NestedWizardState,
    StepErrors,
} from "./nestedWizardState";

export interface MachineTypeOptions {
    pending: boolean;
    data: ServerMachineTypes[];
    error: string;
}

interface HostStepProps {
    state: NestedWizardState;
    errors: StepErrors;
    machineTypes: MachineTypeOptions;
    // The OS catalog and media library, for the size of each guest's install media.
    context: GuestRuleContext;
    disabled?: boolean;
    onChange: (patch: Partial<NestedWizardState>) => void;
}

const machineTypeLabel = (type: ServerMachineTypes): string =>
    `${type.name} — ${type.guest_cpus} vCPU, ${Math.round(type.memory_mb / 1024)} GB memory`;

const HostStep: React.FC<HostStepProps> = ({state, errors, machineTypes, context, disabled, onChange}) => {
    const minDiskSize = nestedMinDiskSize(state.guests, context);
    // What the instructor is typing; without it, clearing the field would snap back to the minimum mid-edit.
    const [diskInput, setDiskInput] = useState<string | null>(null);

    const machineTypeSelect = (
        field: 'build_machine_type' | 'machine_type',
        label: string,
        helperText: string,
    ) => (
        <FormControl fullWidth required error={!!errors[field]} disabled={disabled || machineTypes.pending}>
            <InputLabel id={`nested-${field}-label`}>{label}</InputLabel>
            <Select
                labelId={`nested-${field}-label`}
                id={`nested-${field}`}
                label={label}
                // A value outside the options (still loading, or the default is missing) would make MUI warn.
                value={machineTypes.data.some(type => type.name === state[field]) ? state[field] : ""}
                onChange={(event) => onChange({[field]: event.target.value} as Partial<NestedWizardState>)}
            >
                {machineTypes.data.map(type => (
                    <MenuItem key={type.name} value={type.name}>{machineTypeLabel(type)}</MenuItem>
                ))}
            </Select>
            <FormHelperText>{errors[field] || helperText}</FormHelperText>
        </FormControl>
    );

    return (
        <Stack gap={3} mt={2}>
            <TextField
                autoComplete="off"
                id="nested-server-name"
                label="Server Name"
                required
                disabled={disabled}
                value={state.server_name}
                onChange={(event) => onChange({server_name: event.target.value})}
                error={!!errors.server_name}
                helperText={errors.server_name || "The image is saved as image-<name>. Up to 54 lowercase letters, numbers, or hyphens."}
                placeholder="ad-lab-host"
                slotProps={{htmlInput: {maxLength: 54}}}
            />
            <TextField
                id="nested-description"
                label="Description"
                required
                multiline
                maxRows={4}
                disabled={disabled}
                value={state.description}
                onChange={(event) => onChange({description: event.target.value})}
                error={!!errors.description}
                helperText={errors.description || "Up to 200 characters on what the lab host contains."}
                slotProps={{htmlInput: {maxLength: 200}}}
            />
            <Stack gap={1}>
                <Typography>Image Labels</Typography>
                <InputTags
                    id="nested-image-labels"
                    name="labels"
                    tagType={"labels"}
                    ariaLabel={"Image Labels input"}
                    helperText={"Comma delimited list of services and functionality provided on this host"}
                    required={false}
                    initialTags={state.labels}
                    onTagChanges={(labels) => onChange({labels})}
                />
            </Stack>

            <Typography variant="h6" component="h3">Parent</Typography>
            <FormControl fullWidth required error={!!errors.parent_os} disabled={disabled}>
                <InputLabel id="nested-parent-os-label">Parent OS</InputLabel>
                <Select
                    labelId="nested-parent-os-label"
                    id="nested-parent-os"
                    label="Parent OS"
                    value={state.parent_os}
                    onChange={(event) => onChange({parent_os: event.target.value as NestedParentOs})}
                >
                    {NESTED_PARENT_OS_OPTIONS.map(option => (
                        <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                    ))}
                </Select>
                <FormHelperText>
                    {errors.parent_os || "The Debian release that runs libvirt and hosts the guests."}
                </FormHelperText>
            </FormControl>
            {machineTypes.error && <Alert severity="error">{machineTypes.error}</Alert>}
            {machineTypeSelect(
                'build_machine_type',
                "Build machine type",
                "Used only while the guests install. A larger type installs faster.",
            )}
            {machineTypeSelect(
                'machine_type',
                "Lab machine type",
                "What lab servers built from this image default to. Only nested-capable N1 and N2 types are listed.",
            )}
            <TextField
                id="nested-disk-size"
                label="Disk Size (GB)"
                type="number"
                required
                disabled={disabled}
                value={diskInput ?? String(effectiveDiskSize(state, context))}
                onChange={(event) => {
                    const value = event.target.value;
                    setDiskInput(value);
                    onChange({disk_size: value === "" ? null : Number(value)});
                }}
                onBlur={() => setDiskInput(null)}
                error={!!errors.disk_size}
                helperText={
                    errors.disk_size ||
                    `At least ${minDiskSize} GB: the parent, every guest disk, build scratch space, and the install media. ` +
                    `Raise it for room inside the guests (up to ${NESTED_MAX_DISK_GB} GB).`
                }
                slotProps={{htmlInput: {min: minDiskSize, max: NESTED_MAX_DISK_GB, step: 1}}}
            />

            <Typography variant="h6" component="h3">Parent access</Typography>
            <TextField
                autoComplete="off"
                id="nested-username"
                label="Username"
                required
                disabled={disabled}
                value={state.username}
                onChange={(event) => onChange({username: event.target.value})}
                error={!!errors.username}
                helperText={errors.username || "The parent's user; you reach the guest consoles through it."}
                slotProps={{htmlInput: {maxLength: 20}}}
            />
            <TextField
                id="nested-ssh-key"
                label="SSH Public Key"
                required
                multiline
                minRows={2}
                disabled={disabled}
                value={state.ssh_key}
                onChange={(event) => onChange({ssh_key: event.target.value})}
                error={!!errors.ssh_key}
                helperText={errors.ssh_key || "Public key for the parent's user."}
            />
        </Stack>
    );
};

export default HostStep;
