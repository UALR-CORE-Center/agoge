import React from 'react';
import { Box, ToggleButton, ToggleButtonGroup, Paper } from '@mui/material';
import {useSearchParams} from "react-router-dom";
import BuildIncidentsPanel from "./BuildIncidentsPanel";
import UnitManagerTab from "./UnitManager";
import WorkoutManagerTab from "./WorkoutManager";
import {WireGuardRemotePeerManager} from "./WireGuard/WireGuardKitManager";

const ProjectOverviewTabs: React.FC = () => {
    const [params, setParams] = useSearchParams();
    const view = params.get('view') || 'activeUnits';

    const handleViewChange = (_event: React.MouseEvent<HTMLElement>, newView: string) => {
        if (newView) {
            setParams(previous => {
                const next = new URLSearchParams(previous);
                next.set('view', newView);
                return next;
            });
        }
    };

    return (
        <Box
            id="homePage"
            sx={{
                height: '100%',
                display: 'flex',
                width: { xs: '100%', md: '90%' },
                minWidth: 0,
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
            }}
        >
            <ToggleButtonGroup
                color="primary"
                value={view}
                exclusive
                onChange={handleViewChange}
                sx={{
                    marginBottom: 2,
                    flexWrap: 'wrap',
                    justifyContent: 'center',
                    maxWidth: '100%',
                }}
            >
                <ToggleButton value="activeUnits">Active Units</ToggleButton>
                <ToggleButton value="allUnits">All Units</ToggleButton>
                <ToggleButton value="activeWorkouts">Active Workouts</ToggleButton>
                <ToggleButton value="allWorkouts">All Workouts</ToggleButton>
                <ToggleButton value="wireguardRemotePeers">Remote Labs</ToggleButton>
                <ToggleButton value="incidents">Incidents</ToggleButton>
            </ToggleButtonGroup>
            <Paper elevation={1} sx={{width:'100%', minWidth: 0}}>
                {view === 'incidents' ? <BuildIncidentsPanel /> : view === 'wireguardRemotePeers' ? <WireGuardRemotePeerManager /> : view === 'activeUnits' || view === 'allUnits' ? (
                    <UnitManagerTab key="unitManager" viewType={view === 'activeUnits' ? 'active' : 'all'} />
                ) : (
                    <WorkoutManagerTab viewType={view === 'activeWorkouts' ? 'active' : 'all'} />
                )}
            </Paper>
        </Box>
    );
};

export default ProjectOverviewTabs;
