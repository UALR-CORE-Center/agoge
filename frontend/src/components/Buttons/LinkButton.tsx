import {Button} from "@mui/material";
import React from "react";
import {Link} from "react-router-dom";

interface ButtonProps {
    variant?: "contained" | "outlined";
    buildId: string;
    endpoint: string;
    target?: "_blank" | "_self" | "_parent" | "_top" | string | undefined;
    color?: "primary" | "inherit" | "secondary" | "success" | "error" | "info" | "warning" | undefined;
    endIcon?: React.ReactNode;
    startIcon?: React.ReactNode;
    label?: string;
    width?: string;
    height?: string;
    fontSize?: string;
}

export const LinkButton: React.FC<ButtonProps> = (props) => {
    const url = `${props.endpoint}/${props.buildId}`;
    const btnWidth = props.width ? props.width : '120px';
    const btnHeight = props.height ? props.height : '36px';
    const btnFontSize = props.fontSize ? props.fontSize : '14px';

    return (
        <Button
            component={Link}
            to={url}
            variant={props.variant ? props.variant : "contained"}
            color={props.color ? props.color : 'primary'}
            style={{ width: btnWidth, height: btnHeight, fontSize: btnFontSize }}
            target={props.target ?? "_blank"}
            endIcon={props?.endIcon}
            startIcon={props?.startIcon}
            aria-label={`Link to ${url}`}
        >
            {props.label ? props.label : props.buildId}
        </Button>
    );
};
