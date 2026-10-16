import {useCallback, useEffect, useRef, useState} from "react";
import {usePolling} from "../../../hooks/usePolling";
import {CtfStudentBoardResponse} from "../../../services/Ctf/ctf.model";
import {ctfBoardService} from "../../../services/Ctf/ctf.service";

// PRD performance budget: an enrolled student's page polls its board every 15 s.
export const BOARD_POLL_INTERVAL_MS = 15000;

/**
 * Reads the caller's CTF board for a workout. The first poll doubles as the on-mount read; once the API answers
 * `enrolled: false` polling is disabled, so a non-CTF workout costs exactly one CTF request. A failed read keeps the
 * last good board and the poll keeps trying, because an error does not tell us the workout is not enrolled.
 */
export const useCtfBoard = (workoutId: string) => {
    const [board, setBoard] = useState<CtfStudentBoardResponse | null>(null);
    // null until the first successful read; false stops polling for good.
    const [enrolled, setEnrolled] = useState<boolean | null>(null);
    const workoutRef = useRef(workoutId);
    // usePolling schedules its next tick before React commits `enabled: false`, so the ref, not the state, is what
    // guarantees no request follows a not-enrolled answer.
    const notEnrolledRef = useRef(false);

    useEffect(() => {
        workoutRef.current = workoutId;
        notEnrolledRef.current = false;
        setBoard(null);
        setEnrolled(null);
    }, [workoutId]);

    const fetchBoard = useCallback(async () => {
        if (notEnrolledRef.current) {
            return;
        }
        try {
            const fetched = await ctfBoardService.getBoard(workoutId);
            // Drop a response for a workout the page has since navigated away from.
            if (workoutRef.current !== workoutId) {
                return;
            }
            notEnrolledRef.current = !fetched.enrolled;
            setBoard(fetched.enrolled ? fetched : null);
            setEnrolled(fetched.enrolled);
        } catch {
            // Keep the last good board; the next poll retries.
        }
    }, [workoutId]);

    usePolling(fetchBoard, {enabled: enrolled !== false, interval: BOARD_POLL_INTERVAL_MS});

    return {board, refresh: fetchBoard};
};
