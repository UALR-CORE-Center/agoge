import {WorkoutStates, ServerStates, ImageStates} from '../../../types/AgogeStates';
import { ChipProps } from '@mui/material/Chip';

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