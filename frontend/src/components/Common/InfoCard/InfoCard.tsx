import React from 'react';
import {UnitInfoCard} from "./UnitInfoCard";
import {WorkoutInfoCard} from "./WorkoutInfoCard";

interface InfoCardProps {
    buildId?: string;
    buildType: "unit" | "workout";
    data: any;
    isLoading?: boolean;
}

export const InfoCard: React.FC<InfoCardProps> = (props) => {
    if (props.buildType == 'unit') {
        return (
            <UnitInfoCard
                data={props.data}
                isLoading={props.isLoading}
            />
        )
    } else if (props.buildType == 'workout') {
        return (
            <WorkoutInfoCard
                buildId={props.buildId!}
                data={props.data}
                isLoading={!!props.isLoading}
            />
        )
    } else {
        return null
    }
}
