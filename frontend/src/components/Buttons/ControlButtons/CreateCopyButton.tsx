import {FileCopy, FileCopyOutlined} from "@mui/icons-material";
import {Button, CircularProgress, IconButton, Tooltip} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, { useState } from 'react';
import {useNavigate} from "react-router-dom";
import {URL_TEACHER_SPECIFICATION_EDIT} from "../../../router/urls";
import {SpecificationEditId} from "../../../services/Specification/specificationEdit.model";
import {specificationEditService} from "../../../services/Specification/specificationEdit.service";
import {SpecificationStates} from "../../../types/AgogeStates";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {ControlButtonProps} from "./ControllerTypes"

export const CreateCopyButton: React.FC = (props: ControlButtonProps) => {
    const {
        title,
        label,
        isDisabled,
        sx,
        iconButton,
        iconProps,
        row,
    } = props;
    const {showModal} = useModal();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const specId = row.id;

    const navigateToEdit = (spec: SpecificationEditId) => {
        if (spec?.build_id) {
            navigate(`${URL_TEACHER_SPECIFICATION_EDIT}/${spec.build_id}`);
        } else {
            console.log("Received response but could not process data", spec);
        }
    };

    const handleOnClick = async () => {
        setLoading(true);
        showModal(SimpleSnackbar, {
            message: "Copying specification ...",
            severity: "info",
            autoHideDuration: 5000,
        });

        try {
            const newSpecId = await specificationEditService.create(SpecificationStates.COPY, specId);
            navigateToEdit(newSpecId);
        } catch (error) {
            console.log(error);
            showModal(SimpleSnackbar, {
                message: "Failed to create copy of specification. Ran out of Post-it notes...",
                severity: "error",
            });
        } finally {
            setLoading(false);
        }
    }

    const isActionDisabled = (): boolean => { return isDisabled || loading; }

    return (
        <React.Fragment>
            {
                iconButton === true ?
                    <Tooltip title={title} placement={"bottom"}>
                        <span>
                            <IconButton
                                onClick={() => handleOnClick()}
                                disabled={isActionDisabled()}
                                size={iconProps?.size ? iconProps.size : "small"}
                                aria-label={iconProps?.label ? iconProps.label : "copy button"}
                                loading={loading}
                                color={isActionDisabled() ? 'inherit' : 'info'}
                            >
                                <FileCopy fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"}/>
                            </IconButton>
                        </span>
                    </Tooltip> :
                    <Button
                        onClick={() => handleOnClick()}
                        sx={sx}
                        disabled={isActionDisabled()}
                        startIcon={!loading && <FileCopyOutlined fontSize="large"/>}
                        variant="outlined"
                        color={"info"}
                    >
                        {loading ? <CircularProgress size={24} color={"info"}/> : label}
                    </Button>
            }
        </React.Fragment>
    );
}