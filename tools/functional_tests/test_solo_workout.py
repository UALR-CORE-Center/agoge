"""Offline Solo scenario: real orchestration/Guacamole configuration, fake cloud.

Only storage, VM/network services and the Guacamole HTTP transport are replaced.
This deliberately exercises SoloWorkout's public lifecycle methods and the real
per-Workout DisplayProxy configuration rather than scripting expected states.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from common.constants.database import DbCollections, DbOperators
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.models.agoge import NetworkModel, ServerModel, WorkoutModel
from cloud_fn_utilities.course_objects.workout import solo_workout as solo_module
from cloud_fn_utilities.course_objects.workout import base_workout as base_module
from cloud_fn_utilities.server_specific.guacamole import display_proxy as proxy_module
from cloud_fn_utilities.server_specific.guacamole import guacamole_configuration as configuration_module
from cloud_fn_utilities.state_managers import base_state_manager as state_module


class MemoryDatabase:
    def __init__(self):
        self.records = {collection: {} for collection in DbCollections}

    def get(self, collection_name, doc_id):
        return deepcopy(self.records[collection_name].get(doc_id))

    def update(self, collection_name, doc_id, data):
        record = self.records[collection_name].setdefault(doc_id, {})
        record.update(deepcopy(data))

    def children(self, parent_id):
        return [deepcopy(record) for record in self.records[DbCollections.SERVER].values()
                if record.get('parent_id') == parent_id]

    def query(self, collection_name, filters):
        records = list(self.records[collection_name].values())
        for field, operator, value in filters:
            assert operator == DbOperators.EQUAL, f'Unexpected offline query: {operator}'
            records = [record for record in records if record.get(field) == value]
        return deepcopy(records)


class CloudBoundary:
    """Small provider adapter; all lifecycle decisions stay in application code."""
    def __init__(self, database, events):
        self.database, self.events = database, events
        self.instances = {}
        self.current = None

    def load(self, server_name, **_):
        assert self.database.get(DbCollections.SERVER, server_name), server_name
        self.current = server_name

    def build(self):
        assert self.current not in self.instances, 'A Solo VM must be created once'
        self.instances[self.current] = 'RUNNING'
        self._state(ServerStates.RUNNING, 'build')

    def start(self):
        assert self.current in self.instances
        self.instances[self.current] = 'RUNNING'
        self._state(ServerStates.RUNNING, 'start')

    def stop(self):
        assert self.current in self.instances
        self.instances[self.current] = 'TERMINATED'
        self._state(ServerStates.STOPPED, 'stop')

    def delete(self):
        self.instances.pop(self.current)
        self._state(ServerStates.DELETED, 'delete')

    def _state(self, state, action):
        self.database.update(DbCollections.SERVER, self.current, {'state': state.value})
        self.events.append((action, self.current))


def test_solo_build_guacamole_session_start_stop_and_delete(monkeypatch):
    """A Solo Workout retains one private JDBC proxy and owns its full teardown."""
    from core import guacamole_api as api_module

    unit_id, workout_id = 'abcdefghij', 'klmnopqrst'
    database, events, networks = MemoryDatabase(), [], set()
    cloud = CloudBoundary(database, events)
    env = SimpleNamespace(parent_dns_suffix='.labs.example', dns_suffix='.labs.example',
                          main_app_url='https://app.labs.example/test', project='offline-project')
    env_dict = {'project': 'offline-project'}
    env.get_env = lambda: env_dict
    for module in (base_module, proxy_module, configuration_module, api_module):
        monkeypatch.setattr(module, 'CloudEnv', lambda *_, **__: env)
    monkeypatch.setattr(proxy_module.DocumentDatabaseFactory, 'create_db_object', lambda **_: database)
    monkeypatch.setattr(api_module.DocumentDatabaseFactory, 'create_db_object', lambda **_: database)
    monkeypatch.setattr(proxy_module.ComputeManagerFactory, 'create_manager_object', lambda **_: cloud)
    monkeypatch.setattr(base_module, 'PubSubManager', lambda *_, **__: Mock())
    monkeypatch.setattr(base_module, 'VpcManager', lambda **_: SimpleNamespace(
        build=lambda network: networks.add(network.name), delete=lambda network: networks.remove(network.name)))
    monkeypatch.setattr(base_module, 'FirewallManager', lambda **_: SimpleNamespace(
        build=lambda *args: events.append(('firewall_build', workout_id)),
        delete=lambda identifier: events.append(('firewall_delete', identifier))))
    monkeypatch.setattr(solo_module.PacketMirrorFactory, 'create_packet_mirror_object', lambda **_: None)

    def unexpected_wait(_):
        raise AssertionError('The fake provider completes synchronously; lifecycle unexpectedly waited')
    monkeypatch.setattr(state_module.time, 'sleep', unexpected_wait)

    student = ServerModel(name='student', image='image-student',
        nics=[{'network': 'external', 'internal_ip': '10.1.1.30'}],
        human_interaction=[{'protocol': 'rdp', 'username': 'student', 'password': 'example-password',
                            'display': True, 'security_mode': 'nla'}])
    network = NetworkModel(name='external', subnets=[{'name': 'default', 'ip_subnet': '10.1.1.0/24'}])
    workout_model = WorkoutModel(id=workout_id, parent_id=unit_id, parent_build_type='unit',
        build_type='workout', state=WorkoutStates.START.value, servers=[student], networks=[network],
        firewall_rules=[], student_email='solo-student@example.edu', expires=10_000_000_000)
    database.update(DbCollections.WORKOUT, workout_id, workout_model.model_dump())
    database.update(DbCollections.UNIT, unit_id, {'id': unit_id, 'unit_type': 'solo',
        'state': UnitStates.READY.value, 'workspace_settings': {'expires': 10_000_000_000}})

    workout = solo_module.SoloWorkout(workout_id=workout_id, workout_model=workout_model,
        unit_model=SimpleNamespace(id=unit_id, unit_type='solo', workout_duration_days=None,
                                   workspace_settings=SimpleNamespace(expires=10_000_000_000)),
        debug=True, env_dict=env_dict)

    # Actual SoloWorkout.build invokes actual DisplayProxy.build and SQL renderer.
    workout.build()
    assert workout.state_manager.get_state() == WorkoutStates.RUNNING.value
    proxy_id = f'{workout_id}-display-guacamole-server'
    student_id = f'{workout_id}-student'
    assert set(cloud.instances) == {student_id, proxy_id}
    proxy = database.get(DbCollections.SERVER, proxy_id)
    assert proxy['parent_id'] == workout_id
    assert not proxy.get('community_proxy')
    assert 'INSERT INTO guacamole_user' in proxy['guacamole_startup_script']
    assert 'JSON_SECRET_KEY' not in proxy['guacamole_startup_script']
    claimed = database.get(DbCollections.WORKOUT, workout_id)
    assert len(claimed['proxy_connections']) == 1

    # Exercise API hostname/index/credential resolution; fake only JDBC transport.
    jdbc_sessions = []
    def jdbc_session(url, datasource, username, password):
        jdbc_sessions.append((url, datasource, username, password))
        return SimpleNamespace(token='offline-solo-token')
    monkeypatch.setattr(api_module.guacamole, 'session', jdbc_session)
    session = api_module.Guacamole(workout_id, env_dict).get_connection_from_server('0')
    assert session['token'] == 'offline-solo-token'
    assert session['url'] == f'https://{workout_id}-display.labs.example/guacamole'
    assert jdbc_sessions[0][1] == 'mysql'
    assert jdbc_sessions[0][2:] == (claimed['proxy_connections'][0]['username'],
                                   claimed['proxy_connections'][0]['password'])

    # A concurrent Solo Workout's resources must remain outside this lifecycle.
    foreign_id = 'uvwxyzabcd-student'
    database.update(DbCollections.SERVER, foreign_id,
                    {'parent_id': 'uvwxyzabcd', 'name': 'student', 'state': ServerStates.RUNNING.value})
    cloud.instances[foreign_id] = 'RUNNING'
    workout.stop()
    assert workout.state_manager.get_state() == WorkoutStates.READY.value
    assert {cloud.instances[name] for name in (student_id, proxy_id)} == {'TERMINATED'}
    assert cloud.instances[foreign_id] == 'RUNNING'
    workout.start()
    assert workout.state_manager.get_state() == WorkoutStates.RUNNING.value
    assert {cloud.instances[name] for name in (student_id, proxy_id)} == {'RUNNING'}
    workout.delete()
    assert workout.state_manager.get_state() == WorkoutStates.DELETED.value
    assert cloud.instances == {foreign_id: 'RUNNING'} and networks == set()
    assert set(name for action, name in events if action == 'delete') == {student_id, proxy_id}
    assert ('firewall_delete', workout_id) in events
