/*
* ActionButton is a generic component to handle simple actions that would require
* triggering a web request on click. Not ideal for more complex situations.
* */
import {
    IconButton,
    Button,
    CircularProgress,
    Tooltip
} from '@mui/material';
import { useModal } from 'mui-modal-provider';
import React, { useState } from 'react';
import SimpleSnackbar from '../../Common/SnackBar/SnackBar';
import {buttonController, ControlButtonProps} from './ControllerTypes';

export interface ActionButtonProps extends ControlButtonProps{
    action: string;
    successMessage: string;
    errorMessage: string;
    color: 'error' | 'success' | 'warning' | 'info' | 'primary' | 'secondary';
    IconComponent: React.ElementType;
    OutlinedIconComponent: React.ElementType;
    isActionDisabled: (opts: {
        row: any;
        isDisabled?: boolean;
        loading: boolean;
        controlType: string;
    }) => boolean;


    onActionPerformed?: (action: string) => void;
}

export const ActionButton: React.FC<ActionButtonProps> = (props) => {
    const {
        title,
        onClick,
        label,
        isDisabled,
        sx,
        data,
        iconButton,
        iconProps,
        row,
        controlType,
        action,
        successMessage,
        errorMessage,
        color,
        IconComponent,
        OutlinedIconComponent,
        isActionDisabled,
        onActionPerformed
    } = props;

    const { showModal } = useModal();
    const [loading, setLoading] = useState(false);

    const handleOnClick = async () => {
        if (onClick) {
            return onClick();
        }

        setLoading(true);
        try {
            await buttonController(controlType, data, action);
            showModal(SimpleSnackbar, {
                message: successMessage,
                severity: 'success',
            });

            if (onActionPerformed) onActionPerformed(action);
        } catch (error) {
            console.error(`Error performing ${action}: `, error);
            showModal(SimpleSnackbar, {
                message: errorMessage,
                severity: 'error',
            });
        } finally {
            setLoading(false);
        }
    };

    const disabled = isActionDisabled({
        row,
        isDisabled,
        loading,
        controlType,
    });

    return iconButton ? (
        <Tooltip title={title} placement="bottom" describeChild>
            <span aria-busy={loading || undefined}>
                <IconButton
                    onClick={handleOnClick}
                    disabled={disabled}
                    size={iconProps?.size || 'small'}
                >
                    {!loading ? (
                        <IconComponent
                            fontSize={iconProps?.fontSize || 'inherit'}
                            color={disabled ? 'disabled' : color}
                        />
                    ) : (
                        <CircularProgress size={20} color="info" />
                    )}
                </IconButton>
            </span>
        </Tooltip>
    ) : (
        <Button
            onClick={handleOnClick}
            sx={sx}
            disabled={disabled}
            startIcon={!loading && <OutlinedIconComponent fontSize="large" />}
            variant="outlined"
            color={color}
            type="button"
            aria-busy={loading || undefined}
        >
            {loading ? <CircularProgress size={24} color="inherit" /> : label}
        </Button>
    );
};
