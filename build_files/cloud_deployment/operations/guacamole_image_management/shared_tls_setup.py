"""Deploy the shared certificate function and authorize tenant proxy identities."""

import argparse
import base64
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from google.api_core.exceptions import Aborted, AlreadyExists, Conflict, InvalidArgument, NotFound, PreconditionFailed
from google.cloud import firestore, secretmanager, storage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from common.constants.build_constants import BuildConstants
from common.constants.database import ADMIN_INFO_DOCUMENT, DATABASE_NAME, DbCollections
from common.exceptions import AgogeValidationError
from common.services.guacamole_tls_startup import GUACAMOLE_TLS_IMAGE_PATTERN, guacamole_tls_reader_email
from common.services.wireguard_provisioning import WireGuardSecretStore

SHARED_PROJECT = BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT
PUBLISHER_PERMISSIONS = (
    'secretmanager.secrets.get',
    'secretmanager.secrets.update',
    'secretmanager.versions.access',
    'secretmanager.versions.add',
)
ACCESSOR_ROLE = 'roles/secretmanager.secretAccessor'
DNS_PROJECT_LABEL = 'agoge-tls-dns-project'
MAINTENANCE_ATTRIBUTES = {'handler': 'MAINTENANCE'}
ISSUER_SOURCE = Path(__file__).resolve().parents[4] / 'cloud_functions' / (
    'cloud_fn_utilities/periodic_maintenance'
)


def _gcloud(*arguments):
    try:
        result = subprocess.run(
            ['gcloud', '--quiet', *arguments],
            text=True, capture_output=True, check=False,
        )
    except FileNotFoundError as exc:
        raise AgogeValidationError('The gcloud CLI is required for Guacamole TLS setup.') from exc
    if result.returncode:
        raise AgogeValidationError(result.stderr.strip() or f'gcloud {arguments[0]} failed.')
    return result.stdout


def _get_or_create(get, create):
    """Handle an existing resource and concurrent setup without masking other errors."""
    try:
        return get()
    except (NotFound, HttpError) as exc:
        if isinstance(exc, HttpError) and exc.resp.status != 404:
            raise
    try:
        return create()
    except (AlreadyExists, Conflict, HttpError) as exc:
        if isinstance(exc, HttpError) and exc.resp.status != 409:
            raise
        return get()


def _ensure_service_account(project, account_id, display_name):
    accounts = build('iam', 'v1', cache_discovery=False).projects().serviceAccounts()
    email = f'{account_id}@{project}.iam.gserviceaccount.com'
    name = f'projects/{project}/serviceAccounts/{email}'
    account = _get_or_create(
        lambda: accounts.get(name=name).execute(),
        lambda: accounts.create(name=f'projects/{project}', body={
            'accountId': account_id,
            'serviceAccount': {'displayName': display_name},
        }).execute(),
    )
    if account.get('disabled'):
        raise AgogeValidationError(f'Service account {email} is disabled.')
    return email


def _retry_iam_update(email, update):
    delays = (1, 2, 4, 8, 16, None)
    for delay in delays:
        try:
            return update()
        except (Aborted, Conflict, InvalidArgument, PreconditionFailed, HttpError) as exc:
            if delay is None:
                raise
            if isinstance(exc, InvalidArgument) or (isinstance(exc, HttpError) and exc.resp.status == 400):
                if not WireGuardSecretStore._is_unpropagated_identity(exc, email):
                    raise
            elif isinstance(exc, HttpError) and exc.resp.status not in (409, 412):
                raise
            time.sleep(delay)


def _set_secret_membership(client, name, role, email, *, present=True):
    _retry_iam_update(email, lambda: _update_secret_membership(client, name, role, email, present))


def _update_secret_membership(client, name, role, email, present):
    member = f'serviceAccount:{email}'
    policy = client.get_iam_policy(request={
        'resource': name,
        'options': {'requested_policy_version': 3},
    })
    binding = next((value for value in policy.bindings
                    if value.role == role and not value.HasField('condition')), None)
    if present:
        if binding is None:
            binding = policy.bindings.add(role=role)
        if member in binding.members:
            return
        binding.members.append(member)
    else:
        if binding is None or member not in binding.members:
            return
        binding.members.remove(member)
        if not binding.members:
            policy.bindings.remove(binding)
    client.set_iam_policy(request={'resource': name, 'policy': policy})


