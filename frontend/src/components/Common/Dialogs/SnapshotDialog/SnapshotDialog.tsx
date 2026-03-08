import {Close} from "@mui/icons-material";
import ComputerIcon from "@mui/icons-material/Computer";
import {
    Box,
    IconButton,
    Skeleton,
    Stack,
    useTheme
} from '@mui/material';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import {useModal} from "mui-modal-provider";
import React, {useCallback, useEffect, useState} from 'react';
import { usePolling } from "../../../../hooks/usePolling";
import {AgogeImage} from "../../../../services/Server/image.model";
import {SnapshotsModel} from "../../../../services/Server/snapshots.model";
import {snapshotService} from "../../../../services/Server/snapshots.service";
import {Workout} from "../../../../services/Workout/workout.model";
import {PubSub} from "../../../../types/PubSub";
import {capitalizeString} from "../../../../utilities/formatString";
import SimpleSnackbar from "../../SnackBar/SnackBar";
import {StyledTab, StyledTabPanel, StyledTabs} from "./CustomTabs";
import {ServerSnapshotsTable} from "./ServerSnapshotsTable";
import {CourseObject} from "./types";

interface Props {
    row: Workout | AgogeImage;
    courseObject: CourseObject;
}

function a11yProps(index: number) {
    return {
        id: `tab-${index}`,
        'aria-controls': `tabPanel-${index}`,
    };
}


const SnapshotDialog: React.FC<Props> = (props) => {
    const theme = useTheme();
    const {showModal} = useModal();
    const [value, setValue] = useState(0);
    const [snapshots, setSnapshots] = useState<{pending: boolean, value: SnapshotsModel[] | null}>({pending: true, value: null});
    const [dialogState, setDialogState] = useState<{ loading: boolean, error: string }>({
        loading: true, error: ""
    });
    const buildId = props.row.id;
    const courseObjectTitle = props.courseObject === "workout" ? "Workout" : "Server";
    const [open, setOpen] = useState(true);
    const [serverId, setServerId] = useState<null | string>(null)

    // Somewhat frequent to show user we're doing something

    const getServerSnapshots = async () => {
        if (!serverId) {
            return;
        }

        try {
            setSnapshots((prev) =>
                ({...prev, pending: true}));

            const updated = await snapshotService.get(serverId);
            setSnapshots(prev => {
                const exists = prev.value?.some(item => item.server_id === updated.server_id);

                const newValue = exists
                    ? prev.value?.map(item =>
                        item.server_id === updated.server_id
                            ? { ...item, ...updated }
                            : item
                    )
                    : [...(prev.value || []), updated];

                return {
                    pending: false,
                    value: newValue ?? null, // <-- ensure this is never undefined
                };
            });
        } catch (error: any) {
            setSnapshots((prev) =>
                ({...prev, pending: false}));
            showModal(SimpleSnackbar, {
                message: `Error refreshing snapshot records for server ${serverId}`,
                severity: "error",
            });
        }

    }

    const getSnapshots = useCallback(async () => {
        setDialogState({ loading: true, error: ""});
        let courseObject;
        if (props.courseObject === "labServer") {
            courseObject = PubSub.CourseObjects.LAB_SERVER;
        } else if (props.courseObject === "templateServer") {
            courseObject = PubSub.CourseObjects.TEMPLATE_SERVER;
        } else if (props.courseObject === "workout") {
            courseObject = PubSub.CourseObjects.WORKOUT
        }


        let resp;
        try {
            resp = await snapshotService.list(buildId, courseObject);
            setSnapshots({pending: false, value: resp});
            if (resp.length > 0) {
                setServerId(resp[0].server_id);
            }
            setDialogState(
                (prevState) => (
                    {...prevState, loading: false}
                )
            );
        } catch (error) {
            setDialogState(
                (prevState) => (
                    {...prevState, loading: false, error: error}
                )
            );
        }

        return;
    }, [props.courseObject, props.row.id]);

    const handleOnClose = () => {
        setOpen(false);
    }

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
    };

    useEffect(() => {
        if (!snapshots.value) {
            getSnapshots();
        }
    }, [getSnapshots, snapshots]);


    usePolling(getServerSnapshots, { enabled: open, interval: 5000});
    return (
        <Dialog
            open={open}
            onClose={handleOnClose}
            fullWidth={true}
            maxWidth={"lg"}
        >
            <DialogTitle sx={{ color: theme.palette.text.primary }}>
                <Stack direction={'row'} alignItems={'center'} justifyContent={'space-between'}>
                    {capitalizeString(buildId)} {courseObjectTitle} Snapshot Manager
                    <IconButton
                        onClick={handleOnClose}
                        aria-label={"close snapshot manager dialog"}
                        color={"default"}
                        title={"Close snapshot manager"}
                    >
                        <Close />
                    </IconButton>
                </Stack>
            </DialogTitle>
            <DialogContent>
                <Box>
                    {
                        dialogState.loading ? (
                            <>
                                <Skeleton
                                    variant={"rectangular"}
                                    animation={"wave"}
                                    height={300}
                                />
                            </>
                        ) : (
                                <>
                                    <StyledTabs
                                        value={value}
                                        onChange={handleTabChange}
                                        variant={"scrollable"}
                                        scrollButtons
                                        allowScrollButtonsMobile
                                        label={"Server snapshot tabs"}
                                        orientation={"horizontal"}
                                    >
                                        {
                                            snapshots.value?.map((server, index) => {
                                                return (
                                                    <StyledTab
                                                        index={index}
                                                        key={`tab-${index}`}
                                                        label={server.server_id}
                                                        icon={<ComputerIcon />}
                                                        iconPosition={"start"}
                                                        {...a11yProps(index)}
                                                    />
                                                );
                                            })
                                        }
                                    </StyledTabs>
                                    {
                                        !dialogState.loading && snapshots?.value &&
                                        snapshots.value?.map((server, index) => {
                                            return (
                                                <StyledTabPanel
                                                    key={`tabPanel-${index}`}
                                                    index={index}
                                                    value={value}
                                                >
                                                    <ServerSnapshotsTable
                                                        buildId={buildId}
                                                        courseObject={props.courseObject}
                                                        disabled={false}
                                                        loading={dialogState.loading}
                                                        data={server}
                                                        refreshing={snapshots.pending}
                                                    />
                                                </StyledTabPanel>
                                            );
                                        })
                                    }
                                </>
                            )
                    }
                </Box>
            </DialogContent>
            <DialogActions>
                <Button
                    onClick={() => handleOnClose()}
                    sx={{ color: theme.palette.text.primary }}
                >
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default SnapshotDialog;
