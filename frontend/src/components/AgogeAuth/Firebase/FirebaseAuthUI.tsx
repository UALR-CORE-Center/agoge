import { Box, CircularProgress, Typography } from "@mui/material";
import { GoogleAuthProvider, EmailAuthProvider } from 'firebase/auth';
import firebase from "firebase/compat";
import * as firebaseui from "firebaseui";
import React, {useCallback, useEffect, useState} from "react";
import { useNavigate } from "react-router-dom";
import 'firebaseui/dist/firebaseui.css';

import {useAuthContext} from "../../../context/AuthContext";
import {useLocalStorage} from "../../../hooks/useLocalStorage";
import { AgogeLogo } from "../../Common/Logo";
import { auth } from "./firebaseConfig";


export const FirebaseAuthUI: React.FC = () => {
    const { agogeUser } = useAuthContext();
    const { getItem, removeItem } = useLocalStorage();
    const [redirect, setRedirect] = useState<string | null>(null);
    const navigate = useNavigate();

    const firebaseLoginWidget = useCallback((
        setRedirect: (url: string) => void
    ): firebaseui.auth.Config => {
        return {
            signInFlow: 'popup',
            signInOptions: [GoogleAuthProvider.PROVIDER_ID, EmailAuthProvider.PROVIDER_ID],
            signInSuccessUrl: '/home',
            callbacks: {
                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                signInSuccessWithAuthResult: (authResult, redirectUrl) => {
                    document.getElementById('loader')!.style.display = 'block';

                    authResult.user.getIdToken().then(async (idToken: string) => {
                        try {
                            const appUser = await agogeUser.getUser(idToken);

                            if (appUser !== undefined) {
                                document.getElementById('loader')!.style.display = 'none';

                                const redirectUrl = getItem('redirectAfterLogin') || '/';
                                removeItem('redirectAfterLogin');
                                setRedirect(redirectUrl);
                            } else {
                                throw new Error('Failed to authenticate user');
                            }
                        } catch (error: any) {
                            console.error(error.message || 'Unknown error', error);
                            document.getElementById('loader')!.style.display = 'none';
                            document.getElementById('error-msg')!.textContent = error.toString();
                            setTimeout(() => window.location.reload(), 5000);
                        }
                    });

                    return false;
                },
                uiShown: () => {
                    document.getElementById('loader')!.style.display = 'none';
                }
            }
        };
    }, []);

    useEffect(() => {
        const ui = firebaseui.auth.AuthUI.getInstance() || new firebaseui.auth.AuthUI(auth);
        const uiConfig = firebaseLoginWidget(setRedirect);
        ui.start('#firebaseui-auth-container', uiConfig);

        return () => {
            // clean up the UI instance *completely* so we don't accidentally
            // mount multiple listeners in StrictMode
            ui.reset();
        };
    }, [navigate]);

    useEffect(() => {
        if (redirect) navigate(redirect);
    }, [redirect, navigate]);

    return (
        <Box id="main" sx={{
            backgroundColor: '#ffffff',
            borderRadius: 4,
            p: 2,
            boxShadow: 3,
            maxWidth: 500,
        }}>
            <AgogeLogo contained={false} />
            <Box id="login_container" sx={{ textAlign: 'center', maxWidth: 500, mx: 'auto' }}>
                <Box id="firebaseui-auth-container"></Box>
                <Box id="loader" sx={{ display: 'none', textAlign: 'center' }}>
                    <CircularProgress />
                </Box>
                <Typography variant="body1" color="error" id="error-msg"></Typography>
            </Box>
        </Box>
    );
};