def _ensure_bucket(project, region, name, project_number, issuer):
    client = storage.Client(project=project)

    def create():
        bucket = client.bucket(name)
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        bucket.iam_configuration.public_access_prevention = 'enforced'
        return client.create_bucket(bucket, location=region)

    bucket = _get_or_create(lambda: client.get_bucket(name), create)
    if (str(bucket.project_number) != str(project_number)
            or not bucket.iam_configuration.uniform_bucket_level_access_enabled
            or bucket.iam_configuration.public_access_prevention != 'enforced'):
        raise AgogeValidationError(
            f'Use a bucket owned by {project} with uniform access and public access prevention enforced.'
        )
    _retry_iam_update(issuer, lambda: _grant_state_access(bucket, issuer))


def _grant_state_access(bucket, issuer):
    member = f'serviceAccount:{issuer}'
    role = 'roles/storage.objectUser'
    policy = bucket.get_iam_policy(requested_policy_version=3)
    binding = next((entry for entry in policy.bindings
                    if entry['role'] == role and not entry.get('condition')), None)
    if binding is None:
        policy.bindings.append({'role': role, 'members': {member}})
    elif member in binding['members']:
        return
    else:
        binding['members'].add(member)
    bucket.set_iam_policy(policy)


def _publisher_role(project):
    role_id = 'agogeGuacamoleTlsPublisher'
    roles = build('iam', 'v1', cache_discovery=False).projects().roles()
    name = f'projects/{project}/roles/{role_id}'
    role = _get_or_create(
        lambda: roles.get(name=name).execute(),
        lambda: roles.create(parent=f'projects/{project}', body={
            'roleId': role_id,
            'role': {
                'title': 'Agoge Guacamole TLS publisher',
                'includedPermissions': list(PUBLISHER_PERMISSIONS),
                'stage': 'GA',
            },
        }).execute(),
    )
    if role.get('deleted') or role.get('stage') == 'DISABLED' or (
        set(role.get('includedPermissions', [])) != set(PUBLISHER_PERMISSIONS)
    ):
        raise AgogeValidationError(f'Check the permissions on {name} before deploying.')
    return name


def _grant_dns_zone_access(project, zone, issuer):
    zones = build('dns', 'v1', cache_discovery=False).managedZones()
    resource = f'projects/{project}/managedZones/{zone}'
    _retry_iam_update(issuer, lambda: _update_dns_zone_policy(zones, resource, issuer))


def _update_dns_zone_policy(zones, resource, issuer):
    policy = zones.getIamPolicy(
        resource=resource, body={'options': {'requestedPolicyVersion': 3}},
    ).execute()
    role = 'roles/dns.admin'
    member = f'serviceAccount:{issuer}'
    bindings = policy.setdefault('bindings', [])
    binding = next((value for value in bindings
                    if value['role'] == role and not value.get('condition')), None)
    if binding is None:
        bindings.append({'role': role, 'members': [member]})
    elif member in binding['members']:
        return
    else:
        binding['members'].append(member)
    zones.setIamPolicy(resource=resource, body={'policy': policy}).execute()


def _maintenance_source(project, region, function, *, reuse_shared=True):
    jobs = build('cloudscheduler', 'v1', cache_discovery=False).projects().locations().jobs()
    location = f'projects/{project}/locations/{region}'
    parent_name = f'{location}/jobs/agoge-hourly-maintenance'
    dedicated_name = f'{location}/jobs/{function}'
    # Keep a dedicated trigger on redeploy if it already exists.
    for name in (dedicated_name, parent_name) if reuse_shared else (dedicated_name,):
        try:
            job = jobs.get(name=name).execute()
        except HttpError as exc:
            if exc.resp.status != 404:
                raise
            continue
        target = job.get('pubsubTarget', {})
        topic = target.get('topicName', '')
        if (not topic.startswith(f'projects/{project}/topics/')
                or target.get('attributes', {}).get('handler') != 'MAINTENANCE'):
            if name == dedicated_name:
                raise AgogeValidationError(f'Check the existing certificate schedule {name}.')
            continue
        if name == dedicated_name:
            if job.get('schedule') != '0 0 * * *' or job.get('state') != 'ENABLED':
                raise AgogeValidationError(f'Check the cadence or paused state of {name}.')
            return jobs, location, topic, '', False
        if job.get('state') == 'ENABLED' and job.get('schedule') == '*/15 * * * *':
            return jobs, location, topic, job.get('timeZone') or 'Etc/UTC', False
    return jobs, location, f'projects/{project}/topics/{function}', '', True


