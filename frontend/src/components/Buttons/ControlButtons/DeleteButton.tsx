import {DeleteOutlined} from "@mui/icons-material";
import DeleteIcon from "@mui/icons-material/Delete";
import {Button, CircularProgress, IconButton, Tooltip} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, { useState } from 'react';
import {specificationService} from "../../../services/Specification/specification.service";
import ConfirmationDialog from "../../Common/Dialogs/ConfirmationDialog/Confirmation";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {ControlButtonProps} from "./ControllerTypes"

export const DeleteButton: React.FC = (props: ControlButtonProps) => {
    const {
        title,
        label,
        isDisabled,
        sx,
        iconButton,
        iconProps,
        row,
        controlType,
        onSuccess
    } = props;
    const {showModal} = useModal();
    const [loading, setLoading] = useState(false);
    const [openDialog, setOpenDialog] = useState(false);

    const handleOnSuccess = () => {
        showModal(SimpleSnackbar, {
            message: "Processing delete request...",
            severity: 'success',
        });

        // Process any additional actions upon success such as table cleanup
        if (onSuccess) onSuccess();
    }

    const handleConfirmDelete = async () => {
        setOpenDialog(false);
        setLoading(true);
        try {
            if (controlType === 'specification') {
                await specificationService.del(String(row.id));
            }

            handleOnSuccess();
        } catch (error) {
            console.error('Error performing delete action:', error);
            showModal(SimpleSnackbar, {
                message: "Delete request failed. Must've been the wind ...",
                severity: 'error',
            });
        } finally {
            setLoading(false);
        }
    };

    const isActionDisabled = (): boolean => { return isDisabled || loading; }

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
                                aria-label={iconProps?.label ? iconProps.label : "delete button"}
                                loading={loading}
                                color={isActionDisabled() ? 'inherit' : 'error'}
                            >
                                <DeleteIcon fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"}/>
                            </IconButton>
                        </span>
                    </Tooltip> :
                    <Button
                        onClick={() => setOpenDialog(true)}
                        sx={sx}
                        disabled={isActionDisabled()}
                        startIcon={!loading && <DeleteOutlined fontSize="large"/>}
                        variant="outlined"
                        color={"error"}
                    >
                        {loading ? <CircularProgress size={24} color={"info"}/> : label}
                    </Button>
            }
            <ConfirmationDialog
                open={openDialog}
                action={"delete"}
                onClose={() => setOpenDialog(false)}
                handleConfirm={handleConfirmDelete}
                expectedText={row.id}
                loading={false}
            />
        </>
    );
}