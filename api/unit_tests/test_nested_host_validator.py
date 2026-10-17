"""NestedHostValidator enforces the nested image validation table; derive fills alias slots and consoles (PRD V7)."""
import copy
from types import SimpleNamespace

import pytest

from common.constants.database import DbCollections
from common.exceptions import BadRequest
from common.models.agoge import NestedImageCreateRequest
from common.models.google import MachineTypeModel
from core.compute.nested import validator as validator_module
from core.compute.nested.validator import NestedHostValidator

CATALOG = {
    'debian-12': {
        'id': 'debian-12', 'display_name': 'Debian 12', 'family': 'linux', 'group': 'linux', 'version': '12',
        'install_method': 'cloud_image', 'media_url': 'https://cloud.debian.org/debian-12.qcow2',
        'media_sha256': 'a' * 64, 'media_formats': ['qcow2'], 'license_note': 'Free software.',
        'osinfo': 'debian12', 'agent': True, 'net_config': 'ifupdown',
        'min_memory_mb': 512, 'default_memory_mb': 1024, 'min_disk_gb': 4, 'default_disk_gb': 10,
    },
    'win2022-eval': {
        'id': 'win2022-eval', 'display_name': 'Windows Server 2022 Evaluation', 'family': 'windows',
        'group': 'windows_server', 'version': '2022', 'install_method': 'unattended_iso',
        'media_url': 'https://go.microsoft.com/fwlink/p/?LinkID=2195280', 'media_sha256': 'b' * 64,
        'media_formats': ['iso'], 'license_note': '180-day evaluation.', 'eval_days': 180, 'osinfo': 'win2k22',
        'agent': True, 'net_config': 'windows', 'unattend_template': 'autounattend', 'virtio_win_version': '0.1.266',
        'min_memory_mb': 2048, 'default_memory_mb': 4096, 'min_disk_gb': 32, 'default_disk_gb': 40,
    },
    'win10-licensed': {
        'id': 'win10-licensed', 'display_name': 'Windows 10 (licensed)', 'family': 'windows',
        'group': 'windows_client', 'version': '10', 'install_method': 'unattended_iso', 'media_url': None,
        'media_formats': ['iso'], 'requires_upload': True, 'license_note': 'Bring your own license.',
        'osinfo': 'win10', 'agent': True, 'net_config': 'windows', 'unattend_template': 'autounattend',
        'min_memory_mb': 2048, 'default_memory_mb': 4096, 'min_disk_gb': 32, 'default_disk_gb': 40,
    },
    'retired-os': {
        'id': 'retired-os', 'display_name': 'Retired', 'family': 'linux', 'group': 'linux', 'version': '1',
        'install_method': 'cloud_image', 'media_url': 'https://example.org/retired.qcow2', 'media_sha256': 'c' * 64,
        'media_formats': ['qcow2'], 'license_note': 'Old.', 'osinfo': 'linux2020', 'agent': False,
        'net_config': 'none', 'min_memory_mb': 256, 'default_memory_mb': 512, 'min_disk_gb': 2,
        'default_disk_gb': 4, 'is_enabled': False,
    },
}
MEDIA = {
    'media-win10': {'id': 'media-win10', 'filename': 'win10.iso', 'format': 'iso', 'size_bytes': 5_000_000_000,
                    'gcs_path': 'gs://test-dev-787001_nested-media/media/media-win10/win10.iso',
                    'uploaded_by': 'teacher', 'uploaded_at': '2026-10-17T00:00:00', 'complete': True},
    'media-partial': {'id': 'media-partial', 'filename': 'win10.iso', 'format': 'iso', 'size_bytes': 10,
                      'gcs_path': 'gs://test-dev-787001_nested-media/media/media-partial/win10.iso',
                      'uploaded_by': 'teacher', 'uploaded_at': '2026-10-17T00:00:00', 'complete': False},
    'media-vmdk': {'id': 'media-vmdk', 'filename': 'win10.vmdk', 'format': 'vmdk', 'size_bytes': 10,
                   'gcs_path': 'gs://test-dev-787001_nested-media/media/media-vmdk/win10.vmdk',
                   'uploaded_by': 'teacher', 'uploaded_at': '2026-10-17T00:00:00', 'complete': True},
}
MACHINE_TYPES = {
    'n2-standard-8': (32768, 8),
    'n2-standard-4': (16384, 4),
    'n1-standard-2': (7680, 2),
    'n1-highmem-2': (13312, 2),
}
PRODUCT_KEY = 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'


