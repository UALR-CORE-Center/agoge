"""Image selection regressions using local records, without GCP clients."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from api.core.compute.image import ComputeImage
from common.constants.database import DbCollections, DbOperators
from common.constants.enumerators import ImageScopes
from common.exceptions import BadRequest, NotFound
from common.models.agoge import AgogeImageModel
from common.models.google import ComputeImageModel
from common.models.model_validators.model_validator import ModelValidator


PUBLIC_IMAGE = {
    'uuid': 'ubuntu-image-id',
    'global_id': 123456,
    'name': 'Ubuntu 2404 Lts Amd64',
    'self_link': 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-test',
    'disk_size': 10,
    'os': 'linux',
    'family': 'ubuntu-2404-lts-amd64',
    'is_enabled': True,
    'creationTimestamp': '2026-09-09T00:00:00Z',
    'project': 'ubuntu-os-cloud',
    'description': 'Ubuntu base image',
}

CUSTOM_IMAGE = {
    'name': 'wireguard-server',
    'machine_type': 'e2-medium',
    'description': 'Shared WireGuard gateway',
    'tags': ['wireguard-gateway'],
    'image': 'image-wireguard-server',
    'os': 'linux',
    'add_disk': '20',
    'human_interaction': [],
    'status': 0,
    'self_link': 'https://www.googleapis.com/compute/v1/projects/tenant-project/global/images/image-wireguard-server',
    'base_family': 'ubuntu-2404-lts-amd64',
}


@pytest.fixture
def catalog():
    service = object.__new__(ComputeImage)
    service.collection = DbCollections.IMAGE
    service.db = Mock()
    service.logger = Mock()
    service.compute_model_validator = ModelValidator(ComputeImageModel)
    service.agoge_model_validator = ModelValidator(AgogeImageModel)
    records = {
        DbCollections.GOOGLE_IMAGES: [deepcopy(PUBLIC_IMAGE)],
        DbCollections.IMAGE: [deepcopy(CUSTOM_IMAGE)],
    }

    def query(collection_name, filters=None):
        images = records[collection_name]
        if filters:
            field, operator, value = filters[0]
            assert operator == DbOperators.EQUAL
            return [image for image in images or [] if image[field] == value]
        return images

    service.db.query.side_effect = query
    return service, records


@pytest.mark.parametrize('available', ['public', 'custom', 'both', 'neither'])
@pytest.mark.parametrize('empty', [[], None], ids=['empty-list', 'missing-collection'])
def test_each_image_catalog_remains_available_independently(catalog, available, empty):
    service, records = catalog
    if available not in ('public', 'both'):
        records[DbCollections.GOOGLE_IMAGES] = empty
    if available not in ('custom', 'both'):
        records[DbCollections.IMAGE] = empty

    result = service.list_project_images()

    assert [image.uuid for image in result['project']] == (
        [PUBLIC_IMAGE['uuid']] if available in ('public', 'both') else []
    )
    assert [image.name for image in result['custom']] == (
        [CUSTOM_IMAGE['name']] if available in ('custom', 'both') else []
    )


def test_first_custom_server_can_resolve_a_listed_public_image(catalog):
    service, records = catalog
    records[DbCollections.IMAGE] = []

    selected = service.list_project_images()['project'][0]
    source, family = service._get_image(ImageScopes.GLOBAL.value, selected.uuid)

    assert source == PUBLIC_IMAGE['self_link']
    assert family == PUBLIC_IMAGE['family']
    assert selected.disk_size == 10
    assert selected.os == 'linux'


def test_listing_keeps_disabled_images_disabled_and_creation_rejects_them(catalog):
    service, records = catalog
    records[DbCollections.IMAGE] = []
    records[DbCollections.GOOGLE_IMAGES][0]['is_enabled'] = False

    selected = service.list_project_images()['project'][0]

    assert selected.is_enabled is False
    with pytest.raises(BadRequest, match='not enabled'):
        service._get_image(ImageScopes.GLOBAL.value, selected.uuid)


def test_global_scope_still_returns_public_images_only(catalog):
    service, _ = catalog
    assert [image.uuid for image in service.list_project_images(ImageScopes.GLOBAL)] == [PUBLIC_IMAGE['uuid']]


def test_empty_global_scope_retains_existing_not_found_response(catalog):
    service, records = catalog
    records[DbCollections.GOOGLE_IMAGES] = []
    with pytest.raises(NotFound, match='No image data found'):
        service.list_project_images(ImageScopes.GLOBAL)


@pytest.mark.parametrize('scope', [ImageScopes.GLOBAL, ImageScopes.PROJECT])
@pytest.mark.parametrize('source', [None, '', '  \n '])
def test_invalid_catalog_source_stops_before_build_is_queued(catalog, scope, source):
    service, records = catalog
    public = scope == ImageScopes.GLOBAL
    collection = DbCollections.GOOGLE_IMAGES if public else DbCollections.IMAGE
    record = records[collection][0]
    record['self_link'] = source
    service.db.get.return_value = record

    with pytest.raises(BadRequest, match='no source image URL'):
        service._create_database_object({
            'server_name': 'wireguard-server', 'machine_type': 'e2-standard-2',
            'description': 'WireGuard router', 'disk_size': '20',
            'image_template': record['uuid'] if public else record['name'],
            'image_scope': scope.value, 'os': 'linux', 'username': 'wgadmin',
            'ssh_key': 'ssh-ed25519 test-key wgadmin',
        })

    service.db.update.assert_not_called()


def test_creation_keeps_selected_public_source_in_saved_template(catalog):
    service, records = catalog
    service._create_database_object({
        'server_name': 'wireguard-server', 'machine_type': 'e2-standard-2',
        'description': 'WireGuard router', 'disk_size': '20',
        'image_template': PUBLIC_IMAGE['uuid'], 'image_scope': ImageScopes.GLOBAL.value,
        'os': 'linux', 'username': 'wgadmin', 'ssh_key': 'ssh-ed25519 test-key wgadmin',
        'password': 'test-password',
    })
    record = service.db.update.call_args.kwargs['data']
    assert record['self_link'] == PUBLIC_IMAGE['self_link']
    assert record['base_family'] == PUBLIC_IMAGE['family']
    assert record['add_disk'] == '20'
