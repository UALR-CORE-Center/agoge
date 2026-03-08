import {GppBad, LockOpen, VerifiedUser} from '@mui/icons-material';
import {Box, Button, CircularProgress, Container, Paper, Stack, Typography} from '@mui/material';
import {useModal} from "mui-modal-provider";
import React, {useState} from 'react';
import {useAccessConfiguration} from "../../hooks/useAccessConfiguration";
import {useUserIp} from "../../hooks/userIp";
import {WorkoutStates} from "../../types/AgogeStates";
import SimpleSnackbar from "../Common/SnackBar/SnackBar"

interface ComponentProps {
    buildId: string;
    safeToConfigure: boolean;
    currentState: string | number;
}

export const ConfigureAccess = ({ buildId, safeToConfigure, currentState }: ComponentProps) => {
    const userIp = useUserIp();
    const { configured, error, checkAccess, enabled } = useAccessConfiguration(buildId, userIp, safeToConfigure);
    const {showModal} = useModal();
    const [isLoading, setIsLoading] = useState<boolean>(false);

    const handleOnClick = async () => {
        setIsLoading(true);
        showModal(SimpleSnackbar, {
            message: "Checking access ...",
            severity: "info"
        })
        await checkAccess();
        setIsLoading(false);
    }

    const isBrokenOrDeleted = (): boolean => {
        return [
            WorkoutStates.BROKEN.toString(),
            WorkoutStates.DELETED.toString()
        ].includes(String(currentState));
    }

    const handleIsLoading = (): boolean => {
        if (!configured || isLoading ) {
            return true
        } else return !(!isLoading && configured);
    }

    const renderConfigureButton = () => {
        const loading = handleIsLoading();
        const brokenOrDeleted = isBrokenOrDeleted();

        if (loading && !brokenOrDeleted) {
            // loading
            return (
                <>
                    <Button
                        fullWidth
                        color={"info"}
                        variant={"outlined"}
                        startIcon={
                            handleIsLoading() ?
                                <CircularProgress size={20} color={"info"}/>
                                : <LockOpen size={20} />
                        }
                        sx={{my: 1, mx: 0}}
                        onClick={handleOnClick}
                        disabled={handleIsLoading()}
                        aria-busy={handleIsLoading() || undefined}
                    >
                        Checking...
                    </Button>
                </>
            )
        } else if (loading && brokenOrDeleted || !enabled) {
            return (
                <>
                    <Button
                        fullWidth
                        color={"info"}
                        variant={"outlined"}
                        startIcon={<LockOpen size={20} />}
                        sx={{my: 1, mx: 0}}
                        onClick={handleOnClick}
                        disabled={true}
                    >
                        Check Access
                    </Button>
                </>
            );
        } else {
            // ready
            return (
                <>
                    <Button
                        fullWidth
                        color={"info"}
                        variant={"outlined"}
                        startIcon={<LockOpen size={20} />}
                        sx={{my: 1, mx: 0}}
                        onClick={handleOnClick}
                        disabled={handleIsLoading()}
                    >
                        Check Access
                    </Button>
                </>
            );
        }
    }

    const render = () => {
        if (!enabled) {
            return (
                <>
                    <VerifiedUser fontSize="small" color={'disabled'} sx={{ mt: 0.5 }} aria-hidden />
                    <Typography component="h3" variant={'subtitle1'}>
                        This lab is available for public access
                    </Typography>
                </>
            )
        }
        if (userIp && configured) {
            return (
                <>
                    <VerifiedUser fontSize="small" color={'success'} sx={{ mt: 0.5 }} aria-hidden />
                    <Typography component="h3" variant={'subtitle1'}>
                        This lab is secured for public IP: {userIp}
                    </Typography>
                </>
            );
        } else if (!userIp) {
            return (
                <>
                    <GppBad fontSize="small" color={'warning'} sx={{ mt: 0.5 }} aria-hidden />
                    <Typography component="h3" variant={'subtitle1'}>
                        Configuring Access
                    </Typography>
                </>
            );
        } else {
            return (
                <>
                    <GppBad fontSize="small" color={'warning'} sx={{ mt: 0.5 }} aria-hidden />
                    <Typography component="h3" variant={'subtitle1'}>
                        Not authorized to connect to servers.
                    </Typography>
                </>
            );
        }
    };

    const helpText = () => {
        if (enabled) {
            return 'Servers are temporarily configured to be available ' +
                'for a finite set of IP addresses.';
        } else {
            return "Servers are operating normally without " +
                "any IP-based restrictions.";
        }
    }

    return (
        <Paper component="section" aria-labelledby="configure-access-h2" sx={{ mt: 2 }}>
            <Box p={2}>
                <Typography id="configure-access-h2" component="h2" variant="h6" sx={{ mb: 1 }}>
                    Access Configuration
                </Typography>
                <Box component="section" aria-live="polite" sx={{ mt: 1 }}>
                    <Typography
                        component="p"
                        variant="body1"
                        color={error ? 'secondary' : 'text.secondary'}
                        role={error ? 'alert' : undefined}
                        sx={{ overflow: 'auto' }}
                    >
                        {error || helpText()}
                    </Typography>
                </Box>
                <Box component="section" sx={{ mt: 1 }}>
                    {renderConfigureButton()}
                </Box>
            </Box>
        </Paper>
    );
};
