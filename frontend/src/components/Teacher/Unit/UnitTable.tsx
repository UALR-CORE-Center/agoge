import {AddAPhotoOutlined, BuildOutlined, DangerousOutlined, PlayArrowOutlined} from "@mui/icons-material";
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import QuizIcon from '@mui/icons-material/Quiz';
import {Box, Button, Paper, Typography} from '@mui/material';
import {GridColDef} from "@mui/x-data-grid";
import {useModal} from "mui-modal-provider";
import React, {useEffect, useState} from 'react';

import {useAuthContext} from '../../../context/AuthContext';
import {URL_STUDENT_WORKOUT} from '../../../router/urls';
import {snapshotService} from "../../../services/Server/snapshots.service";
import {unitService} from '../../../services/Unit/unit.service';
import {Workout} from '../../../services/Workout/workout.model';
import {WorkoutStates} from '../../../types/AgogeStates';
import {PubSub} from '../../../types/PubSub';

import {RebuildButton} from "../../Buttons/ControlButtons/RebuildButton";
import {SnapshotButton} from "../../Buttons/ControlButtons/SnapshotButton";
import {StartButton} from "../../Buttons/ControlButtons/StartButton";
import {StopButton} from "../../Buttons/ControlButtons/StopButton";
import {LinkButton} from "../../Buttons/LinkButton";
import {ExpandableCell} from "../../Common/DataGrid/ExpandableCell";
import StyledDataGrid, {ButtonConfig} from "../../Common/DataGrid/StyledDataGrid";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {resolveStatus, StateMapping, StatusInfo} from "../../Common/Status/StateMapping";
import StatusBadge from '../../Common/Status/StatusBadge';
import AssessmentDialog from "./AssessmentDialog";

interface UnitTableProps {
    buildId: string;
    workouts: Workout[];
    lms_available?: boolean;
    isExpired?: boolean;
    refreshing?: boolean;

    onActionPerformed: (action: string, workouts: string[]) => void;
}

interface Question {
    id: string;
    name: string | null;
    type: string;
    question: string;
    key: string | null;
    answer: string;
    script_assessment: boolean;
    complete: boolean;
}

const defaultState: StatusInfo = { text: "Working", color: '#b0a100' };
type UnitActions = "build" | "start" | "stop" | "rebuild" | "snapshot";

