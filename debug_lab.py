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

    def _requester(self, email, *, admin=False):
        requester = self.users_class().get_user(user_email=email)
        if admin:
            if not requester.is_admin:
                raise ValueError('Peer enrollment requires an existing Agoge admin account')
        elif not requester.is_authorized:
            raise ValueError('The instructor must have an existing Agoge instructor or admin account')
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

    def create_lab(self, args):
        from common.exceptions import NotFound, Unauthorized

        instructor = self._requester(args.instructor)
        try:
            peer = self._peer_service().get_authorized_remote_peer(args.remote_peer_id, instructor)
        except NotFound:
            raise ValueError(
                f"Remote peer '{args.remote_peer_id}' is not registered or enabled in {TEST_PROJECT}. "
                'Register it with enroll-peer or Admins → Build Manager → Remote Labs. '
                f'Use list-peers --instructor {args.instructor} to inspect authorized peers.') from None
        except Unauthorized:
            raise ValueError(
                f"Instructor {args.instructor} is not authorized for remote peer '{args.remote_peer_id}'. "
                'Ask an Agoge administrator to authorize this instructor.') from None
        if peer.assigned_unit_id:
            raise ValueError(f"Remote peer '{peer.id}' is already assigned to lab {peer.assigned_unit_id}. "
                             'Delete that lab to release it, or select another available remote peer.')
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
            if parsed.command == 'create-lab':
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
                raise ValueError(f'create-lab requires --{name.replace("_", "-")} or {name} in --profile')
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
    lab = commands.add_parser('create-lab', help='Create a lab from the uploaded catalog template')
    lab.add_argument('--profile', type=_absolute_path, help='JSON debug profile; explicit flags override its values')
    lab.add_argument('--project', default=argparse.SUPPRESS, choices=[TEST_PROJECT])
    lab.add_argument('--wireguard-api-url', type=_https_url, default=argparse.SUPPRESS)
    lab.add_argument('--template', default=argparse.SUPPRESS)
    lab.add_argument('--instructor', default=argparse.SUPPRESS, type=_email)
    lab.add_argument('--remote-peer-id', '--kit-id', dest='remote_peer_id', default=argparse.SUPPRESS, type=_remote_peer_id,
                     help='Registered remote peer ID (--kit-id is a compatibility alias)')
    lab.add_argument('--count', default=argparse.SUPPRESS, type=_count)
    lab.add_argument('--expires-hours', default=argparse.SUPPRESS, type=_hours)
    lab.add_argument('--student-email', default=argparse.SUPPRESS, type=_email, help='Also claim and build one student workout')
    peers = commands.add_parser('list-peers', help='List remote peers authorized for an Agoge instructor or admin')
    peers.add_argument('--instructor', required=True, type=_email)
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
        elif args.command == 'list-peers':
            result = backend.list_peers(args.instructor)
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
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
