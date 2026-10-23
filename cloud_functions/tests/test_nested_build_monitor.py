"""NestedBuildMonitor copies agoge-nested/* guest attributes into nested_build, removes the secrets once, and fails
stalled or overlong builds; the midnight stop leaves running builds alone (PRD V13)."""
import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.project_server_manager import ProjectServerManager
from cloud_fn_utilities.periodic_maintenance import daily_maintenance as daily_maintenance_module
from cloud_fn_utilities.periodic_maintenance import quarter_hourly_maintenance as quarter_hourly_module
from cloud_fn_utilities.periodic_maintenance.daily_maintenance import DailyMaintenance
from common.constants.database import DbCollections, DbOperators
from common.constants.nested import NESTED_BUILD_MAX_MINUTES, NESTED_BUILD_STALL_MINUTES
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus, ServerStates
from common.exceptions import NotFound
from common.utilities import nested_build_monitor as monitor_module
from common.utilities.nested_build_monitor import MSG_STALLED, MSG_TIMED_OUT, NestedBuildMonitor

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
PROJECT = 'test-dev-787001'


def _ago(minutes):
    return (NOW - timedelta(minutes=minutes)).isoformat()


def _epoch_ago(minutes):
    return str(int((NOW - timedelta(minutes=minutes)).timestamp()))


def _image(phase='provisioning', name='nestlab', started=10, heartbeat=None, **build):
    return {
        'name': name,
        'status': ImageStatus.CHECKED_OUT.value,
        'state': ServerStates.RUNNING.value,
        'self_link': 'projects/debian-cloud/global/images/family/debian-12',
        'image_exists': False,
        'nested': {'parent_os': 'debian-12'},
        'nested_build': {
            'phase': phase, 'guests': {}, 'message': None, 'started_at': _ago(started),
            'heartbeat_at': _ago(heartbeat) if heartbeat is not None else None, **build,
        },
    }


class FakeDb:
    """Stores the images and applies update() as Firestore's merge=True set does at the top level."""

    def __init__(self, *images):
        self.images = {image['name']: copy.deepcopy(image) for image in images}
        self.updates = []
        self.queries = []

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.images.get(doc_id))

    def update(self, collection_name, doc_id, data):
        assert collection_name == DbCollections.IMAGE
        self.updates.append((doc_id, copy.deepcopy(data)))
        self.images[doc_id].update(copy.deepcopy(data))

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        docs = list(self.images.values())
        for field, op, value in filters or []:
            def read(doc):
                for part in field.split('.'):
                    doc = (doc or {}).get(part)
                return doc
            docs = [d for d in docs if (read(d) == value if op == DbOperators.EQUAL else read(d) in value)]
        return copy.deepcopy(docs)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    env = SimpleNamespace(project=PROJECT, region='us-central1', zone='us-central1-a', get_env=lambda: {})
    monkeypatch.setattr(monitor_module, 'CloudEnv', lambda **kwargs: env)


def _monitor(db, attributes=None):
    compute = Mock()
    if isinstance(attributes, Exception):
        compute.get_guest_attributes.side_effect = attributes
    else:
        compute.get_guest_attributes.return_value = attributes or {}
    return NestedBuildMonitor(env_dict={}, db=db, compute_instance=compute, pubsub_manager=Mock())


def _refresh(db, name='nestlab', attributes=None):
    monitor = _monitor(db, attributes)
    return monitor, monitor.refresh(db.get(DbCollections.IMAGE, name), now=NOW)


def test_a_standard_image_is_not_monitored():
    db = FakeDb({'name': 'plain', 'status': ImageStatus.CHECKED_OUT.value})
    monitor, status = _refresh(db, name='plain')
    assert status is None
    monitor.compute_instance.get_guest_attributes.assert_not_called()
    assert db.updates == []


@pytest.mark.parametrize('reported, expected', [('building', 'building'), ('ready', 'ready'), ('failed', 'failed')])
def test_each_reported_phase_is_recorded(reported, expected):
    db = FakeDb(_image())
    monitor, status = _refresh(db, attributes={'phase': reported, 'heartbeat': _epoch_ago(1)})
    assert status.phase == expected
    assert db.images['nestlab']['nested_build']['phase'] == expected
    monitor.compute_instance.get_guest_attributes.assert_called_once_with('nestlab', query_path='agoge-nested/')


