import {apiService} from '../api-request.service';

export interface CloudQuota {
    metric: string;
    scope: string;
    usage: number;
    limit: number;
    remaining: number;
    utilization: number | null;
    level: 'normal' | 'warning' | 'critical' | 'exhausted';
}

export interface CloudQuotaReport {
    project: string;
    region: string;
    observed_at: string;
    quotas: CloudQuota[];
    unavailable_scopes?: string[];
}

export type WorkoutRuntimeSort = 'build_date' | 'student_name' | 'lab_name' | 'workout_id' | 'runtime_seconds' | 'last_seen_at' | 'run_count';

export interface WorkoutRuntimeFilters {
    month?: string;
    start?: string;
    end?: string;
    q?: string;
    sort: WorkoutRuntimeSort;
    direction: 'asc' | 'desc';
}

export interface WorkoutRuntimeRow {
    row_id: string;
    workout_id: string;
    unit_id: string | null;
    lab_name: string | null;
    student_name: string | null;
    student_email: string | null;
    runtime_seconds: number;
    run_count: number;
    build_date: string | null;
    started_at: string | null;
    last_seen_at: string | null;
    running: boolean;
}

export interface WorkoutRuntimeReport {
    month?: string | null;
    start: string;
    end: string;
    rows: WorkoutRuntimeRow[];
    total: number;
    total_workouts: number;
    total_runtime_seconds: number;
    notes: string[];
}

export interface WorkoutRuntimeMonths {
    months: {month: string; workouts: number; runtime_seconds: number; run_count: number}[];
    start: string;
    end: string;
    notes: string[];
}

const runtimePath = 'cloud-monitoring/workout-runtime/';

export const cloudMonitoringService = {
    getQuotas: () => apiService.get<CloudQuotaReport>('project/cloud-quotas/'),
    listWorkoutRuntime: (filters: WorkoutRuntimeFilters, offset: number, limit: number) =>
        apiService.get<WorkoutRuntimeReport>(runtimePath, {...filters, offset, limit}),
    listRuntimeMonths: () => apiService.get<WorkoutRuntimeMonths>(`${runtimePath}months/`),
    exportWorkoutRuntime: (filters: WorkoutRuntimeFilters) =>
        apiService.get<string>(`${runtimePath}export/`, filters),
};