class FakeDb:
    def get(self, collection_name, doc_id):
        source = {DbCollections.NESTED_OS_CATALOG: CATALOG, DbCollections.NESTED_MEDIA: MEDIA}[collection_name]
        return copy.deepcopy(source.get(doc_id))


class FakeMachineTypes:
    def get(self, name):
        if name not in MACHINE_TYPES:
            return None
        memory, cpus = MACHINE_TYPES[name]
        return MachineTypeModel(id=name, name=name, description=name, is_shared_core=False,
                                memory_mb=memory, guest_cpus=cpus)


def _body():
    """Three guests on two networks: a Linux router, an evaluation Windows server, a licensed Windows client."""
    return {
        'server_name': 'ad-lab',
        'description': 'AD lab',
        'machine_type': 'n2-standard-8',
        'username': 'agoge',
        'ssh_key': 'ssh-ed25519 AAAA',
        'nested': {
            'build_machine_type': 'n2-standard-8',
            'networks': [
                {'name': 'corp', 'cidr': '10.20.0.0/24', 'mode': 'nat', 'parent_address': '10.20.0.1',
                 'dhcp_start': '10.20.0.100', 'dhcp_end': '10.20.0.200'},
                {'name': 'dmz', 'cidr': '172.16.5.0/28', 'mode': 'isolated', 'dhcp': False},
            ],
            'guests': [
                {'name': 'router', 'os_id': 'debian-12', 'memory_mb': 1024, 'disk_gb': 10,
                 'nics': [{'network': 'corp', 'ip': '10.20.0.2', 'expose': True}, {'network': 'dmz', 'ip': '172.16.5.2'}],
                 'admin_username': 'agoge', 'admin_password': 'longenough', 'packages': ['nmap', 'tcpdump']},
                {'name': 'dc01', 'os_id': 'win2022-eval', 'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 40,
                 'nics': [{'network': 'corp', 'ip': '10.20.0.10', 'expose': True}],
                 'admin_username': 'Administrator', 'admin_password': 'Passw0rd!'},
                {'name': 'ws01', 'os_id': 'win10-licensed', 'media_id': 'media-win10', 'vcpus': 2,
                 'memory_mb': 4096, 'disk_gb': 40, 'nics': [{'network': 'corp'}], 'console': True,
                 'admin_username': 'student', 'admin_password': 'Passw0rd!'},
            ],
        },
        'product_keys': {'ws01': PRODUCT_KEY},
    }


@pytest.fixture
def validator(monkeypatch):
    monkeypatch.setattr(validator_module, 'CloudEnv', lambda **kwargs: SimpleNamespace(
        project='test-dev-787001', region='us-central1', zone='us-central1-a'))
    return NestedHostValidator(env_dict={}, db=FakeDb(), machine_type_api=FakeMachineTypes())


def _reject(validator, body, *expected):
    with pytest.raises(BadRequest) as excinfo:
        validator.validate(NestedImageCreateRequest(**body))
    message = str(excinfo.value)
    for fragment in expected:
        assert fragment in message, message


def _network(body, name):
    return next(n for n in body['nested']['networks'] if n['name'] == name)


def _guest(body, name):
    return next(g for g in body['nested']['guests'] if g['name'] == name)


