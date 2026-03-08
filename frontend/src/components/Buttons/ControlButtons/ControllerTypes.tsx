import {imageService} from "../../../services/Server/image.service";
import {unitService} from "../../../services/Unit/unit.service";
import {workoutService} from "../../../services/Workout/workout.service";

export type ControlType = "server" | "assignment" | "workout" | "specification"

export interface ControlButtonProps {
    title: string;
    label: string;
    onClick?: () => void;
    onSuccess?: () => void;
    isDisabled?: boolean;
    sx?: any;
    controlType: ControlType;
    data?: any;
    days?: number;
    iconButton?: boolean;
    iconProps?: {
        label: string;
        size?: "small" | "large";
        fontSize: "small" | "medium" | "large" | "inherit"
    }
    row?: any;
}

export const buttonController = async (
    controlType: ControlType,
    data: any,
    action: string
) => {
    try {
        switch (controlType) {
            case 'server':
                await imageService.post_action(data, action);
                break;
            case 'assignment':
                if (data?.days !== undefined){
                    await unitService.put_action(data.id, action, data.days);
                } else {
                    await unitService.put_action(data, action);
                }
                break;
            case 'workout':
                if ( data?.duration !== undefined ){
                    await workoutService.put_action(data.id, action, data.duration);
                } else {
                    await workoutService.put_action(data.id, action);
                }
                break;
            default:
                break;
        }
    } catch (error) {
        console.error('Error', error);
    }
};