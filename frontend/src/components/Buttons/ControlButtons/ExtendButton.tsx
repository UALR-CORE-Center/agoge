import AddIcon from "@mui/icons-material/Add";
import {Button, CircularProgress, IconButton, Tooltip} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, { useState } from 'react';
import {WorkoutStates} from "../../../types/AgogeStates";
import {PubSub} from "../../../types/PubSub";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {ControlButtonProps, buttonController} from "./ControllerTypes"

interface ExtendButtonProps extends ControlButtonProps {
    additionalOnClick?: () => void;
}

export const ExtendButton: React.FC = (props: ExtendButtonProps) => {
    const {
        title,
        onClick,
        label,
        isDisabled,
        sx,
        data,
        iconButton,
        controlType,
        iconProps,
        row,
        additionalOnClick
    } = props;
    const {showModal} = useModal();
    const [loading, setLoading] = useState(false);
    const action = controlType === 'workout' ? String(PubSub.Actions.EXTEND_RUNTIME) : String(PubSub.Actions.RESET_EXPIRATION);
    const actionLabel =
        controlType === 'workout'
            ? (data?.hours
                ? `Extend workout by ${data.hours} hour${Number(data.hours) === 1 ? '' : 's'}`
                : 'Extend workout')
            : (data?.days
                ? `Extend expiration by ${data.days} day${Number(data.days) === 1 ? '' : 's'}`
                : 'Extend expiration');

    const handleOnClick = async () => {
        if (onClick) {
            return onClick();
        }

        setLoading(true);
        try {
            await buttonController(controlType, data, action);
            setLoading(false);
            showModal(SimpleSnackbar, {
                message: "Processing extend request",
                severity: "success",
                vertical: "top",
                autoHideDuration: 3000,
            });

            if (additionalOnClick) {
                additionalOnClick();
            }
        } catch (error) {
            console.error('Error processing extend request: ', error);
            showModal(SimpleSnackbar, {
                message: "Oops! Extend request failed",
                severity: 'error',
                vertical: 'top',
            });
        }
    };

    const isActionDisabled = (): boolean => {
        if (isDisabled || loading) {
            return true;
        } else {
            if (controlType === 'assignment') {
                return !!isDisabled;
            }
            else if (row?.state) {
                return row.state === WorkoutStates.DELETED;
            } else {
                return true;
            }
        }
    }

    return (
        <React.Fragment>
            {
                iconButton === true ?
                    <Tooltip title={title || actionLabel} placement="bottom" describeChild>
                        <span aria-busy={loading || undefined}>
                            <IconButton
                                onClick={handleOnClick}
                                disabled={isActionDisabled()}
                                size={iconProps?.size ?? "small"}
                                aria-label={iconProps?.label ?? actionLabel}
                                color={isActionDisabled() ? "inherit" : "info"}
                                type="button"
                            >
                                <AddIcon fontSize={iconProps?.fontSize ?? "inherit"} />
                            </IconButton>
                        </span>
                    </Tooltip> :
                    <Button
                        onClick={handleOnClick}
                        sx={sx}
                        disabled={isActionDisabled()}
                        endIcon={!loading && <AddIcon fontSize="large" />}
                        variant="contained"
                        color="info"
                        type="button"
                        aria-busy={loading || undefined}
                        aria-label={label}
                    >
                        {loading ? <CircularProgress size={24} color="inherit" /> : label}
                    </Button>
            }
        </React.Fragment>
    );
}