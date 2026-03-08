import {OpenInNew} from "@mui/icons-material";
import {Box, Button, Divider, Paper, Typography} from "@mui/material";
import React, {useEffect, useState} from "react";
import {LoadingState} from "../Status/LoadingState";
import {absoluteUrl} from "../../../utilities/appContext";

interface WorkoutInfoCardProps {
    buildId: string;
    data: any;
    isLoading: boolean;
}

export const WorkoutInfoCard: React.FC<WorkoutInfoCardProps> = (props) => {
    const [currentState, setCurrentState] = useState<string|null>("");

    const {summary} = props.data;
    const stepLabels = [
        'Building Assessment',
        'Building Networks',
        'Completed Networks',
        'Building Servers',
        'Completed Servers',
        'Building Firewall',
        'Completed Firewall',
        'Building Routes',
        'Completed Routes',
        'Building Firewall Rules',
        'Completed Firewall Rules',
        'Building Student Entry',
        'Completed Student Entry',
    ];

    useEffect(() => {
        const state = props.data?.state;
        if (state && state >= 1 && state < 13) {
            setCurrentState(stepLabels[state - 1])
        } else {
            setCurrentState("");
        }
    }, [props.data]);

    const getInstructionsUrl = (instructions_url: string) => {
        try {
            return new URL(instructions_url).toString();
        } catch (err) {
            return absoluteUrl(`/documents/${instructions_url}`);
        }
    }

    return (
        <Paper
            component="section"
            aria-labelledby="workout-info-h2"
            elevation={1}
            sx={{
                padding: '16px',
                marginBottom: '16px',
                width: '100%'
            }}
        >
            <Typography id="workout-info-h2" variant="h4" component="h2" gutterBottom>
                {summary.name}
            </Typography>
            <Divider sx={{my: 2}} />
            {summary?.student_instructions_url !== null && (
                <Button
                    component={"a"}
                    variant="contained"
                    color="primary"
                    target={"_blank"}
                    href={getInstructionsUrl(summary.student_instructions_url)}
                    sx={{ marginBottom: 1 }}
                    endIcon={<OpenInNew />}
                >
                    Instructions
                </Button>
            )}
            <Typography variant="body1" component="p" gutterBottom>
                {summary.description}
            </Typography>
            {currentState ? (
                <Box
                    component="section"
                    aria-label="Build status"
                    sx={{ padding: '16px 0' }}
                >
                    <Box role="status" aria-live="polite">
                        <LoadingState label={currentState} color="info" />
                    </Box>
                </Box>
            ) : null}
        </Paper>
    );
}