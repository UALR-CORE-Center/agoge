import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Box, IconButton, Typography, Tooltip } from "@mui/material";
import React, { useEffect, useRef, useState } from "react";
import { useClipboard } from "../../../hooks/useClipboard";

interface UserDetailFieldProps {
    label: string;
    value: string;
}

export const UserDetailField: React.FC<UserDetailFieldProps> = ({ label, value }) => {
    const { copy } = useClipboard();
    const [open, setOpen] = useState(false);
    const leaveTimer = useRef<number | null>(null);

    const clearLeave = () => {
        if (leaveTimer.current) window.clearTimeout(leaveTimer.current);
        leaveTimer.current = null;
    };

    const handleEnter = () => {
        clearLeave();
        setOpen(true);
    };

    const handleLeave = () => {
        clearLeave();
        leaveTimer.current = window.setTimeout(() => setOpen(false), 200);
    };
    // Since Detail fields are in a Modal, to comply with WCAG and exit tooltips with esc without closing the modal,
    // we control it here now just for the tooltips on the copy X tooltip.
    // Close tooltip on Esc and prevent the Modal from seeing it
    useEffect(() => {
        if (!open || typeof document === "undefined") return;
        const onDocKeyDownCapture = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setOpen(false);
                e.preventDefault();
                if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
                e.stopPropagation();
            }
        };
        document.addEventListener("keydown", onDocKeyDownCapture, true); // capture phase
        return () => document.removeEventListener("keydown", onDocKeyDownCapture, true);
    }, [open]);

    // Clear any pending timers on unmount
    useEffect(() => () => clearLeave(), []);

    return (
        <Box sx={{ mt: 2 }}>
            <Typography>{label}:</Typography>
            <Box
                component="section"
                sx={{
                    p: 1,
                    border: "1px solid grey",
                    borderRadius: "4px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                }}
            >
                <Typography sx={{ wordBreak: "break-all" }}>
                    <em>{value || "—"}</em>
                </Typography>

                <Tooltip
                    title={`Copy ${label}`}
                    describeChild
                    open={open}
                    disableHoverListener
                    disableFocusListener
                    disableTouchListener
                    slotProps={{
                        tooltip: {
                            onMouseEnter: handleEnter,
                            onMouseLeave: handleLeave,
                            sx: { pointerEvents: "auto" },
                        },
                    }}
                    arrow
                >
                    <IconButton
                        aria-label={`Copy ${label}`}
                        size="small"
                        onMouseEnter={handleEnter}
                        onMouseLeave={handleLeave}
                        onFocus={handleEnter}
                        onBlur={() => setOpen(false)}
                        onClick={() => value && copy(value)}
                    >
                        <ContentCopyIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </Box>
        </Box>
    );
};