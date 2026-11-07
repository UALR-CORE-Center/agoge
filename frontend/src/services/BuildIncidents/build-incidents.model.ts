export interface QuotaHold {
    id: string;
    project: string;
    metric: string;
    incident_id?: string | null;
    scope: string;
    limit?: number | null;
    usage?: number | null;
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    verified_at?: string | null;
}

export interface BuildAvailability {
    hold: QuotaHold | null;
    support_contact?: string | null;
    quota?: {usage: number; limit: number};
}

export interface BuildIncident {
    id: string;
    unit_id: string | null;
    workout_id?: string | null;
    project?: string | null;
    stage: string;
    reason: string;
    metric?: string | null;
    limit_name?: string | null;
    limit?: number | null;
    scope?: string | null;
    occurred_at: string;
    last_seen_at?: string | null;
    status: 'open' | 'resolved';
    kind: 'build_failure' | 'build_blocked' | 'cleanup_failed';
    operation_id?: string | null;
    resource?: string | null;
}

export interface BuildIncidentPage {
    incidents: BuildIncident[];
    next_cursor?: string | null;
}

export const quotaHoldMessage = 'New labs that need a Google Cloud network are paused.';

export function quotaLabel(quota: Pick<QuotaHold, 'scope' | 'metric' | 'limit'>) {
    const limit = quota.limit == null ? '' : ` (limit ${quota.limit})`;
    return `${quota.scope} ${quota.metric}${limit}`;
}
