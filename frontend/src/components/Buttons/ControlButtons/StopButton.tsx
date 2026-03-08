import { Stop, StopOutlined } from '@mui/icons-material';
import React from 'react';
import { ServerStates, WorkoutStates } from '../../../types/AgogeStates';
import { PubSub } from '../../../types/PubSub';
import { ActionButton } from './ActionButton';

function isStopDisabled({row, isDisabled, loading, controlType}: {
    row: any;
    isDisabled?: boolean;
    loading: boolean;
    controlType: string;
}) {
    if (isDisabled || loading) return true;
    if (!row?.state) return true;

    if (controlType === 'server') {
        const disableStatesServer = [
            ServerStates.READY,
            ServerStates.STOPPING,
            ServerStates.STOPPED,
            ServerStates.STARTING
        ];
        return disableStatesServer.includes(row.state);
    } else {
        const disableStatesWorkout = [
            WorkoutStates.READY,
            WorkoutStates.STOPPING,
            WorkoutStates.STARTING,
        ];
        return disableStatesWorkout.includes(row.state);
    }
}

export const StopButton: React.FC<any> = (props) => {
    return (
        <ActionButton
            {...props}
            action={PubSub.Actions.STOP.toString()}
            successMessage="Processing stop request"
            errorMessage="Stop request failed!"
            color="error"
            IconComponent={Stop}
            OutlinedIconComponent={StopOutlined}
            isActionDisabled={isStopDisabled}
        />
    );
};
