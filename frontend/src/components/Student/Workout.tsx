import KeyboardTabIcon from '@mui/icons-material/KeyboardTab';
import { Box, Skeleton, Button } from "@mui/material";
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from "react-router-dom";
import {useUserIp} from "../../hooks/userIp";
import {URL_ERROR} from "../../router/urls";
import { WorkoutFull } from "../../services/Workout/workout.model";
import { workoutService } from "../../services/Workout/workout.service";
import {WorkoutStates} from "../../types/AgogeStates";
import HttpError from "../Common/Errors/HttpError";
import {InfoCard} from "../Common/InfoCard/InfoCard";
import TimerBox from "../Common/Timer";
import {ConfigureAccess} from "./ConfigureAccess";
import WorkoutAssessment from "./WorkoutAssessment";
import WorkoutTable from "./WorkoutTable";

const StudentWorkout: React.FC = () => {
    const { build_id } = useParams<{ build_id: string }>();
    const [isLoading, setIsLoading] = useState(true);
    const [safeToConfigure, setSafeToConfigure] = useState(false);
    const [currentState, setCurrentState] = useState<string>("");
    const [isConfigured, setIsConfigured] = useState(false);
    const [workoutFull, setWorkoutFull] = useState<WorkoutFull | null>(null);
    const [showAssessment, setShowAssessment] = useState(false);
    const [error, setError] = useState<HttpError | null>(null);
    const userIp = useUserIp();
    const navigate = useNavigate();

    const workoutRef = useRef<HTMLDivElement>(null);
    const assessmentRef = useRef<HTMLDivElement>(null);

    const handleError = useCallback(
        (error: HttpError) => {
            if ([404].includes(error.status)) {
                navigate(URL_ERROR, {
                    state: {
                        status: error.status,
                        message: error.message || "An error occurred",
                    },
                });
            } else {
                navigate(URL_ERROR, {
                    state: {
                        status: 500,
                        message: "Something went wrong!",
                    },
                });
            }
        },
        [navigate]
    );

    const isReadyOrRunning = (fetchedWorkout: WorkoutFull) => {
        let isSafe = false;
        const ipExists = checkIpExists(fetchedWorkout);

        if (!isConfigured || !ipExists) {
            const state = fetchedWorkout?.workout?.state;

            if (state) {
                if (
                    [
                        WorkoutStates.READY.toString(),
                        WorkoutStates.RUNNING.toString()
                    ].includes(String(state))
                ) {
                    isSafe = true;
                }
                setCurrentState(state);
            }
        }
        setSafeToConfigure(isSafe);
    }

    const checkIpExists = (fetchedWorkout: WorkoutFull) => {
        let configured = false;
        if (userIp && fetchedWorkout) {
            const external_addresses = fetchedWorkout.workout.student_external_ip_addresses;
            if (external_addresses && external_addresses.includes(String(userIp))) {
                configured = true;
            }
        }
        return configured;
    }

    const fetchWorkout = useCallback(async () => {
        try {
            const fetchedWorkout = await workoutService.get_full(String(build_id));
            setWorkoutFull(fetchedWorkout);
            isReadyOrRunning(fetchedWorkout);
        } catch (error) {
            handleError(error as HttpError);
            setError(error as HttpError);
        } finally {
            setIsLoading(false);
        }
    }, [build_id, handleError]);

    useEffect(() => {
        fetchWorkout();
    }, [fetchWorkout]);

    useEffect(() => {
        fetchWorkout();

        let intervalTime = 3500;
        const serverCount = workoutFull?.servers?.length || 0;

        if (serverCount === 0) {
            intervalTime = 60000;
        }

        const intervalId = setInterval(fetchWorkout, intervalTime);
        return () => clearInterval(intervalId);
    }, [fetchWorkout, workoutFull?.servers?.length]);

    return (
        <Box
            component="main"
            id="homePage"
            aria-label="Student Workout"
            sx={{
                height: '100%',
                display: 'flex',
                width: '100%',
                flexDirection: 'row',
                justifyContent: 'center',
                alignItems: 'start',
                mt: 10,
                pl: 2,
                pr: 2
            }}
        >
            <Box
                component="aside"
                aria-label="Workout session controls"
                sx={{
                    width: '25%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    mr: 4
                }}
            >
                {isLoading ? (
                    <>
                        <Skeleton
                            variant="rectangular"
                            width="100%"
                            height={150}
                            animation="wave"
                        />
                        <Skeleton
                            variant={"rectangular"}
                            width="100%"
                            height={100}
                            animation={"wave"}
                        />
                    </>
                ) : (
                    <Box component="section" aria-label="session" sx={{ width: '100%' }}>
                        <TimerBox
                            type="workout"
                            build_id={String(build_id)}
                            workoutData={workoutFull?.workout}
                            expires={workoutFull?.workout.expires || null}
                        />

                        <ConfigureAccess
                            buildId={String(build_id)}
                            safeToConfigure={safeToConfigure}
                            currentState={currentState}
                        />

                        <Box component="nav" aria-label="Assessment navigation">
                            <Button
                                variant="outlined"
                                onClick={() => {
                                    setShowAssessment((prev) => {
                                        const next = !prev;
                                        requestAnimationFrame(() => {
                                            (next ? assessmentRef.current : workoutRef.current)?.focus();
                                        });
                                        return next;
                                    });
                                }}
                                sx={{ mt: 2 }}
                                endIcon={<KeyboardTabIcon />}
                            >
                                {showAssessment ? 'Back to Workout' : 'Go to Assessment'}
                            </Button>
                        </Box>
                    </Box>
                )}
            </Box>
            <Box
                sx={{
                    width: '75%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center'
                }}
            >
                {isLoading || !workoutFull ? (
                    <>
                        <Skeleton
                            variant="rectangular"
                            width="100%"
                            height={200}
                            animation="wave"
                        />
                        <Skeleton
                            variant="rectangular"
                            width="100%"
                            height={500}
                            animation="wave"
                            sx={{ mt: 2 }}
                        />
                    </>
                ) : (
                    <>
                        <Box
                            id="workout-view"
                            role="region"
                            aria-label="Workout details"
                            aria-hidden={showAssessment}
                            hidden={showAssessment}
                            tabIndex={-1}
                            ref={workoutRef}
                            sx={{ width: '100%' }}
                        >
                            <InfoCard
                                buildId={String(build_id)}
                                buildType={"workout"}
                                data={{ ...workoutFull.workout }}
                                isLoading={isLoading}
                            />
                            <WorkoutTable workoutFull={workoutFull} />
                        </Box>

                        <Box
                            id="assessment-view"
                            role="region"
                            aria-label="Workout assessment"
                            aria-hidden={!showAssessment}
                            hidden={!showAssessment}
                            tabIndex={-1}
                            ref={assessmentRef}
                            sx={{ width: '100%' }}
                        >
                            <WorkoutAssessment workout={workoutFull.workout} />
                        </Box>
                    </>
                )}
            </Box>
        </Box>
    );
}

export default StudentWorkout;