"""A nested host's template check-out: the first build and the re-check-out of a finalized image (V11)."""
import copy
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.server_specific import nested_scripts
from cloud_fn_utilities.server_specific.nested_scripts import BUILDER_PATH, render_builder_bootstrap
from common.constants.database import DbCollections
from common.constants.states import ImageStatus
from common.exceptions import Conflict, NotFound

ADMIN_PASSWORD = 'Adm1n-S3cret!x'
VNC_PASSWORD = 'vncPw123'
PRODUCT_KEY = 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'
PROJECT = 'test-dev-787001'
USER = {'username': 'agoge', 'password': None, 'ssh_key': 'ssh-ed25519 AAAA parent', 'protocol': 'ssh'}
NESTED_KEYS = {'agoge-nested-manifest', 'agoge-nested-secrets', 'enable-guest-attributes'}

LINUX_ENTRY = dict(
    id='ubuntu-24.04', display_name='Ubuntu 24.04', family='linux', group='linux', version='24.04',
    install_method='cloud_image', media_url='https://cloud-images.ubuntu.com/noble/current/noble.img',
    media_sha256='b' * 64, media_formats=['qcow2'], license_note='GPL', osinfo='ubuntu24.04', agent=True,
    net_config='netplan', min_memory_mb=1024, default_memory_mb=2048, min_disk_gb=10, default_disk_gb=20,
)
WINDOWS_ENTRY = dict(
    id='win-7', display_name='Windows 7', family='windows', group='windows_client', version='7',
    install_method='unattended_iso', media_formats=['iso'], requires_upload=True, license_note='Retail key',
    osinfo='win7', agent=True, net_config='windows', unattend_template='autounattend', windows_image_index=1,
    disk_bus='sata', nic_model='e1000', virtio_win_version='0.1.173', min_memory_mb=2048,
    default_memory_mb=4096, min_disk_gb=32, default_disk_gb=40,
)
UPLOAD = dict(
    id='med-1', filename='win7.iso', format='iso', size_bytes=3_000_000_000,
    gcs_path=f'gs://{PROJECT}_nested-media/media/med-1/win7.iso', uploaded_by='teacher@example.com',
    uploaded_at='2026-10-17T00:00:00+00:00', complete=True,
)


def _guest(name, os_id, **overrides):
    guest = dict(name=name, os_id=os_id, nics=[{'network': 'lab', 'ip': '10.10.0.10'}],
                 admin_username='student', admin_password=ADMIN_PASSWORD)
    guest.update(overrides)
    return guest


def _record(phase='queued', **overrides):
    record = dict(
        name='nestedhost', machine_type='n2-standard-4', description='Nested lab host', tags=[],
        image='nestedhost', os='linux', add_disk='120', human_interaction=[USER],
        status=ImageStatus.CHECKED_OUT.value, self_link='projects/debian-cloud/global/images/family/debian-12',
        nested=dict(
            parent_os='debian-13', build_machine_type='n2-standard-8',
            networks=[{'name': 'lab', 'cidr': '10.10.0.0/24', 'mode': 'isolated'}],
            guests=[_guest('web', 'ubuntu-24.04'), _guest('desk', 'win-7', media_id='med-1')],
            console_ports={'web': 5901, 'desk': 5902}, vnc_passwords={'web': VNC_PASSWORD},
        ),
        nested_build={'phase': phase},
    )
    record.update(overrides)
    return record


def _manager(record):
    manager = object.__new__(ImageTemplateManager)
    manager.class_name = 'ImageTemplateManager'
    manager.log_name = 'test'
    manager.logger = Mock()
    manager.image_name = 'nestedhost'
    manager.server_name = 'nestedhost'
    manager.user = 'teacher@example.com'
    manager.collection = DbCollections.IMAGE
    manager.env = SimpleNamespace(project=PROJECT)
    manager.nested_metadata = []
    manager.nested_bootstrap = None
    manager.compute_image = Mock()
    manager._dns_record = Mock(return_value='nestedhost.example.com')
    manager._require_image_management = Mock()
    docs = {
        (DbCollections.IMAGE, 'nestedhost'): record,
        (DbCollections.NESTED_OS_CATALOG, 'ubuntu-24.04'): LINUX_ENTRY,
        (DbCollections.NESTED_OS_CATALOG, 'win-7'): WINDOWS_ENTRY,
        (DbCollections.NESTED_MEDIA, 'med-1'): UPLOAD,
    }
    manager.db = Mock()
    manager.db.get.side_effect = lambda collection_name, doc_id: copy.deepcopy(docs.get((collection_name, doc_id)))
    # What load() puts in server_spec for this record (BaseComputeManager._load_template_server).
    manager.server_spec = SimpleNamespace(
        os=record['os'], machine_type=record['machine_type'], self_link=record['self_link'],
        add_disk=record['add_disk'], startup_script=None, human_interaction=record['human_interaction'],
        ssh_keys=[USER['ssh_key']],
    )
    built = {}

    def build():
        # Capture what _build_server would hand to the instance insert.
        manager._add_metadata()
        built.update(
            machine_type=manager.server_spec.machine_type, self_link=manager.server_spec.self_link,
            add_disk=manager.server_spec.add_disk,
            items={item['key']: item['value'] for item in manager.server_spec.metadata['items']},
        )
    manager.build = Mock(side_effect=build)
    return manager, built


def _stored(manager):
    return manager.db.update.call_args.kwargs['data']


