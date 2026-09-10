"""Validate parent secrets and grant the tenant runtime access before deployment."""

from google.cloud import secretmanager

from common.utilities.gcp.shared_secrets import SHARED_API_SECRET_NAMES


def enabled_api_secret_version(client, project: str, secret_name: str) -> str:
    if not project or secret_name not in SHARED_API_SECRET_NAMES:
        raise ValueError('A project and a supported API secret are required')
    name = f'projects/{project}/secrets/{secret_name}/versions/latest'
    # Only read metadata. Setup/deployment need not read the secret payload.
    version = client.get_secret_version(request={'name': name})
    if version.state != secretmanager.SecretVersion.State.ENABLED:
        raise ValueError(f'API secret {name} must have an enabled latest version')
    return name


def ensure_shared_api_secret_access(env) -> None:
    if not env.shared_api_secrets:
        return
    client = secretmanager.SecretManagerServiceClient()
    member = f'serviceAccount:agoge-service@{env.project}.iam.gserviceaccount.com'
    role = 'roles/secretmanager.secretAccessor'
    for secret_name in env.shared_api_secrets:
        enabled_api_secret_version(client, env.parent_project, secret_name)
        resource = f'projects/{env.parent_project}/secrets/{secret_name}'
        policy = client.get_iam_policy(request={
            'resource': resource,
            'options': {'requested_policy_version': 3},
        })
        binding = next((
            binding for binding in policy.bindings
            if binding.role == role and not binding.HasField('condition')
        ), None)
        if binding is not None and member in binding.members:
            continue
        if binding is None:
            binding = policy.bindings.add(role=role)
        binding.members.append(member)
        # Preserve the etag, version, unrelated grants, and conditional grants.
        # An IAM conflict or permission failure stops deployment instead of
        # deploying a runtime that cannot read its configured credentials.
        client.set_iam_policy(request={'resource': resource, 'policy': policy})
        print(f'Granted {member} read access to {resource}')
