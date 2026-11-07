import {apiService} from '../api-request.service';
import {BuildAvailability, BuildIncidentPage} from './build-incidents.model';

const availabilityPath = 'project/build-availability/';

export const buildIncidentsService = {
    getAvailability: () => apiService.get<BuildAvailability>(availabilityPath),
    recheckQuota: () => apiService.post<BuildAvailability>(`${availabilityPath}recheck/`, {}),
    list: (includeResolved: boolean, cursor?: string) => apiService.get<BuildIncidentPage>(
        'project/build-incidents/',
        {include_resolved: includeResolved, ...(cursor ? {cursor} : {})}
    ),
};
