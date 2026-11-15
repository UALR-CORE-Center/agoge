"""Provision an isolated JSON authentication identity for one community proxy."""
import re

from googleapiclient import discovery
from googleapiclient.errors import HttpError

from common.exceptions import BadRequest
from common.services.community_guacamole import CommunityGuacamoleService
from common.services.community_guacamole_startup import render_community_guacamole_startup
from common.services.guacamole_tls_startup import (
    GUACAMOLE_TLS_SCOPE, guacamole_tls_boot_image, guacamole_tls_metadata, guacamole_tls_reader_email,
)


SECRET_METADATA_KEY = 'agoge-community-guacamole-secret'
_TOKEN_CREATOR = 'roles/iam.serviceAccountTokenCreator'


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

    def grant_tls_reader_impersonation(self, unit_id):
        self._update_tls_reader_binding(unit_id, grant=True)

    def revoke_tls_reader_impersonation(self, unit_id):
        self._update_tls_reader_binding(unit_id, grant=False)

    def _update_tls_reader_binding(self, unit_id, *, grant):
        # Manage only this member on the tenant's dedicated cert reader. The
        # community proxy still accesses its JSON auth secret as itself.
        resource = f'projects/{self.project}/serviceAccounts/{guacamole_tls_reader_email(self.project)}'
        accounts = self.iam.projects().serviceAccounts()
        member = f'serviceAccount:{self.email(unit_id)}'
        for attempt in range(3):
            try:
                policy = accounts.getIamPolicy(resource=resource, options_requestedPolicyVersion=3).execute()
            except HttpError as error:
                if not grant and error.resp.status == 404:
                    return
                raise
            bindings = policy.setdefault('bindings', [])
            binding = next((item for item in bindings if item.get('role') == _TOKEN_CREATOR
                            and not item.get('condition')), None)
            if grant:
                if binding is None:
                    binding = {'role': _TOKEN_CREATOR, 'members': []}
                    bindings.append(binding)
                if member in binding['members']:
                    return
                binding['members'].append(member)
            else:
                if binding is None or member not in binding['members']:
                    return
                binding['members'].remove(member)
                if not binding['members']:
                    bindings.remove(binding)
            try:
                accounts.setIamPolicy(resource=resource, body={'policy': policy}).execute()
                return
            except HttpError as error:
                if error.resp.status not in (409, 412) or attempt == 2:
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
    tls_secret = env_dict.get('guacamole_tls_secret')
    tls_image = guacamole_tls_boot_image(env_dict)
    tls_reader = guacamole_tls_reader_email(identity.project) if tls_secret else None
    startup = render_community_guacamole_startup(
        secret_version_name, unit_id, domain, tls_secret=tls_secret, tls_reader=tls_reader,
    )
    items = {SECRET_METADATA_KEY: secret_version_name, 'startup-script': startup}
    if tls_secret:
        identity.grant_tls_reader_impersonation(unit_id)
        hostname = f'{unit_id}-display.{domain.strip(".").lower()}'
        items.update(guacamole_tls_metadata(tls_secret, hostname, impersonate=tls_reader))
    accounts = [{'email': email, 'scopes': [GUACAMOLE_TLS_SCOPE]}]
    metadata = {'items': [{'key': key, 'value': value} for key, value in items.items()]}
    return {
        **({'image': tls_image} if tls_image else {}),
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
    identity = CommunityProxyIdentity(env_dict['project'], iam=iam)
    if env_dict.get('guacamole_tls_secret'):
        identity.revoke_tls_reader_impersonation(unit_id)
    identity.delete(unit_id)