def test_first_build_boots_debian_family_on_build_machine_type_with_builder_metadata():
    manager, built = _manager(_record())

    manager.check_out(product_keys={'desk': PRODUCT_KEY})

    assert built['self_link'] == 'projects/debian-cloud/global/images/family/debian-13'
    assert built['machine_type'] == 'n2-standard-8'
    assert built['add_disk'] == '120'
    assert set(built['items']) == NESTED_KEYS | {'startup-script', 'ssh-keys'}
    assert built['items']['enable-guest-attributes'] == 'TRUE'
    script = built['items']['startup-script']
    # The parent's login account is created before the hours-long builder is started.
    assert script.startswith('#!/bin/bash')
    assert script.index('useradd') < script.index('agoge-nested-builder bootstrap')
    assert f"'{BUILDER_PATH}'" in script and 'systemd-run --unit=agoge-nested-builder' in script

    manifest = json.loads(built['items']['agoge-nested-manifest'])
    assert [guest['name'] for guest in manifest['guests']] == ['web', 'desk']
    assert manifest['guests'][1]['media']['gcs_path'] == UPLOAD['gcs_path']
    secrets = json.loads(built['items']['agoge-nested-secrets'])
    assert secrets['web'] == {'admin_password': ADMIN_PASSWORD, 'vnc_password': VNC_PASSWORD}
    assert secrets['desk']['product_key'] == PRODUCT_KEY
    # The builder fails an unattended Windows guest whose autounattend is not in the secrets (V9).
    assert '<unattend' in secrets['desk']['autounattend'] and PRODUCT_KEY in secrets['desk']['autounattend']
    assert 'autounattend' not in secrets['web']
    for secret in (ADMIN_PASSWORD, VNC_PASSWORD, PRODUCT_KEY):
        assert secret not in built['items']['agoge-nested-manifest']

    stored = _stored(manager)
    assert stored['nested_build']['phase'] == 'provisioning'
    assert stored['nested_build']['started_at'] and stored['nested_build']['updated_at']
    assert stored['status'] == ImageStatus.CHECKED_OUT.value
    # Product keys are used for the build and never stored (Design Decisions).
    assert PRODUCT_KEY not in json.dumps(stored)


def test_re_check_out_of_a_finalized_image_sends_no_manifest_or_secrets():
    source = f'projects/{PROJECT}/global/images/image-nestedhost'
    manager, built = _manager(_record(phase='finalized', self_link=source, status=ImageStatus.CHECKED_IN.value))

    manager.check_out()

    assert built['self_link'] == source
    assert built['machine_type'] == 'n2-standard-4'
    assert set(built['items']) == {'enable-guest-attributes', 'startup-script', 'ssh-keys'}
    assert 'agoge-nested-builder' not in built['items']['startup-script']
    assert _stored(manager)['nested_build']['phase'] == 'finalized'
    # Only the image template record is read: nothing is resolved from the catalog or media.
    assert {call.kwargs['collection_name'] for call in manager.db.get.call_args_list} == {DbCollections.IMAGE}


def test_duplicate_first_check_out_delivery_renders_the_build_again():
    manager, built = _manager(_record(phase='provisioning', nested_build={
        'phase': 'provisioning', 'started_at': '2026-10-17T01:00:00+00:00'}))

    manager.check_out()

    assert NESTED_KEYS <= set(built['items'])
    assert _stored(manager)['nested_build']['started_at'] == '2026-10-17T01:00:00+00:00'


@pytest.mark.parametrize('phase', ['building', 'ready', 'finalizing', 'failed'])
def test_check_out_mid_build_is_refused_before_any_build(phase):
    manager, _ = _manager(_record(phase=phase))

    with pytest.raises(Conflict, match=phase):
        manager.check_out()

    manager.build.assert_not_called()
    manager.db.update.assert_not_called()


def test_missing_catalog_entry_fails_the_build_without_creating_a_server():
    record = _record()
    record['nested']['guests'][0]['os_id'] = 'gone-os'
    manager, _ = _manager(record)

    with pytest.raises(NotFound, match='gone-os'):
        manager.check_out()

    manager.build.assert_not_called()
    stored = _stored(manager)
    assert stored['nested_build']['phase'] == 'failed'
    assert 'gone-os' in stored['nested_build']['message']


def test_standard_image_check_out_is_unchanged():
    record = _record()
    del record['nested'], record['nested_build']
    manager, built = _manager(record)

    manager.check_out()

    assert built['self_link'] == record['self_link']
    assert built['machine_type'] == 'n2-standard-4'
    assert set(built['items']) == {'startup-script', 'ssh-keys'}
    assert 'agoge-nested' not in built['items']['startup-script']
    assert 'nested_build' not in _stored(manager)


def test_builder_bootstrap_is_valid_bash_and_embeds_the_builder_verbatim():
    bootstrap = render_builder_bootstrap()

    subprocess.run(['bash', '-n'], input=bootstrap, text=True, check=True)
    assert nested_scripts.render_builder().rstrip('\n') in bootstrap
    # Merged into a startup-script, an exit would end the scripts that follow it.
    assert not any(line.strip().startswith('exit') for line in bootstrap.splitlines()[-6:])


def test_builder_bootstrap_refuses_a_builder_holding_its_delimiter(monkeypatch):
    monkeypatch.setattr(nested_scripts, 'render_builder', lambda: 'echo\nAGOGE_NESTED_BUILDER_SCRIPT\n')

    with pytest.raises(ValueError, match='AGOGE_NESTED_BUILDER_SCRIPT'):
        render_builder_bootstrap()
