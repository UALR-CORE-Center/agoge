"""Manifest, secrets, and autounattend rendering for nested lab hosts (V8, SC-33)."""
import json
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

from common.constants.nested import NESTED_METADATA_MAX_BYTES
from common.exceptions.agoge import BadRequest
from common.models.agoge import NestedHostSpecModel, NestedMediaModel, NestedOsCatalogModel
from common.utilities import nested_manifest
from common.utilities.nested_manifest import (build_secrets, guest_mac, load_autounattend_template,
                                              render_autounattend, render_manifest, render_secrets)

NS = {'u': 'urn:schemas-microsoft-com:unattend'}
CATALOG_JSON = Path(__file__).resolve().parents[2] / 'common' / 'data' / 'nested_os_catalog.json'
ADMIN_PASSWORD = 'Adm1n-S3cret!x'
PRODUCT_KEY = 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'
SHA = 'a' * 64


def _entry(entry_id, osinfo, **overrides):
    base = dict(
        id=entry_id, display_name=entry_id, family='windows', group='windows_server', version='1',
        install_method='unattended_iso', media_url='https://go.microsoft.com/fwlink/p/?LinkID=1',
        media_sha256=SHA, media_formats=['iso'], license_note='Evaluation, 180 days', eval_days=180,
        osinfo=osinfo, agent=True, net_config='windows', unattend_template='autounattend',
        windows_image_index=2, virtio_win_version='0.1.262', min_memory_mb=2048, default_memory_mb=4096,
        min_disk_gb=32, default_disk_gb=40,
    )
    base.update(overrides)
    return NestedOsCatalogModel(**base)


# Stand-ins until V6 seeds common/data/nested_os_catalog.json (blocked on Open Question V-5);
# they cover every unattend shape the contract's catalog table needs.
FIXTURE_WINDOWS_ENTRIES = [
    _entry('win-server-2016-eval', 'win2k16'),
    _entry('win-server-2019-eval', 'win2k19'),
    _entry('win-server-2022-eval', 'win2k22'),
    _entry('win-server-2025-eval', 'win2k25'),
    _entry('win-10-enterprise-eval', 'win10', group='windows_client', eval_days=90, windows_image_index=1),
    _entry('win-11-enterprise-eval', 'win11', group='windows_client', eval_days=90, windows_image_index=1),
    _entry('win-7', 'win7', group='windows_client', media_url=None, media_sha256=None, requires_upload=True,
           eval_days=None, disk_bus='sata', nic_model='e1000', virtio_win_version='0.1.173', windows_image_index=1),
    _entry('win-vista', 'winvista', group='windows_client', media_url=None, media_sha256=None,
           requires_upload=True, eval_days=None, disk_bus='sata', nic_model='e1000', virtio_win_version=None,
           agent=False, windows_image_index=1),
    _entry('win-server-2012r2', 'win2k12r2', media_url=None, media_sha256=None, requires_upload=True,
           eval_days=None, disk_bus='sata', nic_model='e1000', virtio_win_version='0.1.190'),
    _entry('win-server-2022-uefi', 'win2k22', firmware='uefi'),
]
LINUX_ENTRY = NestedOsCatalogModel(
    id='ubuntu-24.04', display_name='Ubuntu 24.04', family='linux', group='linux', version='24.04',
    install_method='cloud_image', media_url='https://cloud-images.ubuntu.com/noble/current/noble.img',
    media_sha256='b' * 64, media_formats=['qcow2'], license_note='GPL', osinfo='ubuntu24.04', agent=True,
    net_config='netplan', min_memory_mb=1024, default_memory_mb=2048, min_disk_gb=10, default_disk_gb=20,
)
UPLOAD = NestedMediaModel(
    id='med-1', filename='win7.iso', format='iso', size_bytes=3_000_000_000,
    gcs_path='gs://proj_nested-media/media/med-1/win7.iso', uploaded_by='teacher@example.com',
    uploaded_at='2026-10-17T00:00:00Z', complete=True,
)


def _catalog_entries():
    entries = list(FIXTURE_WINDOWS_ENTRIES)
    if CATALOG_JSON.is_file():
        entries += [NestedOsCatalogModel(**item) for item in json.loads(CATALOG_JSON.read_text())]
    return [entry for entry in entries if entry.install_method == 'unattended_iso']


def _guest(name, os_id, nics=None, **overrides):
    guest = dict(name=name, os_id=os_id, admin_username='labadmin', admin_password=ADMIN_PASSWORD,
                 nics=nics or [{'network': 'lan', 'ip': '10.10.0.20'}])
    guest.update(overrides)
    return guest


