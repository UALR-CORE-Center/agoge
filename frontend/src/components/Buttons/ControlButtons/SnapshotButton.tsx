import {AlbumOutlined, PhotoCamera} from "@mui/icons-material";
import {Button, CircularProgress, IconButton, Tooltip} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, { useState } from 'react';
import {ImageStates, WorkoutStates} from "../../../types/AgogeStates";
import SnapshotDialog from "../../Common/Dialogs/SnapshotDialog/SnapshotDialog";
import {ControlButtonProps} from "./ControllerTypes"


export const SnapshotButton: React.FC = (props: ControlButtonProps) => {
    const {
        title,
        label,
        isDisabled,
        sx,
        iconButton,
        iconProps,
        controlType,
        row
    } = props;
    const [loading, setLoading] = useState(false);
    const courseObject = controlType === "server" ? "templateServer" : "workout";

    const {showModal} = useModal();

    const blockingWorkoutStates = [
        WorkoutStates.NOT_BUILT,
        WorkoutStates.DELETED,
        WorkoutStates.EXPIRED
    ]

    const blockingImageStates = [
        ImageStates.CHECKED_IN
    ]

    const isActionDisabled = (): boolean => {
        if (isDisabled || loading) {
            return true;
        } else if (row?.state) {
            if (controlType === 'workout'){
                if (blockingWorkoutStates.includes(row.state)) {
                    return true;
                }
            } else if (controlType === 'server') {
                if (blockingImageStates.includes(row.state)) {
                    return true;
                }
            }
        }
        return false;
    }

    const openDialog = () => {
        showModal(SnapshotDialog, {row: row, courseObject: courseObject})
    }

    return (
        <>
            {
                iconButton === true ?
                    <Tooltip title={title} placement={"bottom"}>
                        <span>
                            <IconButton
                                onClick={() => openDialog()}
                                disabled={isActionDisabled()}
                                size={iconProps?.size ? iconProps.size : "small"}
                                aria-label={iconProps?.label ? iconProps.label : "manage snapshots button"}
                                color={isActionDisabled() ? "inherit" : "info"}
                            >
                                <PhotoCamera fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"} />
                            </IconButton>
                        </span>
                    </Tooltip> :
                    <Button
                        onClick={() => openDialog()}
                        sx={sx}
                        disabled={isActionDisabled()}
                        startIcon={!loading && <AlbumOutlined fontSize="large"/>}
                        variant="outlined"
                        color={"info"}
                    >
                        {loading ? <CircularProgress size={24} color={"info"}/> : label}
                    </Button>
            }
        </>
    );
}