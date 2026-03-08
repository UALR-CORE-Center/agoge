import {Chip} from "@mui/material";
import React from "react";
import tagColors from "./tagColors";

export interface TagChipProps {
    chipType: string;
}

export const TagChip = ({ chipType }: TagChipProps) => {
    const chipStyle = tagColors[chipType] || { backgroundColor: 'gray', color: 'white' };
    return (
        <Chip
            label={chipType}
            variant={"outlined"}
            style={{
                backgroundColor: chipStyle.backgroundColor,
                color: chipStyle.color,
                borderRadius: "6px",
                padding: 0
            }}
            sx={{mx: "1px", my: "2px"}}
        />
    );
}