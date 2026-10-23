"""Run API and Cloud Function build code locally against real test-dev resources.

Run ``python debug_lab.py --help`` from any working directory. No application
deployment or Pub/Sub emulator is required. Debug execution is always enabled.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
TEST_PROJECT = 'test-dev-787001'


class DebugLabStageError(RuntimeError):
    """A locally generated state diagnostic, safe to include in run output."""


class DebugLabInputError(ValueError):
    """A locally generated account/peer diagnostic, safe to show to the user."""


def report_error_location(error):
    from common.utilities.debug_error_trace import safe_error_trace

    frames = safe_error_trace(error, ROOT)
    if frames:
        print('Repository call trace (argument values omitted):', file=sys.stderr)
        for frame in frames:
            print(f'  {frame["file"]}:{frame["line"]} in {frame["function"]}', file=sys.stderr)
    return frames


def invoke_local_worker(attributes: dict, env_dict: dict) -> None:
    # Use the qualified module name: both API and function folders have main.py.
    from cloud_functions.main import agoge_cloud_function

    context = SimpleNamespace(event_id=f'local-{uuid4()}',
                              timestamp=datetime.now(timezone.utc).isoformat())
    agoge_cloud_function({'attributes': attributes}, context,
                         debug_mode=True, env_dict=env_dict)


class LocalBackend:
    def __init__(self, env_dict, db, unit_class, workout_class, users_class,
                 worker=invoke_local_worker):
        if env_dict.get('project') != TEST_PROJECT:
            raise ValueError(f'Local debug builds require project {TEST_PROJECT}')
        self.env_dict, self.db = env_dict, db
        self.unit_class, self.workout_class, self.users_class = unit_class, workout_class, users_class
        self.worker = worker

    def dispatch(self, attributes):
        self.worker(attributes, self.env_dict)

    def _unit(self, unit_id):
        from common.constants.database import DbCollections

        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            raise ValueError(f'Lab {unit_id} was not found in {TEST_PROJECT}')
        return unit

    def _requester(self, email, *, admin=False):
        requester = self.users_class().get_user(user_email=email)
        if admin:
            if not requester.is_admin:
                raise DebugLabInputError('Peer enrollment requires an existing Agoge admin account')
        elif not requester.is_authorized:
            raise DebugLabInputError('The instructor must have an existing Agoge instructor or admin account')
        return requester

    def _peer_service(self):
        from common.services.wireguard_provisioning import WireGuardProvisioningService

        return WireGuardProvisioningService(self.env_dict, db=self.db)

    def list_peers(self, instructor):
        requester = self._requester(instructor)
        peers = self._peer_service().list_remote_peers(requester)
        items = [{**peer.model_dump(by_alias=True),
                  'available': peer.enabled and not peer.assigned_unit_id} for peer in peers]
        return {'project': TEST_PROJECT, 'items': items, 'total': len(items)}

    def enroll_peer(self, admin, spec, token_out):
        from common.models.wireguard_provisioning import WireGuardRemotePeerCreate
        from common.utilities.local_token_file import enrollment_token_output

        requester = self._requester(admin, admin=True)
        peer = WireGuardRemotePeerCreate.model_validate(spec)
        # Reserve/protect a new file before registering the device, so an
        # existing output path cannot consume a one-time enrollment token.
        with enrollment_token_output(token_out) as save:
            result = self._peer_service().enroll_remote_peer(peer, requester)
            save(result['enrollment_token'])
        return {'project': TEST_PROJECT, 'remote_peer': result['remote_peer'].model_dump(by_alias=True),
                'token_file': str(token_out)}

    @staticmethod
    def _can_access_lab(unit, requester):
        owners = unit.get('instructor_id') or []
        if isinstance(owners, str):
            owners = [owners]
        return requester.is_admin or (requester.email or '').lower() in {
            value.lower() for value in owners if isinstance(value, str)}

    @staticmethod
    def _lab_summary(unit):
        from common.constants.states import UnitStates

        try:
            state_name = UnitStates(unit.get('state')).name
        except ValueError:
            state_name = 'UNKNOWN'
        lease = unit.get('wireguard_lease') or {}
        return {'unit_id': unit['id'], 'name': (unit.get('summary') or {}).get('name'),
                'state': unit.get('state'), 'state_name': state_name,
                'creation_timestamp': unit.get('creation_timestamp'),
                'expires': (unit.get('workspace_settings') or {}).get('expires'),
                'instructor_id': unit.get('instructor_id'),
                'remote_peer_id': lease.get('remote_peer_id') or lease.get('kit_id')}

    def list_labs(self, instructor, remote_peer_id=None, include_deleted=False):
        from common.constants.database import DbCollections, DbOperators
        from common.constants.states import UnitStates

        requester = self._requester(instructor)
        units = self.db.query(collection_name=DbCollections.UNIT, filters=[('test', DbOperators.EQUAL, True)]) or []
        items = []
        for unit in units:
            if unit.get('test') is not True or not self._can_access_lab(unit, requester):
                continue
            if not include_deleted and unit.get('state') == UnitStates.DELETED.value:
                continue
            summary = self._lab_summary(unit)
            if remote_peer_id and summary['remote_peer_id'] != remote_peer_id:
                continue
            items.append(summary)
        def sort_key(item):
            timestamp = item['creation_timestamp']
            return (timestamp if type(timestamp) in (int, float) and math.isfinite(timestamp) else 0,
                    item['unit_id'])

        items.sort(key=sort_key, reverse=True)
        return {'project': TEST_PROJECT, 'items': items, 'total': len(items)}

    def _cleanup_confirmation(self, unit):
        from common.constants.database import DbCollections
        from common.constants.states import UnitStates

        unit_id = unit['id']
        lease = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id) or {}
        snapshot = unit.get('wireguard_lease') or {}
        expected_lease = bool(snapshot) or any(
            server.get('wireguard_managed') for server in unit.get('servers') or [])
        lease_released = lease.get('status') == 'released' if lease else not expected_lease
        peer_id = (lease.get('remote_peer_id') or lease.get('kit_id')
                   or snapshot.get('remote_peer_id') or snapshot.get('kit_id'))
        peer = (self.db.get(collection_name=DbCollections.WIREGUARD_KIT, doc_id=peer_id)
                if peer_id else {}) or {}
        peer_released = peer.get('assigned_unit_id') != unit_id
        endpoint_id = lease.get('endpoint_id') or (unit.get('wireguard_endpoint') or {}).get('id')
        endpoint = (self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT, doc_id=endpoint_id)
                    if endpoint_id else {}) or {}
        endpoint_released = (not endpoint or endpoint.get('unit_id') != unit_id
                             or endpoint.get('status') == 'released')
        deleted = (unit.get('state') == UnitStates.DELETED.value and lease_released
                   and peer_released and endpoint_released)
        summary = self._lab_summary(unit)
        return {'unit_id': unit_id, 'deleted': bool(deleted),
                'state': summary['state'], 'state_name': summary['state_name'],
                'lease_released': bool(lease_released), 'peer_released': bool(peer_released),
                'endpoint_released': bool(endpoint_released)}

    def delete_labs(self, instructor, unit_ids, execute=False):
        requester = self._requester(instructor)
        identifiers = list(dict.fromkeys(unit_ids))
        if not identifiers:
            raise ValueError('Select at least one lab with --unit-id')

        def selected(identifier):
            unit = self._unit(identifier)
            if unit.get('test') is not True:
                raise ValueError(f'Lab {identifier} is not marked test:true; debug cleanup cannot delete it')
            if not self._can_access_lab(unit, requester):
                raise ValueError(f'This Agoge account is not authorized to delete lab {identifier}')
            return unit

        # Validate the complete batch before the first resource mutation.
        targets = [selected(identifier) for identifier in identifiers]
        if not execute:
            return {'project': TEST_PROJECT, 'dry_run': True,
                    'items': [self._lab_summary(unit) for unit in targets], 'total': len(targets)}
        items = []
        for identifier in identifiers:
            try:
                current = selected(identifier)
                result = self._cleanup_confirmation(current)
                if not result['deleted']:
                    print(f'Deleting test lab {identifier} and its managed resources locally.', flush=True)
                    self.action('unit', identifier, 'delete')
                    result = self._cleanup_confirmation(self._unit(identifier))
                items.append(result)
            except Exception as error:
                # Worker error bodies can contain SDK data; leave the original
                # worker logs for debugging and report only the exception type.
                items.append({'unit_id': identifier, 'deleted': False, 'error': type(error).__name__})
        deleted = sum(item['deleted'] for item in items)
        return {'project': TEST_PROJECT, 'dry_run': False, 'items': items,
                'total': len(items), 'deleted': deleted, 'failed': len(items) - deleted}

    def recent_labs(self, instructor, remote_peer_id, hours=24):
        from common.constants.states import UnitStates

        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - hours * 3600
        listing = self.list_labs(instructor, remote_peer_id, include_deleted=True)
        items = []
        for item in listing['items']:
            owners = item.get('instructor_id') or []
            if isinstance(owners, str):
                owners = [owners]
            timestamp = item.get('creation_timestamp')
            # Admin visibility must not expand automatic cleanup to someone
            # else's labs. Missing/future timestamps are never selected.
            if (instructor.lower() not in {owner.lower() for owner in owners if isinstance(owner, str)}
                    or item.get('remote_peer_id') != remote_peer_id
                    or type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                    or not cutoff <= timestamp <= now):
                continue
            if (item.get('state') == UnitStates.DELETED.value
                    and self._cleanup_confirmation(self._unit(item['unit_id']))['deleted']):
                continue
            items.append(item)
        return {**listing, 'items': items, 'total': len(items)}

    def _verify_lab_stage(self, unit_id, stage):
        from common.constants.database import DbCollections, DbOperators
        from common.constants.states import ServerStates, UnitStates, WorkoutStates

        status = self.status(unit_id)
        expected_unit = ({UnitStates.READY.value, UnitStates.RUNNING.value} if stage == 'build'
                         else {UnitStates.RUNNING.value} if stage == 'start' else {UnitStates.READY.value})
        expected_workout = ({WorkoutStates.READY.value, WorkoutStates.RUNNING.value} if stage == 'build'
                            else {WorkoutStates.RUNNING.value} if stage == 'start' else {WorkoutStates.READY.value})
        expected_server = ServerStates.STOPPED.value if stage == 'stop' else ServerStates.RUNNING.value
        if status['state'] not in expected_unit:
            raise DebugLabStageError(f'Lab {unit_id} did not complete {stage}; state is {status["state_name"]}')
        workouts = status['workouts']
        for workout in workouts:
            if workout.get('state') not in expected_workout:
                raise DebugLabStageError(f'Workout {workout["workout_id"]} did not complete {stage}')

        unit = self._unit(unit_id)
        expected = set()
        for server in unit.get('servers') or []:
            parents = [unit_id] if server.get('community_server') else [w['workout_id'] for w in workouts]
            expected.update(f'{parent}-{server["name"]}' for parent in parents)
        if unit.get('wireguard_lease'):
            expected.update(f'{w["workout_id"]}-display-guacamole-server' for w in workouts)
        # Include dynamically created resources such as display proxies and
        # firewalls, rather than accepting a READY parent with BROKEN servers.
        for parent in [unit_id, *(w['workout_id'] for w in workouts)]:
            records = self.db.query(collection_name=DbCollections.SERVER,
                                    filters=[('parent_id', DbOperators.EQUAL, parent)]) or []
            expected.update(record['name'] if record['name'].startswith(f'{parent}-')
                            else f'{parent}-{record["name"]}' for record in records
                            if record.get('name') and record.get('state') != ServerStates.DELETED.value)
        for name in sorted(expected):
            record = self.db.get(collection_name=DbCollections.SERVER, doc_id=name) or {}
            if record.get('state') != expected_server:
                raise DebugLabStageError(f'Server {name} did not complete {stage}; expected state {expected_server}')
        return status

    def run_lab(self, args, read_input=None):
        """Run one prompted lifecycle, retaining failed runs for inspection."""
        read_input = input if read_input is None else read_input
        result = {'project': TEST_PROJECT, 'unit_id': None, 'outcome': 'kept',
                  'completed_steps': [], 'exit_code': 0}
        stage = 'recent cleanup'

        def confirm(message, default=False):
            while True:
                answer = read_input(message).strip().lower()
                if not answer:
                    return default
                if answer in ('y', 'yes'):
                    return True
                if answer in ('n', 'no'):
                    return False
                if answer in ('q', 'quit'):
                    return None
                print('Enter y, n, or q to quit.', flush=True)

        def created(unit_id):
            result['unit_id'] = unit_id

        try:
            if args.recent_cleanup != 'skip':
                recent = self.recent_labs(args.instructor, args.remote_peer_id, args.recent_hours)
                if recent['items']:
                    print(f'Recent test labs for {args.instructor} / {args.remote_peer_id} '
                          f'in the last {args.recent_hours:g} hours:', flush=True)
                    for item in recent['items']:
                        print(f'  {item["unit_id"]}: {item["state_name"]} ({item.get("name") or "unnamed"})', flush=True)
                    approved = (True if args.recent_cleanup == 'delete' else
                                confirm('Delete these labs before building? [y/N/q]: '))
                    if approved is None:
                        result['outcome'] = 'cancelled'
                        return result
                    if approved:
                        # Recheck scope after the prompt; never add a newly
                        # discovered lab to the set the user saw and approved.
                        current = {item['unit_id'] for item in self.recent_labs(
                            args.instructor, args.remote_peer_id, args.recent_hours)['items']}
                        identifiers = [item['unit_id'] for item in recent['items'] if item['unit_id'] in current]
                        if identifiers:
                            result['cleanup'] = self.delete_labs(args.instructor, identifiers, execute=True)
                            print(json.dumps(result['cleanup'], indent=2), flush=True)
                            if result['cleanup'].get('failed', 0):
                                result.update(outcome='failed', exit_code=1, failed_step=stage)
                                return result
                else:
                    print('No matching recent test labs need cleanup.', flush=True)

            stage = 'build'
            built = self.create_lab(args, on_created=created)
            created(built['unit_id'])
            unit_id = result['unit_id']
            status = self._verify_lab_stage(unit_id, 'build')
            workout_ids = [workout['workout_id'] for workout in status['workouts']]
            result['completed_steps'].append('build')
            print(json.dumps(status, indent=2), flush=True)

            stage = 'start'
            if not confirm(f'Start lab {unit_id} and its workouts? [Y/n/q]: ', default=True):
                return result
            self.action('unit', unit_id, 'start')
            for workout_id in workout_ids:
                self.action('workout', workout_id, 'start', args.duration_hours)
            status = self._verify_lab_stage(unit_id, 'start')
            result['completed_steps'].append('start')
            print(json.dumps(status, indent=2), flush=True)

            stage = 'stop'
            if not confirm(f'Stop lab {unit_id} and its workouts? [Y/n/q]: ', default=True):
                return result
            for workout_id in workout_ids:
                self.action('workout', workout_id, 'stop')
            self.action('unit', unit_id, 'stop')
            status = self._verify_lab_stage(unit_id, 'stop')
            result['completed_steps'].append('stop')
            print(json.dumps(status, indent=2), flush=True)

            stage = 'delete'
            if confirm(f'Delete test lab {unit_id} and its managed resources? [y/N/q]: '):
                result['deletion'] = self.delete_labs(args.instructor, [unit_id], execute=True)
                if result['deletion'].get('failed', 0):
                    result.update(outcome='failed', exit_code=1, failed_step=stage)
                else:
                    result['completed_steps'].append('delete')
                    result['outcome'] = 'deleted'
        except KeyboardInterrupt:
            result.update(outcome='cancelled', exit_code=130, failed_step=stage)
        except EOFError:
            print('Input ended; lifecycle execution stopped.', flush=True)
            result.update(outcome='cancelled', exit_code=1, failed_step=stage)
        except Exception as error:
            # Keep SDK error bodies out of the summary. Worker logs and status
            # identify the failure; preserve the lab for interactive debugging.
            print(f'Lifecycle stopped during {stage} ({type(error).__name__}).', flush=True)
            result.update(outcome='failed', exit_code=1, failed_step=stage, error=type(error).__name__)
            result['error_trace'] = report_error_location(error)
            if isinstance(error, (DebugLabStageError, DebugLabInputError)):
                result['detail'] = str(error)
                print(result['detail'], flush=True)
        finally:
            if result['unit_id'] and result['outcome'] != 'deleted':
                print(f'Lab {result["unit_id"]} was retained. Inspect it with debug_lab.py status '
                      f'--unit-id {result["unit_id"]}.', flush=True)
                print(f'Cleanup: debug_lab.py delete-labs --instructor {args.instructor} '
                      f'--unit-id {result["unit_id"]} --yes', flush=True)
        return result

    def create_lab(self, args, *, on_created=None):
        from common.exceptions import NotFound, Unauthorized

        instructor = self._requester(args.instructor)
        try:
            peer = self._peer_service().get_authorized_remote_peer(args.remote_peer_id, instructor)
        except NotFound:
            raise DebugLabInputError(
                f"Remote peer '{args.remote_peer_id}' is not registered or enabled in {TEST_PROJECT}. "
                'Register it with enroll-peer or Admins → Build Manager → Remote Labs. '
                f'Use list-peers --instructor {args.instructor} to inspect authorized peers.') from None
        except Unauthorized:
            raise DebugLabInputError(
                f"Instructor {args.instructor} is not authorized for remote peer '{args.remote_peer_id}'. "
                'Ask an Agoge administrator to authorize this instructor.') from None
        if peer.assigned_unit_id:
            raise DebugLabInputError(f"Remote peer '{peer.id}' is already assigned to lab {peer.assigned_unit_id}. "
                             'Delete that lab to release it, or select another available remote peer.')
        data = {'build_file': args.template, 'remote_peer_id': args.remote_peer_id, 'build_count': args.count,
                'expires': (datetime.now(timezone.utc) + timedelta(hours=args.expires_hours)).isoformat(),
                'registration_required': False, 'lms_integration': False, 'test': True}
        manager = self.unit_class(env_dict=self.env_dict, debug=True)
        unit_id = manager.build(requester=instructor, data=data)
        if on_created is not None:
            on_created(unit_id)
        # Print before provisioning so failures/breakpoints retain a resumable ID.
        print(f'Created lab {unit_id}; provisioning locally.', flush=True)
        self._build_unit(unit_id)
        result = self.status(unit_id)
        if args.student_email:
            result['workout'] = self.create_workout(unit_id, args.student_email)
        return result

    def _build_unit(self, unit_id):
        from common.constants.pub_sub import PubSub

        self.dispatch({'handler': PubSub.Handlers.BUILD.value, 'action': str(PubSub.Actions.BUILD.value),
                       'course_object': str(PubSub.CourseObjects.UNIT.value), 'build_id': unit_id})

    def create_workout(self, unit_id, student_email):
        from common.constants.database import DbCollections
        from common.constants.states import UnitStates

        unit = self._unit(unit_id)
        if unit.get('state') not in (UnitStates.READY.value, UnitStates.RUNNING.value):
            raise ValueError('The lab must finish provisioning before a student claims a workout; '
                             'use unit-action --action build to resume it')
        manager = self.workout_class(env_dict=self.env_dict, debug_dispatch=self.dispatch)
        workout_id, exists = manager.build({'join_code': unit['join_code'], 'input_email': student_email,
                                            'accessibility_features': False, 'debug': True})
        record = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
        if not record:
            raise RuntimeError('The local worker returned without creating a workout')
        return {'workout_id': workout_id, 'exists': exists, 'state': record.get('state')}

    def action(self, scope, identifier, action, duration=2):
        from common.constants.database import DbCollections
        from common.constants.pub_sub import PubSub

        if scope == 'unit':
            self._unit(identifier)
        elif not self.db.get(collection_name=DbCollections.WORKOUT, doc_id=identifier):
            raise ValueError(f'Workout {identifier} was not found in {TEST_PROJECT}')
        attrs = {'handler': (PubSub.Handlers.BUILD if action == 'build' else PubSub.Handlers.CONTROL).value,
                 'action': str(PubSub.Actions[action.upper()].value), 'build_id': identifier,
                 'course_object': str((PubSub.CourseObjects.UNIT if scope == 'unit'
                                       else PubSub.CourseObjects.WORKOUT).value)}
        if action == 'start':
            attrs['duration'] = str(duration)
        self.dispatch(attrs)
        return {'scope': scope, 'id': identifier, 'action': action, 'worker_returned': True}

    def status(self, unit_id):
        from common.constants.database import DbCollections, DbOperators
        from common.constants.states import ServerStates, UnitStates

        unit = self._unit(unit_id)
        workouts = self.db.query(collection_name=DbCollections.WORKOUT,
                                 filters=[('parent_id', DbOperators.EQUAL, unit_id)])
        endpoint_snapshot = unit.get('wireguard_endpoint') or {}
        endpoint = (self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT,
                                doc_id=endpoint_snapshot['id']) if endpoint_snapshot.get('id') else {})
        # A reused gateway number must not advertise a different lab's DNS.
        if endpoint.get('unit_id') != unit_id:
            endpoint = {}
        lease = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id) or {}
        timestamp = lease.get('health_timestamp')
        health_age = (round(datetime.now(timezone.utc).timestamp() - timestamp, 1)
                      if type(timestamp) in (int, float) and math.isfinite(timestamp) else None)
        health_error = lease.get('health_error')
        if health_error and health_error not in ('wireguard_service_unready', 'bootstrap_failed'):
            health_error = 'other_error'
        gateway = {}
        for server in unit.get('servers') or []:
            if server.get('wireguard_gateway') is True:
                server_name = f'{unit_id}-{server["name"]}'
                record = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name) or {}
                try:
                    server_state_name = ServerStates(record.get('state')).name
                except ValueError:
                    server_state_name = 'UNKNOWN'
                gateway = {'server_name': server_name, 'state': record.get('state'),
                           'state_name': server_state_name}
                break
        try:
            state_name = UnitStates(unit.get('state')).name
        except ValueError:
            state_name = 'UNKNOWN'
        return {'project': TEST_PROJECT, 'unit_id': unit_id, 'join_code': unit.get('join_code'),
                'connection_id': f'{TEST_PROJECT}:{unit_id}' if endpoint else None,
                'state': unit.get('state'), 'state_name': state_name,
                'gateway': gateway,
                'endpoint': {key: endpoint.get(key) for key in ('hostname', 'port', 'status')},
                'wireguard': {'remote_peer_id': lease.get('remote_peer_id') or lease.get('kit_id'),
                              'remote_network_cidr': lease.get('remote_network_cidr') or lease.get('equipment_subnet'),
                              'health_age_seconds': health_age, 'health_error': health_error,
                              **{key: lease.get(key) for key in
                                 ('status', 'service_ready', 'tunnel_ready', 'health_timestamp', 'latest_handshake')}},
                'workouts': [{'workout_id': w['id'], 'state': w.get('state'),
                              'student_email': w.get('student_email')} for w in workouts]}


def load_backend(project, wireguard_api_url=None):
    if project != TEST_PROJECT:
        raise ValueError(f'This runner is limited to {TEST_PROJECT}')
    # Set before importing application modules: older nested factories use ADC's
    # default project rather than passing project_id explicitly.
    os.environ['GOOGLE_CLOUD_PROJECT'] = project
    os.environ['GCLOUD_PROJECT'] = project
    for directory in reversed((ROOT, ROOT / 'api', ROOT / 'cloud_functions')):
        sys.path.insert(0, str(directory))
    os.chdir(ROOT)

    from common.constants.database import DATABASE_NAME, DatabaseTypes
    from common.document_database import DocumentDatabaseFactory
    from common.utilities.gcp.cloud_env import CloudEnv
    from core.unit import Unit
    from core.workout import Workout
    from core.users import Users

    env_dict = CloudEnv(project=project).get_env()
    if env_dict.get('project') != project:
        raise ValueError('The selected environment document has a different project; correct it before building')
    if wireguard_api_url:
        env_dict = {**env_dict, 'wireguard_api_url': wireguard_api_url}
    db = DocumentDatabaseFactory.create_db_object(db_type=DatabaseTypes.firestore,
                                                 project_id=project, database_name=DATABASE_NAME)
    print(f'Local API + Cloud Function execution; real resources in {project}/{DATABASE_NAME}.', flush=True)
    return LocalBackend(env_dict, db, Unit, Workout, Users)


def _identifier(value):
    if not re.fullmatch(r'[a-z]{10}', value):
        raise argparse.ArgumentTypeError('Use the ten-letter lab/workout ID')
    return value


def _email(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise argparse.ArgumentTypeError('Use an email address')
    return value


def _count(value):
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError('Choose between 1 and 100 students')
    return number


def _hours(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 168:
        raise argparse.ArgumentTypeError('Choose more than zero and at most 168 hours')
    return number


def _https_url(value):
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise argparse.ArgumentTypeError('Use an HTTPS API base URL without credentials, query, or fragment')
    return value.rstrip('/')


def _remote_peer_id(value):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', value):
        raise argparse.ArgumentTypeError('Use a remote peer ID: 1–40 lowercase letters, digits, or hyphens')
    return value


def _absolute_path(value):
    # Resolve relative paths before load_backend changes the working directory.
    # Keep the final entry intact so exclusive token creation rejects symlinks.
    return Path(os.path.abspath(Path(value).expanduser()))


def _json_object(path, label):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('non-finite JSON number')

    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_keys,
                          parse_constant=invalid_constant)
    except OSError as error:
        raise ValueError(f'Cannot read {label} file {path}: {error.strerror}') from None
    except (UnicodeError, ValueError):
        raise ValueError(f'The {label} file must contain valid JSON with unique fields and finite numbers') from None
    if not isinstance(data, dict):
        raise ValueError(f'The {label} file must contain a JSON object')
    return data


class DebugArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        parsed = super().parse_args(args, namespace)
        try:
            if parsed.command in ('create-lab', 'run-lab'):
                self._lab_profile(parsed)
            else:
                parsed.project = getattr(parsed, 'project', TEST_PROJECT)
                parsed.wireguard_api_url = getattr(parsed, 'wireguard_api_url', None)
            if parsed.command == 'enroll-peer':
                from pydantic import ValidationError
                from common.models.wireguard_provisioning import WireGuardRemotePeerCreate

                data = _json_object(parsed.spec, 'peer registration')
                try:
                    parsed.peer_spec = WireGuardRemotePeerCreate.model_validate(data).model_dump(by_alias=True)
                except ValidationError as error:
                    # Validator messages can contain raw values themselves,
                    # e.g. ipaddress errors. Static hints also protect a
                    # credential accidentally placed in the wrong field.
                    hints = {
                        'id': 'use 1–40 lowercase letters, digits, or hyphens, starting with a letter',
                        'device_id': 'use a nonempty printable device identifier of at most 128 characters',
                        'remote_network_cidr': 'use a private IPv4 network address and CIDR, such as 192.168.50.0/24',
                        'equipment_subnet': 'use a private IPv4 network address and CIDR',
                        'peer_public_key': 'use the device WireGuard public key (base64-encoded 32 bytes)',
                        'authorized_instructors': 'use a list of 1–100 Agoge instructor email addresses',
                    }
                    details = []
                    for item in error.errors(include_input=False, include_context=False):
                        field = '.'.join(map(str, item['loc'])) or 'spec'
                        if item['type'] == 'extra_forbidden':
                            hint = 'unsupported field'
                        elif item['type'] == 'missing':
                            hint = 'required field'
                        else:
                            hint = hints.get(str(item['loc'][0]) if item['loc'] else '',
                                             'invalid or conflicting registration settings')
                        details.append(f'{field}: {hint}')
                    details = '; '.join(details)
                    raise ValueError(f'Invalid peer registration: {details}') from None
        except (ValueError, argparse.ArgumentTypeError) as error:
            self.error(str(error))
        return parsed

    @staticmethod
    def _lab_profile(args):
        defaults = {'project': TEST_PROJECT, 'wireguard_api_url': None,
                    'template': 'wireguard-factory-lab', 'count': 1, 'expires_hours': 2,
                    'student_email': None}
        allowed = {*defaults, 'instructor', 'remote_peer_id'}
        profile = _json_object(args.profile, 'debug profile') if getattr(args, 'profile', None) else {}
        unknown = profile.keys() - allowed
        if unknown:
            raise ValueError('Unknown debug profile fields: ' + ', '.join(sorted(unknown)))
        values = {**defaults, **profile, **{key: value for key, value in vars(args).items() if key in allowed}}
        for name in ('instructor', 'remote_peer_id'):
            if name not in values:
                raise ValueError(f'{args.command} requires --{name.replace("_", "-")} or {name} in --profile')
        for name in ('project', 'template', 'instructor', 'remote_peer_id', 'student_email', 'wireguard_api_url'):
            value = values[name]
            if value is None and name in ('student_email', 'wireguard_api_url'):
                continue
            if not isinstance(value, str):
                raise ValueError(f'Debug profile {name} must be a string')
        if values['project'] != TEST_PROJECT:
            raise ValueError(f'This runner is limited to {TEST_PROJECT}')
        template = values['template']
        if not template.strip() or '/' in template or any(ord(c) < 32 for c in template):
            raise ValueError('Use a catalog template document ID')
        values['instructor'] = _email(values['instructor'])
        values['remote_peer_id'] = _remote_peer_id(values['remote_peer_id'])
        if values['student_email'] is not None:
            values['student_email'] = _email(values['student_email'])
        if values['wireguard_api_url'] is not None:
            values['wireguard_api_url'] = _https_url(values['wireguard_api_url'])
        if type(values['count']) is not int:
            raise ValueError('Debug profile count must be an integer')
        values['count'] = _count(values['count'])
        if type(values['expires_hours']) not in (int, float):
            raise ValueError('Debug profile expires_hours must be a number')
        values['expires_hours'] = _hours(values['expires_hours'])
        for name, value in values.items():
            setattr(args, name, value)


def parser():
    result = DebugArgumentParser(description=__doc__)
    result.add_argument('--project', default=argparse.SUPPRESS, choices=[TEST_PROJECT])
    result.add_argument('--wireguard-api-url', type=_https_url, default=argparse.SUPPRESS,
                        help='HTTPS callback base for a new lab; defaults to the project API')
    commands = result.add_subparsers(dest='command', required=True)
    for name, description in (
            ('create-lab', 'Create a lab from the uploaded catalog template'),
            ('run-lab', 'Build, start, stop, and delete a lab with prompts between stages')):
        lab = commands.add_parser(name, help=description)
        lab.add_argument('--profile', type=_absolute_path, help='JSON debug profile; explicit flags override its values')
        lab.add_argument('--project', default=argparse.SUPPRESS, choices=[TEST_PROJECT])
        lab.add_argument('--wireguard-api-url', type=_https_url, default=argparse.SUPPRESS)
        lab.add_argument('--template', default=argparse.SUPPRESS)
        lab.add_argument('--instructor', default=argparse.SUPPRESS, type=_email)
        lab.add_argument('--remote-peer-id', '--kit-id', dest='remote_peer_id', default=argparse.SUPPRESS, type=_remote_peer_id,
                        help='Registered remote peer ID (--kit-id is a compatibility alias)')
        lab.add_argument('--count', default=argparse.SUPPRESS, type=_count)
        lab.add_argument('--expires-hours', default=argparse.SUPPRESS, type=_hours)
        lab.add_argument('--student-email', default=argparse.SUPPRESS, type=_email,
                         help='Also claim and build one student workout')
        if name == 'run-lab':
            lab.set_defaults(recent_cleanup='ask')
            cleanup_mode = lab.add_mutually_exclusive_group()
            cleanup_mode.add_argument('--delete-recent', dest='recent_cleanup', action='store_const', const='delete',
                                      help='Automatically delete recent test labs for this instructor and peer')
            cleanup_mode.add_argument('--skip-cleanup', dest='recent_cleanup', action='store_const', const='skip',
                                      help='Bypass the recent-lab check; lifecycle prompts still apply')
            lab.add_argument('--recent-hours', type=_hours, default=24,
                             help='Recent cleanup window in hours, more than zero and at most 168 (default: 24)')
            lab.add_argument('--duration-hours', type=int, default=2, choices=range(1, 11),
                             help='Student workout runtime when starting (default: 2)')
    peers = commands.add_parser('list-peers', help='List remote peers authorized for an Agoge instructor or admin')
    peers.add_argument('--instructor', required=True, type=_email)
    labs = commands.add_parser('list-labs', help='List authorized test labs from previous debug runs')
    labs.add_argument('--instructor', required=True, type=_email)
    labs.add_argument('--remote-peer-id', type=_remote_peer_id)
    labs.add_argument('--include-deleted', action='store_true')
    cleanup = commands.add_parser('delete-labs', help='Preview or delete explicitly selected test labs')
    cleanup.add_argument('--instructor', required=True, type=_email)
    cleanup.add_argument('--unit-id', dest='unit_ids', required=True, action='append', type=_identifier,
                         help='Lab ID to delete; repeat this flag to select multiple labs')
    cleanup.add_argument('--yes', action='store_true', help='Execute deletion; otherwise only preview selected labs')
    enroll = commands.add_parser('enroll-peer', help='Register one remote peer without creating a lab')
    enroll.add_argument('--admin', required=True, type=_email, help='Existing Agoge admin account')
    enroll.add_argument('--spec', required=True, type=_absolute_path, help='JSON public peer registration fields')
    enroll.add_argument('--token-out', required=True, type=_absolute_path,
                        help='New protected file for the one-time enrollment token; never overwritten')
    workout = commands.add_parser('create-workout', help='Claim a student workout through local API code')
    workout.add_argument('--unit-id', required=True, type=_identifier)
    workout.add_argument('--student-email', required=True, type=_email)
    status = commands.add_parser('status', help='Read lab, workout, and WireGuard status')
    status.add_argument('--unit-id', required=True, type=_identifier)
    for scope in ('unit', 'workout'):
        action = commands.add_parser(f'{scope}-action', help=f'Run a local {scope} lifecycle operation')
        action.add_argument(f'--{scope}-id', required=True, type=_identifier)
        action.add_argument('--action', required=True, choices=['build', 'start', 'stop', 'delete'])
        action.add_argument('--duration-hours', type=int, default=2, choices=range(1, 11))
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    from common.exceptions import BaseAgogeException

    try:
        backend = load_backend(args.project, args.wireguard_api_url)
        if args.command == 'create-lab':
            result = backend.create_lab(args)
        elif args.command == 'run-lab':
            result = backend.run_lab(args)
        elif args.command == 'list-peers':
            result = backend.list_peers(args.instructor)
        elif args.command == 'list-labs':
            result = backend.list_labs(args.instructor, args.remote_peer_id, args.include_deleted)
        elif args.command == 'delete-labs':
            result = backend.delete_labs(args.instructor, args.unit_ids, execute=args.yes)
        elif args.command == 'enroll-peer':
            result = backend.enroll_peer(args.admin, args.peer_spec, args.token_out)
        elif args.command == 'create-workout':
            result = backend.create_workout(args.unit_id, args.student_email)
        elif args.command == 'status':
            result = backend.status(args.unit_id)
        else:
            scope = args.command.removesuffix('-action')
            result = backend.action(scope, getattr(args, f'{scope}_id'), args.action, args.duration_hours)
    except (ValueError, OSError, BaseAgogeException) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except Exception as error:
        print(f'Error: {type(error).__name__}', file=sys.stderr)
        report_error_location(error)
        return 1
    print(json.dumps(result, indent=2))
    if args.command == 'run-lab':
        return result['exit_code']
    return 1 if args.command == 'delete-labs' and result.get('failed', 0) else 0


if __name__ == '__main__':
    raise SystemExit(main())
