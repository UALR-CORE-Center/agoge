import { Box, CircularProgress, FormControl, TextField, Typography, useTheme } from '@mui/material';
import Button from "@mui/material/Button";
import React, { FormEvent, useState } from 'react';
import { Navigate, Form } from "react-router-dom";
import { URL_STUDENT_WORKOUT } from "../../router/urls";
import { workoutService } from "../../services/Workout/workout.service";
import { AgogeLogo } from "../Common/Logo";

const JoinWorkout: React.FC = () => {
    const theme = useTheme();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [redirect, setRedirect] = useState(false);
    const [buildId, setBuildId] = useState<string | null>(null);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setLoading(true);
        setError(null);
        const formData = new FormData(event.currentTarget);
        const formObject = Object.fromEntries(formData.entries());

        try {
            const resp = await workoutService.post(formObject);
            if (resp?.build_id && !resp?.exists) {
                setBuildId(resp.build_id);
                await poll(resp.build_id);
            } else if (resp?.build_id && resp?.exists) {
                setBuildId(resp.build_id);
                setRedirect(true);
            }
        } catch (error: any) {
            if (error?.detail) {
                setError(error.detail);
            } else {
                setError('An error occurred during submission.');
            }
            setLoading(false);
        }
    };

    const poll = async (buildId: string, maxErrors = 10) => {
        let errorCount = 0;

        const fetchAndCheck = async () => {
            try {
                const data = await workoutService.get_state(buildId);

                if (data?.state && Number(data.state) >= 0) {
                    setRedirect(true);
                } else {
                    setTimeout(fetchAndCheck, 3000);
                }
            } catch (error) {
                console.error('Error during fetch:', error);
                errorCount++;
                if (errorCount >= maxErrors) {
                    setError('No build found for given ID');
                    setLoading(false);
                } else {
                    console.log('Retrying in 3 seconds...');
                    setTimeout(fetchAndCheck, 3000);
                }
            }
        };

        fetchAndCheck();
    };

    return (
        <Box
            id="homePage"
            component="main"
            aria-labelledby="join-h1"
            sx={{
                backgroundColor: '#1c2538',
                height: '100vh',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                color: 'black'
            }}
        >
            <Box id="main" sx={{
                backgroundColor: '#ffffff',
                borderRadius: 4,
                p: 2,
                boxShadow: 3,
                maxWidth: 500,
            }}>
                <AgogeLogo contained={false}/>
                <Box id="claim-container" sx={{ textAlign: 'center', maxWidth: 500, mx: 'auto' }}>
                    {loading ? (
                        <Box id="loader" role="status" aria-live="polite" sx={{ textAlign: 'center' }}>
                            <CircularProgress aria-label="Loading" />
                            <Typography variant="h6">Finding your lab ...</Typography>
                            <Typography>This could take a few minutes.</Typography>
                        </Box>
                    ) : (
                        <Box id="claim-form-container">
                            <Typography id="join-h1" component="h1" variant="h5" sx={{ mb: 1 }}>
                                Claim Your Lab
                            </Typography>
                            <Form onSubmit={handleSubmit} aria-labelledby="join-h1" aria-busy={loading || undefined}>
                                <FormControl fullWidth required margin="normal">
                                    <TextField
                                        required
                                        size="small"
                                        id="join-code"
                                        name="join_code"
                                        label="Join Code"
                                        type="text"
                                        autoComplete="one-time-code"
                                        slotProps={{
                                            inputLabel: {
                                                style: { color: '#1c2538' }
                                            },
                                            input: {
                                                sx: {
                                                    color: 'black',
                                                    borderColor: '#1c2538',
                                                }
                                            }
                                        }}
                                        sx={{
                                            color: 'black',
                                            '& .MuiOutlinedInput-root': {
                                                '& fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                                '&:hover fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                                '&.Mui-focused fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                            }
                                        }}
                                    />
                                </FormControl>
                                <FormControl required fullWidth>
                                    <TextField
                                        required
                                        id="email"
                                        name="input_email"
                                        label="Email"
                                        type="email"
                                        size="small"
                                        helperText="We'll never share your email with anyone else."
                                        autoComplete="email"
                                        slotProps={{
                                            formHelperText: {
                                                style: { color: '#1c2538' }
                                            },
                                            inputLabel: {
                                                style: { color: '#1c2538' }
                                            },
                                            input: {
                                                sx: {
                                                    color: 'black',
                                                    borderColor: '#1c2538',
                                                }
                                            }
                                        }}
                                        sx={{
                                            '& .MuiOutlinedInput-root': {
                                                '& fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                                '&:hover fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                                '&.Mui-focused fieldset': {
                                                    borderColor: '#1c2538',
                                                },
                                            }
                                        }}
                                    />
                                </FormControl>
                                <Button
                                    type="submit"
                                    variant="contained"
                                    sx={{
                                        mt: 3,
                                        width: '50%',
                                        backgroundColor: '#1c2538',
                                        color: 'white',
                                        '&:hover': { backgroundColor: '#39455e' },
                                    }}
                                    disabled={loading}
                                >
                                    {loading ? "Submitting…" : "Submit"}
                                </Button>
                            </Form>
                        </Box>
                    )}
                    {error && (
                        <Typography
                            role="alert"
                            variant="body1"
                            color="error"
                            id="error-msg"
                            sx={{ mt: 2 }}
                        >
                            {error}
                        </Typography>
                    )}
                </Box>
            </Box>
            {redirect && buildId && (
                <Navigate to={`${URL_STUDENT_WORKOUT}/${buildId}`} />
            )}
        </Box>
    );
};

export default JoinWorkout;
