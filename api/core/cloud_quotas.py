from datetime import datetime, timezone
from math import isfinite

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import compute_v1
from requests.exceptions import RequestException

from common.utilities.gcp.cloud_logger import Logger, LoggerNames


_READ_TIMEOUT_SECONDS = 5
_GLOBAL_METRICS = frozenset({
    'NETWORKS', 'FIREWALLS', 'ROUTES', 'CPUS_ALL_REGIONS', 'IMAGES', 'SNAPSHOTS',
})
_REGIONAL_METRICS = frozenset({
    'CPUS', 'E2_CPUS', 'N2_CPUS', 'INSTANCES', 'IN_USE_ADDRESSES',
    'STATIC_ADDRESSES', 'DISKS_TOTAL_GB', 'SSD_TOTAL_GB',
})

logger = Logger(LoggerNames.API)


def _quota_row(quota: compute_v1.Quota, scope: str) -> dict | None:
    # The proto returns 0.0 for absent numeric fields, so check presence first.
    if 'usage' not in quota or 'limit' not in quota:
        return None
    usage, limit = quota.usage, quota.limit
    if not (isfinite(usage) and isfinite(limit) and usage >= 0 and limit >= 0):
        return None
    utilization = usage / limit if limit else None
    if utilization is not None and not isfinite(utilization):
        return None
    if usage >= limit:
        level = 'exhausted'
    elif utilization >= 0.9:
        level = 'critical'
    elif utilization >= 0.8:
        level = 'warning'
    else:
        level = 'normal'
    return {
        'metric': quota.metric,
        'scope': scope,
        'usage': usage,
        'limit': limit,
        'remaining': max(limit - usage, 0),
        'utilization': utilization,
        'level': level,
    }


def read_cloud_quotas(project: str, region: str) -> dict:
    """Read the deployment's lab-related Compute allocation quotas."""
    quotas = []
    unavailable_scopes = []
    for scope, metrics, client_type, location in (
        ('global', _GLOBAL_METRICS, compute_v1.ProjectsClient, {}),
        (region, _REGIONAL_METRICS, compute_v1.RegionsClient, {'region': region}),
    ):
        try:
            with client_type() as client:
                result = client.get(project=project, **location, retry=None, timeout=_READ_TIMEOUT_SECONDS)
        except (GoogleAPIError, GoogleAuthError, RequestException) as error:
            logger.warning('Could not read Google Cloud quotas.', project=project, scope=scope,
                           error_type=type(error).__name__)
            unavailable_scopes.append(scope)
            continue
        rows = [
            row for quota in result.quotas
            if quota.metric in metrics and (row := _quota_row(quota, scope)) is not None
        ]
        if rows:
            quotas.extend(sorted(rows, key=lambda row: row['metric']))
        else:
            unavailable_scopes.append(scope)

    snapshot = {
        'project': project,
        'region': region,
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'quotas': quotas,
    }
    if unavailable_scopes:
        snapshot['unavailable_scopes'] = unavailable_scopes
    return snapshot
