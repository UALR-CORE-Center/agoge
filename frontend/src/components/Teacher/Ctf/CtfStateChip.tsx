import {SxProps, Theme} from "@mui/system";
import React from "react";
import {StateAnnouncement} from "../../Common/Status/StateInfo";
import {resolveCtfStatus} from "../../Common/Status/StateMapping";
import StatusBadge from "../../Common/Status/StatusBadge";

interface CtfStateChipProps {
    state: number;
    sx?: SxProps<Theme>;
}

const CtfStateChip: React.FC<CtfStateChipProps> = ({state, sx}) => {
    const status = resolveCtfStatus(state);

    return (
        <>
            {/* Polling updates `state`; the live region tells screen-reader users when it changes. */}
            <StateAnnouncement label={status.text} context="CTF event" />
            <StatusBadge color={status.color} label={status.text} icon={status.icon} sx={sx} />
        </>
    );
};

export default CtfStateChip;
