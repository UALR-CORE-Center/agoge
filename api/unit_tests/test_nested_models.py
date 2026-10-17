import pytest
from pydantic import ValidationError

from common.constants import nested as nested_constants
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.models.agoge import (
    AgogeImageModel,
    HumanInteractionModel,
    NestedBuildStatusModel,
    NestedGuestModel,
    NestedHostSpecModel,
    NestedImageCreateRequest,
    NestedMediaModel,
    NestedOsCatalogModel,
)


def _catalog(**overrides):
    entry = {
        'id': 'win-server-2022-eval',
        'display_name': 'Windows Server 2022 Evaluation',
        'family': 'windows',
        'group': 'windows_server',
        'version': '2022',
        'install_method': 'unattended_iso',
        'media_url': 'https://go.microsoft.com/fwlink/p/?LinkID=2195280',
        'media_sha256': 'a' * 64,
        'media_formats': ['iso'],
        'license_note': '180-day evaluation.',
        'eval_days': 180,
        'osinfo': 'win2k22',
        'agent': True,
        'net_config': 'windows',
        'min_memory_mb': 2048,
        'default_memory_mb': 4096,
        'min_disk_gb': 32,
        'default_disk_gb': 40,
    }
    entry.update(overrides)
    return entry


def _guest(**overrides):
    guest = {
        'name': 'linux-guest',
        'os_id': 'debian-12',
        'nics': [{'network': 'lab', 'ip': '10.10.0.10', 'expose': True}],
        'admin_username': 'agoge',
        'admin_password': 'Passw0rd!',
    }
    guest.update(overrides)
    return guest


def _host(**overrides):
    host = {
        'networks': [{'name': 'lab', 'cidr': '10.10.0.0/24', 'mode': 'nat', 'parent_address': '10.10.0.1'}],
        'guests': [_guest()],
    }
    host.update(overrides)
    return host


def _image(**overrides):
    image = {
        'name': 'ubuntu',
        'machine_type': 'e2-medium',
        'description': 'Ubuntu',
        'tags': [],
        'image': 'image-ubuntu',
        'os': 'linux',
        'add_disk': '',
        'human_interaction': [{'protocol': 'ssh', 'username': 'agoge'}],
        'status': 1,
    }
    image.update(overrides)
    return image


def test_catalog_entry_validates():
    entry = NestedOsCatalogModel(**_catalog())
    assert entry.firmware == 'bios' and entry.disk_bus == 'virtio' and entry.is_enabled


@pytest.mark.parametrize('url', ['http://example.com/os.iso', 'ftp://example.com/os.iso', 'example.com/os.iso'])
def test_catalog_rejects_non_https_media_url(url):
    with pytest.raises(ValidationError, match='https'):
        NestedOsCatalogModel(**_catalog(media_url=url))


def test_catalog_rejects_unknown_install_method():
    with pytest.raises(ValidationError):
        NestedOsCatalogModel(**_catalog(install_method='pxe'))


def test_catalog_entry_without_url_must_require_upload():
    with pytest.raises(ValidationError, match='requires_upload'):
        NestedOsCatalogModel(**_catalog(media_url=None, media_sha256=None))
    entry = NestedOsCatalogModel(**_catalog(media_url=None, media_sha256=None, requires_upload=True))
    assert entry.requires_upload


def test_catalog_windows_entry_needs_license_note():
    with pytest.raises(ValidationError, match='license_note'):
        NestedOsCatalogModel(**_catalog(license_note='  '))


def test_catalog_rejects_bad_sha256():
    with pytest.raises(ValidationError):
        NestedOsCatalogModel(**_catalog(media_sha256='A' * 64))


@pytest.mark.parametrize('name', ['Linux', '1guest', 'guest-', 'g', 'a' * 16, 'web_01', 'web.01'])
def test_guest_rejects_bad_slug(name):
    with pytest.raises(ValidationError):
        NestedGuestModel(**_guest(name=name))


@pytest.mark.parametrize('name', ['ab', 'web-01', 'a' * 15])
def test_guest_accepts_good_slug(name):
    assert NestedGuestModel(**_guest(name=name)).name == name


def test_guest_defaults_and_nic_bounds():
    guest = NestedGuestModel(**_guest())
    assert (guest.vcpus, guest.memory_mb, guest.disk_gb, guest.console, guest.autostart) == (1, 2048, 20, True, True)
    with pytest.raises(ValidationError):
        NestedGuestModel(**_guest(nics=[]))
    with pytest.raises(ValidationError):
        NestedGuestModel(**_guest(nics=[{'network': 'lab'}] * 5))


def test_host_spec_limits_networks_and_guests():
    NestedHostSpecModel(**_host())
    with pytest.raises(ValidationError):
        NestedHostSpecModel(**_host(guests=[_guest(name=f'g{i}x') for i in range(9)]))
    with pytest.raises(ValidationError):
        NestedHostSpecModel(**_host(networks=[{'name': 'Bad', 'cidr': '10.0.0.0/24', 'mode': 'nat'}]))


