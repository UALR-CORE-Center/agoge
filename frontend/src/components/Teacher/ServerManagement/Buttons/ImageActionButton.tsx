import {IconButton, Tooltip} from "@mui/material";
import React from "react";


interface Props {
    title: string;
    onClick: () => void;
    Icon: React.ElementType;
    iconProps: {
        label: string;
        size?: "small" | "large";
        fontSize?: "small" | "medium" | "large" | "inherit",
        color: "info" | "error" | "warning" | "success"
    }
    sx?: any;
    isDisabled: boolean;
    loading: boolean;
}

export const ImageActionButton: React.FC<Props> = (props) => {
    const {onClick, title, iconProps, Icon, isDisabled, loading} = props;

    const handleOnClick = () => {
        if (onClick) onClick();
    }

    return (
        <Tooltip title={title} placement={"bottom"}>
            <span>
                <IconButton
                    onClick={handleOnClick}
                    size={iconProps?.size ? iconProps.size : "small"}
                    aria-label={iconProps.label}
                    disabled={isDisabled}
                    loading={loading ? loading : undefined}
                    color={isDisabled ? "inherit" : iconProps.color}
                >
                    <Icon fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"} />
                </IconButton>
            </span>
        </Tooltip>
    );
}