def _spec(guests, networks=None):
    networks = networks or [
        {'name': 'lan', 'cidr': '10.10.0.0/24', 'mode': 'nat', 'parent_address': '10.10.0.1',
         'dhcp_start': '10.10.0.100', 'dhcp_end': '10.10.0.200'},
        {'name': 'dmz', 'cidr': '10.20.0.0/24', 'mode': 'isolated', 'parent_address': None, 'dhcp': False},
    ]
    spec = NestedHostSpecModel(networks=networks, guests=guests)
    console = [guest.name for guest in spec.guests if guest.console]
    return spec.model_copy(update={
        'console_ports': {name: 5901 + slot for slot, name in enumerate(console)},
        'vnc_passwords': {name: f'vnc{slot:05d}' for slot, name in enumerate(console)},
    })


def _three_guest_spec():
    return _spec([
        _guest('kali', 'ubuntu-24.04', nics=[{'network': 'lan', 'ip': '10.10.0.10', 'expose': True}]),
        _guest('dc', 'win-server-2022-eval', nics=[{'network': 'lan', 'ip': '10.10.0.20'},
                                                   {'network': 'dmz', 'ip': '10.20.0.20'}]),
        _guest('legacy', 'win-7', media_id='med-1'),
    ])


def _catalog():
    return {entry.id: entry for entry in [*FIXTURE_WINDOWS_ENTRIES, LINUX_ENTRY]}


def _render(entry, guest=None, product_key=None, networks=None):
    spec = _spec([guest or _guest('win', entry.id)], networks=networks)
    secrets = build_secrets(spec, {spec.guests[0].name: product_key} if product_key else {})
    return render_autounattend(spec.guests[0], entry, secrets, spec.networks)


def _first_logon(xml):
    root = ElementTree.fromstring(xml)
    commands = root.findall('.//u:FirstLogonCommands/u:SynchronousCommand', NS)
    ordered = sorted(commands, key=lambda command: int(command.find('u:Order', NS).text))
    return [command.find('u:CommandLine', NS).text for command in ordered]


# --- manifest ---------------------------------------------------------------------------------

def test_manifest_holds_no_secret():
    spec = _three_guest_spec()
    manifest = render_manifest(spec, _catalog(), {'med-1': UPLOAD})
    assert ADMIN_PASSWORD not in manifest
    assert PRODUCT_KEY not in manifest
    for password in spec.vnc_passwords.values():
        assert password not in manifest
    assert 'admin_password' not in manifest
    assert 'vnc_passwords' not in manifest
    assert 'product_key' not in manifest


def test_manifest_resolves_catalog_entry_and_media_source():
    manifest = json.loads(render_manifest(_three_guest_spec(), _catalog(), {'med-1': UPLOAD}))
    guests = {guest['name']: guest for guest in manifest['guests']}
    assert guests['dc']['catalog']['osinfo'] == 'win2k22'
    assert guests['dc']['media'] == {'source': 'url', 'url': 'https://go.microsoft.com/fwlink/p/?LinkID=1',
                                     'sha256': SHA, 'format': 'iso'}
    assert guests['legacy']['media'] == {'source': 'gcs', 'media_id': 'med-1', 'gcs_path': UPLOAD.gcs_path,
                                         'sha256': None, 'format': 'iso'}
    assert [nic['mac'] for nic in guests['dc']['nics']] == [guest_mac('dc', 0), guest_mac('dc', 1)]
    assert manifest['console_ports'] == {'kali': 5901, 'dc': 5902, 'legacy': 5903}
    assert manifest['networks'][0]['name'] == 'lan'


def _json_cloud_image_entries():
    items = json.loads(CATALOG_JSON.read_text()) if CATALOG_JSON.is_file() else []
    return [NestedOsCatalogModel(**item) for item in items if item['install_method'] == 'cloud_image']


@pytest.mark.parametrize('entry', _json_cloud_image_entries(), ids=lambda entry: entry.id)
def test_manifest_downloads_each_seeded_cloud_image_by_its_pinned_url(entry):
    spec = _spec([_guest('web', entry.id, packages=['nginx'])])
    guest = json.loads(render_manifest(spec, {entry.id: entry}, {}))['guests'][0]
    assert guest['media'] == {'source': 'url', 'url': entry.media_url, 'sha256': entry.media_sha256,
                              'format': entry.media_formats[0]}
    assert guest['catalog']['install_method'] == 'cloud_image'
    assert guest['catalog']['net_config'] == entry.net_config