def test_valid_three_guest_two_network_spec_passes(validator):
    entries = validator.validate(NestedImageCreateRequest(**_body()))

    assert {name: entry.id for name, entry in entries.items()} == {
        'router': 'debian-12', 'dc01': 'win2022-eval', 'ws01': 'win10-licensed'}


# Row 1: server_name passes _validate_new_name and is not `nested`.
@pytest.mark.parametrize('name, fragment', [('nested', 'nested'), ('Bad_Name', 'lowercase'), ('image-x', 'image-')])
def test_rejects_bad_or_reserved_server_name(validator, name, fragment):
    body = _body()
    body['server_name'] = name
    _reject(validator, body, fragment)


# Row 2: network names unique; RFC 1918, /16–/29, no overlaps.
def test_rejects_duplicate_network_name(validator):
    body = _body()
    _network(body, 'dmz')['name'] = 'corp'
    _reject(validator, body, 'Network corp', 'more than one')


@pytest.mark.parametrize('cidr, fragment', [
    ('8.8.8.0/24', 'RFC 1918'),
    ('10.0.0.0/15', '/16 to /29'),
    ('10.30.0.0/30', '/16 to /29'),
    ('10.20.0.5/24', 'CIDR'),
    ('192.168.122.0/24', '192.168.122.0/24'),
    ('10.20.0.0/16', 'overlaps network corp'),
])
def test_rejects_bad_cidr(validator, cidr, fragment):
    body = _body()
    _network(body, 'dmz')['cidr'] = cidr
    _reject(validator, body, 'Network dmz', fragment)


def test_link_local_is_reserved():
    # 169.254.0.0/16 is not RFC 1918, so the RFC 1918 check fires first; the reserved list still guards it.
    assert any(str(net) == '169.254.0.0/16' for net in validator_module.RESERVED_NETWORKS)


# Row 3: parent_address and DHCP range inside the CIDR, not network/broadcast; nat/dhcp need parent_address.
@pytest.mark.parametrize('field, value, fragment', [
    ('parent_address', '10.21.0.1', 'outside'),
    ('parent_address', '10.20.0.0', 'network or broadcast'),
    ('dhcp_end', '10.20.0.255', 'network or broadcast'),
    ('parent_address', '10.20.0.150', 'exclude parent_address'),
    ('dhcp_start', '10.20.0.201', 'dhcp_start must not be after dhcp_end'),
    ('parent_address', None, 'nat mode requires parent_address'),
    ('dhcp_start', None, 'dhcp_start and dhcp_end'),
])
def test_rejects_bad_network_addresses(validator, field, value, fragment):
    body = _body()
    _network(body, 'corp')[field] = value
    _reject(validator, body, 'Network corp', fragment)


def test_dhcp_on_isolated_network_requires_parent_address(validator):
    body = _body()
    _network(body, 'dmz')['dhcp'] = True
    _reject(validator, body, 'Network dmz', 'DHCP requires parent_address')


# Row 4: guest names unique; enabled catalog entry; uploaded media is complete and of an accepted format.
def test_rejects_duplicate_guest_name(validator):
    body = _body()
    _guest(body, 'ws01')['name'] = 'dc01'
    body['product_keys'] = {'dc01': PRODUCT_KEY}
    _reject(validator, body, 'Guest dc01', 'more than one')


@pytest.mark.parametrize('os_id', ['no-such-os', 'retired-os'])
def test_rejects_unknown_or_disabled_os(validator, os_id):
    body = _body()
    _guest(body, 'router')['os_id'] = os_id
    _guest(body, 'router')['packages'] = []
    _reject(validator, body, 'Guest router', os_id, 'enabled catalog entry')


@pytest.mark.parametrize('media_id, fragment', [
    (None, 'requires uploaded media'),
    ('missing', 'not a completed upload'),
    ('media-partial', 'not a completed upload'),
    ('media-vmdk', 'format vmdk'),
])
def test_rejects_missing_incomplete_or_wrong_format_media(validator, media_id, fragment):
    body = _body()
    _guest(body, 'ws01')['media_id'] = media_id
    _reject(validator, body, 'Guest ws01', fragment)


