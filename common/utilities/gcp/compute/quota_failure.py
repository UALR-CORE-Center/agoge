"""Normalize the quota information exposed by Compute without retaining raw payloads."""

import math
import re
from collections.abc import Mapping

from common.exceptions import ResourceExhausted


_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,255}')
_LOCATION = re.compile(r'[a-z][a-z0-9-]*[0-9](?:-[a-z])?')
_QUOTA_MESSAGE = re.compile(
    r"(?:\bQUOTA_EXCEEDED:\s*)?\bQuota ['\"](?P<metric>[A-Za-z0-9_./-]{1,150})['\"] exceeded\."
    r"\s+Limit:\s*(?P<limit>[0-9]{1,18}(?:\.[0-9]{1,10})?)"
    r"(?:\s+(?P<scope>globally|in (?:region|zone) ['\"]?[a-z0-9-]+['\"]?))?(?=\.(?:\s|$)|$)",
    re.IGNORECASE,
)
_REASONS = {
    'QUOTAEXCEEDED': ('allocation', 'QUOTA_EXCEEDED'),
    'RATELIMITEXCEEDED': ('rate', 'RATE_LIMIT_EXCEEDED'),
    'USERRATELIMITEXCEEDED': ('rate', 'USER_RATE_LIMIT_EXCEEDED'),
    'CONCURRENTOPERATIONSQUOTAEXCEEDED': ('rate', 'CONCURRENT_OPERATIONS_QUOTA_EXCEEDED'),
    'RESOURCEEXHAUSTED': ('unknown', 'RESOURCE_EXHAUSTED'),
}
_CONTEXT_FIELDS = ('project', 'operation_id', 'operation_type', 'resource_type', 'resource', 'action')
_DIMENSION_FIELDS = ('zone', 'region', 'location', 'machine_family', 'machineFamily', 'operationType')


def _field(value, *names):
    for name in names:
        item = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
        if item not in (None, ''):
            # Compute's proto-plus messages expose default scalars for fields absent from the response.
            if hasattr(type(value), 'pb') and name not in value:
                continue
            return item
    return None


def _identifier(value):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


def _limit(value):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or not 0 <= number < 2**63:
        return None
    return int(number) if number.is_integer() else number


def _scope(value):
    if not isinstance(value, str):
        return None
    name = value.rsplit('/', 1)[-1].strip("'\"").lower()
    if name in ('global', 'globally'):
        return 'global'
    return name if len(name) <= 64 and _LOCATION.fullmatch(name) else None


def _reason(value):
    return _REASONS.get(value.replace('_', '').upper()) if isinstance(value, str) else None


class ComputeQuotaFailure(ResourceExhausted):
    """A sanitized quota or throttling error with the operation's request context."""

    def __init__(
        self, *, category, reason, metric=None, limit_name=None, limit=None, scope=None, dimensions=None, **context,
    ):
        self.category = category
        self.reason = reason
        self.metric = _identifier(metric)
        self.limit_name = _identifier(limit_name)
        self.limit = _limit(limit)
        self.scope = _scope(scope)
        self.dimensions = {
            key: value for key in _DIMENSION_FIELDS if (value := _identifier(_field(dimensions, key)))
        }
        if ((self.metric or '').lower() in ('networks', 'compute.googleapis.com/networks')
                or (not self.metric and (self.limit_name or '').lower() == 'networks-per-project')):
            self.metric = 'NETWORKS'
        for field in _CONTEXT_FIELDS:
            setattr(self, field, None)
        self.add_context(**context)
        name = self.metric or self.limit_name
        details = [part for part in (
            f'quota {name}' if name else None,
            f'limit {self.limit}' if self.limit is not None else None,
            self.scope,
        ) if part]
        super().__init__(f'{self.reason}: {", ".join(details)}' if details else self.reason)

    def add_context(self, **context):
        for field in _CONTEXT_FIELDS:
            if not getattr(self, field):
                setattr(self, field, _identifier(context.get(field)))
        if self.metric == 'NETWORKS' and self.operation_type == 'GLOBAL' and not self.scope:
            self.scope = 'global'

    def as_dict(self):
        fields = ('category', 'reason', 'metric', 'limit_name', 'limit', 'scope', 'dimensions', *_CONTEXT_FIELDS)
        return {field: getattr(self, field) for field in fields}