def test_provisioning_without_a_reported_phase_stays_provisioning_and_an_unknown_phase_is_ignored():
    db = FakeDb(_image())
    _, status = _refresh(db, attributes={})
    assert status.phase == 'provisioning'
    _, status = _refresh(db, attributes={'phase': 'finalized'})  # only the builder's three values count
    assert status.phase == 'provisioning'
    assert db.updates == []


def test_guest_statuses_message_and_heartbeat_are_copied():
    db = FakeDb(_image(phase='building', heartbeat=5))
    attributes = {
        'phase': 'building',
        'guest-kali': 'installing',
        'guest-win-dc': 'failed:sha256 mismatch',  # the reason after the colon is not a status
        'guest-odd': 'exploded',  # not a NestedGuestStatus: ignored rather than failing validation
        'message': 'x' * 300,
        'heartbeat': _epoch_ago(1),
    }
    _, status = _refresh(db, attributes=attributes)
    assert status.guests == {'kali': 'installing', 'win-dc': 'failed'}
    assert status.message == 'x' * 200
    assert status.heartbeat_at == _ago(1)
    assert status.updated_at == NOW.isoformat()


def test_guest_addresses_are_copied_and_malformed_pairs_dropped():
    # The Connect dialog tunnels to these; addresses-<guest> must not be read as a guest named "addresses-…".
    db = FakeDb(_image(phase='building', heartbeat=5))
    attributes = {
        'phase': 'ready',
        'guest-win': 'ready',
        'addresses-win': '0=192.168.100.166,1=10.20.0.20',
        'addresses-kali': '0=192.168.100.10,x=1.2.3.4,1=not-an-ip,2=',
        'addresses-fw': '',
        'heartbeat': _epoch_ago(1),
    }
    _, status = _refresh(db, attributes=attributes)
    assert status.guest_addresses == {'win': {'0': '192.168.100.166', '1': '10.20.0.20'},
                                      'kali': {'0': '192.168.100.10'}}
    assert status.guests == {'win': 'ready'}
    assert db.images['nestlab']['nested_build']['guest_addresses']['win']['0'] == '192.168.100.166'


def test_only_nested_build_is_written():
    db = FakeDb(_image())
    _refresh(db, attributes={'phase': 'building', 'heartbeat': _epoch_ago(1)})
    [(doc_id, data)] = db.updates
    assert doc_id == 'nestlab' and list(data) == ['nested_build']


def test_an_unchanged_build_is_not_rewritten():
    db = FakeDb(_image(phase='building', heartbeat=1))
    db.images['nestlab']['nested_build']['heartbeat_at'] = datetime.fromtimestamp(
        int(_epoch_ago(1)), tz=timezone.utc).isoformat()
    _refresh(db, attributes={'phase': 'building', 'heartbeat': _epoch_ago(1)})
    assert db.updates == []


@pytest.mark.parametrize('reported', ['ready', 'failed'])
def test_secrets_are_removed_exactly_once(reported):
    db = FakeDb(_image(phase='building', heartbeat=2))
    first, _ = _refresh(db, attributes={'phase': reported, 'heartbeat': _epoch_ago(1)})
    second, status = _refresh(db, attributes={'phase': reported, 'heartbeat': _epoch_ago(1)})
    first.compute_instance.set_metadata.assert_called_once_with('nestlab', remove=['agoge-nested-secrets'], wait=False)
    # A terminal record is returned as stored: no poll, no second removal.
    second.compute_instance.get_guest_attributes.assert_not_called()
    second.compute_instance.set_metadata.assert_not_called()
    assert status.phase == reported


def test_secrets_stay_while_building():
    db = FakeDb(_image(phase='building', heartbeat=2))
    monitor, _ = _refresh(db, attributes={'phase': 'building', 'guest-kali': 'downloading', 'heartbeat': _epoch_ago(1)})
    monitor.compute_instance.set_metadata.assert_not_called()


def test_a_failed_secret_removal_leaves_the_build_active_so_the_next_refresh_retries():
    db = FakeDb(_image(phase='building', heartbeat=2))
    monitor = _monitor(db, {'phase': 'ready', 'heartbeat': _epoch_ago(1)})
    monitor.compute_instance.set_metadata.side_effect = RuntimeError('412')
    with pytest.raises(RuntimeError):
        monitor.refresh(db.get(DbCollections.IMAGE, 'nestlab'), now=NOW)
    assert db.images['nestlab']['nested_build']['phase'] == 'building'

    retry, status = _refresh(db, attributes={'phase': 'ready', 'heartbeat': _epoch_ago(1)})
    retry.compute_instance.set_metadata.assert_called_once()
    assert status.phase == 'ready'


