import {Alert, AlertTitle, Button, Stack, Typography} from '@mui/material';
import React from 'react';
import {Link} from 'react-router-dom';
import {useAuthContext} from '../../context/AuthContext';
import {useBuildAvailability} from '../../context/BuildAvailabilityContext';
import {useClipboard} from '../../hooks/useClipboard';
import {URL_ADMIN_BASE} from '../../router/urls';
import {QuotaHold, quotaHoldMessage, quotaLabel} from '../../services/BuildIncidents/build-incidents.model';

export default function ProjectQuotaBanner() {
    const availability = useBuildAvailability();
    return availability?.hold ? <QuotaWarning hold={availability.hold} supportContact={availability.support_contact} /> : null;
}

function QuotaWarning({hold, supportContact}: {hold: QuotaHold; supportContact?: string | null}) {
    const {agogeUser} = useAuthContext();
    const {copy} = useClipboard();
    const isAdmin = agogeUser.user?.permissions.admin;
    const quota = quotaLabel(hold);
    return (
        <Alert severity="warning" sx={{width: '100%', mb: 2, '& .MuiAlert-message': {width: '100%'}}}>
            <AlertTitle>{quotaHoldMessage}</AlertTitle>
            <Typography variant="body2">
                This project reached its {quota} quota. Existing labs remain available for use and cleanup.
                {!isAdmin && ` Contact ${supportContact || 'your Agoge administrator'}.`}
            </Typography>
            <Stack direction="row" sx={{gap: 1, flexWrap: 'wrap', mt: 1}}>
                {isAdmin && <Button component={Link} to={`${URL_ADMIN_BASE}?view=cloudMonitoring`} color="inherit" size="small">
                    View Cloud Monitoring
                </Button>}
                <Button color="inherit" size="small" onClick={() => copy([
                    quotaHoldMessage, `Project: ${hold.project}`, `Quota: ${quota}`, `Hold ID: ${hold.id}`,
                    hold.incident_id && `Incident ID: ${hold.incident_id}`,
                ].filter(Boolean).join('\n'))}>
                    Copy quota report
                </Button>
            </Stack>
        </Alert>
    );
}
