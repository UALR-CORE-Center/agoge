"""Create or update <project>_nested-media, where instructors upload guest media for nested images (PRD V15)."""
from urllib.parse import urlsplit

from google.api_core.exceptions import NotFound
from google.cloud import storage as gcs
from googleapiclient import discovery

from common.constants.nested import NESTED_MEDIA_BUCKET_SUFFIX, NESTED_MEDIA_SIGNED_HEADERS, NESTED_UPLOAD_URL_TTL_SECONDS
from common.utilities.gcp.cloud_env import CloudEnv
from cloud_deployment.operations.app_install_updates.agoge_app import Commands

TOKEN_CREATOR_ROLE = 'roles/iam.serviceAccountTokenCreator'
OBJECT_ADMIN_ROLE = 'roles/storage.objectAdmin'
# An abandoned upload never reaches the API's completion check; the bucket removes it.
INCOMPLETE_UPLOAD_AGE_DAYS = 2
# Browsers start the resumable upload with a signed POST, then PUT the bytes to the session URI. The preflight
# checks every signed header (NestedMedia.create_upload) against this list, so a missing one blocks the upload.
CORS_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'OPTIONS']
CORS_RESPONSE_HEADERS = ['Content-Type', 'Content-Length', 'Content-Range', 'Location', 'Range', 'x-goog-hash',
                         *NESTED_MEDIA_SIGNED_HEADERS]
DEVELOPMENT_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']


class NestedMediaBucket:
    def __init__(self, project: str, storage_client: gcs.Client = None, iam_client=None):
        self.project = project
        self._storage = storage_client
        self._iam = iam_client

    def run(self) -> bool:
        print(f'Configuring the nested image media bucket for {self.project}.')
        try:
            env = CloudEnv(project=self.project)
            if env.project != self.project:
                raise ValueError('The selected project differs from its environment document.')
            service_account = Commands.ServiceAccounts.AGOGE.format(project=self.project)
            bucket = self._ensure_bucket(env)
            origins = self.origins(env.main_app_url)
            bucket.cors = [{
                'origin': origins, 'method': CORS_METHODS,
                'responseHeader': CORS_RESPONSE_HEADERS, 'maxAgeSeconds': NESTED_UPLOAD_URL_TTL_SECONDS,
            }]
            bucket.lifecycle_rules = [self.incomplete_upload_rule()]
            bucket.patch()
            print(f'  gs://{bucket.name}: CORS for {", ".join(origins)}; '
                  f'media/ objects older than {INCOMPLETE_UPLOAD_AGE_DAYS} days that never completed are deleted.')
            self._grant_bucket_access(bucket, service_account)
            self._grant_self_token_creator(service_account)
        except Exception as error:
            print(f'The nested media bucket was not configured: {error}')
            print('Check the error, refresh setup credentials if needed, then rerun '
                  'Server Images & Build Specs → Configure Nested Image Media Bucket.')
            return False
        print('Instructors can now upload guest media from the nested image wizard.')
        return True

    @staticmethod
    def origins(main_app_url: str) -> list:
        # A shared deployment serves the app at https://app.<parent>/<project_path>; CORS matches the origin only.
        parts = urlsplit(main_app_url)
        return [f'{parts.scheme}://{parts.netloc}', *DEVELOPMENT_ORIGINS]

    @staticmethod
    def incomplete_upload_rule() -> dict:
        # Lifecycle cannot read Firestore's `complete`, so the signed upload stamps Custom-Time with its start and the
        # completion route (PUT …/media/{id}/) moves it to MEDIA_KEEP_CUSTOM_TIME. Only never-completed objects age.
        return {
            'action': {'type': 'Delete'},
            'condition': {'daysSinceCustomTime': INCOMPLETE_UPLOAD_AGE_DAYS, 'matchesPrefix': ['media/']},
        }

    @property
    def storage(self) -> gcs.Client:
        if self._storage is None:
            self._storage = gcs.Client(project=self.project)
        return self._storage

    @property
    def iam(self):
        if self._iam is None:
            self._iam = discovery.build('iam', 'v1', cache_discovery=False)
        return self._iam

    def _ensure_bucket(self, env: CloudEnv) -> gcs.Bucket:
        name = f'{self.project}_{NESTED_MEDIA_BUCKET_SUFFIX}'
        try:
            bucket = self.storage.get_bucket(name)
            print(f'  gs://{name} exists; updating its settings.')
        except NotFound:
            bucket = self.storage.bucket(name)
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            bucket.iam_configuration.public_access_prevention = 'enforced'
            bucket = self.storage.create_bucket(bucket, location=env.region)
            print(f'  Created gs://{name} in {env.region}.')
        return bucket

    def _grant_bucket_access(self, bucket: gcs.Bucket, service_account: str) -> None:
        # The API reads object sizes (completion) and deletes media; it must not depend on a project-wide role.
        policy = bucket.get_iam_policy(requested_policy_version=3)
        member = f'serviceAccount:{service_account}'
        for binding in policy.bindings:
            if binding['role'] == OBJECT_ADMIN_ROLE and member in binding['members']:
                return
        policy.bindings.append({'role': OBJECT_ADMIN_ROLE, 'members': {member}})
        bucket.set_iam_policy(policy)
        print(f'  Granted {OBJECT_ADMIN_ROLE} on gs://{bucket.name} to {service_account}.')

    def _grant_self_token_creator(self, service_account: str) -> None:
        # Cloud Run credentials have no private key, so the API signs upload URLs through IAM signBlob on itself.
        resource = f'projects/{self.project}/serviceAccounts/{service_account}'
        accounts = self.iam.projects().serviceAccounts()
        policy = accounts.getIamPolicy(resource=resource).execute()
        member = f'serviceAccount:{service_account}'
        bindings = policy.setdefault('bindings', [])
        binding = next((b for b in bindings if b.get('role') == TOKEN_CREATOR_ROLE), None)
        if binding and member in binding.get('members', []):
            print(f'  {service_account} already has {TOKEN_CREATOR_ROLE} on itself.')
            return
        if binding:
            binding.setdefault('members', []).append(member)
        else:
            bindings.append({'role': TOKEN_CREATOR_ROLE, 'members': [member]})
        accounts.setIamPolicy(resource=resource, body={'policy': policy}).execute()
        print(f'  Granted {TOKEN_CREATOR_ROLE} to {service_account} on itself, so the API can sign upload URLs.')