def _normalize(records, details, message, status, **context):
    """Use recognized provider codes and allowlisted quota fields only."""
    error_info = [_field(detail, 'error_info', 'errorInfo') or detail for detail in details]
    quota_info = [_field(detail, 'quota_info', 'quotaInfo') for detail in details]
    quota_info.extend(violation for detail in details for violation in (_field(detail, 'violations') or ()))
    reasons = [_field(record, 'reason', 'code') for record in (*error_info, *records)]
    if isinstance(message, str):
        reasons.append(message[:64].split(':', 1)[0])
    classifications = [classification for reason in reasons if (classification := _reason(reason))]
    rate = next((item for item in classifications if item[0] == 'rate'), None)
    allocation = next((item for item in classifications if item[0] == 'allocation'), None)
    quota = next((info for info in quota_info if info), None)
    metadata = next((metadata for info in error_info if _reason(_field(info, 'reason'))
                     and (metadata := _field(info, 'metadata', 'metadatas'))), None)
    dimensions = _field(quota, 'dimensions', 'quota_dimensions', 'quotaDimensions')
    metric = (_field(quota, 'metric_name', 'metricName', 'quota_metric', 'quotaMetric')
              or _field(metadata, 'quota_metric', 'quotaMetric'))
    limit_name = (_field(quota, 'limit_name', 'limitName', 'quota_id', 'quotaId')
                  or _field(metadata, 'quota_limit', 'quotaLimit'))
    limit = _field(quota, 'limit', 'quota_value', 'quotaValue')
    if limit is None:
        limit = _field(metadata, 'quota_limit_value', 'quotaLimitValue')
    scope = (_field(dimensions, 'zone', 'region', 'location')
             or _field(metadata, 'quota_location', 'quotaLocation', 'location'))
    quota_message = next(
        (match for value in [*(_field(record, 'message') for record in records), message]
         if isinstance(value, str) and (match := _QUOTA_MESSAGE.search(value[:1024]))), None,
    )
    if quota_message:
        metric = metric or quota_message['metric']
        if limit is None:
            limit = quota_message['limit']
        scope = scope or (quota_message['scope'] or '').rsplit(' ', 1)[-1]
    classification = rate or allocation
    if not classification and (quota or quota_message):
        classification = ('allocation', 'QUOTA_EXCEEDED')
    if not classification and any(isinstance(value, str) and 'RESOURCE_POOL_EXHAUSTED' in value
                                  for value in (*reasons, message)):
        return None
    if not classification and (status == 429 or classifications):
        classification = ('unknown', 'RESOURCE_EXHAUSTED')
    if classification:
        category, reason = classification
        return ComputeQuotaFailure(
            category=category, reason=reason, metric=metric, limit_name=limit_name, limit=limit,
            scope=scope, dimensions=dimensions, **context,
        )
    return None


def classify_compute_api_error(error, **context):
    """Handle errors raised directly by the Google API client."""
    # google-api-core exposes typed ErrorInfo through reason and metadata properties.
    details = [*(_field(error, 'details') or ()), error]
    return _normalize(
        tuple(_field(error, 'errors') or ()), details, _field(error, 'message'), _field(error, 'code'), **context,
    )


def classify_compute_operation_error(operation, **context):
    """Handle structured errors returned inside a completed operation."""
    records = tuple(_field(_field(operation, 'error'), 'errors') or ())
    details = [detail for record in records for detail in (_field(record, 'error_details', 'errorDetails') or ())]
    return _normalize(
        records, details, _field(operation, 'http_error_message', 'httpErrorMessage'),
        _field(operation, 'http_error_status_code', 'httpErrorStatusCode'), **context,
    )
