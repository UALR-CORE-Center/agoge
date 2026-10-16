import {CtfStateResponse, CtfStates} from "../../../services/Ctf/ctf.model";

type ClockFields = Pick<CtfStateResponse, 'state' | 'ends_at' | 'paused_at'>;

// Mirrors CtfScoring._remaining_seconds (api/core/ctf/scoring.py) so the dashboard and the student board agree.
export const remainingSeconds = (event: ClockFields, nowSeconds: number): number | null => {
    if (event.ends_at === null) {
        return null;
    }
    if (event.state === CtfStates.ENDED) {
        return 0;
    }
    // While paused the clock is held; resume moves ends_at forward by the paused duration.
    const now = event.state === CtfStates.PAUSED && event.paused_at ? event.paused_at : nowSeconds;
    return Math.max(0, Math.ceil(event.ends_at - now));
};

export const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return [hours, minutes, secs].map(part => String(part).padStart(2, '0')).join(':');
};