const UnitTable: React.FC<UnitTableProps> = (props) => {
    const {showModal} = useModal();
    const { agogeUser } = useAuthContext();

    const [selectedRows, setSelectedRows] = useState<string[]>([]);
    const [activeButton, setActiveButton] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [currentStudent, setCurrentStudent] = useState<Workout | null>(null);

    const [internalRefreshing, setInternalRefreshing] = useState(props.refreshing)


    useEffect(() => {
        // Creates a delay when updating the internal refreshing logic. This prevents
        // "Refreshing" from popping up for .5 seconds and then disappearing - right now
        // we're using a 1.5s buffer
        const refreshing = props.refreshing
        setTimeout(() => setInternalRefreshing(refreshing), refreshing ? 0: 1500)
    }, [props.refreshing]);


    if (!agogeUser?.user) return <Typography color="error">User not authenticated</Typography>;
    
    const handleOpenResponses = (student: any) => {
        try {
            setCurrentStudent(student);
        } catch (error) {
            console.error('Error parsing assessment:', error);
        }
        setModalOpen(true);
    };

    const handleCloseModal = () => {
        setModalOpen(false);
    };

    const buttonController = async (action: UnitActions) => {
        switch(action) {
            case 'build':
                setActiveButton(action);
                setLoading(true);
                showModal(SimpleSnackbar, {
                    message: "Processing build request for selected workouts!",
                    severity: 'success',
                });
                try {
                    await unitService.put_action(
                        props.buildId,
                        PubSub.Actions.BUILD.toString(),
                        undefined,
                        selectedRows
                    );


                    props.onActionPerformed(PubSub.Actions.BUILD.toString(), selectedRows)
                } catch (error) {
                    console.error('Error building selected workouts:', error);
                    showModal(SimpleSnackbar, {
                        message: "Failed to build selected workouts!",
                        severity: 'error',
                    });
                } finally {
                    setActiveButton(null);
                    setLoading(false);
                }
                return;
            case 'start':
                try{
                    setActiveButton(action);

                    showModal(SimpleSnackbar, {
                        message: "Starting selected workouts...",
                        severity: 'success',
                    });
                    await unitService.put_action(
                        props.buildId,
                        PubSub.Actions.START.toString(),
                        undefined,
                        selectedRows
                    );
                    props.onActionPerformed(PubSub.Actions.START.toString(), selectedRows)
                } catch(error) {
                    console.error('Error starting selected workouts...', error);
                    showModal(SimpleSnackbar, {
                        message: "Oh no an error occurred.",
                        severity: 'error',
                    });
                } finally {
                    setActiveButton(null);
                }
                return;
            case 'stop':
                try {
                    setActiveButton(action);
                    showModal(SimpleSnackbar, {
                        message: "Stopping selected workouts...",
                        severity: 'success',
                    });
                    await unitService.put_action(
                        props.buildId,
                        PubSub.Actions.STOP.toString(),
                        undefined,
                        selectedRows
                    );

                    console.log(PubSub.Actions.STOP, selectedRows)
                    props.onActionPerformed(PubSub.Actions.STOP.toString(), selectedRows)
                } catch(error) {
                    console.error('Error stopping selected workouts...', error);
                    showModal(SimpleSnackbar, {
                        message: "Oh no an error occurred.",
                        severity: 'error',
                    });
                } finally {
                    setActiveButton(null);
                }
                return;
            case 'snapshot':
                try {
                    setActiveButton(action);
                    showModal(SimpleSnackbar, {
                        message: "Snapshotting selected workouts...",
                        severity: 'success',
                    });
                    const formData = {
                        action: PubSub.Actions.SNAPSHOT,
                        course_object: PubSub.CourseObjects.WORKOUT,
                        items: selectedRows
                    }
                    await snapshotService.post(formData);
                    props.onActionPerformed(PubSub.Actions.SNAPSHOT.toString(), selectedRows)
                } catch(error) {
                    console.error('Error snapshotting selected workouts...', error);
                    showModal(SimpleSnackbar, {
                        message: "Oh no an error occurred.",
                        severity: 'error',
                    });
                } finally { setActiveButton(null); }
                return;
            default:
                console.error("Not valid action");
                break;
        }
    };

    const columns: GridColDef[] = [
        {
            field: 'state',
            headerName: 'State',
            headerAlign: 'center',
            minWidth: 150,
            renderCell: (params: any) => {
                const status = resolveStatus("workout",params.value);
                return (
                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        height: '100%',
                        width: '100%',
                    }}>
                        <StatusBadge color={status.color} label={status.text} />
                    </Box>
                );
            }
        },
        {
            field: 'id',
            headerName: 'ID',
            width: 150,
            headerAlign: 'center',
            renderCell: (params: any) => (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    width: '100%',
                }}>
                    <ExpandableCell
                        {...params}
                        value={params.value}
                        variant={"body1"}
                    />
                </Box>
            ),
        },
        {
            field: 'student_email',
            headerName: 'Student Email',
            minWidth: 250,
            headerAlign: 'center',
            renderCell: (params: any) => (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    width: '100%',
                }}>
                    <ExpandableCell
                        {...params}
                        value={params.value}
                        variant={"body1"}
                    />
                </Box>
            ),
        },
        {
            field: 'workoutLink',
            headerName: '',
            minWidth: 175,
            renderCell: (params: any) => (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    width: '100%',
                }}>
                    <LinkButton
                        buildId={params.row.id}
                        endpoint={URL_STUDENT_WORKOUT}
                        color={"primary"}
                        endIcon={<OpenInNewIcon />}
                        label={"View Workout"}
                        width={"150px"}
                        fontSize={"12px"}
                    />
                </Box>
            ),
        },
        {
            field: 'assessment',
            headerName: '',
            minWidth: 175,
            renderCell: (params: any) => {
                if (params.row.assessment === undefined) return null;

                const focusIfNeeded = (el: HTMLButtonElement | null) => {
                    if (el && params.hasFocus) el.focus();
                };

                return (
                    <Box sx={{ display:'flex', justifyContent:'center', alignItems:'center', height:'100%', width:'100%' }}>
                        <Button
                            ref={focusIfNeeded}
                            tabIndex={params.hasFocus ? 0 : -1}
                            variant="contained"
                            color="primary"
                            endIcon={<QuizIcon />}
                            onKeyDown={(e) => e.stopPropagation()}
                            onClick={(e) => { e.stopPropagation(); handleOpenResponses(params.row); }}
                        >
                            Assessment
                        </Button>
                    </Box>
                );
            }
        },
        {
            field: 'actions',
            headerName: 'Actions',
            minWidth: 180,
            renderCell: (params: any) => {
                return renderWorkoutRowActions(params.row);
            }
        }
    ];

    const isTableHeaderButtonDisabled = (action: UnitActions)=> {
        const loadingOrExpired = loading || props.isExpired!;
        const areRowsSelected = selectedRows.length > 0;
        let isDisabled;
        if (action === "build") {
            isDisabled = !props.lms_available;
        } else {
            isDisabled = props.workouts.length === 0;
        }
        return loadingOrExpired || isDisabled || !areRowsSelected;
    }

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Build",
                variant: 'contained',
                color: "primary",
                requiresSelection: false,
                icon: <BuildOutlined fontSize={"large"} />,
                addTooltip: true,
                tooltip: "Build all selected workouts",
                onClick: () => buttonController('build'),
                isDisabled: isTableHeaderButtonDisabled('build')
            },
            {
                label: "Start",
                variant: 'outlined',
                color: "success",
                requiresSelection: false,
                icon: <PlayArrowOutlined fontSize="large"/>,
                addTooltip: true,
                tooltip: "Start all selected workouts",
                loading: activeButton==="start",
                onClick: () => buttonController("start"),
                isDisabled: isTableHeaderButtonDisabled('start')
            },
            {
                label: "Stop",
                variant: 'outlined',
                color: "secondary",
                requiresSelection: false,
                icon: <DangerousOutlined fontSize="large"/>,
                addTooltip: true,
                tooltip: "Stop all selected workouts",
                loading: activeButton==="stop",
                onClick: () => buttonController("stop"),
                isDisabled: isTableHeaderButtonDisabled('stop')
            },
            {
                label: "Snapshot",
                variant: 'outlined',
                color: "info",
                requiresSelection: false,
                icon: <AddAPhotoOutlined fontSize="large"/>,
                addTooltip: true,
                tooltip: "Snapshot selected workouts",
                loading: activeButton==="snapshot",
                onClick: () => buttonController("snapshot"),
                isDisabled: isTableHeaderButtonDisabled('snapshot')
            },
        ];

        return buttonConfig;
    }

    const renderWorkoutRowActions = (row: Workout) => {
        return (
            <>
                <StartButton
                    title={"Start Workout"}
                    label={"Start Workout"}
                    controlType={"workout"}
                    iconButton={true}
                    iconProps={{
                        size: "medium",
                        label: "start workout button"
                    }}
                    isDisabled={props.isExpired || loading}
                    row={row}
                    onActionPerformed={(action: string) => {
                        props.onActionPerformed(action, [row.id])
                    }}
                    data={{ id: row.id, duration: 2}}
                />
                <StopButton
                    title={"Stop Workout"}
                    label={"Stop Workout"}
                    controlType={"workout"}
                    iconButton={true}
                    iconProps={{
                        size: "medium",
                        label: "stop workout button"
                    }}
                    isDisabled={props.isExpired || loading}
                    row={row}
                    onActionPerformed={(action: string) => {
                        props.onActionPerformed(action, [row.id])
                    }}
                    data={{ id: row.id }}
                />
                <RebuildButton
                    title={"Rebuild Workout"}
                    label={"Rebuild Workout"}
                    controlType={"workout"}
                    iconButton={true}
                    iconProps={{
                        size: "medium",
                        label: "rebuild workout button"
                    }}
                    onActionPerformed={(action: string) => {
                        props.onActionPerformed(action, [row.id])
                    }}
                    isDisabled={props.isExpired || loading}
                    row={row}
                />
                <SnapshotButton
                    title={"Manage Workout Snapshots"}
                    label={"Manage Workout Snapshots"}
                    controlType={"workout"}
                    iconButton={true}
                    onActionPerformed={(action: string) => {
                        console.log(row);
                        props.onActionPerformed(action, [row.id])
                    }}
                    iconProps={{
                        size: "medium",
                        label: "manage workout snapshots button"
                    }}
                    isDisabled={props.isExpired}
                    loading={loading}
                    row={row}
                />
            </>
        )
    };

    return (
        <Paper
            square={false}
            sx={{
                display: 'flex',
                flexDirection: 'column',
                flexGrow: 1,
                padding: "0 10px 10px 10px"
            }}
        >
            <Box sx={{ width: "100%" }}>
                <StyledDataGrid
                    data={props.workouts}
                    columns={columns}
                    disableMultiRowSelection={false}
                    disableSelectBtn={false}
                    disableRowSelectionOnClick={true}
                    density={"compact"}
                    loading={loading}
                    onSelection={setSelectedRows}
                    refreshing={internalRefreshing}
                    selectedRow={selectedRows}
                    labelProps={{
                        disable: false,
                        text: "Student Lab Workouts",
                        variant: "h5",
                    }}
                    buttonsConfig={getButtonConfig()}
                />
                <AssessmentDialog
                    open={modalOpen}
                    onClose={handleCloseModal}
                    currentStudent={currentStudent}
                />
            </Box>
        </Paper>
    );
};

export default UnitTable;