# Row 5: memory and disk minimums from the catalog.
@pytest.mark.parametrize('field, value, fragment', [('memory_mb', 2047, 'memory_mb'), ('disk_gb', 31, 'disk_gb')])
def test_rejects_guest_below_catalog_minimum(validator, field, value, fragment):
    body = _body()
    _guest(body, 'dc01')[field] = value
    _reject(validator, body, 'Guest dc01', fragment)


# Row 6: guest memory + overhead and vCPUs fit both machine types.
@pytest.mark.parametrize('field', ['machine_type', 'build_machine_type'])
def test_rejects_machine_type_too_small_for_guest_memory(validator, field):
    body = _body()
    (body if field == 'machine_type' else body['nested'])[field] = 'n2-standard-4'
    # 1024 + 12288 + 4096 guest MB + 2048 overhead = 19456 MB > 16384 MB.
    _guest(body, 'dc01')['memory_mb'] = 12288
    _reject(validator, body, field, 'n2-standard-4', '19456 MB')


def test_rejects_too_many_guest_vcpus(validator):
    body = _body()
    # n1-highmem-2 holds the 11264 MB the guests need, but its 2 vCPUs allow only 4 guest vCPUs, not 5.
    body['machine_type'] = 'n1-highmem-2'
    _reject(validator, body, 'machine_type', 'at most 4', 'ask for 5')


# Row 7: N1/N2 only.
@pytest.mark.parametrize('field', ['machine_type', 'build_machine_type'])
def test_rejects_e2_and_unknown_machine_types(validator, field):
    for name, fragment in (('e2-standard-8', 'N1 or N2'), ('n2-standard-999', 'not an available')):
        body = _body()
        (body if field == 'machine_type' else body['nested'])[field] = name
        _reject(validator, body, field, name, fragment)


# Row 8: disk_size between the computed minimum and NESTED_MAX_DISK_GB.
def test_computed_minimum_disk_size():
    request = NestedImageCreateRequest(**_body())
    assert NestedHostValidator.min_disk_size(request.nested.guests) == 20 + (10 + 40 + 40) + 12


@pytest.mark.parametrize('size, fragment', [(121, 'below the 122 GB'), (1001, 'exceeds')])
def test_rejects_disk_size_out_of_range(validator, size, fragment):
    body = _body()
    body['disk_size'] = size
    _reject(validator, body, 'disk_size', fragment)


def test_accepts_disk_size_at_the_minimum(validator):
    body = _body()
    body['disk_size'] = 122
    validator.validate(NestedImageCreateRequest(**body))


# Row 9: NIC networks exist; static IPs inside, unique, not parent_address, outside the DHCP range.
@pytest.mark.parametrize('nic, fragment', [
    ({'network': 'lan'}, 'network lan does not exist'),
    ({'network': 'corp', 'ip': '10.99.0.4'}, 'outside'),
    ({'network': 'corp', 'ip': '10.20.0.10'}, 'already used by guest dc01'),
    ({'network': 'corp', 'ip': '10.20.0.1'}, 'parent_address'),
    ({'network': 'corp', 'ip': '10.20.0.150'}, 'inside the DHCP range'),
    ({'network': 'dmz', 'ip': '172.16.5.15'}, 'network or broadcast'),
])
def test_rejects_bad_guest_nic(validator, nic, fragment):
    body = _body()
    _guest(body, 'ws01')['nics'] = [nic]
    _reject(validator, body, 'Guest ws01', fragment)


# Row 10: exposed NICs need a static IP; at most NESTED_MAX_EXPOSURES.
def test_rejects_exposed_nic_without_static_ip(validator):
    body = _body()
    _guest(body, 'ws01')['nics'] = [{'network': 'corp', 'expose': True}]
    _reject(validator, body, 'Guest ws01', 'static ip')