def test_secret_removal_tolerates_a_deleted_server():
    db = FakeDb(_image(phase='building', heartbeat=2))
    monitor = _monitor(db, {'phase': 'ready'})
    monitor.compute_instance.set_metadata.side_effect = NotFound('gone')
    assert monitor.refresh(db.get(DbCollections.IMAGE, 'nestlab'), now=NOW).phase == 'ready'


def _assert_failed_and_stopped(db, monitor, status, message):
    assert status.phase == 'failed' and status.message == message
    assert db.images['nestlab']['nested_build']['phase'] == 'failed'
    monitor.compute_instance.set_metadata.assert_called_once_with(
        'nestlab', remove=['agoge-nested-secrets'], wait=False
    )
    monitor.pubsub_manager.msg.assert_called_once_with(
        handler=str(PubSub.Handlers.CONTROL.value),
        action=str(PubSub.Actions.STOP.value),
        course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
        image_name='nestlab',
        shared_edit_authorized='false',
    )


def test_a_stale_heartbeat_fails_and_stops_the_build():
    db = FakeDb(_image(phase='building', started=60))
    monitor, status = _refresh(db, attributes={
        'phase': 'building', 'heartbeat': _epoch_ago(NESTED_BUILD_STALL_MINUTES + 1)})
    _assert_failed_and_stopped(db, monitor, status, MSG_STALLED)


def test_a_build_that_never_reported_is_stalled_from_its_start():
    # Before the first heartbeat, and even before the server exists, the stall clock runs from started_at.
    db = FakeDb(_image(phase='provisioning', started=NESTED_BUILD_STALL_MINUTES + 1))
    monitor, status = _refresh(db, attributes=NotFound('no instance yet'))
    _assert_failed_and_stopped(db, monitor, status, MSG_STALLED)


def test_a_build_past_the_maximum_fails_even_with_a_fresh_heartbeat():
    db = FakeDb(_image(phase='building', started=NESTED_BUILD_MAX_MINUTES + 1))
    monitor, status = _refresh(db, attributes={'phase': 'building', 'heartbeat': _epoch_ago(1)})
    _assert_failed_and_stopped(db, monitor, status, MSG_TIMED_OUT)


def test_a_recent_heartbeat_is_not_a_stall():
    db = FakeDb(_image(phase='building', started=NESTED_BUILD_MAX_MINUTES - 1))
    monitor, status = _refresh(db, attributes={
        'phase': 'building', 'heartbeat': _epoch_ago(NESTED_BUILD_STALL_MINUTES - 1)})
    assert status.phase == 'building'
    monitor.pubsub_manager.msg.assert_not_called()


def test_a_build_that_reports_ready_late_is_not_failed():
    db = FakeDb(_image(phase='building', started=NESTED_BUILD_MAX_MINUTES + 30))
    monitor, status = _refresh(db, attributes={'phase': 'ready'})
    assert status.phase == 'ready'
    monitor.pubsub_manager.msg.assert_not_called()


@pytest.mark.parametrize('phase', ['queued', 'ready', 'finalizing', 'finalized', 'failed'])
def test_inactive_phases_are_not_polled_or_timed_out(phase):
    db = FakeDb(_image(phase=phase, started=NESTED_BUILD_MAX_MINUTES * 2))
    monitor, status = _refresh(db, attributes={'phase': 'building'})
    assert status.phase == phase
    monitor.compute_instance.get_guest_attributes.assert_not_called()
    monitor.pubsub_manager.msg.assert_not_called()
    assert db.updates == []


def test_refresh_active_queries_checked_out_active_builds_and_survives_one_failure():
    db = FakeDb(_image(name='broken'), _image(name='nestlab'), _image(name='done', phase='ready'))
    monitor = _monitor(db)
    calls = []

    def refresh(image):
        calls.append(image['name'])
        if image['name'] == 'broken':
            raise RuntimeError('compute down')

    monitor.refresh = refresh
    monitor.refresh_active()
    assert sorted(calls) == ['broken', 'nestlab']
    assert db.queries == [(DbCollections.IMAGE, [
        ('status', DbOperators.EQUAL, ImageStatus.CHECKED_OUT.value),
        ('nested_build.phase', DbOperators.IN, ['provisioning', 'building']),
    ])]


