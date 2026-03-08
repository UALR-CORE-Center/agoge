import { Box, Skeleton } from '@mui/material';
import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, useNavigate } from "react-router-dom";
import {useAuthContext} from "../../../context/AuthContext";
import {usePolling} from "../../../hooks/usePolling";
import { URL_ERROR } from "../../../router/urls";
import { UnitFull, UnitRoster } from "../../../services/Unit/unit.model";
import { unitService } from "../../../services/Unit/unit.service";
import { Workout } from "../../../services/Workout/workout.model";
import { WorkoutStates } from "../../../types/AgogeStates";
import HttpError from "../../Common/Errors/HttpError";
import {InfoCard} from "../../Common/InfoCard/InfoCard";
import TimerBox from "../../Common/Timer";
import UnitRubricEditor from "./UnitRubricEditor";
import UnitTable from "./UnitTable";

const TeacherUnit: React.FC = () => {
    const { firebaseUser } = useAuthContext();
    const { build_id } = useParams<{ build_id: string }>();
    const navigate = useNavigate();

    // typically this would have pending set to true, but the global loader is isLoading, so we don't
    // want to trigger that when fetching periodically
    const [unitFull, setUnitFull] = useState<{pending: boolean, value: UnitFull | null}>({pending: false, value: null});
    const [expiresTimestamp, setExpiresTimestamp] = useState<number | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isExpired, setIsExpired] = useState(false);
    const [workoutList, setWorkoutList] = useState<Workout[]>([]);
    const previousWorkoutListLengthRef = useRef(0);
    const [rosterSize, setRosterSize] = useState<UnitRoster | undefined>();


    const handleOptimisticUpdates = (action: string, workouts: string[]): void =>  {
        setWorkoutList((prev) => {
            return prev.map((workout) => {
                const copy = {...workout};
                if (workouts.includes(workout.id)) {
                    copy.state = action;
                }

                return copy;
            });
        });
    }

    function handleError(error: HttpError) {
        if ([404].includes(error.status)) {
            navigate(URL_ERROR, {
                state: {status: error.status, message: error.message || "An error occurred"},
            });
        } else {
            navigate(URL_ERROR, {
                state: {status: 500, message: "Something went wrong!"},
            });
        }
    }

    const fetchData = async (isInitialLoad = false) => {
        if (isInitialLoad) {
            setIsLoading(true)
        } else {
            setUnitFull((prev) =>
                ({...prev, pending: true}));
        }

        const checkExpiration = (fetchedUnitFull: UnitFull) => {
            const expiry = fetchedUnitFull?.workspace_settings?.expires;
            setExpiresTimestamp(Number(expiry) || 0);
            const state = fetchedUnitFull?.state;

            if (expiry) {
                const currentDate = new Date();
                const expiryDate = new Date(Number(expiry) * 1000);
                setIsExpired(expiryDate < currentDate);
            } else {
                setIsExpired([WorkoutStates.EXPIRED, WorkoutStates.DELETED].includes(Number(state)));
            }
        };

        try {
            const fetchedUnitFull = await unitService.get_full(String(build_id));
            setUnitFull({pending: false, value: fetchedUnitFull});
            if (fetchedUnitFull) {
                checkExpiration(fetchedUnitFull);
                setWorkoutList(fetchedUnitFull.workouts || []);
                setRosterSize({ id: String(fetchedUnitFull.id), roster: fetchedUnitFull.roster });
                previousWorkoutListLengthRef.current = fetchedUnitFull.workouts?.length || 0;
            }
        } catch (error) {
            handleError(error as HttpError);
            setUnitFull((prev) => ({...prev, pending: false}));
        } finally {
            if (isInitialLoad) setIsLoading(false);
        }
    }

    useEffect(() => {
        if (firebaseUser.user) {
            fetchData(true)
        } else {
            setIsLoading(false);
        }
    }, [firebaseUser.user]);

    usePolling(fetchData, {enabled: !!firebaseUser.user && !isExpired, interval: 15000})
    const memoizedRosterSize = useMemo(() => rosterSize?.roster, [rosterSize]);
    return (
        <Box
            id="homePage"
            sx={{
                height: '100%', width: '100%',
                display: 'flex', flexDirection: 'row',
                justifyContent: 'center', alignItems: 'flex-start',
                mt: 10, pl: 2, pr: 2
            }}
        >
            <Box
                sx={{
                    width: '25%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    mr: 4
                }}
            >
                {isLoading || !unitFull.value ? (
                    <Skeleton
                        variant="rectangular"
                        width="100%"
                        height={150}
                        animation="wave"
                    />
                ) : (
                    <Box sx={{ width: '100%' }}>
                        <TimerBox
                            type="unit"
                            build_id={String(build_id)}
                            expires={expiresTimestamp}
                        />
                        {
                            unitFull.value?.rubric_support && (
                                <UnitRubricEditor buildId={String(build_id)} isExpired={isExpired} />
                            )
                        }

                    </Box>
                )}
            </Box>
            <Box sx={{ width: '75%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {isLoading || !unitFull.value ? (
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
                        <InfoCard
                            buildType='unit'
                            data={{ ...unitFull.value, roster: memoizedRosterSize }}
                            isLoading={isLoading}
                        />
                        <Box sx={{ mt: 2, width: '100%' }}>
                            <UnitTable
                                buildId={String(build_id)}
                                workouts={workoutList}
                                lms_available={unitFull.value?.lms_integration !== null}
                                refreshing={unitFull.pending && !isLoading}
                                isExpired={isExpired}
                                onActionPerformed={(action, workouts) => handleOptimisticUpdates(action, workouts)}
                            />
                        </Box>
                    </>
                )}
            </Box>
        </Box>
    );
};

export default TeacherUnit;