def _ensure_topic(topic):
    topics = build('pubsub', 'v1', cache_discovery=False).projects().topics()
    _get_or_create(
        lambda: topics.get(topic=topic).execute(),
        lambda: topics.create(name=topic, body={}).execute(),
    )


def _alert_on_errors(project, function, channel):
    if not re.fullmatch(rf'projects/{re.escape(project)}/notificationChannels/[0-9]+', channel):
        raise AgogeValidationError('Use the full Monitoring notification channel name from the issuer project.')
    name = f'projects/{project}'
    policies = build('monitoring', 'v3', cache_discovery=False).projects().alertPolicies()
    title = f'Agoge certificate errors ({function})'
    body = {
        'displayName': title,
        'combiner': 'OR',
        'conditions': [{
            'displayName': 'Renewal failed or certificate expires soon',
            'conditionMatchedLog': {'filter': (
                'resource.type="cloud_run_revision" '
                f'resource.labels.service_name="{function}" severity>=ERROR'
            )},
        }],
        'notificationChannels': [channel],
        'alertStrategy': {
            'notificationRateLimit': {'period': '3600s'},
            'autoClose': '604800s',
        },
    }
    request = policies.list(name=name, filter=f'display_name = "{title}"')
    while request is not None:
        response = request.execute()
        for existing in response.get('alertPolicies', []):
            if existing['displayName'] == title:
                body['conditions'][0]['name'] = existing['conditions'][0]['name']
                policies.patch(
                    name=existing['name'], body=body,
                    updateMask='conditions,notification_channels,alert_strategy',
                ).execute()
                return
        request = policies.list_next(request, response)
    policies.create(name=name, body=body).execute()