def test_quarter_hourly_maintenance_refreshes_active_builds():
    maintenance = object.__new__(quarter_hourly_module.QuarterHourlyMaintenance)
    maintenance.env_dict, maintenance.db, maintenance.pub_sub_mgr = {}, Mock(), Mock()
    with patch.object(quarter_hourly_module, 'NestedBuildMonitor') as monitor_cls:
        maintenance._refresh_nested_builds()
    monitor_cls.assert_called_once_with(env_dict={}, db=maintenance.db, pubsub_manager=maintenance.pub_sub_mgr)
    monitor_cls.return_value.refresh_active.assert_called_once_with()


# --- Midnight stop exemption -----------------------------------------------------------------------------------


@pytest.mark.parametrize('phase', ['provisioning', 'building'])
def test_stop_all_running_skips_a_running_build(phase):
    manager = object.__new__(ImageTemplateManager)
    manager.debug = False
    manager.env = SimpleNamespace(project=PROJECT)
    manager.db_query = Mock()
    manager.db_query.get_running.return_value = [
        _image(name='building', phase=phase), _image(name='built', phase='ready'), {'name': 'plain'},
    ]
    manager.pubsub_manager = Mock()
    manager.stop_all_running()
    stopped = [call.kwargs['image_name'] for call in manager.pubsub_manager.msg.call_args_list]
    assert stopped == ['built', 'plain']


def test_daily_stop_exempts_running_build_servers_by_exact_name():
    maintenance = object.__new__(DailyMaintenance)
    maintenance.debug = False
    maintenance.env_dict = {}
    maintenance.db = FakeDb(_image(name='building', phase='building'), _image(name='built', phase='ready'))
    maintenance.db_query = Mock()
    maintenance.db_query.get_running.return_value = []
    maintenance.pub_sub_mgr = Mock()
    maintenance.project_server_manager = Mock()
    with patch.object(daily_maintenance_module, 'ComputeManagerFactory'), \
            patch.object(DailyMaintenance, '_ctf_workout_ids', return_value=set()):
        maintenance._stop_all()
    maintenance.project_server_manager.stop_everything.assert_called_once_with(
        exempt_prefixes=[], exempt_names=['building']
    )


def test_stop_everything_leaves_exempt_names_running_and_their_state_alone():
    manager = object.__new__(ProjectServerManager)
    manager.class_name, manager.log_name, manager.logger = 'ProjectServerManager', 'test', MagicMock()
    manager.env = SimpleNamespace(project=PROJECT, zone='us-central1-a')
    manager.collection = DbCollections
    manager.compute_instance = Mock()
    manager.compute_instance.list.return_value = [
        SimpleNamespace(name='building'), SimpleNamespace(name='building-2'), SimpleNamespace(name='other'),
    ]
    manager.db = Mock()
    manager.db.query.return_value = [{'name': 'building'}, {'name': 'other'}]
    with patch.object(ProjectServerManager, 'validate', create=True) as validate:
        validate.return_value.load.side_effect = lambda image: SimpleNamespace(state=image['state'])
        manager.stop_everything(exempt_names=['building'])
    # Exact names: an instance merely starting with the name is still stopped.
    stopped = [call.kwargs['resource_name'] for call in manager.compute_instance.stop.call_args_list]
    assert stopped == ['building-2', 'other']
    synced = [call.kwargs['doc_id'] for call in manager.db.operation.call_args_list]
    assert synced == ['other']


def test_an_unreadable_build_is_returned_as_stored_rather_than_judged_stalled():
    # A Compute outage must not fail a build whose stored heartbeat merely looks old.
    db = FakeDb(_image(phase='building', heartbeat=NESTED_BUILD_STALL_MINUTES + 5))
    monitor, status = _refresh(db, attributes=RuntimeError('503'))
    assert status.phase == 'building'
    assert db.updates == []
    monitor.pubsub_manager.msg.assert_not_called()


def test_an_active_build_without_a_start_gets_one():
    db = FakeDb(_image(phase='building', started_at=None))
    _, status = _refresh(db, attributes={})
    assert status.started_at == NOW.isoformat()
    assert db.images['nestlab']['nested_build']['started_at'] == NOW.isoformat()