def test_rejects_more_than_eight_exposures(validator):
    body = _body()
    _guest(body, 'router')['nics'] = [{'network': 'corp', 'ip': f'10.20.0.{20 + i}', 'expose': True} for i in range(4)]
    _guest(body, 'ws01')['nics'] = [{'network': 'corp', 'ip': f'10.20.0.{30 + i}', 'expose': True} for i in range(4)]
    _reject(validator, body, 'Guest ws01', 'at most 8')


# Row 11: a non-evaluation unattended Windows entry needs a well-formed product key.
@pytest.mark.parametrize('keys', [{}, {'ws01': 'abcde-fghij-klmno-pqrst-uvwxy'}, {'ws01': 'ABCDE-FGHIJ'}])
def test_rejects_missing_or_malformed_product_key(validator, keys):
    body = _body()
    body['product_keys'] = keys
    _reject(validator, body, 'Guest ws01', 'product key')


def test_rejects_product_key_for_unknown_guest(validator):
    body = _body()
    body['product_keys']['ghost'] = PRODUCT_KEY
    _reject(validator, body, 'Guest ghost', 'does not exist')


def test_evaluation_entry_needs_no_product_key(validator):
    body = _body()
    assert 'dc01' not in body['product_keys']
    validator.validate(NestedImageCreateRequest(**body))


# Row 12: packages only for Linux cloud images, each a valid package name.
def test_rejects_packages_on_windows_guest(validator):
    body = _body()
    _guest(body, 'dc01')['packages'] = ['nmap']
    _reject(validator, body, 'Guest dc01', 'packages')


def test_rejects_bad_package_name(validator):
    body = _body()
    _guest(body, 'router')['packages'] = ['nmap; rm -rf /']
    _reject(validator, body, 'Guest router', 'package name')


# Row 13: Windows complexity for Windows guests, eight characters otherwise.
@pytest.mark.parametrize('guest, password', [('dc01', 'password1'), ('dc01', 'Pa1!'), ('router', 'short')])
def test_rejects_weak_admin_password(validator, guest, password):
    body = _body()
    _guest(body, guest)['admin_password'] = password
    _reject(validator, body, f'Guest {guest}', 'admin_password')


def test_linux_password_needs_no_complexity(validator):
    body = _body()
    _guest(body, 'router')['admin_password'] = 'alllowercase'
    validator.validate(NestedImageCreateRequest(**body))


# derive
def test_derive_fills_slots_ports_and_passwords_in_guest_order():
    spec = NestedImageCreateRequest(**_body()).nested
    derived = NestedHostValidator.derive(spec)

    assert derived.exposures == [('router', 0), ('dc01', 0)]
    assert derived.console_ports == {'router': 5901, 'dc01': 5902, 'ws01': 5903}
    assert set(derived.vnc_passwords) == {'router', 'dc01', 'ws01'}
    assert all(len(p) == 8 and p.isalnum() for p in derived.vnc_passwords.values())
    # The input spec is untouched, so a request can be derived again.
    assert spec.exposures == [] and spec.console_ports == {} and spec.vnc_passwords == {}


def test_derive_is_deterministic_except_for_passwords():
    spec = NestedImageCreateRequest(**_body()).nested
    first, second = NestedHostValidator.derive(spec), NestedHostValidator.derive(spec)

    assert first.exposures == second.exposures
    assert first.console_ports == second.console_ports
    assert first.model_dump(exclude={'vnc_passwords'}) == second.model_dump(exclude={'vnc_passwords'})


def test_derive_skips_guests_without_a_console():
    body = _body()
    _guest(body, 'router')['console'] = False
    derived = NestedHostValidator.derive(NestedImageCreateRequest(**body).nested)

    assert derived.console_ports == {'dc01': 5901, 'ws01': 5902}
    assert set(derived.vnc_passwords) == {'dc01', 'ws01'}