def deploy_shared_tls(args):
    """Deploy only certificate issuance. The tenant Cloud Function is separate."""
    project = args.project
    domain = args.domain.lower().strip('.')
    labels = domain.split('.')
    if len(labels) < 2 or not all(
        re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels
    ):
        raise AgogeValidationError('A DNS domain such as agoge-labs.com is required.')
    if not re.fullmatch(r'[^\s,=]+@[^\s,=]+', args.email):
        raise AgogeValidationError('A valid ACME contact email is required.')
    ZoneInfo(args.timezone)
    stage_suffix = '-staging' if args.staging else ''
    function = f'agoge-guacamole-tls{stage_suffix}'
    mandatory = (
        'cloudfunctions', 'run', 'eventarc', 'artifactregistry', 'cloudbuild', 'pubsub',
        'cloudscheduler', 'secretmanager', 'storage', 'iam',
    )
    services = [f'{service}.googleapis.com' for service in mandatory]
    if args.notification_channel:
        services.append('monitoring.googleapis.com')
    # Validate the explicit public zone before changing shared resources.
    zone = json.loads(_gcloud(
        'dns', 'managed-zones', 'describe', args.dns_zone,
        '--project', args.dns_project, '--format=json',
    ))
    if zone.get('visibility') != 'public' or zone.get('dnsName') != f'{domain}.':
        raise AgogeValidationError(
            f'{args.dns_zone} in {args.dns_project} must be a public DNS zone for {domain}.'
        )
    _gcloud('services', 'enable', *services, '--project', project)
    project_number = json.loads(
        _gcloud('projects', 'describe', project, '--format=json')
    )['projectNumber']
    issuer = _ensure_service_account(project, f'agoge-tls-issuer{stage_suffix}', 'Agoge TLS issuer')
    trigger = _ensure_service_account(project, f'agoge-tls-trigger{stage_suffix}', 'Agoge TLS Pub/Sub trigger')
    bucket_name = args.state_bucket or f'{project}-guacamole-tls-state{stage_suffix}'
    _ensure_bucket(project, args.region, bucket_name, project_number, issuer)

    secret_id = f'guacamole-tls-{domain.replace(".", "-")}{stage_suffix}'
    secret_name = f'projects/{project}/secrets/{secret_id}'
    secrets = secretmanager.SecretManagerServiceClient()
    certificate = _get_or_create(
        lambda: secrets.get_secret(request={'name': secret_name}),
        lambda: secrets.create_secret(request={
            'parent': f'projects/{project}', 'secret_id': secret_id,
            'secret': {
                'replication': {'automatic': {}},
                'labels': {DNS_PROJECT_LABEL: args.dns_project},
            },
        }),
    )
    if certificate.labels.get(DNS_PROJECT_LABEL) != args.dns_project:
        secrets.update_secret(request={
            'secret': {
                'name': secret_name,
                'etag': certificate.etag,
                'labels': dict(certificate.labels) | {DNS_PROJECT_LABEL: args.dns_project},
            },
            'update_mask': {'paths': ['labels']},
        })
    _set_secret_membership(secrets, secret_name, _publisher_role(project), issuer)
    issuer_member = f'--member=serviceAccount:{issuer}'
    _gcloud('projects', 'add-iam-policy-binding', args.dns_project, issuer_member,
            '--role=roles/dns.reader', '--condition=None')
    _grant_dns_zone_access(args.dns_project, args.dns_zone, issuer)

    jobs, scheduler_location, topic, schedule_timezone, create_schedule = _maintenance_source(
        project, args.scheduler_region or args.region, function, reuse_shared=not args.staging,
    )
    _ensure_topic(topic)
    env = {
        'AGOGE_TLS_PROJECT': project,
        'AGOGE_TLS_DOMAIN': domain,
        'AGOGE_TLS_DNS_PROJECT': args.dns_project,
        'AGOGE_TLS_STATE_BUCKET': bucket_name,
        'AGOGE_TLS_SECRET': secret_id,
        'AGOGE_TLS_EMAIL': args.email,
        'AGOGE_TLS_STAGING': str(args.staging).lower(),
        'AGOGE_TLS_SCHEDULE_TIMEZONE': schedule_timezone,
    }
    print(f'Deploying {function} in {project} for {domain}.', flush=True)
    with TemporaryDirectory(prefix='agoge-guacamole-tls-') as staging:
        for source, target in (
            ('guacamole_certificate_issuer.py', 'main.py'),
            ('guacamole_certificate_requirements.txt', 'requirements.txt'),
            ('maintenance_schedule.py', 'maintenance_schedule.py'),
        ):
            shutil.copyfile(ISSUER_SOURCE / source, Path(staging) / target)
        _gcloud(
            'functions', 'deploy', function, '--gen2', '--project', project,
            '--region', args.region, '--runtime=python312', '--source', staging,
            '--entry-point=renew_guacamole_certificate', '--trigger-topic', topic,
            '--trigger-service-account', trigger, '--run-service-account', issuer,
            '--timeout=540s', '--memory=512Mi', '--max-instances=1', '--concurrency=1', '--retry',
            '--set-env-vars', ','.join(f'{key}={value}' for key, value in env.items()),
        )
    _gcloud(
        'run', 'services', 'add-iam-policy-binding', function, '--project', project,
        '--region', args.region, '--member', f'serviceAccount:{trigger}',
        '--role=roles/run.invoker',
    )
    if create_schedule:
        job_name = f'{scheduler_location}/jobs/{function}'
        _get_or_create(
            lambda: jobs.get(name=job_name).execute(),
            lambda: jobs.create(parent=scheduler_location, body={
                'name': job_name,
                'schedule': '0 0 * * *',
                'timeZone': args.timezone,
                'pubsubTarget': {
                    'topicName': topic,
                    'attributes': MAINTENANCE_ATTRIBUTES,
                    'data': base64.b64encode(b'Guacamole certificate check').decode('ascii'),
                },
            }).execute(),
        )
    if args.notification_channel:
        _alert_on_errors(project, function, args.notification_channel)
    print(f'Deployed {function}. Certificate destination: {secret_name}/versions/active')
    print(f'To check now: gcloud pubsub topics publish {topic} --attribute=handler=MAINTENANCE '
          '--message=guacamole-certificate-check' if not schedule_timezone else
          f'Reusing the shared maintenance schedule ({schedule_timezone}).')


