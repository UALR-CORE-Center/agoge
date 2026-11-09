import React, {useEffect, useState} from 'react';
import {BUILD_AVAILABILITY_REFRESH} from '../components/Common/Errors/HttpError';
import {useAuthContext} from '../context/AuthContext';
import {BuildAvailabilityContext} from '../context/BuildAvailabilityContext';
import {BuildAvailability} from '../services/BuildIncidents/build-incidents.model';
import {buildIncidentsService} from '../services/BuildIncidents/build-incidents.service';

export function BuildAvailabilityProvider({children}: {children: React.ReactNode}) {
    const {agogeUser, firebaseUser} = useAuthContext();
    const user = agogeUser.user;
    const staffId = user?.permissions?.instructor || user?.permissions?.admin ? firebaseUser.user?.uid : null;
    const [status, setStatus] = useState<{staffId: string; value: BuildAvailability} | null>(null);

    useEffect(() => {
        setStatus(null);
        if (!staffId) return;

        let current = true;
        let request = 0;
        const refresh = async () => {
            const requested = ++request;
            try {
                const value = await buildIncidentsService.getAvailability();
                if (current && requested === request) setStatus({staffId, value});
            } catch {
                // A failed refresh leaves the last confirmed hold in view.
            }
        };
        void refresh();
        const timer = window.setInterval(refresh, 30000);
        window.addEventListener('focus', refresh);
        window.addEventListener(BUILD_AVAILABILITY_REFRESH, refresh);
        return () => {
            current = false;
            window.clearInterval(timer);
            window.removeEventListener('focus', refresh);
            window.removeEventListener(BUILD_AVAILABILITY_REFRESH, refresh);
        };
    }, [staffId]);

    return (
        <BuildAvailabilityContext.Provider value={status?.staffId === staffId ? status?.value ?? null : null}>
            {children}
        </BuildAvailabilityContext.Provider>
    );
}
