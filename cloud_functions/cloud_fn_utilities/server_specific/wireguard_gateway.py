"""Identity and metadata bootstrap for managed Ubuntu WireGuard gateways."""

from googleapiclient import discovery
from googleapiclient.errors import HttpError

from common.exceptions import BadRequest
from common.services.wireguard_startup import render_wireguard_startup


UBUNTU_IMAGE = (
    'projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64'
)
BOOT_METADATA_KEY = 'agoge-wireguard-boot'
SECRET_METADATA_KEY = 'agoge-wireguard-secret'


class WireGuardGatewayIdentity:
    """Give one VM access to only the configuration secret for its own lease."""

    def __init__(self, project: str, iam=None):
        self.project = project
        self.iam = iam or discovery.build('iam', 'v1', cache_discovery=False)

    def email(self, unit_id: str) -> str:
        return f'agoge-wg-{unit_id}@{self.project}.iam.gserviceaccount.com'

    def resource(self, unit_id: str) -> str:
        return f'projects/{self.project}/serviceAccounts/{self.email(unit_id)}'

    def ensure(self, unit_id: str) -> str:
        accounts = self.iam.projects().serviceAccounts()
        resource = self.resource(unit_id)
        try:
            account = accounts.get(name=resource).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise
            try:
                account = accounts.create(
                    name=f'projects/{self.project}',
                    body={
                        'accountId': f'agoge-wg-{unit_id}',
                        'serviceAccount': {'displayName': f'Agoge WireGuard {unit_id}'},
                    },
                ).execute()
            except HttpError as create_error:
                if create_error.resp.status != 409:
                    raise
                account = accounts.get(name=resource).execute()
        if account.get('disabled'):
            raise BadRequest('The lab gateway service account is disabled')

        # The application can attach this one identity, rather than granting
        # actAs over every service account in the project.
        member = f'serviceAccount:agoge-service@{self.project}.iam.gserviceaccount.com'
        policy = accounts.getIamPolicy(resource=resource, options_requestedPolicyVersion=3).execute()
        bindings = policy.setdefault('bindings', [])
        binding = next((entry for entry in bindings if
                        entry.get('role') == 'roles/iam.serviceAccountUser'
                        and not entry.get('condition')), None)
        if binding is None:
            binding = {'role': 'roles/iam.serviceAccountUser', 'members': []}
            bindings.append(binding)
        if member not in binding.setdefault('members', []):
            binding['members'].append(member)
            accounts.setIamPolicy(resource=resource, body={'policy': policy}).execute()
        return self.email(unit_id)

    def delete(self, unit_id: str) -> None:
        try:
            self.iam.projects().serviceAccounts().delete(name=self.resource(unit_id)).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise


def managed_metadata(secret_version_name: str, boot_id: str) -> dict:
    """Embed code and non-secret references; private keys never enter metadata."""
    return {'items': [
        {'key': BOOT_METADATA_KEY, 'value': boot_id},
        {'key': SECRET_METADATA_KEY, 'value': secret_version_name},
        {'key': 'startup-script', 'value': render_wireguard_startup(secret_version_name, boot_id)},
    ]}