def _tenant_config(project, parent, domain, dns_project):
    database = firestore.Client(project=project, database=DATABASE_NAME)
    ref = database.collection(DbCollections.ADMIN_INFO.value).document(ADMIN_INFO_DOCUMENT)
    snapshot = ref.get()
    data = snapshot.to_dict() or {}
    tenant_domain = (data.get('parent_dns_suffix') or data.get('dns_suffix') or '').strip('.').lower()
    valid_parents = {parent, dns_project or parent}
    if (data.get('project') != project or data.get('parent_project') not in valid_parents
            or tenant_domain != domain):
        raise AgogeValidationError(
            f'{project} must use {domain} and a parent matching the shared or DNS project.'
        )
    return database, ref, snapshot, data


def reconcile_tenants(args):
    """Grant or remove access for named tenants while preserving unrelated grants."""
    parent = args.project
    domain = args.domain.strip('.').lower()
    secret_name = f'projects/{parent}/secrets/guacamole-tls-{domain.replace(".", "-")}'
    client = secretmanager.SecretManagerServiceClient()
    secret = client.get_secret(request={'name': secret_name})
    dns_project = secret.labels.get(DNS_PROJECT_LABEL)
    if args.allow:
        active = secret.version_aliases.get('active')
        if not active or client.get_secret_version(request={
            'name': f'{secret_name}/versions/{active}',
        }).state != secretmanager.SecretVersion.State.ENABLED:
            raise AgogeValidationError('Publish the first active production certificate before enrolling tenants.')
    if set(args.allow) & set(args.remove):
        raise AgogeValidationError('A tenant cannot be enrolled and removed in the same command.')

    for project in dict.fromkeys(args.allow):
        database, ref, snapshot, data = _tenant_config(project, parent, domain, dns_project)
        configured_secret = data.get('guacamole_tls_secret')
        if configured_secret and configured_secret != secret_name:
            raise AgogeValidationError(f'{project} is already configured for {configured_secret}.')
        _gcloud('services', 'enable', 'iamcredentials.googleapis.com', '--project', project)
        reader = guacamole_tls_reader_email(project)
        _ensure_service_account(project, reader.split('@', 1)[0], 'Agoge Guacamole TLS reader')
        for role in ('roles/iam.serviceAccountUser', 'roles/iam.serviceAccountAdmin'):
            _gcloud(
                'iam', 'service-accounts', 'add-iam-policy-binding', reader, '--project', project,
                '--member', f'serviceAccount:agoge-service@{project}.iam.gserviceaccount.com',
                '--role', role, '--condition=None',
            )
        _set_secret_membership(client, secret_name, ACCESSOR_ROLE, reader)
        changes = {}
        if configured_secret != secret_name:
            changes['guacamole_tls_secret'] = secret_name
        if args.image and data.get('guacamole_tls_image') != args.image:
            changes['guacamole_tls_image'] = args.image
        if changes:
            ref.update(changes, option=database.write_option(last_update_time=snapshot.update_time))
        print(f'{project}: opted in with {reader}.')

    for project in dict.fromkeys(args.remove):
        # The child may have been offboarded or deleted already. In that case
        # the remaining parent IAM binding is still safe to revoke.
        _set_secret_membership(
            client, secret_name, ACCESSOR_ROLE, guacamole_tls_reader_email(project), present=False,
        )
        try:
            database, ref, snapshot, data = _tenant_config(project, parent, domain, dns_project)
        except (AgogeValidationError, NotFound):
            print(f'{project}: removed shared access. The tenant configuration was unavailable or differs.')
            continue
        if data.get('guacamole_tls_secret') == secret_name:
            ref.update({'guacamole_tls_secret': firestore.DELETE_FIELD,
                        'guacamole_tls_image': firestore.DELETE_FIELD},
                       option=database.write_option(last_update_time=snapshot.update_time))
        print(f'{project}: removed shared access and tenant opt-in.')


