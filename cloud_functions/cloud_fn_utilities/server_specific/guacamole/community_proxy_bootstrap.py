"""Provision an isolated JSON authentication identity for one community proxy."""
import re

from googleapiclient import discovery
from googleapiclient.errors import HttpError

from common.exceptions import BadRequest
from common.services.community_guacamole import CommunityGuacamoleService
from common.services.community_guacamole_startup import render_community_guacamole_startup


SECRET_METADATA_KEY = 'agoge-community-guacamole-secret'


def _validate_unit(unit_id):
    if not isinstance(unit_id, str) or not re.fullmatch(r'[a-z]{10}', unit_id):
        raise BadRequest('Invalid community lab ID')
    return unit_id


class CommunityProxyIdentity:
    """A proxy can read its JSON key, but never the WireGuard lease key."""

    def __init__(self, project, iam=None):
        self.project = project
        self.iam = iam if iam is not None else discovery.build('iam', 'v1', cache_discovery=False)

    def email(self, unit_id):
        return f'agoge-guac-{_validate_unit(unit_id)}@{self.project}.iam.gserviceaccount.com'

    def resource(self, unit_id):
        return f'projects/{self.project}/serviceAccounts/{self.email(unit_id)}'

    def ensure(self, unit_id):
        resource = self.resource(unit_id)
        accounts = self.iam.projects().serviceAccounts()
        try:
            account = accounts.get(name=resource).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise
            try:
                account = accounts.create(name=f'projects/{self.project}', body={
                    'accountId': f'agoge-guac-{unit_id}',
                    'serviceAccount': {'displayName': f'Agoge community display {unit_id}'},
                }).execute()
            except HttpError as create_error:
                if create_error.resp.status != 409:
                    raise
                account = accounts.get(name=resource).execute()
        if account.get('disabled'):
            raise BadRequest('The community proxy service account is disabled')
        member = f'serviceAccount:agoge-service@{self.project}.iam.gserviceaccount.com'
        policy = accounts.getIamPolicy(resource=resource, options_requestedPolicyVersion=3).execute()
        bindings = policy.setdefault('bindings', [])
        binding = next((item for item in bindings
                        if item.get('role') == 'roles/iam.serviceAccountUser'
                        and not item.get('condition')), None)
        if binding is None:
            binding = {'role': 'roles/iam.serviceAccountUser', 'members': []}
            bindings.append(binding)
        if member not in binding.setdefault('members', []):
            binding['members'].append(member)
            accounts.setIamPolicy(resource=resource, body={'policy': policy}).execute()
        return self.email(unit_id)

    def delete(self, unit_id):
        try:
            self.iam.projects().serviceAccounts().delete(name=self.resource(unit_id)).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise


def prepare_community_proxy(unit_id, env_dict, *, secret_version_name=None, secret_client=None, iam=None):
    """Return the bootstrap fields merged into the Unit-owned proxy record.

    Reusing the immutable reference makes retries safe. Neither Firestore nor
    Compute metadata receives key material. No server image update is required.
    """
    _validate_unit(unit_id)
    service = CommunityGuacamoleService(env_dict, secret_client=secret_client)
    if secret_version_name:
        # Validate ownership and confirm it remains accessible before attachment.
        service.get_key(unit_id, secret_version_name)
    else:
        secret_version_name = service.ensure_key(unit_id)
    identity = CommunityProxyIdentity(env_dict['project'], iam=iam)
    email = identity.ensure(unit_id)
    service.grant_proxy_access(unit_id, secret_version_name, email)
    domain = env_dict.get('parent_dns_suffix') or env_dict['dns_suffix']
    accounts = [{'email': email, 'scopes': ['https://www.googleapis.com/auth/cloud-platform']}]
    metadata = {'items': [
        {'key': SECRET_METADATA_KEY, 'value': secret_version_name},
        {'key': 'startup-script', 'value': render_community_guacamole_startup(
            secret_version_name, unit_id, domain)},
    ]}
    return {
        'community_proxy': True,
        'guacamole_secret_version_name': secret_version_name,
        'service_accounts': accounts, 'serviceAccounts': accounts,
        'metadata': metadata, 'guacamole_startup_script': None,
        'no_service_account': False,
    }


def delete_community_proxy(unit_id, env_dict, *, secret_client=None, iam=None):
    """Delete only this lab's signing secret and identity after its VM is gone."""
    _validate_unit(unit_id)
    CommunityGuacamoleService(env_dict, secret_client=secret_client).delete(unit_id)
    CommunityProxyIdentity(env_dict['project'], iam=iam).delete(unit_id)