def _json_downloaded_iso_entries():
    items = json.loads(CATALOG_JSON.read_text()) if CATALOG_JSON.is_file() else []
    return [NestedOsCatalogModel(**item) for item in items
            if item['install_method'] == 'manual_iso' and not item['requires_upload']]


@pytest.mark.parametrize('entry', _json_downloaded_iso_entries(), ids=lambda entry: entry.id)
def test_manifest_downloads_each_seeded_appliance_iso_by_its_pinned_url(entry):
    # A downloaded manual_iso guest has no media_id; the builder fetches and verifies the pinned ISO itself.
    spec = _spec([_guest('appliance', entry.id, memory_mb=entry.default_memory_mb, disk_gb=entry.default_disk_gb)])
    guest = json.loads(render_manifest(spec, {entry.id: entry}, {}))['guests'][0]
    assert guest['media'] == {'source': 'url', 'url': entry.media_url, 'sha256': entry.media_sha256, 'format': 'iso'}
    assert guest['catalog']['install_method'] == 'manual_iso'
    assert guest['catalog']['net_config'] == 'none'


def _json_downloaded_disk_entries():
    items = json.loads(CATALOG_JSON.read_text()) if CATALOG_JSON.is_file() else []
    return [NestedOsCatalogModel(**item) for item in items
            if item['install_method'] == 'disk_image' and not item['requires_upload']]


@pytest.mark.parametrize('entry', _json_downloaded_disk_entries(), ids=lambda entry: entry.id)
def test_manifest_downloads_each_seeded_appliance_disk_by_its_pinned_url(entry):
    # builder.sh prepare_disk expands the compressed download in scratch, so the format must be one it knows.
    spec = _spec([_guest('appliance', entry.id, memory_mb=entry.default_memory_mb, disk_gb=entry.default_disk_gb)])
    guest = json.loads(render_manifest(spec, {entry.id: entry}, {}))['guests'][0]
    assert guest['media'] == {'source': 'url', 'url': entry.media_url, 'sha256': entry.media_sha256,
                              'format': entry.media_formats[0]}
    assert entry.media_formats[0] in {'qcow2', 'raw', 'img.xz', 'img.bz2'}
    assert guest['catalog']['install_method'] == 'disk_image'
    assert guest['catalog']['net_config'] == 'none'


def test_manifest_rejects_missing_catalog_entry_and_medium():
    spec = _three_guest_spec()
    with pytest.raises(ValueError, match='legacy: no medium med-1'):
        render_manifest(spec, _catalog(), {})
    with pytest.raises(ValueError, match='kali: no catalog entry ubuntu-24.04'):
        render_manifest(spec, {entry.id: entry for entry in FIXTURE_WINDOWS_ENTRIES}, {'med-1': UPLOAD})
    upload_only = _spec([_guest('legacy', 'win-7')])
    with pytest.raises(ValueError, match='requires an uploaded medium'):
        render_manifest(upload_only, _catalog(), {})


def test_guest_mac_is_stable_and_in_the_qemu_range():
    assert guest_mac('dc', 0) == guest_mac('dc', 0)
    assert guest_mac('dc', 0) != guest_mac('dc', 1)
    assert guest_mac('dc', 0).startswith('52:54:00:')
    assert len(guest_mac('dc', 0).split(':')) == 6


def test_manifest_rejects_a_mac_collision(monkeypatch):
    monkeypatch.setattr(nested_manifest, 'guest_mac', lambda name, index: '52:54:00:00:00:01')
    spec = _spec([_guest('one', 'ubuntu-24.04'), _guest('two', 'ubuntu-24.04', nics=[{'network': 'lan'}])])
    with pytest.raises(BadRequest, match='one and two'):
        render_manifest(spec, _catalog(), {})


def _eight_large_guests(script_bytes):
    guests = [
        _guest(f'guest-{index}', 'ubuntu-24.04',
               nics=[{'network': 'lan', 'ip': f'10.10.0.{10 + index * 4 + nic}'} for nic in range(4)],
               packages=[f'package-name-{n:02d}' for n in range(50)],
               post_install_script='x' * script_bytes, admin_password=f'P@ssw0rd-{index}' * 8)
        for index in range(8)
    ]
    return _spec(guests)


def test_manifest_and_secrets_stay_under_the_metadata_limit_for_eight_guests():
    spec = _eight_large_guests(script_bytes=16384)
    keys = {guest.name: PRODUCT_KEY for guest in spec.guests}
    manifest = render_manifest(spec, _catalog(), {})
    secrets = render_secrets(spec, keys)
    assert len(json.loads(manifest)['guests']) == 8
    assert len(manifest.encode()) < NESTED_METADATA_MAX_BYTES
    assert len(secrets.encode()) < NESTED_METADATA_MAX_BYTES


