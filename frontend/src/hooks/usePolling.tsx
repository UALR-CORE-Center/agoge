import { useEffect, useRef, useCallback } from 'react';

type UsePollingOptions = {
    enabled?: boolean;
    interval?: number;
    debugLogName?: string;
};


export const usePolling = (
    fn: (...args: any[]) => Promise<void>,
    { debugLogName, enabled = true, interval = 10000 }: UsePollingOptions = {}
) => {
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const isMountedRef = useRef(true);
    const isPendingRef = useRef(false);
    const fnRef = useRef(fn);
    const abortControllerRef = useRef<AbortController | null>(null);
    const effectInstanceIdRef = useRef(0);

    useEffect(() => {
        fnRef.current = fn;
    }, [fn]);

    const log = useCallback((message: string) => {
        if (debugLogName) {
            console.log(`[${debugLogName}] ${message}`);
        }
    }, [debugLogName]);

    const clearTimer = useCallback(() => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
            log('Timer cleared');
        }
    }, [log]);

    const cancelCurrentRequest = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            log('Aborted in-flight request');
        }
    }, [log]);

    const executePoll = useCallback(async () => {
        // Create a new instance ID for this execution
        const instanceId = effectInstanceIdRef.current;

        if (!isMountedRef.current || !enabled || effectInstanceIdRef.current !== instanceId) {
            log(`Poll not executed - unmounted, disabled, or stale instance`);
            return;
        }

        clearTimer();

        if (isPendingRef.current) {
            log('Poll skipped - request already pending');
            if (isMountedRef.current && enabled && effectInstanceIdRef.current === instanceId) {
                timerRef.current = setTimeout(executePoll, interval);
            }
            return;
        }

        abortControllerRef.current = new AbortController();
        const signal = abortControllerRef.current.signal;

        try {
            isPendingRef.current = true;
            log('Starting poll');
            await fnRef.current();

            // Check if component is still mounted and instance is current
            if (!isMountedRef.current || effectInstanceIdRef.current !== instanceId) {
                log('Component unmounted or instance changed during request');
                return;
            }

            if (signal.aborted) {
                log('Poll was aborted after completion');
                return;
            }
            log('Poll completed');
        } catch (error) {
            if (!isMountedRef.current || effectInstanceIdRef.current !== instanceId) {
                log('Component unmounted or instance changed during error handling');
                return;
            }

            if (signal.aborted) {
                log('Poll aborted mid-request');
                return;
            }
            log(`Poll error: ${error}`);
        } finally {
            isPendingRef.current = false;
            abortControllerRef.current = null;

            // Only schedule next poll if component is still mounted and instance is current
            if (isMountedRef.current && enabled && effectInstanceIdRef.current === instanceId) {
                log(`Scheduling next poll in ${interval}ms`);
                timerRef.current = setTimeout(executePoll, interval);
            } else {
                log('Not scheduling next poll - component unmounted, polling disabled, or instance changed');
            }
        }
    }, [enabled, interval, clearTimer, log]);

    useEffect(() => {
        // Create a new instance ID for this effect instance
        const instanceId = ++effectInstanceIdRef.current;

        isMountedRef.current = true;
        log(`Setting up polling effect instance ${instanceId}`);

        if (enabled) {
            log('Initial poll starting immediately');
            executePoll();
        }

        return () => {
            log(`Cleaning up polling effect instance ${instanceId}`);
            isMountedRef.current = false;
            clearTimer();
            cancelCurrentRequest();

            // Mark this instance as obsolete by incrementing if it's still the current one
            if (effectInstanceIdRef.current === instanceId) {
                effectInstanceIdRef.current++;
            }

            log('Polling cleanup complete');
        };
    }, [enabled, executePoll, clearTimer, log, cancelCurrentRequest]);

    return {
        poll: executePoll,
        cancel: () => {
            clearTimer();
            cancelCurrentRequest();
        },
        isPending: () => isPendingRef.current
    };
};