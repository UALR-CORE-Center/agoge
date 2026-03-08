import React, { useState, useEffect } from "react";
import Chip from "@mui/material/Chip";
import { WorkoutStates, ImageStates, ServerStates } from "../../../types/AgogeStates";

interface StateChipProps {
    state: number;
    stateType: "workout" | "image" | "server";
    size: "small" | "medium"
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

interface ChipColors {
    [key: number]: [string, string];
}

const chipColors: ChipColors = {
    1:  ["#7A7A7A", "black"],
    2:  ["#938C00", "black"],
    50: ["#388E3C", "black"],
    53: ["#398ED3", "black"],
    62: ["#FF1744", "black"],
    72: ["#6A6A6A", "white"]
};

const StateChip: React.FC<StateChipProps> = (
    { state, stateType, size, onChange }
) => {
    const [states, setStates] = useState<{ [key: number]: string }>({});

    useEffect(() => {
        if (stateType === "server") {
            setStates(ServerStates);
        } else if (stateType === "image") {
            setStates(ImageStates);
        } else {
            setStates(WorkoutStates);
        }
    }, [stateType]);

    const renderChip = () => {
        if (state in states) {
            let label = state === 53 ? "Stopped" : states[state];
            //let label = states[state];
            let chipColor = chipColors[state] || chipColors[2];
            return (
                <Chip
                    label={label}
                    variant={"filled"}
                    size={size}
                    style={{
                        backgroundColor: chipColor[0],
                        color: chipColor[1],
                        textOverflow: "ellipsis"
                    }}
                    onChange={onChange}
                />
            );
        }
        return (
            <Chip
                label="Working"
                variant={"filled"}
                size={size}
                style={{
                    backgroundColor: chipColors[2][0],
                    color: chipColors[2][1]
                }}
                onChange={onChange}
            />
        );
    };

    return renderChip();
}

export default StateChip;
