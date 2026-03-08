import {EditOutlined} from "@mui/icons-material";
import {IconButton, Tooltip} from "@mui/material";
import React from "react";
import {AgogeImage} from "../../../../services/Server/image.model";


interface Props {
    title: string;
    row: AgogeImage;
    onClick: (row: AgogeImage) => void;
    iconProps?: {
        label: string;
        size?: "small" | "large";
        fontSize: "small" | "medium" | "large" | "inherit"
    }
    sx?: any;
}

export const EditImageButton: React.FC<Props> = (props) => {
    const {row, onClick, title, iconProps} = props;

    const handleOnClick = () => {
        if (onClick) {
            onClick(row)
        }
    }

    return (
        <Tooltip title={title} placement={"bottom"}>
            <span>
                <IconButton
                    onClick={handleOnClick}
                    size={iconProps?.size ? iconProps.size : "small"}
                    aria-label={iconProps?.label ? iconProps.label : "Edit template server image button"}
                >
                    <EditOutlined
                        fontSize={iconProps?.fontSize ? iconProps.fontSize : "inherit"}
                        color={"info"}
                    />
                </IconButton>
            </span>
        </Tooltip>
    )
}