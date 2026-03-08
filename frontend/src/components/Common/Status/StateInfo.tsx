import React, {useEffect, useRef, useState} from "react";
import Chip from "@mui/material/Chip";
import {Box, Tooltip} from "@mui/material";
import {AppUiObjectNames} from "../../../types/AppObjectNames";
import {LoadingState} from "./LoadingState";


interface StateInfoProps {
    label: string;
    context?: AppUiObjectNames.UNIT | AppUiObjectNames.WORKOUT;
    variant?: "outlined" | "filled" | undefined
    color?:  "success" | "error" | "warning" | "info" | "primary" | "secondary" | "default" | undefined;
    loading?: boolean;
}

export const StateInfo: React.FC<StateInfoProps> = (props) => {
    const context = props.context || AppUiObjectNames.WORKOUT

    const [liveMsg, setLiveMsg] = useState("");
    const prevLabel = useRef(props.label);

    useEffect(() => {
        if (prevLabel.current !== props.label) {
            setLiveMsg(`${context} status is now ${props.label}`);
            prevLabel.current = props.label;
            const t = setTimeout(() => setLiveMsg(""), 800);
            return () => clearTimeout(t);
        }
    }, [props.label, context]);

    return (
        <>
            <Box
                aria-live="polite"
                role="status"
                aria-atomic="true"
                sx={{
                    position: "absolute",
                    width: 1,
                    height: 1,
                    p: 0,
                    m: -1,
                    overflow: "hidden",
                    clip: "rect(0 0 0 0)",
                    whiteSpace: "nowrap",
                    border: 0,
                }}
            >
                {liveMsg}
            </Box>
            <Tooltip
                title={`Status: ${context} ${props.label}`}
                describeChild
                leaveDelay={200}
                arrow
                slotProps={{
                    popper: {
                        modifiers: [
                            {
                                name: 'offset',
                                options: {
                                    offset: [0, -8],
                                },
                            },
                        ],
                    },
                }}
            >
                {props.loading ? (
                    <LoadingState
                        label={props.label.toUpperCase()}
                        variant={props.variant || "outlined"}
                        color={props.color || "info"}
                        width={"100%"}
                    />
                ) : (
                    <Chip
                        label={props.label.toUpperCase()}
                        variant={props.variant || "outlined"}
                        color={props.color || "info"}
                        sx={{
                            borderRadius: 1,
                            '.MuiChip-label': {
                                fontSize: 18,
                                letterSpacing: 2
                            },
                            width: "100%",
                        }}
                        size={"medium"}
                    />
                )}

            </Tooltip>
        </>
    );
}