def test_media_model_rejects_unknown_format():
    media = {'id': 'm1', 'filename': 'xp.iso', 'format': 'iso', 'size_bytes': 1, 'gcs_path': 'gs://p_nested-media/media/m1/xp.iso',
             'uploaded_by': 't@example.edu', 'uploaded_at': '2026-10-17T00:00:00Z'}
    assert NestedMediaModel(**media).complete is False
    with pytest.raises(ValidationError):
        NestedMediaModel(**{**media, 'format': 'exe'})


def test_build_status_defaults_and_rejects_unknown_guest_status():
    assert NestedBuildStatusModel().phase == 'queued'
    assert NestedBuildStatusModel(guests={'g1': 'manual'}).guests == {'g1': 'manual'}
    with pytest.raises(ValidationError):
        NestedBuildStatusModel(guests={'g1': 'booting'})
    with pytest.raises(ValidationError):
        NestedBuildStatusModel(message='x' * 201)


def _request(**overrides):
    body = {'server_name': 'nested-lab', 'description': 'lab', 'machine_type': 'n2-standard-8', 'username': 'agoge',
            'ssh_key': 'ssh-ed25519 AAAA', 'nested': _host()}
    body.update(overrides)
    return body


def test_create_request_forbids_unknown_fields():
    NestedImageCreateRequest(**_request())
    with pytest.raises(ValidationError):
        NestedImageCreateRequest(**_request(state=1))


@pytest.mark.parametrize('derived', [{'exposures': [['linux-guest', 0]]}, {'console_ports': {'linux-guest': 5901}},
                                     {'vnc_passwords': {'linux-guest': 'abcdefgh'}}])
def test_create_request_rejects_derived_fields(derived):
    with pytest.raises(ValidationError, match='derived'):
        NestedImageCreateRequest(**_request(nested=_host(**derived)))


def test_existing_image_without_nested_still_validates():
    image = AgogeImageModel(**_image())
    assert image.nested is None and image.nested_build is None


def test_base_family_defaults_to_none():
    # It was the tuple (None,) because of a trailing comma (Working Note 19).
    assert AgogeImageModel(**_image()).base_family is None


def test_image_carries_nested_spec_and_build_status():
    image = AgogeImageModel(**_image(nested=_host(), nested_build={'phase': 'building', 'guests': {'linux-guest': 'installing'}}))
    assert image.nested.guests[0].name == 'linux-guest'
    assert image.nested_build.phase == 'building'


def test_human_interaction_nested_fields_default_to_none():
    hi = HumanInteractionModel(protocol='vnc')
    assert (hi.nested_guest, hi.alias_index, hi.port) == (None, None, None)
    hi = HumanInteractionModel(protocol='vnc', nested_guest='linux-guest', alias_index=0, port=5901)
    assert (hi.nested_guest, hi.alias_index, hi.port) == ('linux-guest', 0, 5901)
    with pytest.raises(ValidationError):
        HumanInteractionModel(protocol='rdp', alias_index=-1)


def test_nested_finalize_collides_with_no_existing_action():
    # A duplicate Enum value becomes an alias of the earlier member, so the function would dispatch
    # NESTED_FINALIZE as some other action; equal lengths mean every value is unique.
    members = PubSub.Actions.__members__
    assert len(members) == len(list(PubSub.Actions))
    assert members['NESTED_FINALIZE'].name == 'NESTED_FINALIZE'


def test_nested_collections():
    assert DbCollections.NESTED_OS_CATALOG.value == 'nested-os-catalog'
    assert DbCollections.NESTED_MEDIA.value == 'nested-media'
    assert len(DbCollections.__members__) == len(list(DbCollections))


def test_nested_constants():
    c = nested_constants
    assert c.ENABLE_VMX_LICENSE.endswith('/projects/vm-options/global/licenses/enable-vmx')
    assert (c.NESTED_PARENT_OVERHEAD_MB, c.NESTED_PARENT_BASE_DISK_GB, c.NESTED_BUILD_SCRATCH_GB, c.NESTED_MAX_DISK_GB) == (2048, 20, 12, 1000)
    assert (c.NESTED_MAX_EXPOSURES, c.NESTED_CONSOLE_BASE_PORT, c.NESTED_MAX_MACHINE_MEMORY_MB) == (8, 5901, 65536)
    assert c.NESTED_FINALIZE_TIMEOUT_SECONDS < 540
    assert (c.NESTED_BUILD_STALL_MINUTES, c.NESTED_BUILD_MAX_MINUTES) == (45, 240)
    assert (c.NESTED_MEDIA_MAX_BYTES, c.NESTED_UPLOAD_URL_TTL_SECONDS) == (20 * 1024 ** 3, 3600)
    assert c.NESTED_MEDIA_BUCKET_SUFFIX == 'nested-media'
