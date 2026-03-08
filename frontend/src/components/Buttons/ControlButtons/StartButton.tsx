import { PlayArrow, PlayArrowOutlined } from '@mui/icons-material';
import React from 'react';
import { ServerStates, WorkoutStates } from '../../../types/AgogeStates';
import { PubSub } from '../../../types/PubSub';
import { ActionButton } from './ActionButton';

function isStartDisabled({row, isDisabled, loading, controlType}: {
    row: any;
    isDisabled?: boolean;
    loading: boolean;
    controlType: string;
}) {
    if (isDisabled || loading) return true;

    if (!row?.state) return true;

    const blockingStatesServer = [
        ServerStates.RUNNING,
        ServerStates.STARTING,
        ServerStates.STOPPING
    ];
    const blockingStatesWorkout = [
        WorkoutStates.RUNNING,
        WorkoutStates.STARTING,
        WorkoutStates.STOPPING
    ];

    if (controlType === 'server') {
        return blockingStatesServer.includes(row.state);
    } else {
        return blockingStatesWorkout.includes(row.state);
    }
}

export const StartButton: React.FC<any> = (props) => {
    return (
        <ActionButton
            {...props}
            action={PubSub.Actions.START.toString()}
            successMessage="Processing start request"
            errorMessage="Start request failed!"
            color="success"
            IconComponent={PlayArrow}
            OutlinedIconComponent={PlayArrowOutlined}
            isActionDisabled={isStartDisabled}
        />
    );
};
