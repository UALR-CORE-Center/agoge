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

    def create_lab(self, args):
        instructor = self.users_class().get_user(user_email=args.instructor)
        if not instructor.is_authorized:
            raise ValueError('The instructor must have an existing Agoge instructor or admin account')
        data = {'build_file': args.template, 'remote_peer_id': args.remote_peer_id, 'build_count': args.count,
                'expires': (datetime.now(timezone.utc) + timedelta(hours=args.expires_hours)).isoformat(),
                'registration_required': False, 'lms_integration': False, 'test': True}
        manager = self.unit_class(env_dict=self.env_dict, debug=True)
        unit_id = manager.build(requester=instructor, data=data)
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
        from common.constants.database import DbCollections
        from common.constants.states import UnitStates

        unit = self._unit(unit_id)
        workouts = self.db.query(collection_name=DbCollections.WORKOUT,
                                 filters=[('parent_id', '==', unit_id)])
        endpoint_snapshot = unit.get('wireguard_endpoint') or {}
        endpoint = (self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT,
                                doc_id=endpoint_snapshot['id']) if endpoint_snapshot.get('id') else {})
        # A reused gateway number must not advertise a different lab's DNS.
        if endpoint.get('unit_id') != unit_id:
            endpoint = {}
        lease = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id) or {}
        try:
            state_name = UnitStates(unit.get('state')).name
        except ValueError:
            state_name = 'UNKNOWN'
        return {'project': TEST_PROJECT, 'unit_id': unit_id, 'join_code': unit.get('join_code'),
                'connection_id': f'{TEST_PROJECT}:{unit_id}' if endpoint else None,
                'state': unit.get('state'), 'state_name': state_name,
                'endpoint': {key: endpoint.get(key) for key in ('hostname', 'port')},
                'wireguard': {'remote_peer_id': lease.get('remote_peer_id') or lease.get('kit_id'),
                              'remote_network_cidr': lease.get('remote_network_cidr') or lease.get('equipment_subnet'),
                              **{key: lease.get(key) for key in
                                 ('status', 'service_ready', 'tunnel_ready', 'health_timestamp')}},
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


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--project', default=TEST_PROJECT, choices=[TEST_PROJECT])
    result.add_argument('--wireguard-api-url', type=_https_url,
                        help='HTTPS callback base for a new lab; defaults to the project API')
    commands = result.add_subparsers(dest='command', required=True)
    lab = commands.add_parser('create-lab', help='Create a lab from the uploaded catalog template')
    lab.add_argument('--template', default='wireguard-factory-lab')
    lab.add_argument('--instructor', required=True, type=_email)
    lab.add_argument('--remote-peer-id', '--kit-id', dest='remote_peer_id', required=True,
                     help='Registered remote peer ID (--kit-id is a compatibility alias)')
    lab.add_argument('--count', default=1, type=_count)
    lab.add_argument('--expires-hours', default=2, type=_hours)
    lab.add_argument('--student-email', type=_email, help='Also claim and build one student workout')
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
    backend = load_backend(args.project, args.wireguard_api_url)
    if args.command == 'create-lab':
        result = backend.create_lab(args)
    elif args.command == 'create-workout':
        result = backend.create_workout(args.unit_id, args.student_email)
    elif args.command == 'status':
        result = backend.status(args.unit_id)
    else:
        scope = args.command.removesuffix('-action')
        result = backend.action(scope, getattr(args, f'{scope}_id'), args.action, args.duration_hours)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
