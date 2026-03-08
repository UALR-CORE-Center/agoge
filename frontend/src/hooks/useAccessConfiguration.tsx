import {useState, useEffect, useRef} from "react";
import {workoutService} from "../services/Workout/workout.service";

let sharedAccessConfig = {};
let accessSubscribers = [];

export const useAccessConfiguration = (buildId, userIp, safeToConfigure) => {
    const [configured, setConfigured] = useState(sharedAccessConfig[buildId]);
    const [error, setError] = useState<string>("");
    const [enabled, setEnabled] = useState<boolean>(true);
    const isMountedRef = useRef(false);

    const updateAccessSubscribers = (newValue: boolean) => {
        accessSubscribers.forEach((cb) => cb(buildId, newValue));
    }

    const checkAccess = async () => {
        try {
            const resp = await workoutService.configure(buildId, userIp);
            if (isMountedRef.current) {
                sharedAccessConfig[buildId] = true;
                setConfigured(true);
                updateAccessSubscribers(true);
            }
        } catch (err) {
            if (err.status === 409) {
                sharedAccessConfig[buildId] = true;
                setError("");
                setConfigured(true);
                updateAccessSubscribers(true);
            } else if (err.status === 405) {
                sharedAccessConfig[buildId] = true;
                setError("");
                setConfigured(true);
                setEnabled(false);
                updateAccessSubscribers(true)
            } else {
                sharedAccessConfig[buildId] = false;
                setConfigured(false);
                setError(String(err));
                updateAccessSubscribers(false);
            }
        }
    };

    useEffect(() => {
        isMountedRef.current = true;

        if (sharedAccessConfig[buildId] !== undefined) {
            setConfigured(sharedAccessConfig[buildId]);
        } else {
            if (safeToConfigure) {
                checkAccess();
            }
        }

        const subscriber = (id, status) => {
            if (id === buildId) setConfigured(status);
        };
        accessSubscribers.push(subscriber);

        return () => {
            isMountedRef.current = false;
            accessSubscribers = accessSubscribers.filter((cb) => cb !== subscriber);
        };
    }, [buildId, userIp, safeToConfigure]);

    return { configured, error, checkAccess, enabled };
}