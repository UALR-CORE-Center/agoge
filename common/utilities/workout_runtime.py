"""Record observable Agoge workout runtime alongside the state change."""

from datetime import datetime, timezone

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates


def utc_time(value):
    """Read ISO state times, Firestore timestamps, or legacy Unix seconds."""
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            value = datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return None


def next_month(value):
    return datetime(value.year + (value.month == 12), value.month % 12 + 1, 1, tzinfo=timezone.utc)


def record_workout_runtime(transaction, client, workout_id, current, patch):
    """Write build and running intervals in the workout state transaction."""
    before, after = current.get('state'), patch.get('state')
    if after is None or not current:
        return
    at = utc_time(patch.get('state_timestamp')) or datetime.now(timezone.utc)
    previous_at = utc_time(current.get('state_timestamp'))
    if previous_at and at < previous_at:
        at = previous_at

    running = WorkoutStates.RUNNING.value
    opened = utc_time(current.get('runtime_running_since'))
    built = utc_time(current.get('runtime_build_date'))
    web_only = current.get('web_applications') is not None and not current.get('networks') and not current.get('servers')
    finishing_provisioning = (
        isinstance(before, int) and WorkoutStates.BUILDING_NETWORKS.value <= before <= WorkoutStates.COMPLETED_STUDENT_ENTRY.value
    )
    first_build = (
        built is None
        and (finishing_provisioning or (web_only and before in (WorkoutStates.NOT_BUILT.value, WorkoutStates.START.value)))
        and after in (running, WorkoutStates.READY.value)
        and current.get('action') not in (PubSub.Actions.NUKE.value, PubSub.Actions.START.value, PubSub.Actions.STOP.value)
    )
    opening = after == running and opened is None and not web_only
    # A delivered START can briefly put an already-running workout back in
    # STARTING. Keep the original interval until it actually leaves runtime.
    closing = opened is not None and after not in (running, WorkoutStates.STARTING.value)
    if not (first_build or opening or closing):
        return

    summary = current.get('summary') or {}
    metadata = {
        'workout_id': workout_id,
        'unit_id': current.get('parent_id'),
        'lab_name': summary.get('name'),
        'student_name': current.get('runtime_student_name') or current.get('student_name') or current.get('team_name'),
        'student_email': current.get('student_email'),
        'build_date': at if first_build else built,
    }
    records = client.collection(DbCollections.WORKOUT_RUNTIME.value)
    live = records.document(f'live-{workout_id}')
    if closing:
        # Preserve the student and lab recorded at entry, even if an
        # administrator reassigns the workout before this run ends.
        snapshot = live.get(transaction=transaction)
        if snapshot.exists:
            live_record = snapshot.to_dict()
            if utc_time(live_record.get('started_at')) == opened:
                metadata = {key: live_record.get(key, value) for key, value in metadata.items()}

    if first_build:
        patch['runtime_build_date'] = at
        transaction.set(records.document(f'build-{workout_id}'), {
            **metadata, 'kind': 'build', 'month': at.strftime('%Y-%m'),
        })

    if opening:
        patch['runtime_running_since'] = at
        transaction.set(live, {
            **metadata, 'kind': 'live', 'started_at': at,
            'session_id': f'{workout_id}-{at:%Y%m%d%H%M%S%f}',
        })
    elif closing:
        patch['runtime_running_since'] = None
        cursor = opened
        session_id = f'{workout_id}-{opened:%Y%m%d%H%M%S%f}'
        while cursor < at:
            stop = min(at, next_month(cursor))
            month = cursor.strftime('%Y-%m')
            transaction.set(records.document(f'run-{session_id}-{month}'), {
                **metadata, 'kind': 'run', 'month': month,
                'session_id': session_id, 'started_at': cursor, 'ended_at': stop,
            })
            cursor = stop
        transaction.delete(live)
