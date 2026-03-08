import {CircularProgress} from "@mui/material";
import Chip from "@mui/material/Chip";
import React from "react";

interface LoadingStateProps {
    label: string;
    variant?: "outlined" | "filled" | undefined
    color?:  "success" | "error" | "warning" | "info" | "primary" | "secondary" | "default" | undefined;
    width?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = (props) => {
    return (
        <>
            <Chip
                label={props.label}
                variant={props.variant || "outlined"}
                color={props.color || "info"}
                icon={
                    <CircularProgress
                        size={24}
                        sx={{ marginRight: 2, color: 'secondary.main' }}
                    />
                }
                sx={{
                    borderRadius: "4px",
                    '.MuiChip-label': {
                        fontSize: 18,
                        letterSpacing: 2
                    },
                    p: 2,
                    width: props.width
                }}
            />
        </>
    );
}