def test_manifest_over_the_metadata_limit_is_a_bad_request():
    # Eight maximum-length post-install scripts are 512 KB, twice what one metadata value holds.
    with pytest.raises(BadRequest, match='agoge-nested-manifest .* metadata limit'):
        render_manifest(_eight_large_guests(script_bytes=65536), _catalog(), {})


# --- secrets ----------------------------------------------------------------------------------

def test_secrets_carry_passwords_and_only_given_product_keys():
    spec = _three_guest_spec()
    secrets = json.loads(render_secrets(spec, {'dc': PRODUCT_KEY, 'ghost': PRODUCT_KEY}))
    assert set(secrets) == {'kali', 'dc', 'legacy'}
    assert secrets['dc'] == {'admin_password': ADMIN_PASSWORD, 'vnc_password': spec.vnc_passwords['dc'],
                             'product_key': PRODUCT_KEY}
    assert 'product_key' not in secrets['kali']


def test_secrets_omit_vnc_password_without_a_console():
    spec = _spec([_guest('headless', 'ubuntu-24.04', console=False)])
    assert build_secrets(spec) == {'headless': {'admin_password': ADMIN_PASSWORD}}


# --- autounattend -----------------------------------------------------------------------------

@pytest.mark.parametrize('entry', _catalog_entries(), ids=lambda entry: entry.id)
def test_autounattend_parses_for_every_unattended_entry(entry):
    root = ElementTree.fromstring(_render(entry, product_key=None if entry.eval_days else PRODUCT_KEY))
    passes = {settings.get('pass') for settings in root.findall('u:settings', NS)}
    assert passes == {'windowsPE', 'specialize', 'oobeSystem'}
    index = root.find('.//u:InstallFrom/u:MetaData/u:Value', NS).text
    assert index == str(entry.windows_image_index)
    assert root.find('.//u:ComputerName', NS).text == 'WIN'


@pytest.mark.parametrize('entry', _catalog_entries(), ids=lambda entry: entry.id)
def test_virtio_driver_paths_only_with_a_virtio_release(entry):
    root = ElementTree.fromstring(_render(entry))
    paths = [path.text for path in root.findall('.//u:DriverPaths/u:PathAndCredentials/u:Path', NS)]
    commands = ' '.join(_first_logon(ElementTree.tostring(root, encoding='unicode')))
    if entry.virtio_win_version:
        directory = nested_manifest.VIRTIO_OS_DIRECTORIES[entry.osinfo]
        assert f'E:\\viostor\\{directory}\\amd64' in paths
        assert f'E:\\NetKVM\\{directory}\\amd64' in paths
        assert 'start "" /wait msiexec /i %d:\\guest-agent\\qemu-ga-x86_64.msi' in commands
    else:
        assert paths == []
        assert root.find('.//u:DriverPaths', NS) is None
        assert 'msiexec' not in commands


@pytest.mark.parametrize('entry', _catalog_entries(), ids=lambda entry: entry.id)
def test_labconfig_only_for_windows_11_and_server_2025(entry):
    xml = _render(entry)
    root = ElementTree.fromstring(xml)
    paths = [path.text for path in root.findall('.//u:RunSynchronous/u:RunSynchronousCommand/u:Path', NS)]
    if entry.osinfo in ('win11', 'win2k25'):
        assert any('LabConfig /v BypassTPMCheck' in path for path in paths)
        assert any('LabConfig /v BypassSecureBootCheck' in path for path in paths)
        assert any('LabConfig /v BypassRAMCheck' in path for path in paths)
    else:
        assert 'LabConfig' not in xml


@pytest.mark.parametrize('entry', _catalog_entries(), ids=lambda entry: entry.id)
def test_first_logon_deletes_panther_unattend_and_ends_with_shutdown(entry):
    commands = _first_logon(_render(entry))
    assert any(r'del /f /q C:\Windows\Panther\unattend*.xml' in command for command in commands)
    assert commands[-1].startswith('shutdown /s')
    # Nothing runs after the shutdown, and the password cleanup happens before it.
    assert any('DefaultPassword' in command for command in commands[:-1])


