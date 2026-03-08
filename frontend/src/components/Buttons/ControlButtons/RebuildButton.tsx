import {Handyman, HandymanOutlined} from "@mui/icons-material";
import {Button, CircularProgress, IconButton, Tooltip} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, { useState } from 'react';
import {workoutService} from "../../../services/Workout/workout.service";
import {PubSub} from "../../../types/PubSub";
import ConfirmationDialog from "../../Common/Dialogs/ConfirmationDialog/Confirmation";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {ControlButtonProps} from "./ControllerTypes"

export const RebuildButton: React.FC = (props: ControlButtonProps) => {
    const {
        title,
        label,
        isDisabled,
        sx,
        iconButton,
        iconProps,
        row
    } = props;
    const {showModal} = useModal();
    const [loading, setLoading] = useState(false);
    const [openDialog, setOpenDialog] = useState(false);

    
    const handleConfirmNuke = async () => {
        setOpenDialog(false);
        setLoading(true)
        try {
            await workoutService.put_action(String(row.id), String(PubSub.Actions.NUKE));
            showModal(SimpleSnackbar, {
                message: "Processing rebuild request...",
                severity: 'success',
            });
        } catch (error) {
            console.error('Error performing rebuild action:', error);
            showModal(SimpleSnackbar, {
                message: "Oops! Rebuild request failed. Is there a chip shortage?",
                severity: 'error',
            });
        } finally {
            setLoading(false);
        }
    };

    const isActionDisabled = (): boolean => {
        return isDisabled || loading;
    }

    return (
        <>
            {
                iconButton === true ?
                    <Tooltip title={title} placement={"bottom"}>
                        <span>
                            <IconButton
                                onClick={() => setOpenDialog(true)}
                                disabled={isActionDisabled()}
                                size={iconProps?.size ? iconProps.size : "small"}
                                aria-label={iconProps?.label ? iconProps.label : "rebuild button"}
                                loading={loading}
                                color={isActionDisabled() ? "inherit" : "secondary"}
                            >
                                <Handyman fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"}/>
                            </IconButton>
                        </span>
                    </Tooltip> :
                    <Button
                        onClick={() => setOpenDialog(true)}
                        sx={sx}
                        disabled={isActionDisabled()}
                        startIcon={!loading && <HandymanOutlined fontSize="large"/>}
                        variant="outlined"
                        color={"secondary"}
                    >
                        {loading ? <CircularProgress size={24} color={"info"}/> : label}
                    </Button>
            }
            <ConfirmationDialog
                open={openDialog}
                action={"rebuild"}
                onClose={() => setOpenDialog(false)}
                handleConfirm={handleConfirmNuke}
                expectedText={row.id}
                loading={false}
            />
        </>
    );
}