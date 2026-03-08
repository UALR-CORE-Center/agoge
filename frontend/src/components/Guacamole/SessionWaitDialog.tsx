import React, { useEffect, useState, useCallback } from 'react';
import { Typography, Box, CircularProgress } from '@mui/material';
import { guacamoleService } from '../../services/Guacamole/guacamole.service';
import { GuacamoleSessionType } from '../../services/Guacamole/guacamole.model';
import {GuacamoleLogo} from '../Common/Logo';
import { useParams } from 'react-router-dom';

const SessionWaitDialog: React.FC = () => {
    const { buildId, serverIdx } = useParams<{ buildId: string, serverIdx: string }>();

    const [loadingMessage] = useState('Contacting Server ...');
    const [redirectMessage, setRedirectMessage] = useState('You will be redirected automatically.');
    const [errorMessage, setErrorMessage] = useState('');
    const [loading, setLoading] = useState(true);

    const calculateBackoff = (retries: number) => {
        return Math.min(3000 * Math.pow(2, retries), 60000); // Exponential backoff with a cap at 60 seconds
    };

    const displayMessage = (message: string | undefined, stopPolling: boolean) => {
        if (stopPolling) {
            setErrorMessage(message || 'Could not process request.');
            setLoading(false);
            setRedirectMessage('Contact your instructor for further assistance.');
        } else {
            setErrorMessage(`${message} Retrying...`);
        }
    };

    const pollGuacamole = useCallback(async (build_id: string | undefined) => {
        let retries = 0;
        const maxRetries = 5;

        const fetchStatus = async () => {
            try {
                const session: GuacamoleSessionType = await guacamoleService.getSession(build_id, serverIdx);
                if (session && session.url) {
                    window.location.href = guacamoleService.tokenizedUrl(session);
                } else {
                    displayMessage('Invalid session response', true);
                }
            } catch (error) {
                const err = error as { response?: { status: number } };
                if (err.response) {
                    const { status } = err.response;
                    if (status === 503) {
                        displayMessage('Service Unavailable', false);
                        setTimeout(fetchStatus, calculateBackoff(retries));
                    } else if (status === 404) {
                        displayMessage('Resource Not Found', true);
                    } else if (status === 400) {
                        displayMessage('Bad Request', true);
                    } else if (status === 500) {
                        displayMessage('Internal Server Error', true);
                    } else {
                        if (retries < maxRetries) {
                            retries++;
                            setTimeout(fetchStatus, calculateBackoff(retries));
                        } else {
                            displayMessage('Max retries exceeded. Please try again later.', true);
                        }
                    }
                } else {
                    if (retries < maxRetries) {
                        retries++;
                        setTimeout(fetchStatus, calculateBackoff(retries));
                    } else {
                        displayMessage('Max retries exceeded. Please try again later.', true);
                    }
                }
            }
        };

        await fetchStatus();
    }, [serverIdx]);

    useEffect(() => {
        pollGuacamole(buildId);
    }, [buildId, pollGuacamole]);

    return (
        <div
            id="main"
            style={{
                backgroundColor: '#1c2538',
                minHeight: "100vh",
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center'
            }}
        >
            <Box
                id="logoBox"
                sx={{
                    background: '#f5f5f5',
                    borderRadius: 1,
                    padding: 2,
                    boxShadow: 3,
                    maxWidth: '600px',
                    margin: 'auto',
                    textAlign: 'center'
                }}
            >
                <Typography sx={{ color: "black" }} variant="h4" align="center" gutterBottom>
                    Apache Guacamole
                </Typography>
                <Box display="flex" justifyContent="center">
                    <GuacamoleLogo />
                </Box>
                <Box
                    id="loading-msg-div"
                    sx={{
                        display: loading ? 'block' : 'none',
                        textAlign: 'center'
                    }}
                >
                    <Typography
                        variant="h5"
                        id="loading-msg"
                        gutterBottom
                        sx={{ color: "black" }}
                    >
                        {loadingMessage}
                    </Typography>
                    <CircularProgress />
                </Box>
                <Box id="claim-workout-div" sx={{ display: loading ? 'none' : 'block' }}>
                    {errorMessage && (
                        <Typography variant="h6" color="error" align="center" sx={{ p: 3 }}>
                            {errorMessage}
                        </Typography>
                    )}
                </Box>
                <Typography
                    align="center"
                    sx={{
                        display: loading ? 'none' : 'block',
                        color: '#6c757d',
                        p: 2
                    }}
                >
                    {redirectMessage}
                </Typography>
            </Box>
        </div>
    );
};

export default SessionWaitDialog;
