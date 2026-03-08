import ComputerIcon from "@mui/icons-material/Computer";
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {Box, Paper, Typography, Button} from '@mui/material';
import {GridColDef} from "@mui/x-data-grid";
import React from 'react';
import { WorkoutFull } from '../../services/Workout/workout.model';
import { WorkoutConnectButton } from "../Buttons/ConnectButton/WorkoutConnectButton";
import {ExpandableCell} from "../Common/DataGrid/ExpandableCell";
import StyledDataGrid from "../Common/DataGrid/StyledDataGrid";

interface WorkoutTableProps {
    workoutFull: WorkoutFull;
}

const WorkoutTable: React.FC<WorkoutTableProps> = ({ workoutFull }) => {
    const servers =
        workoutFull?.workout?.servers
            ?.filter(server => !server.hidden)
            ?.filter(server => !server.dns_hostname)
        || [];
    const sortedServers = servers.sort((a, b) => {
        const nameA = a.name?.toString() || '';
        const nameB = b.name?.toString() || '';
        return nameA.localeCompare(nameB);
    });
    const processedServers = sortedServers.map((server: any, index: number) => ({
        ...server,
        index,
        internal_ip: server.nics?.[0]?.internal_ip || '',
        state: workoutFull?.workout.state,
        id: server.name,
    }));

    const columns: GridColDef[] = [
        {
            field: 'connect',
            headerName: 'Connection',
            minWidth: 175,
            headerAlign: 'center',
            renderCell: (params: any) => (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    width: '100%',
                }}>
                    <WorkoutConnectButton
                        item={params.row}
                        buildId={workoutFull.workout.id}
                        serverIdx={params.row.index.toString()}
                        addGuacamole={true}
                    />
                </Box>
            )
        },
        {
            field: 'name',
            headerName: 'Server Name',
            minWidth: 175,
            headerAlign: 'center',
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                />
            )
        },
        {
            field: 'hostname',
            headerName: 'Host',
            headerAlign: 'center',
            minWidth: 350,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                />
            )
        },
        {
            field: 'internal_ip',
            headerName: 'IP',
            headerAlign: 'center',
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.value}
                    variant={"body1"}
                />
            )
        }
    ];
    return (
        <Box sx={{ width:"100%", display: 'flex', flexDirection: 'row'}}>
            <Box sx={{ width: workoutFull.workout.web_applications ? "65%": "100%" }}>
                <Paper
                    elevation={1}
                    component="section"
                    sx={{ p: 1 }}
                >
                    <StyledDataGrid
                        data={processedServers}
                        columns={columns}
                        disableMultiRowSelection={true}
                        disableSelectBtn={true}
                        disableCheckBoxes={true}
                        labelProps={{
                            text: "Servers",
                            icon: <ComputerIcon fontSize={"large"}/>,
                        }}
                        density={"compact"}
                    />
                </Paper>
            </Box>
            {workoutFull.workout?.web_applications && (
                <Box sx={{ width: "35%", justifyContent: "center", display: "flex", ml: 2, mr: 2 }}>
                    <Paper
                        component="section"
                        aria-labelledby="web-apps-h2"
                        elevation={1}
                        sx={{
                            width: "100%",
                            justifyContent: "center",
                            display: "flex",
                            alignItems: "center",
                            flexDirection: "column",
                            p: 2,
                        }}
                    >
                        <Typography
                            id="web-apps-h2"
                            variant="h5"
                            component="h2"
                            sx={{ mb: 4 }}
                        >
                            Web Applications
                        </Typography>

                        {workoutFull.workout.web_applications.map((app, index) => (
                            <Button
                                component="a"
                                variant="contained"
                                color="primary"
                                target="_blank"
                                rel="noopener noreferrer"
                                href={app.url as unknown as string}
                                sx={{ mb: 2 }}
                                endIcon={<OpenInNewIcon />}
                            >
                                {app.name || "Web App"}
                            </Button>
                        ))}
                    </Paper>
                </Box>
            )}
        </Box>
    );
};

export default WorkoutTable;
