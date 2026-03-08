import {Paper, Typography, Box, useTheme, Divider} from '@mui/material';
import React, { useState, useEffect, useRef } from 'react';
import { WorkoutStates } from "../../types/AgogeStates";
import {AppUiObjectNames} from "../../types/AppObjectNames";
import { ExtendButton } from '../Buttons/ControlButtons/ExtendButton'
import { StartButton } from '../Buttons/ControlButtons/StartButton';
import { StopButton } from '../Buttons/ControlButtons/StopButton';
import NumberInputField from "./FormInputs/NumberInputField";
import {StateInfo} from "./Status/StateInfo";
import {WorkoutStateMapping, StatusInfo} from "./Status/StateMapping";


interface TimerBoxProps {
    type: 'unit' | 'workout';
    build_id: string;
    workoutData?: {
        expires: number;
        state: string;
        shutoff_timestamp?: number;
        proxy_connections?: any;
        servers?: any;
    };
    expires?: number | null;
}

const defaultState: StatusInfo = { text: "Working", color: '#b0b049' };

const TimerBox: React.FC<TimerBoxProps> = ({ type, build_id, workoutData, expires }) => {
    const [days, setDays] = useState('0');
    const [duration, setHours] = useState('1');
    const [time, setTime] = useState(workoutData?.shutoff_timestamp || 0);
    const [expiresTimestamp, setExpiresTimestamp] = useState(expires);

    const currentDate = new Date();
    const expiryDate =
        typeof expiresTimestamp === 'number' ? new Date(expiresTimestamp * 1000) : null;
    const isExpired = !expiryDate || expiryDate < currentDate;
    const theme = useTheme();

    const [timerLiveMsg, setTimerLiveMsg] = useState("");
    const lastAnnouncedRef = useRef<number | null>(null);

    useEffect(() => {
        if (time < 0) return;

        const shouldAnnounce = () => {
            if (time === 0) return true;
            if (time <= 10) return true;
            if (time <= 60) return time % 10 === 0;
            if (time <= 120) return time % 15 === 0;
            if (time <= 600) return time % 30 === 0;
            return time % 60 === 0;
        };

        if (shouldAnnounce() && lastAnnouncedRef.current !== time) {
            setTimerLiveMsg(
                time === 0 ? "Session ended" : `Time remaining ${formatTime(time)}`
            );
            lastAnnouncedRef.current = time;

            const t = setTimeout(() => setTimerLiveMsg(""), 700);
            return () => clearTimeout(t);
        }
    }, [time]);


    const formattedDate = isExpired || !expiryDate
        ? "EXPIRED"
        : expiryDate.toLocaleString('en-US', {
            month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: true
        });

    useEffect(() => {
        if (workoutData?.shutoff_timestamp) {
            const shutoffTime = Math.floor(workoutData.shutoff_timestamp - Date.now() / 1000);
            setTime(shutoffTime > 0 ? shutoffTime : 0);
        }
    }, [workoutData]);

    useEffect(() => {
        const timer = setInterval(() => {
            setTime(prevTime => (prevTime > 0 ? prevTime - 1 : 0));
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const handleDaysChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setDays(event.target.value);
    };

    const handleHoursChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setHours(event.target.value);
    };

    const increaseUnitTimeByDays = (additionalDays: number) => {
        const newExpiresTimestamp = expiresTimestamp + additionalDays * 24 * 60 * 60;
        setExpiresTimestamp(newExpiresTimestamp);
    };

    const increaseTimeByOneHour = () => {
        setTime(prevTime => prevTime + 60 * 60);
    };

    const formatTime = (seconds: number) => {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const workoutState = workoutData?.state ? WorkoutStateMapping[workoutData.state as unknown as WorkoutStates] || defaultState : defaultState;

    const stateColor = (): string => {
        const state = workoutData?.state.toString() || '0';

        const stateColorMap: { [p: string]: string } = {
            [WorkoutStates.READY.toString()]: "ready",
            [WorkoutStates.RUNNING.toString()]: "success",
            [WorkoutStates.NOT_BUILT.toString()]: "neutral",
            [WorkoutStates.DELETED.toString()]: "neutral",
            [WorkoutStates.EXPIRED.toString()]: "neutral",
            [WorkoutStates.BROKEN.toString()]: "error",
            [WorkoutStates.MISFIT.toString()]: "error",
        };

        return stateColorMap[state] || "warning";
    };

    const isLoading = () => {
        const state = Number(workoutData?.state) || 0;

        if (state === WorkoutStates.READY || state === WorkoutStates.NOT_BUILT) {
            return false;
        }

        return (
            (state > WorkoutStates.READY && state < WorkoutStates.RUNNING) ||
            (state > WorkoutStates.RUNNING && state !== WorkoutStates.BROKEN && state !== WorkoutStates.DELETED)
        );
    };



    const renderUnitTimer = () => {
        return (
            <>
                <Typography component="p" variant="body1" gutterBottom sx={{ fontSize: '1.25rem', fontWeight: 500 }}>
                    {!isExpired ? 'Expires' : `${AppUiObjectNames.UNIT}`}: {formattedDate}
                </Typography>
                {!isExpired && (
                    <Box component="section" aria-label="Extend controls" role="group" sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <NumberInputField
                            size="small"
                            label="Extend By (days)"
                            min={1}
                            max={60}
                            value={days}
                            onChange={handleDaysChange}
                        />
                        <ExtendButton
                            title={"Extend Expiration"}
                            label="Extend Expiration"
                            controlType="assignment"
                            data={{ id: build_id, days: parseInt(days, 10) }}
                            additionalOnClick={() => increaseUnitTimeByDays(parseInt(days, 10))}
                            isDisabled={isExpired}
                        />
                    </Box>
                )}
            </>
        );
    }


    const renderWorkoutTimer = () => {
        return (
            <>
                <Typography
                    component="p"
                    variant="body1"
                    gutterBottom
                    sx={{ fontSize: '1.5rem', fontWeight: 700 }}
                >
                    {!isExpired ? 'Expires' : `${AppUiObjectNames.WORKOUT}`}: {formattedDate}
                </Typography>
                {workoutData ? (
                    <Box
                        component="section"
                        aria-label="Workout session"
                        sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: '8px' }}
                    >
                        {workoutData.servers && workoutState.text === 'Stopped' && (
                            <Box
                                component="section"
                                aria-label="Start controls"
                                role="group"
                                sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}
                            >
                                <NumberInputField
                                    size="small"
                                    label="Duration (hours)"
                                    min={1}
                                    max={10}
                                    value={duration}
                                    onChange={handleHoursChange}
                                />
                                <StartButton
                                    title={"Start Workout"}
                                    label="Start Workout"
                                    controlType="workout"
                                    row={workoutData}
                                    data={{ id: build_id, duration: duration }}
                                />
                            </Box>
                        )}
                        {workoutData.servers && workoutState.text === 'Running' && (
                            <Box component="section" aria-label="Active session" sx={{ display: 'flex', flexDirection: 'column',}}>
                                <Box
                                    aria-live="polite"
                                    role="status"
                                    aria-atomic="true"
                                    sx={{
                                        position: "absolute", width: 1, height: 1, p: 0, m: -1,
                                        overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap", border: 0,
                                    }}
                                >
                                    {timerLiveMsg}
                                </Box>
                                <Box
                                    role="timer"
                                    aria-labelledby="time-remaining-label"
                                    aria-atomic="true"
                                    sx={{
                                        mt: 2, padding: '10px', borderRadius: '4px',
                                        backgroundColor: theme.palette.mode === 'dark' ? '#121212' : '#dcdcdc',
                                        color: theme.palette.mode === 'dark' ? '#dedcdc' : '#000000',
                                        display: 'inline-block', fontFamily: 'monospace', fontSize: '24px', textAlign: 'center'
                                    }}
                                >
                                    {formatTime(time)}
                                </Box>
                                <Typography
                                    id="time-remaining-label"
                                    component="p"
                                    color={theme.palette.text.disabled}
                                    variant="caption"
                                    m="auto"
                                >
                                    Time Remaining
                                </Typography>

                                <Divider sx={{ my: 1 }} />

                                <Box
                                    component="section"
                                    aria-label="Workout controls"
                                    role="group"
                                    sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}
                                >
                                    <ExtendButton
                                        title={"Add one hour"}
                                        label="Add one hour"
                                        controlType="workout"
                                        row={workoutData}
                                        data={{ id: build_id, hours: 1 }}
                                        additionalOnClick={increaseTimeByOneHour}
                                    />
                                    <StopButton
                                        title="Stop Workout"
                                        label="Stop Workout"
                                        controlType="workout"
                                        row={workoutData}
                                        data={{ id: build_id }}
                                    />
                                </Box>
                            </Box>
                        )}
                        <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
                            <StateInfo
                                label={workoutState.text}
                                variant="filled"
                                color={stateColor()}
                                loading={isLoading()}
                            />
                        </Box>
                    </Box>
                ) : null}
            </>
        );
    };


    return (
        <Paper
            component="section"
            aria-label={type === 'unit' ? 'Unit Timer' : 'Workout Timer'}
            elevation={1}
            sx={{
                padding: '16px',
                marginBottom: '16px',
                backgroundColor: 'background.paper',
                color: 'text.primary'
            }}
        >
            {type === 'unit' && (
                renderUnitTimer()
            )}
            {type === 'workout' && (
                renderWorkoutTimer()
            )}
        </Paper>
    );
};

export default TimerBox;