def test_first_logon_enables_rdp_icmp_and_static_ips_by_mac():
    spec = _three_guest_spec()
    dc = spec.guests[1]
    xml = render_autounattend(dc, _catalog()['win-server-2022-eval'], build_secrets(spec), spec.networks)
    commands = _first_logon(xml)
    joined = '\n'.join(commands)
    assert 'fDenyTSConnections /t REG_DWORD /d 0' in joined
    assert 'icmpv4:8' in joined
    lan = next(command for command in commands if guest_mac('dc', 0).upper() in command)
    assert "EnableStatic(@('10.10.0.20'), @('255.255.255.0'))" in lan
    assert "SetGateways(@('10.10.0.1')" in lan
    dmz = next(command for command in commands if guest_mac('dc', 1).upper() in command)
    assert "EnableStatic(@('10.20.0.20')" in dmz
    # The dmz has no parent address, so it gets neither a gateway nor a DNS server.
    assert 'SetGateways' not in dmz and 'SetDNSServerSearchOrder' not in dmz


def test_dhcp_nic_gets_no_static_command():
    entry = _catalog()['win-server-2022-eval']
    commands = _first_logon(_render(entry, guest=_guest('win', entry.id, nics=[{'network': 'lan'}])))
    assert not any('EnableStatic' in command for command in commands)


def test_autounattend_escapes_credentials_and_sets_product_key():
    entry = _catalog()['win-7']
    guest = _guest('win', entry.id, admin_password='P<a&ss>"w0rd')
    root = ElementTree.fromstring(_render(entry, guest=guest, product_key=PRODUCT_KEY))
    assert root.find('.//u:AdministratorPassword/u:Value', NS).text == 'P<a&ss>"w0rd'
    assert root.find('.//u:AutoLogon/u:Password/u:Value', NS).text == 'P<a&ss>"w0rd'
    assert root.find('.//u:ProductKey/u:Key', NS).text == PRODUCT_KEY
    account = root.find('.//u:LocalAccounts/u:LocalAccount', NS)
    assert account.find('u:Name', NS).text == 'labadmin'
    assert account.find('u:Group', NS).text == 'Administrators'


def test_eval_entry_without_key_has_no_product_key_and_administrator_has_no_local_account():
    entry = _catalog()['win-server-2022-eval']
    root = ElementTree.fromstring(_render(entry, guest=_guest('win', entry.id, admin_username='Administrator')))
    assert root.find('.//u:ProductKey', NS) is None
    assert root.find('.//u:LocalAccounts', NS) is None
    assert root.find('.//u:AutoLogon/u:Username', NS).text == 'Administrator'


def test_bios_and_uefi_partition_layouts():
    bios = ElementTree.fromstring(_render(_catalog()['win-server-2022-eval']))
    assert [node.text for node in bios.findall('.//u:CreatePartition/u:Type', NS)] == ['Primary']
    assert bios.find('.//u:InstallTo/u:PartitionID', NS).text == '1'
    assert bios.find('.//u:ModifyPartition/u:Active', NS).text == 'true'
    uefi = ElementTree.fromstring(_render(_catalog()['win-server-2022-uefi']))
    assert [node.text for node in uefi.findall('.//u:CreatePartition/u:Type', NS)] == ['EFI', 'MSR', 'Primary']
    assert uefi.find('.//u:InstallTo/u:PartitionID', NS).text == '3'


def test_autounattend_rejects_non_unattended_entries_and_missing_image_index():
    spec = _spec([_guest('kali', 'ubuntu-24.04')])
    with pytest.raises(ValueError, match='not an unattended Windows install'):
        render_autounattend(spec.guests[0], LINUX_ENTRY, build_secrets(spec), spec.networks)
    entry = _entry('win-noindex', 'win2k22', windows_image_index=None)
    with pytest.raises(ValueError, match='no windows_image_index'):
        _render(entry)
    with pytest.raises(ValueError, match='no virtio-win driver directory'):
        _render(_entry('win-odd', 'winxp'))


def test_static_nic_without_its_network_is_a_value_error():
    spec = _three_guest_spec()
    with pytest.raises(ValueError, match='dc: static NIC 0 names unknown network lan'):
        render_autounattend(spec.guests[1], _catalog()['win-server-2022-eval'], build_secrets(spec))


def test_template_is_found_in_the_staging_layout(tmp_path, monkeypatch):
    # Deployed, common/ sits beside cloud_fn_utilities/ in .staging/<app>/.
    template = tmp_path / nested_manifest.TEMPLATE_RELATIVE_PATH
    template.parent.mkdir(parents=True)
    template.write_text('staged')
    monkeypatch.setattr(nested_manifest, '__file__', str(tmp_path / 'common' / 'utilities' / 'nested_manifest.py'))
    assert load_autounattend_template() == 'staged'


def test_template_is_found_in_the_repository_layout():
    template = load_autounattend_template()
    assert '${first_logon_commands}' in template
