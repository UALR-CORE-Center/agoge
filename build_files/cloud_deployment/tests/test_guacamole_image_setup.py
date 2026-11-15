from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from google.api_core.exceptions import NotFound, PermissionDenied, ServiceUnavailable
from google.cloud import compute_v1

from cloud_deployment.operations.guacamole_image_management import guacamole_image_manager as guac_module
from cloud_deployment.operations.guacamole_image_management.guacamole_image_manager import GuacamoleImageManager
from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from common.constants.database import DbCollections
from common.exceptions import OperationTimeout


BOOT = ('Starting startup scripts (version 1).\n'
        '[ 42.7] google_metadata_script_runner[1]: startup-script: 🔹 Obtaining wildcard SSL certificate\n')
PROJECT_IMAGE = 'image-guac-tenant-project'
PROJECT_IMAGE_LINK = f'https://www.googleapis.com/compute/v1/projects/tenant-project/global/images/{PROJECT_IMAGE}'
CERTIFICATE_DIGEST = 'AB:' * 31 + 'AB'
CERTIFICATE_READY = BOOT + f'startup-script: {GuacamoleImageManager.STARTUP_CERTIFICATE_MARKER}{CERTIFICATE_DIGEST}\n'


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
    base_image = compute_v1.Image(
        status='READY',
        self_link='https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-guac-base',
    )
    client.get.return_value = base_image
    client.get.side_effect = [NotFound('no project image'), base_image]
    monkeypatch.setattr(guac_module.compute_v1, 'ImagesClient', lambda: client)
    manager.instances = MagicMock()
    manager.instances.get.side_effect = NotFound('no builder VM')
    manager.instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(contents=CERTIFICATE_READY)
    monkeypatch.setattr(guac_module.compute_v1, 'InstancesClient', lambda: manager.instances)
    monkeypatch.setattr(guac_module.time, 'sleep', lambda _: None)
    return manager, client


def test_shared_image_source_and_tenant_vm_identity_are_kept_separate(setup):
    manager, client = setup
    assert manager.create_guac_project_image() is True
    assert client.get.call_args_list == [
        call(project='tenant-project', image=PROJECT_IMAGE),
        call(project='shared-images', image='image-guac-base'),
    ]
    inserted = manager.db.insert.call_args.kwargs
    assert inserted['collection_name'] == DbCollections.IMAGE
    assert inserted['data']['self_link'] == client.get.return_value.self_link
    assert inserted['data']['name'] == 'guac-tenant-project'
    # Boots from the shared base, but captures into this project's own image.
    assert inserted['data']['image'] == 'image-guac-tenant-project'
    assert inserted['data']['image_exists'] is False
    manager.image_manager.load.assert_called_once_with(server_name='guac-tenant-project')
    manager.image_manager.check_out.assert_called_once_with()
    manager.image_manager.check_in.assert_called_once_with()


def test_refresh_boots_from_existing_project_image_and_waits_for_its_certificate(setup):
    manager, client = setup
    client.get.side_effect = None
    client.get.return_value = compute_v1.Image(status='READY', self_link=PROJECT_IMAGE_LINK)
    manager.instances.get_serial_port_output.side_effect = [
        compute_v1.SerialPortOutput(contents=CERTIFICATE_READY + BOOT),
        compute_v1.SerialPortOutput(contents=CERTIFICATE_READY),
        compute_v1.SerialPortOutput(contents=CERTIFICATE_READY),
    ]
    manager._verify_certificate_operation.side_effect = [False, True]
    assert manager.create_guac_project_image() is True
    client.get.assert_called_once_with(project='tenant-project', image=PROJECT_IMAGE)
    inserted = manager.db.insert.call_args.kwargs['data']
    assert inserted['self_link'] == PROJECT_IMAGE_LINK
    assert inserted['image'] == PROJECT_IMAGE
    assert inserted['image_exists'] is True
    assert manager.instances.get_serial_port_output.call_count == 3
    assert manager._verify_certificate_operation.call_args_list == [call('ab' * 32), call('ab' * 32)]
    manager.image_manager.check_in.assert_called_once_with()


@pytest.mark.parametrize('error', [PermissionDenied('denied'), None])
def test_refresh_does_not_fall_back_if_project_image_is_inaccessible_or_unready(setup, error):
    manager, client = setup
    client.get.side_effect = error
    client.get.return_value = compute_v1.Image(status='PENDING', self_link=PROJECT_IMAGE_LINK)
    message = 'Cannot access' if error else 'not ready'
    with pytest.raises(RuntimeError, match=message):
        manager.create_guac_project_image()
    client.get.assert_called_once_with(project='tenant-project', image=PROJECT_IMAGE)
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()


@pytest.mark.parametrize('parent, expected', [('parent-project', 'parent-project'), (None, 'tenant-project')])
def test_image_project_fallbacks(setup, parent, expected):
    manager, client = setup
    manager.env.default_server_image_project = None
    manager.env.parent_project = parent
    client.get.side_effect = None
    manager._resolve_base_image(client)
    client.get.assert_called_once_with(project=expected, image='image-guac-base')


