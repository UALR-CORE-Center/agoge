import {Box, Tooltip} from "@mui/material";
import Chip from "@mui/material/Chip";
import React, {useEffect, useRef, useState} from "react";
import {AppUiObjectNames} from "../../../types/AppObjectNames";
import {LoadingState} from "./LoadingState";


interface StateInfoProps {
    label: string;
    context?: AppUiObjectNames.UNIT | AppUiObjectNames.WORKOUT;
    variant?: "outlined" | "filled" | undefined
    color?:  "success" | "error" | "warning" | "info" | "primary" | "secondary" | "default" | undefined;
    loading?: boolean;
}

interface StateAnnouncementProps {
    label: string;
    // Object name spoken before the status, e.g. "Workout" or "CTF event".
    context: string;
}

// Visually hidden live region: announces "<context> status is now <label>" when label changes
// (not on first render), then clears so a later change back to the same label is announced again.
export const StateAnnouncement: React.FC<StateAnnouncementProps> = ({label, context}) => {
    const [liveMsg, setLiveMsg] = useState("");
    const prevLabel = useRef(label);

    useEffect(() => {
        if (prevLabel.current !== label) {
            setLiveMsg(`${context} status is now ${label}`);
            prevLabel.current = label;
            const t = setTimeout(() => setLiveMsg(""), 800);
            return () => clearTimeout(t);
        }
    }, [label, context]);

    return (
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
    );
}

export const StateInfo: React.FC<StateInfoProps> = (props) => {
    const context = props.context || AppUiObjectNames.WORKOUT

    return (
        <>
            <StateAnnouncement label={props.label} context={context} />
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