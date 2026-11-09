import React from 'react';
import { Box, ToggleButton, ToggleButtonGroup, Paper } from '@mui/material';
import {useSearchParams} from "react-router-dom";
import BuildLogPanel from "./BuildLogPanel";
import CloudMonitoringPanel from "./CloudMonitoringPanel";
import UnitManagerTab from "./UnitManager";
import WorkoutManagerTab from "./WorkoutManager";
import {WireGuardRemotePeerManager} from "./WireGuard/WireGuardKitManager";

const views: Record<string, {label: string; panel: React.ReactElement}> = {
    activeUnits: {label: 'Active Units', panel: <UnitManagerTab viewType="active" />},
    allUnits: {label: 'All Units', panel: <UnitManagerTab viewType="all" />},
    activeWorkouts: {label: 'Active Workouts', panel: <WorkoutManagerTab viewType="active" />},
    allWorkouts: {label: 'All Workouts', panel: <WorkoutManagerTab viewType="all" />},
    wireguardRemotePeers: {label: 'Remote Labs', panel: <WireGuardRemotePeerManager />},
    buildLog: {label: 'Build Log', panel: <BuildLogPanel />},
    cloudMonitoring: {label: 'Cloud Monitoring', panel: <CloudMonitoringPanel />},
};

const ProjectOverviewTabs: React.FC = () => {
    const [params, setParams] = useSearchParams();
    const requestedView = params.get('view') || '';
    const view = requestedView === 'incidents' ? 'buildLog'
        : Object.hasOwn(views, requestedView) ? requestedView : 'activeUnits';

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
                {Object.entries(views).map(([value, {label}]) => <ToggleButton key={value} value={value}>{label}</ToggleButton>)}
            </ToggleButtonGroup>
            <Paper elevation={1} sx={{width:'100%', minWidth: 0}}>
                {views[view].panel}
            </Paper>
        </Box>
    );
};

export default ProjectOverviewTabs;
