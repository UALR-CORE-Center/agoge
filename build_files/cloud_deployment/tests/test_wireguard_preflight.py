from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_deployment.operations.app_install_updates import base_build as base_build_module
from cloud_deployment.operations.app_install_updates.base_build import BaseBuild
from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables
from cloud_deployment.utilities.globals import ShellCommands


def test_api_enable_targets_requested_project_and_fails_closed():
    build = object.__new__(BaseBuild)
    build.project = 'tenant-project'
    succeeded = SimpleNamespace(returncode=0, stderr='')

    with patch.object(base_build_module.subprocess, 'run', return_value=succeeded) as run:
        build._enable_apis((ShellCommands.EnableAPIs.COMPUTE,))

    run.assert_called_once_with(
        'gcloud services enable compute.googleapis.com --project=tenant-project',
        capture_output=True,
        shell=True,
        text=True,
    )

    failed = SimpleNamespace(returncode=1, stderr='permission denied')
    with patch.object(base_build_module.subprocess, 'run', return_value=failed):
        with pytest.raises(RuntimeError, match='permission denied'):
            build._enable_apis((ShellCommands.EnableAPIs.DNS,))


def test_existing_install_backfills_wireguard_defaults_without_prompts():
    environment = object.__new__(EnvironmentVariables)
    environment.env = {'parent_dns_suffix': '.vpn.example.edu.'}
    environment.db = MagicMock()

    updates = environment.ensure_wireguard_defaults()

    assert updates == {
        'wireguard_dns_prefix': 'wg',
        'wireguard_port': 51820,
        'wireguard_dns_suffix': '.vpn.example.edu',
    }
    environment.db.update.assert_called_once()


def test_wireguard_preflight_grants_zone_scoped_dns_access():
    build = object.__new__(BaseBuild)
    build.project = 'tenant-project'
    build._enable_apis = MagicMock()
    environment = MagicMock()
    env = SimpleNamespace(
        project='tenant-project',
        parent_project='dns-project',
        parent_zone='public-zone',
        wireguard_dns_suffix='.gateways.example.edu.',
    )
    managed_zones = MagicMock()
    managed_zones.get.return_value.execute.return_value = {
        'dnsName': 'example.edu.',
    }
    managed_zones.getIamPolicy.return_value.execute.return_value = {
        'etag': 'etag-value',
        'version': 3,
        'bindings': [{
            'role': 'roles/dns.admin',
            'members': ['serviceAccount:somebody@example.iam.gserviceaccount.com'],
            'condition': {'title': 'restricted', 'expression': 'request.time < timestamp("2030-01-01T00:00:00Z")'},
        }],
    }
    dns_service = MagicMock()
    dns_service.managedZones.return_value = managed_zones

    with (
        patch.object(base_build_module, 'EnvironmentVariables', return_value=environment),
        patch.object(base_build_module, 'CloudEnv', return_value=env),
        patch.object(base_build_module.discovery, 'build', return_value=dns_service),
    ):
        build.ensure_wireguard_prerequisites()

    build._enable_apis.assert_called_once_with((
        ShellCommands.EnableAPIs.COMPUTE,
        ShellCommands.EnableAPIs.DNS,
    ))
    environment.ensure_wireguard_defaults.assert_called_once_with()
    managed_zones.get.assert_called_once_with(
        project='dns-project',
        managedZone='public-zone',
    )
    resource = 'projects/dns-project/managedZones/public-zone'
    managed_zones.getIamPolicy.assert_called_once_with(
        resource=resource,
        body={'options': {'requestedPolicyVersion': 3}},
    )
    expected_policy = {
        'etag': 'etag-value',
        'version': 3,
        'bindings': [
            {
                'role': 'roles/dns.admin',
                'members': ['serviceAccount:somebody@example.iam.gserviceaccount.com'],
                'condition': {
                    'title': 'restricted',
                    'expression': 'request.time < timestamp("2030-01-01T00:00:00Z")',
                },
            },
            {
                'role': 'roles/dns.admin',
                'members': [
                    'serviceAccount:agoge-service@tenant-project.iam.gserviceaccount.com'
                ],
            },
        ],
    }
    managed_zones.setIamPolicy.assert_called_once_with(
        resource=resource,
        body={'policy': expected_policy},
    )
    managed_zones.setIamPolicy.return_value.execute.assert_called_once_with()


def test_wireguard_preflight_rejects_suffix_outside_managed_zone():
    build = object.__new__(BaseBuild)
    build.project = 'tenant-project'
    build._enable_apis = MagicMock()
    environment = MagicMock()
    env = SimpleNamespace(
        project='tenant-project',
        parent_project='dns-project',
        parent_zone='public-zone',
        wireguard_dns_suffix='.other.example.net.',
    )
    managed_zones = MagicMock()
    managed_zones.get.return_value.execute.return_value = {'dnsName': 'example.edu.'}
    dns_service = MagicMock()
    dns_service.managedZones.return_value = managed_zones

    with (
        patch.object(base_build_module, 'EnvironmentVariables', return_value=environment),
        patch.object(base_build_module, 'CloudEnv', return_value=env),
        patch.object(base_build_module.discovery, 'build', return_value=dns_service),
    ):
        with pytest.raises(ValueError, match='not in managed zone'):
            build.ensure_wireguard_prerequisites()

    managed_zones.getIamPolicy.assert_not_called()


def test_wireguard_preflight_rejects_private_managed_zone():
    build = object.__new__(BaseBuild)
    build.project = 'tenant-project'
    build._enable_apis = MagicMock()
    env = SimpleNamespace(
        project='tenant-project',
        parent_project='dns-project',
        parent_zone='private-zone',
        wireguard_dns_suffix='.vpn.example.edu.',
    )
    managed_zones = MagicMock()
    managed_zones.get.return_value.execute.return_value = {
        'dnsName': 'example.edu.',
        'visibility': 'private',
    }
    dns_service = MagicMock()
    dns_service.managedZones.return_value = managed_zones

    with (
        patch.object(base_build_module, 'EnvironmentVariables'),
        patch.object(base_build_module, 'CloudEnv', return_value=env),
        patch.object(base_build_module.discovery, 'build', return_value=dns_service),
    ):
        with pytest.raises(ValueError, match='must be public'):
            build.ensure_wireguard_prerequisites()

    managed_zones.getIamPolicy.assert_not_called()