@pytest.mark.parametrize('error, message', [
    (NotFound('missing'), 'was not found'),
    (PermissionDenied('denied'), 'Cannot access'),
])
def test_missing_or_inaccessible_source_stops_before_secret_reads_and_writes(setup, error, message):
    manager, client = setup
    client.get.side_effect = [NotFound('no project image'), error]
    with pytest.raises(RuntimeError, match=message) as raised:
        manager.create_guac_project_image()
    assert 'projects/shared-images/global/images/image-guac-base' in str(raised.value)
    assert raised.value.__cause__ is error
    assert client.get.call_args_list == [
        call(project='tenant-project', image=PROJECT_IMAGE),
        call(project='shared-images', image='image-guac-base'),
    ]
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

    def getpeercert(self, binary_form=False):
        return b'certificate bytes' if binary_form else self.cert


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
    assert manager._verify_certificate_operation(sha256(b'certificate bytes').hexdigest()) is expected
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
    assert manager._verify_certificate_operation('ab' * 32) is False


def test_refresh_verifies_the_certificate_reported_by_the_builder(monkeypatch):
    manager = object.__new__(GuacamoleImageManager)
    manager.env = SimpleNamespace(parent_dns_suffix='.agoge-labs.com', dns_suffix=None)
    manager.image_manager = SimpleNamespace(dns_record='guac.agoge-labs.com')
    monkeypatch.setattr(guac_module.socket, 'create_connection', lambda *args, **kwargs: _TlsSocket(None))
    context = MagicMock()
    context.wrap_socket.return_value = _TlsSocket({'subjectAltName': (('DNS', '*.agoge-labs.com'),)})
    monkeypatch.setattr(guac_module.ssl, 'create_default_context', lambda: context)
    assert manager._verify_certificate_operation('ab' * 32) is False
    assert manager._verify_certificate_operation(sha256(b'certificate bytes').hexdigest()) is True


@pytest.mark.parametrize('status', ['RUNNING', 'TERMINATED'])
def test_existing_builder_requires_canceling_before_the_template_is_changed(setup, status):
    manager, _ = setup
    manager.instances.get.side_effect = None
    manager.instances.get.return_value = compute_v1.Instance(status=status)
    with pytest.raises(RuntimeError, match='Cancel Template Server Changes'):
        manager.create_guac_project_image()
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()
    manager.image_manager.check_out.assert_not_called()


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
        project='tenant-project', zone='us-central1-a', instance='guac-tenant-project', timeout=10, retry=None)
    manager.image_manager.check_in.assert_not_called()
    out = capsys.readouterr().out
    assert 'retry after 2026-10-27 21:07:09 UTC' in out
    assert out.count('An unexpected error occurred') == 1


def test_failure_from_an_earlier_boot_is_ignored(setup):
    manager, _ = setup
    manager.instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(
        contents=BOOT + RATE_LIMITED + BOOT)
    assert manager._startup_script_failure(manager._startup_script_output()) is None


def test_transient_serial_error_falls_back_to_the_deadline(setup):
    manager, _ = setup
    manager.instances.get_serial_port_output.side_effect = ServiceUnavailable('unavailable')
    assert manager._startup_script_output() == ''


def test_missing_serial_permission_stops_before_capture(setup):
    manager, _ = setup
    manager.instances.get_serial_port_output.side_effect = PermissionDenied('denied')
    with pytest.raises(RuntimeError, match='compute.instances.getSerialPortOutput'):
        manager.create_guac_project_image()
    manager.image_manager.check_in.assert_not_called()


@pytest.fixture
def image_template():
    manager = object.__new__(ImageTemplateManager)
    manager.class_name = 'ImageTemplateManager'
    manager.server_name = 'guac-tenant-project'
    manager.image_name = PROJECT_IMAGE
    manager.env = SimpleNamespace(project='tenant-project')
    manager.server_spec = SimpleNamespace(description='Guacamole template')
    manager.logger = MagicMock()
    manager.stop_server = MagicMock()
    manager.snapshot_manager = MagicMock()
    manager.snapshot_manager.create_snapshot.return_value = 'guac-snapshot'
    manager.compute_snapshot = MagicMock()
    manager.compute_snapshot.get.return_value = compute_v1.Snapshot(
        status='READY', self_link='projects/tenant-project/global/snapshots/guac-snapshot',
    )
    manager.compute_image = MagicMock()
    manager.compute_image.get.return_value = compute_v1.Image(status='READY', self_link=PROJECT_IMAGE_LINK)
    return manager


def test_check_in_retains_the_project_image_if_the_snapshot_is_unready(image_template):
    image_template.compute_snapshot.get.return_value.status = 'CREATING'

    with pytest.raises(OperationTimeout, match='existing image was retained'):
        image_template.check_in()

    image_template.compute_image.delete.assert_not_called()
    image_template.compute_image.create.assert_not_called()


def test_check_in_leaves_builder_checked_out_if_replacement_image_fails(image_template):
    image_template.compute_image.create.return_value = False
    image_template.delete_server = MagicMock()
    image_template._update_record_status = MagicMock()

    with pytest.raises(OperationTimeout, match='server remains checked out'):
        image_template.check_in()

    image_template.delete_server.assert_not_called()
    image_template._update_record_status.assert_not_called()


def test_completed_check_in_verifies_the_replacement_in_the_project(image_template):
    image_template.debug = True
    image_template.delete_server = MagicMock()
    image_template._update_record_status = MagicMock()

    image_template.check_in()

    image_template.compute_image.get.assert_called_once_with(
        PROJECT_IMAGE, project='tenant-project', fallback_to_shared=False,
    )
    image_template.delete_server.assert_called_once_with()
    assert image_template._update_record_status.call_args.kwargs['image_created'] is True
