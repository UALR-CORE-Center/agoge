import EditNoteIcon from '@mui/icons-material/EditNote';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import FlagIcon from '@mui/icons-material/Flag';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import HourglassTopIcon from '@mui/icons-material/HourglassTop';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SportsScoreIcon from '@mui/icons-material/SportsScore';
import { ChipProps } from '@mui/material/Chip';
import React from 'react';
import {CtfStates} from '../../../services/Ctf/ctf.model';
import {WorkoutStates, ServerStates, ImageStates} from '../../../types/AgogeStates';

type ChipColor = ChipProps['color'];

export interface StatusInfo {
    text: string;
    color: ChipColor;
}

export const WorkoutStateMapping: { [key in WorkoutStates]?: StatusInfo } = {
    [WorkoutStates.NOT_BUILT]: { text: 'Not Built', color: 'neutral' },
    [WorkoutStates.RUNNING]:   { text: 'Running',   color: 'success' },
    [WorkoutStates.STOPPING]:  { text: 'Stopping',  color: 'warning' },
    [WorkoutStates.READY]:     { text: 'Stopped',     color: 'ready' },
    [WorkoutStates.STARTING]:  { text: 'Starting',  color: 'warning' },
    [WorkoutStates.EXPIRED]:   { text: 'Expired',   color: 'neutral' },
    [WorkoutStates.BROKEN]:    { text: 'Broken',    color: 'error' },
    [WorkoutStates.DELETED]:   { text: 'Deleted',   color: 'secondary' },
};

export const ServerStateMapping: { [key in ServerStates]?: StatusInfo } = {
    [ServerStates.START]: { text: 'Not Built', color: 'neutral' },
    [ServerStates.RUNNING]: { text: 'Running', color: 'success' },
    [ServerStates.STOPPED]: { text: 'Stopped', color: 'ready' },
    [ServerStates.BROKEN]: { text: 'Broken', color: 'error' },
}

export const ImageStateMapping: { [key in ImageStates]?: StatusInfo } = {
    [ImageStates.CHECKED_IN]: { text: 'Checked In', color: 'success' },
    [ImageStates.CHECKED_OUT]: { text: 'Checked Out', color: 'error' },
}

// For all other states "WORKING"
export function resolveStatus(
    type: "workout" | "server" | "image",
    state: WorkoutStates | ServerStates | ImageStates
): StatusInfo {
    if (type === "server") {
        return ServerStateMapping[state as ServerStates] ?? { text: 'Working', color: 'neutral' };
    } else if (type === "image") {
        return ImageStateMapping[state as ImageStates] ?? { text: 'Working', color: 'neutral' };
    }
    return WorkoutStateMapping[state as WorkoutStates] ?? { text: 'Working', color: 'neutral' };
}

export interface CtfStatusInfo extends StatusInfo {
    icon: React.ReactElement;
}

type CtfStateValue = typeof CtfStates[keyof typeof CtfStates];

// Every CtfStates value is mapped (the Record type enforces it). The icon carries the meaning
// alongside the colour, so the chip still reads correctly without colour vision.
export const CtfStateMapping: Record<CtfStateValue, CtfStatusInfo> = {
    [CtfStates.DRAFT]:    { text: 'Draft',    color: 'neutral', icon: <EditNoteIcon /> },
    [CtfStates.ARMING]:   { text: 'Arming',   color: 'warning', icon: <HourglassTopIcon /> },
    [CtfStates.ARMED]:    { text: 'Armed',    color: 'ready',   icon: <FlagIcon /> },
    [CtfStates.RUNNING]:  { text: 'Running',  color: 'success', icon: <PlayArrowIcon /> },
    [CtfStates.PAUSED]:   { text: 'Paused',   color: 'warning', icon: <PauseIcon /> },
    [CtfStates.ENDED]:    { text: 'Ended',    color: 'info',    icon: <SportsScoreIcon /> },
    [CtfStates.ARCHIVED]: { text: 'Archived', color: 'neutral', icon: <Inventory2Icon /> },
    [CtfStates.BROKEN]:   { text: 'Broken',   color: 'error',   icon: <ErrorOutlineIcon /> },
};

// A state this build does not know (e.g. the API added one) reads "Unknown" rather than
// being mislabelled as a known state.
export function resolveCtfStatus(state: number): CtfStatusInfo {
    return CtfStateMapping[state as CtfStateValue]
        ?? { text: 'Unknown', color: 'neutral', icon: <HelpOutlineIcon /> };
}
