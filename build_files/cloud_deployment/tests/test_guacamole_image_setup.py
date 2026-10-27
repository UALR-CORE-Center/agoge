from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import compute_v1

from cloud_deployment.operations.guacamole_image_management import guacamole_image_manager as guac_module
from cloud_deployment.operations.guacamole_image_management.guacamole_image_manager import GuacamoleImageManager
from common.constants.database import DbCollections


@pytest.fixture
def setup(monkeypatch):
    manager = object.__new__(GuacamoleImageManager)
    manager.project = 'tenant-project'
    manager.env = SimpleNamespace(
        project=manager.project, zone='us-central1-a', default_server_image_project='shared-images',
        parent_project='parent-project',
    )
    manager.db = MagicMock()
    manager.image_manager = MagicMock()
    manager._get_guac_startup_script = MagicMock(return_value='#!/bin/bash\necho setup')
    manager._verify_certificate_operation = MagicMock(return_value=True)
    client = MagicMock()
    client.get.return_value = compute_v1.Image(
        status='READY',
        self_link='https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-guac-base',
    )
    monkeypatch.setattr(guac_module.compute_v1, 'ImagesClient', lambda: client)
    manager.instances = MagicMock()
    manager.instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(contents='')
    monkeypatch.setattr(guac_module.compute_v1, 'InstancesClient', lambda: manager.instances)
    monkeypatch.setattr(guac_module.time, 'sleep', lambda _: None)
    return manager, client


def test_shared_image_source_and_tenant_vm_identity_are_kept_separate(setup):
    manager, client = setup
    assert manager.create_guac_project_image() is True
    client.get.assert_called_once_with(project='shared-images', image='image-guac-base')
    inserted = manager.db.insert.call_args.kwargs
    assert inserted['collection_name'] == DbCollections.IMAGE
    assert inserted['data']['self_link'] == client.get.return_value.self_link
    assert inserted['data']['name'] == 'guac-tenant-project'
    # Boots from the shared base, but captures into this project's own image.
    assert inserted['data']['image'] == 'image-guac-tenant-project'
    manager.image_manager.load.assert_called_once_with(server_name='guac-tenant-project')
    manager.image_manager.check_out.assert_called_once_with()
    manager.image_manager.check_in.assert_called_once_with()


@pytest.mark.parametrize('parent, expected', [('parent-project', 'parent-project'), (None, 'tenant-project')])
def test_image_project_fallbacks(setup, parent, expected):
    manager, client = setup
    manager.env.default_server_image_project = None
    manager.env.parent_project = parent
    manager._resolve_base_image()
    client.get.assert_called_once_with(project=expected, image='image-guac-base')


@pytest.mark.parametrize('error, message', [
    (NotFound('missing'), 'was not found'),
    (PermissionDenied('denied'), 'Cannot access'),
])
def test_missing_or_inaccessible_source_stops_before_secret_reads_and_writes(setup, error, message):
    manager, client = setup
    client.get.side_effect = error
    with pytest.raises(RuntimeError, match=message) as raised:
        manager.create_guac_project_image()
    assert 'projects/shared-images/global/images/image-guac-base' in str(raised.value)
    assert raised.value.__cause__ is error
    # Do not silently try an unrelated image in the tenant or another project.
    assert client.get.call_count == 1
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()
    manager.image_manager.load.assert_not_called()
    manager.image_manager.check_out.assert_not_called()


@pytest.mark.parametrize('status', ['PENDING', 'FAILED'])
def test_unready_source_does_not_replace_the_existing_image_record(setup, status):
    manager, client = setup
    client.get.return_value.status = status
    with pytest.raises(RuntimeError, match='not ready'):
        manager.create_guac_project_image()
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()
    manager.image_manager.check_out.assert_not_called()


def test_image_is_not_captured_without_a_verified_wildcard_certificate(setup, monkeypatch):
    manager, _ = setup
    manager.CERTIFICATE_WAIT_SECONDS = 30
    manager._verify_certificate_operation = MagicMock(return_value=False)
    clock = iter(range(0, 1000, 15))
    monkeypatch.setattr(guac_module.time, 'monotonic', lambda: next(clock))
    assert manager.create_guac_project_image() is False
    assert manager._verify_certificate_operation.call_count >= 2
    manager.image_manager.check_out.assert_called_once_with()
    manager.image_manager.check_in.assert_not_called()


def test_image_is_captured_once_the_certificate_verifies(setup):
    manager, _ = setup
    manager._verify_certificate_operation = MagicMock(side_effect=[False, False, True])
    assert manager.create_guac_project_image() is True
    assert manager._verify_certificate_operation.call_count == 3
    manager.image_manager.check_in.assert_called_once_with()


class _TlsSocket:
    def __init__(self, cert):
        self.cert = cert

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getpeercert(self):
        return self.cert


