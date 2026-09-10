"""Keep template boot sources valid until a custom image has been checked in."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from common.constants.database import DbCollections
from common.constants.states import ImageStatus, ServerStates
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI


PUBLIC_SOURCE = (
    'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/'
    'ubuntu-2404-noble-amd64-v20260901'
)
CUSTOM_SOURCE = ComputeImageAPI.self_link('image-wireguard-server', 'test-dev-787001')


@pytest.fixture
def template():
    manager = object.__new__(ImageTemplateManager)
    manager.server_name = 'wireguard-server'
    manager.image_name = 'image-wireguard-server'
    manager.user = 'instructor@example.edu'
    manager.collection = DbCollections.IMAGE
    manager.log_name = LoggerNames.CLOUD_FN
    manager.env = SimpleNamespace(project='test-dev-787001')
    manager.compute_image = Mock()
    manager.compute_image.self_link.side_effect = ComputeImageAPI.self_link
    manager._dns_record = Mock(return_value='wireguard-server.agoge-labs.com.')
    record = {
        'name': manager.server_name,
        'machine_type': 'e2-standard-2',
        'description': 'WireGuard template server',
        'tags': [],
        'image': PUBLIC_SOURCE,
        'os': 'linux',
        'add_disk': '20',
        'human_interaction': [],
        'status': ImageStatus.CHECKED_OUT.value,
        'state': ServerStates.RUNNING.value,
        'self_link': PUBLIC_SOURCE,
        'image_exists': False,
        'base_family': 'ubuntu-2404-lts-amd64',
    }
    manager.db = Mock()
    manager.db.get.side_effect = lambda **kwargs: deepcopy(record)

    def update(collection_name, doc_id, data):
        assert collection_name == DbCollections.IMAGE
        assert doc_id == manager.server_name
        record.update(deepcopy(data))

    manager.db.update.side_effect = update
    return manager, record


@pytest.mark.parametrize('checkouts', [1, 2], ids=['first-checkout', 'repeated-checkout'])
def test_checkout_preserves_public_source_until_first_check_in(template, checkouts):
    manager, record = template

    for _ in range(checkouts):
        manager._update_record_status(ImageStatus.CHECKED_OUT)

    assert record['self_link'] == PUBLIC_SOURCE
    assert record['image_exists'] is False
    assert record['image'] == manager.image_name
    assert record['status'] == ImageStatus.CHECKED_OUT.value
    assert record['in_use_by'] == manager.user
    manager.compute_image.self_link.assert_not_called()


def test_checkout_preserves_existing_custom_source(template):
    manager, record = template
    shared_source = ComputeImageAPI.self_link('image-wireguard-server', 'agoge-shared-resources')
    record.update(self_link=shared_source, image_exists=True, status=ImageStatus.CHECKED_IN.value)

    manager._update_record_status(ImageStatus.CHECKED_OUT)

    assert record['self_link'] == shared_source
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_OUT.value


def test_check_in_switches_to_the_created_custom_image(template):
    manager, record = template
    manager._update_record_status(ImageStatus.CHECKED_OUT)

    manager._update_record_status(ImageStatus.CHECKED_IN)

    assert record['self_link'] == CUSTOM_SOURCE
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_IN.value
    assert record['state'] == ServerStates.START.value
    assert record['in_use_by'] is None
    assert record['dns_record'] is None

    manager._update_record_status(ImageStatus.CHECKED_OUT)

    assert record['self_link'] == CUSTOM_SOURCE
    assert record['image_exists'] is True
