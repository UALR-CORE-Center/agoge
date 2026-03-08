import { CopyAll, OpenInNew } from '@mui/icons-material';
import {
    Paper,
    Typography,
    IconButton,
    Button,
    Link,
    Divider,
    Box, Tooltip
} from '@mui/material';
import Chip from "@mui/material/Chip";
import React from 'react';
import {useClipboard} from "../../../hooks/useClipboard";
import {URL_STUDENT_JOIN} from "../../../router/urls";
import {LoadingState} from "../Status/LoadingState";

interface InfoCardProps {
    type: 'unit' | 'workout';
    data: any;
}

const InfoCard: React.FC<InfoCardProps> = ({ type, data }) => {
    const {copy} = useClipboard();

    if (!data) {
        return null;
    }

    const {
        summary,
        workspace_settings,
        join_code,
        roster
    } = data;

    const totalCapacity = workspace_settings ? workspace_settings.count : 0;

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

    return (
        <Paper
            elevation={1}
            sx={{
                padding: '16px',
                marginBottom: '16px',
                width: '100%'
            }}
        >
            <Typography variant="h4" component="div" gutterBottom>
                {summary.name}
            </Typography>
            <Divider sx={{my: 2}} />
            {type === 'workout' && summary?.student_instructions_url && (
                <Button
                    variant="contained"
                    color="primary"
                    target={"_blank"}
                    href={summary.student_instructions_url}
                    sx={{ marginBottom: 1 }}
                    endIcon={<OpenInNew />}
                >
                    Instructions
                </Button>
            )}
            {type === 'unit' && summary?.teacher_instructions_url !== null && (
            <Button
                variant="contained"
                color="primary"
                target={"_blank"}
                href={summary.teacher_instructions_url}
                sx={{ marginBottom: 1 }}
                endIcon={<OpenInNew />}
            >
                Instructions
            </Button>
        )}
            <Typography variant="body1" component="div" gutterBottom>
                {summary.description}
            </Typography>
            {type === 'unit' && summary.author && (
                <Typography variant="body1" component="div" sx={{my: 1, fontWeight: 800}}>
                    Author: <Chip label={summary.author} sx={{borderRadius: 1}} size={"small"} />
                </Typography>
            )}
            {type === 'unit' && totalCapacity && (
                <Typography variant={"body1"} component="div" sx={{ display: 'flex', alignItems: 'center', fontWeight: 800 }}>
                    Capacity: <Chip label={`${roster ? roster : 0}/${totalCapacity}`} sx={{borderRadius: "4px", mx: 1 }} size={"small"}/>
                </Typography>
            )}
            {type === 'unit' && join_code && (
                <>
                    <Divider sx={{my: 2}} />
                    <Typography component="div" gutterBottom>
                        Students can join the assignment by visiting
                        <Link
                            href={URL_STUDENT_JOIN}
                            target="_blank"
                            rel="noopener noreferrer"
                            sx={{mx: .5}}
                        >
                            {`${window.location.origin}${URL_STUDENT_JOIN}`}
                        </Link> and entering the code below:
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Typography sx={{ marginRight: 2, fontWeight: 800 }}>Join Code: </Typography>
                        <Paper
                            variant="outlined"
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                padding: '0px 8px',
                            }}
                        >
                            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                {join_code}
                                <Tooltip title="Copy Join Code" arrow>
                                    <IconButton
                                        aria-label="copy join code"
                                        onClick={() => copy(join_code)}
                                    >
                                        <CopyAll />
                                    </IconButton>
                                </Tooltip>
                            </Typography>
                        </Paper>
                    </Box>
                </>
            )}
            {type === 'workout' && data.state >= 1 && data.state <= 13 && (
                <Box display="flex" alignItems="center" sx={{ padding: '16px 0' }}>
                    <LoadingState
                        label={stepLabels[data.state - 1]}
                        color={"info"}
                    />
                </Box>
            )}
        </Paper>
    );
};

export default InfoCard;