@pytest.mark.parametrize('names, expected', [
    ((('DNS', '*.agoge-labs.com'), ('DNS', 'agoge-labs.com')), True),
    # A host-only certificate would not cover each lab's <id>-display host.
    ((('DNS', 'guac.agoge-labs.com'),), False),
])
def test_certificate_must_cover_lab_proxy_hosts(monkeypatch, names, expected):
    manager = object.__new__(GuacamoleImageManager)
    manager.env = SimpleNamespace(parent_dns_suffix='.agoge-labs.com', dns_suffix='.other.test')
    manager.image_manager = SimpleNamespace(dns_record='guac-tenant.agoge-labs.com.')
    connections = []
    monkeypatch.setattr(guac_module.socket, 'create_connection',
                        lambda address, **k: connections.append(address) or _TlsSocket(None))
    context = MagicMock()
    context.wrap_socket.return_value = _TlsSocket({'subjectAltName': names})
    monkeypatch.setattr(guac_module.ssl, 'create_default_context', lambda: context)
    assert manager._verify_certificate_operation() is expected
    # The fully qualified template DNS name is used without its trailing dot.
    assert connections == [('guac-tenant.agoge-labs.com', 443)]
    assert context.wrap_socket.call_args.kwargs['server_hostname'] == 'guac-tenant.agoge-labs.com'


def test_unreachable_or_untrusted_server_is_not_verified(monkeypatch):
    manager = object.__new__(GuacamoleImageManager)
    manager.env = SimpleNamespace(parent_dns_suffix='.agoge-labs.com', dns_suffix=None)
    manager.image_manager = SimpleNamespace(dns_record='guac.agoge-labs.com')

    def refuse(*args, **kwargs):
        raise ConnectionRefusedError()
    monkeypatch.setattr(guac_module.socket, 'create_connection', refuse)
    assert manager._verify_certificate_operation() is False


def test_project_template_is_local_so_check_in_never_replaces_the_shared_base(setup):
    from common.utilities.gcp.compute.image_ownership import is_shared_image
    manager, client = setup
    manager.create_guac_project_image()
    record = manager.db.insert.call_args.kwargs['data']
    # A shared-looking record is refused at check-out and, if authorized,
    # check-in would delete and recreate agoge-shared-resources/image-guac-base.
    assert is_shared_image(record, 'tenant-project') is False


BOOT = ('Starting startup scripts (version 1).\n'
        '[ 42.7] google_metadata_script_runner[1]: startup-script: 🔹 Obtaining wildcard SSL certificate\n')
RATE_LIMITED = (
    '[ 49.6] google_metadata_script_runner[1]: startup-script: An unexpected error occurred:\n'
    'Oct 27 google_metadata_script_runner[1]: startup-script: An unexpected error occurred:\n'
    '[ 49.6] google_metadata_script_runner[1]: startup-script: There were too many requests of a given type :: '
    'too many certificates (5) already issued, retry after 2026-10-27 21:07:09 UTC\n'
    '[ 49.8] google_metadata_script_runner[1]: Script "startup-script" failed with error: exit status 1\n'
)


def test_failed_startup_script_stops_the_wait_and_reports_certbot(setup, capsys):
    # Certbot fails within a minute (e.g. Let's Encrypt's duplicate-certificate
    # limit); waiting out the full deadline only hid the reason.
    manager, _ = setup
    manager._verify_certificate_operation = MagicMock(return_value=False)
    manager.image_manager.server_name = 'guac-tenant-project'
    manager.instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(contents=BOOT + RATE_LIMITED)
    assert manager.create_guac_project_image() is False
    manager.instances.get_serial_port_output.assert_called_once_with(
        project='tenant-project', zone='us-central1-a', instance='guac-tenant-project')
    manager.image_manager.check_in.assert_not_called()
    out = capsys.readouterr().out
    assert 'retry after 2026-10-27 21:07:09 UTC' in out
    assert out.count('An unexpected error occurred') == 1


def test_failure_from_an_earlier_boot_is_ignored(setup):
    manager, _ = setup
    manager.instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(
        contents=BOOT + RATE_LIMITED + BOOT)
    assert manager._startup_script_failure() is None


def test_unreadable_serial_output_falls_back_to_the_deadline(setup):
    manager, _ = setup
    manager.instances.get_serial_port_output.side_effect = PermissionDenied('denied')
    assert manager._startup_script_failure() is None


def test_baked_compose_restarts_every_service_after_a_clean_exit():
    # A VM stop can end a task with exit 0; 'on-failure' left it Complete (0/1) after boot.
    compose = Path(__file__).resolve().parents[2] / 'server_config/guacamole/configs/docker-compose.yml'
    services = yaml.safe_load(compose.read_text())['services']
    assert set(services) == {'db', 'guacd', 'guacamole', 'nginx'}
    for service in services.values():
        assert service['deploy']['restart_policy']['condition'] == 'any'
