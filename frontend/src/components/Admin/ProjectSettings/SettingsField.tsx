import {Close} from "@mui/icons-material";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {
    Chip, CircularProgress,
    IconButton,
    Skeleton,
    Stack,
    Switch,
    TextField, Tooltip,
    Typography,
} from "@mui/material";
import React, {useEffect, useState} from "react";

import {URL_ADMIN_API_PROJECT_BASE} from "../../../router/urls";
import {apiService} from "../../../services/api-request.service";
import NumberInputField from "../../Common/FormInputs/NumberInputField";


interface Props {
    name: string;
    value: string | number | boolean | null | undefined;
    inputType: string | number | boolean;
    loading: boolean;
    onChange?: (name: string, newValue: any) => void;
}

export const SettingsField: React.FC<Props> = (props) => {
    const { name, value, inputType, loading } = props;
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [editValue, setEditValue] = useState<string | number | boolean | null | undefined>(value);
    const [saveLoading, setSaveLoading] = useState<boolean>(false);
    const [hasError, setHasError] = useState<string>("");

    useEffect(() => {
        setEditValue(value);
    }, [value]);

    const handleLocalChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const { type, checked, value: inputValue } = event.target;
        let newValue: string | number | boolean | null = inputValue;

        if (type === 'checkbox') {
            newValue = checked;
        } else if (type === 'number') {
            newValue = inputValue === '' ? null : parseInt(inputValue, 10);
        }

        setEditValue(newValue);
    }

    const handleEditClick = () => {
        setIsEditing(true);
    }

    const handleSaveClick = async () => {
        setHasError("");
        setSaveLoading(true);
        await apiService.patch(
            URL_ADMIN_API_PROJECT_BASE,
            {[String(name)]: editValue},
            true
        ).then(() => {
            if (props.onChange) {
                props.onChange(name, editValue ?? null);
            }
        }).catch((err) => {
            setHasError(String(err.message ?? "Error saving changes"));
        }).finally(() => {
            setIsEditing(false);
            setSaveLoading(false);
        })
    }

    const handleCancelClick = () => {
        setHasError("");
        setEditValue(value);
        setSaveLoading(false);
        setIsEditing(false);
    }

    const getInputField = () => {
        const hasValue = editValue !== null && editValue !== undefined;

        if (!isEditing) {
            return (
                <Typography variant={"body1"}>
                    {hasValue ? String(editValue) : "Not configured"}
                </Typography>
            )
        } else {
            if (inputType === "string") {
                return (
                    <TextField
                        autoComplete="off"
                        size={"small"}
                        value={editValue ?? ""}
                        onChange={handleLocalChange}
                    />
                );
            } else if (inputType === 'boolean') {
                return (
                    <Switch
                        checked={Boolean(editValue)}
                        onChange={handleLocalChange}
                    />
                );
            } else if (inputType === "number") {
                const isWireGuardPort = name === 'wireguard_port';
                return (
                    <NumberInputField
                        min={isWireGuardPort ? 1 : 10}
                        max={isWireGuardPort ? 65535 : 1000}
                        onChange={handleLocalChange}
                        value={editValue ?? (isWireGuardPort ? 51820 : 10)}
                        size={"small"}
                    />
                );
            }
        }
    }

    const renderActions = () => {
        if (isEditing) {
            return (
                <>
                    <Tooltip title={`Save ${name}`}>
                        <IconButton
                            aria-label={`save ${name}`}
                            size="small"
                            onClick={handleSaveClick}
                            disabled={saveLoading}
                        >
                            {saveLoading ?
                                <CircularProgress size={"1.5rem"}/>
                                : <SaveIcon fontSize="inherit" color="info" />
                            }
                        </IconButton>
                    </Tooltip>
                    <Tooltip title={`Cancel`}>
                        <IconButton
                            aria-label={`cancel ${name} changes`}
                            size="small"
                            onClick={handleCancelClick}
                            disabled={saveLoading}
                        >
                            <Close color={saveLoading ? "disabled" : "error"}/>
                        </IconButton>
                    </Tooltip>
                </>
            );
        }
        return (
            <Tooltip title={`Edit ${name}`}>
                <IconButton
                    aria-label={`edit ${name}`}
                    size="small"
                    onClick={handleEditClick}
                >
                    <EditIcon fontSize="inherit" color="info" />
                </IconButton>
            </Tooltip>
        );
    };

    const getHelpText = () => {
        if (name == 'classroom_user') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>Email account of user to associate with Google Classroom. Used for build-automation for associated LMS courses</Typography>;
        } else if (name == 'max_workspaces') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>Max number of workspaces to allow in project up to 1000</Typography>;
        } else if (name == 'spec_bucket') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>Storage bucket for build specifications</Typography>;
        } else if (name == 'student_workout_firewall') {
            return <Typography variant={"subtitle1"}color={"textDisabled"}>Whether IP-based student workout firewall is enabled</Typography>
        } else if (name == 'wireguard_dns_prefix') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>DNS label prefix used for WireGuard endpoints. The GCP project ID is added automatically to keep shared parent zones collision-free. Defaults to wg.</Typography>
        } else if (name == 'wireguard_dns_suffix') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>Public DNS suffix used for WireGuard gateways. Defaults to the parent DNS suffix.</Typography>
        } else if (name == 'wireguard_port') {
            return <Typography variant={"subtitle1"} color={"textDisabled"}>Public UDP listener port advertised for WireGuard gateways. Defaults to 51820.</Typography>
        }
    }

    const render = () => {
        return (
            <>
                <Chip
                    variant={"filled"}
                    label={name.toUpperCase()}
                    color={"primary"}
                    sx={{
                        color: "white",
                        borderRadius: .9,
                        height: 25,
                        ml: 1
                    }}
                />
                {getInputField()}
                {renderActions()}
                {getHelpText()}
            </>
        )
    }

    return (
        <>
            <Stack direction={"column"} gap={1}>
                <Stack direction={"row"} gap={1}>
                    {
                        loading ?
                            <Skeleton
                                animation={"wave"}
                                variant={"rounded"}
                                width={100}
                                height={20}
                                sx={{my: 2}}
                            />
                            : render()
                    }
                </Stack>
                {hasError && (
                    <Stack direction={"row"} gap={1} sx={{ml: 2}}>
                        <Typography variant="body2" color="error">
                            {hasError}
                        </Typography>
                    </Stack>
                )}
            </Stack>
        </>
    );
};
