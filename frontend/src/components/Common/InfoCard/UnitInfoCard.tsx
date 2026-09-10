import {CopyAll, OpenInNew} from "@mui/icons-material";
import {Box, Button, Divider, IconButton, Link, Paper, Tooltip, Typography} from "@mui/material";
import Chip from "@mui/material/Chip";
import React from "react";
import {useClipboard} from "../../../hooks/useClipboard";
import {URL_STUDENT_JOIN} from "../../../router/urls";
import {absoluteUrl} from "../../../utilities/appContext";

interface UnitInfoCardProps {
    data: any;
    isLoading?: boolean;
}

export const UnitInfoCard: React.FC<UnitInfoCardProps> = (props) => {
    const {copy} = useClipboard();
    const {summary, workspace_settings, join_code, roster, wireguard_endpoint} = props.data;
    const totalCapacity = workspace_settings ? workspace_settings.count : 0;
    const joinUrl = absoluteUrl(URL_STUDENT_JOIN);
    return (
        <>
            <Paper
                elevation={1}
                component="section"
                aria-labelledby="unit-info-h2"
                sx={{
                    padding: '16px',
                    marginBottom: '16px',
                    width: '100%'
                }}
            >
                <Typography id="unit-info-h2" variant="h4" component="h2" gutterBottom>
                    {summary.name}
                </Typography>

                <Divider sx={{my: 2}} />

                {summary?.teacher_instructions_url !== null && (
                    <Button
                        component="a"
                        variant="contained"
                        color="primary"
                        target={"_blank"}
                        href={absoluteUrl(`/documents/${summary.teacher_instructions_url}`)}
                        sx={{ marginBottom: 1 }}
                        endIcon={<OpenInNew />}
                    >
                        Instructions
                    </Button>
                )}

                <Typography variant="body1" component="p" gutterBottom>
                    {summary.description}
                </Typography>

                {summary.author && (
                    <Typography variant="body1" component="p" sx={{my: 1, fontWeight: 800}}>
                        Author: <Chip label={summary.author} sx={{borderRadius: 1}} size={"small"} />
                    </Typography>
                )}

                {totalCapacity ? (
                    <Typography
                        variant="body1"
                        component="p"
                        sx={{ display: 'flex', alignItems: 'center', fontWeight: 800 }}
                    >
                        Capacity:{' '}
                        <Chip
                            label={`${roster ? roster : 0}/${totalCapacity}`}
                            sx={{ borderRadius: '4px', mx: 1 }}
                            size="small"
                        />
                    </Typography>
                ) : null}

                {join_code && (
                    <Box component="section" aria-labelledby="join-code-h3" sx={{ mt: 2 }}>
                        <Divider sx={{ my: 2 }} />
                        <Typography
                            id="join-code-h3"
                            component="h3"
                            variant="subtitle1"
                            gutterBottom
                            sx={{
                                position: 'absolute',
                                width: 1,
                                height: 1,
                                p: 0,
                                m: -1,
                                overflow: 'hidden',
                                clip: 'rect(0 0 0 0)',
                                whiteSpace: 'nowrap',
                                border: 0,
                            }}
                        >
                            How students join
                        </Typography>

                        <Typography component="p" gutterBottom>
                            Students can join the assignment by visiting{' '}
                            <Link
                                href={joinUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                sx={{ mx: 0.5 }}
                            >
                                {joinUrl}
                            </Link>{' '}
                            and entering the code below:
                        </Typography>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography component="p" sx={{ fontWeight: 800, m: 0 }}>
                                Join Code:
                            </Typography>

                            <Paper
                                variant="outlined"
                                sx={{ display: 'flex', alignItems: 'center', px: 1 }}
                                aria-label="Join code container"
                            >
                                <Typography
                                    variant="h6"
                                    component="span"
                                    sx={{ flexGrow: 1, fontFamily: 'monospace' }}
                                >
                                    {join_code}
                                </Typography>

                                <Tooltip title="Copy Join Code" leaveDelay={200} arrow describeChild>
                <span>
                  <IconButton
                      aria-label="Copy join code"
                      onClick={() => copy(join_code)}
                  >
                    <CopyAll />
                  </IconButton>
                </span>
                                </Tooltip>
                            </Paper>
                        </Box>
                    </Box>
                )}

                {wireguard_endpoint && (
                    <Box component="section" aria-labelledby="wireguard-endpoint-h3" sx={{ mt: 2 }}>
                        <Divider sx={{ my: 2 }} />
                        <Typography
                            id="wireguard-endpoint-h3"
                            component="h3"
                            variant="subtitle1"
                            sx={{ fontWeight: 800 }}
                            gutterBottom
                        >
                            WireGuard Gateway
                        </Typography>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <Typography component="p" sx={{ fontWeight: 800, m: 0 }}>
                                Endpoint ID:
                            </Typography>
                            <Paper
                                variant="outlined"
                                sx={{ display: 'flex', alignItems: 'center', px: 1 }}
                                aria-label="WireGuard endpoint ID container"
                            >
                                <Typography component="span" sx={{ fontFamily: 'monospace' }}>
                                    {wireguard_endpoint.id}
                                </Typography>
                                <Tooltip title="Copy WireGuard Endpoint ID" leaveDelay={200} arrow describeChild>
                                    <span>
                                        <IconButton
                                            aria-label="Copy WireGuard endpoint ID"
                                            onClick={() => copy(wireguard_endpoint.id)}
                                        >
                                            <CopyAll />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Paper>
                            <Chip
                                label={wireguard_endpoint.status}
                                color={wireguard_endpoint.status === 'active' ? 'success' : 'default'}
                                size="small"
                            />
                        </Box>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography component="p" sx={{ fontWeight: 800, m: 0 }}>
                                Endpoint:
                            </Typography>
                            <Typography component="span" sx={{ fontFamily: 'monospace', overflowWrap: 'anywhere' }}>
                                {wireguard_endpoint.hostname}:{wireguard_endpoint.port}
                            </Typography>
                            <Tooltip title="Copy WireGuard Endpoint" leaveDelay={200} arrow describeChild>
                                <span>
                                    <IconButton
                                        aria-label="Copy WireGuard endpoint"
                                        onClick={() => copy(`${wireguard_endpoint.hostname}:${wireguard_endpoint.port}`)}
                                    >
                                        <CopyAll />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </Box>
                    </Box>
                )}
            </Paper>
        </>
    )
}
