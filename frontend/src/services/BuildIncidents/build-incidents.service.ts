import {apiService} from '../api-request.service';
import {BuildAvailability, BuildEventFilters, BuildEventPage} from './build-incidents.model';

const availabilityPath = 'project/build-availability/';

export const buildIncidentsService = {
    getAvailability: () => apiService.get<BuildAvailability>(availabilityPath),
    recheckQuota: () => apiService.post<BuildAvailability>(`${availabilityPath}recheck/`, {}),
    listEvents: (filters: BuildEventFilters, cursor?: string) => apiService.get<BuildEventPage>(
        'project/build-events/', {...filters, ...(cursor ? {cursor} : {})}
    ),
};
