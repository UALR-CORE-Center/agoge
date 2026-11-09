from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from common.exceptions import BadRequest
from common.models.response import AgogeResponse
from common.models.users import AgogeUser

from core.cloud_monitoring import CloudMonitoring
from dependencies import admin_required


cloud_monitoring_router = APIRouter(prefix='/cloud-monitoring')
RuntimeSort = Literal['build_date', 'runtime_seconds', 'student_name', 'lab_name', 'workout_id', 'last_seen_at', 'run_count']
SortDirection = Literal['asc', 'desc']


def _runtime_report(month, start, end, q, sort='build_date', direction='desc', *, history=False):
    try:
        first, stop = CloudMonitoring.period(month, start, end, history=history)
    except BadRequest as error:
        raise HTTPException(status_code=400, detail=error.message) from error
    return CloudMonitoring().report(first, stop, q=q, sort=sort, direction=direction)


@cloud_monitoring_router.get('/workout-runtime/')
def get_workout_runtime(
    response: Response,
    _: AgogeUser = Depends(admin_required),
    month: str | None = Query(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
    start: date | None = None,
    end: date | None = None,
    q: str = Query(default='', max_length=120),
    sort: RuntimeSort = 'build_date',
    direction: SortDirection = 'desc',
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AgogeResponse[dict]:
    report = _runtime_report(month, start, end, q, sort, direction)
    report['rows'] = report['rows'][offset:offset + limit]
    response.headers['Cache-Control'] = 'no-store'
    return AgogeResponse(data=report)


@cloud_monitoring_router.get('/workout-runtime/months/')
def get_workout_runtime_months(
    response: Response,
    _: AgogeUser = Depends(admin_required),
    start: date | None = None,
    end: date | None = None,
    q: str = Query(default='', max_length=120),
) -> AgogeResponse[dict]:
    report = _runtime_report(None, start, end, q, history=True)
    response.headers['Cache-Control'] = 'no-store'
    return AgogeResponse(data={key: report[key] for key in ('months', 'start', 'end', 'notes')})


@cloud_monitoring_router.get('/workout-runtime/export/')
def export_workout_runtime(
    _: AgogeUser = Depends(admin_required),
    month: str | None = Query(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
    start: date | None = None,
    end: date | None = None,
    q: str = Query(default='', max_length=120),
    sort: RuntimeSort = 'build_date',
    direction: SortDirection = 'desc',
) -> Response:
    report = _runtime_report(month, start, end, q, sort, direction)
    filename = f"agoge-workout-runtime-{report['start']}-to-{report['end']}.csv"
    return Response(
        content=CloudMonitoring.csv(report['rows']),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'},
    )