def cli(argv):
    parser = argparse.ArgumentParser(prog='setup.py guacamole-tls', description=__doc__)
    subcommands = parser.add_subparsers(dest='operation', required=True)
    deploy = subcommands.add_parser('deploy', help='Deploy serverless renewal in the shared project.')
    deploy.add_argument('--project', default=SHARED_PROJECT, help='Shared project for function and secret.')
    deploy.add_argument('--domain', required=True, help='Apex DNS name covered along with its wildcard.')
    deploy.add_argument('--dns-project', required=True, help='Project hosting the Cloud DNS zone.')
    deploy.add_argument('--dns-zone', required=True, help='Public Cloud DNS managed zone name.')
    deploy.add_argument('--email', required=True, help='ACME account contact.')
    deploy.add_argument('--region', default='us-central1')
    deploy.add_argument('--scheduler-region', help='Scheduler region, if different from the function region.')
    deploy.add_argument('--timezone', default='America/Chicago', help='Timezone for a new daily schedule.')
    deploy.add_argument('--state-bucket', help='Optional dedicated private Certbot state bucket.')
    deploy.add_argument('--notification-channel', help='Full Cloud Monitoring notification channel name.')
    deploy.add_argument('--staging', action='store_true', help='Issue from Let’s Encrypt staging into a separate secret.')
    deploy.set_defaults(run=deploy_shared_tls)

    reconcile = subcommands.add_parser('reconcile', help='Enroll or remove named tenant projects.')
    reconcile.add_argument('--project', default=SHARED_PROJECT, help='Shared project for the certificate secret.')
    reconcile.add_argument('--domain', required=True)
    reconcile.add_argument('--allow', action='append', default=[], metavar='TENANT_PROJECT')
    reconcile.add_argument('--remove', action='append', default=[], metavar='TENANT_PROJECT')
    reconcile.add_argument('--image', help='Ready, project-qualified Guacamole Compute image for enrolled tenants.')
    reconcile.set_defaults(run=reconcile_tenants)

    image = subcommands.add_parser('build-image', help='Build a Guacamole image without a wildcard key.')
    image.add_argument('--project', required=True, help='Project to own the new image.')
    image.add_argument('--image-name', help='Unique image name, default image-guac-tls-PROJECT.')

    migrate = subcommands.add_parser('migrate', help='Plan or apply updates to existing tenant proxy VMs.')
    migrate.add_argument('--project', required=True, help='Tenant project containing Guacamole proxy VMs.')
    migrate.add_argument('--instance', help='Limit migration to one instance name.')
    migrate.add_argument('--apply', action='store_true', help='Apply the migration. By default only show the plan.')
    migrate.add_argument('--restart-running', action='store_true', help='Allow restart where the VM identity must change.')

    args = parser.parse_args(argv)
    if args.operation == 'build-image':
        from .guacamole_image_manager import GuacamoleImageManager

        print(GuacamoleImageManager(args.project).create_guac_tls_image(args.image_name))
        return
    if args.operation == 'migrate':
        if args.restart_running and not args.apply:
            parser.error('--restart-running requires --apply')
        from cloud_deployment.operations.project_maintenance.migrate_guacamole_tls import migrate_guacamole_tls

        if not migrate_guacamole_tls(
            args.project, apply=args.apply, restart_running=args.restart_running, instance_name=args.instance,
        ):
            raise SystemExit(1)
        return
    if args.operation == 'reconcile' and not (args.allow or args.remove):
        parser.error('reconcile requires at least one --allow or --remove')
    if args.operation == 'reconcile' and args.image:
        if not args.allow or not re.fullmatch(GUACAMOLE_TLS_IMAGE_PATTERN, args.image):
            parser.error('--image requires --allow and projects/PROJECT/global/images/IMAGE')
    args.run(args)
