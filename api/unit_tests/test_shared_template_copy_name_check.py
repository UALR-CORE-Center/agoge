"""Copying a shared template refuses a name already used by a local image, or by a VM or disk in ANY zone of the region
(a template server may sit outside the deployment zone after a zone fallback)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from common.exceptions import Conflict, NotFound, OperationTimeout
from core.compute import image as image_module
from core.compute.image import ComputeImage

PROJECT = 'test-dev-787001'
SHARED_PROJECT = 'ualr-cybersecurity'
SHARED_LINK = f'projects/{SHARED_PROJECT}/global/images/image-kali'
LOCAL_LINK = f'projects/{PROJECT}/global/images/image-mine'


def _copier(monkeypatch, local_image_exists=False, instance_zones=(), disk_zones=()):
    image = object.__new__(ComputeImage)
    image.collection = image_module.DbCollections.IMAGE
    image.log_name = 'api'
    image.logger = MagicMock()
    image.env = SimpleNamespace(project=PROJECT, region='us-central1', zone='us-central1-a')
    image.db = MagicMock()
    image.db.get.side_effect = lambda collection_name, doc_id: (
        {'name': 'kali', 'self_link': SHARED_LINK, 'image': 'image-kali', 'image_exists': True,
         'machine_type': 'e2-medium', 'description': 'Kali', 'tags': [], 'os': 'linux', 'add_disk': 'false',
         'human_interaction': [], 'status': 1}
        if doc_id == 'kali' else None
    )

    image_api = MagicMock()
    source = SimpleNamespace(status='READY', self_link=f'https://www.googleapis.com/compute/v1/{SHARED_LINK}',
                             architecture='X86_64')
    local = SimpleNamespace(status='READY', self_link=LOCAL_LINK)

    def get(resource, project, fallback_to_shared):
        if resource == 'image-kali':
            return source
        if local_image_exists:
            return local
        raise NotFound('no local image')

    image_api.get.side_effect = get
    instance_api, disk_api = MagicMock(), MagicMock()
    instance_api.zones_with_instance.return_value = list(instance_zones)
    disk_api.zones_with_disk.return_value = list(disk_zones)
    image_class = MagicMock(return_value=image_api)
    image_class.self_link = lambda name, project: f'projects/{project}/global/images/{name}'
    monkeypatch.setattr(image_module, 'ComputeImageAPI', image_class)
    monkeypatch.setattr(image_module, 'ComputeInstanceAPI', MagicMock(return_value=instance_api))
    monkeypatch.setattr(image_module, 'ComputeDiskAPI', MagicMock(return_value=disk_api))
    return image, image_api, instance_api, disk_api


@pytest.mark.parametrize('kwargs', [
    {'instance_zones': ['us-central1-b']},
    {'disk_zones': ['us-central1-c']},
    {'instance_zones': ['us-central1-a'], 'disk_zones': ['us-central1-f']},
    {'local_image_exists': True},
])
def test_copy_name_in_use_anywhere_in_the_region_is_a_conflict(monkeypatch, kwargs):
    image, image_api, _, _ = _copier(monkeypatch, **kwargs)

    with pytest.raises(Conflict, match='already uses mine'):
        image.copy_shared_image('kali', 'mine')

    image_api.create.assert_not_called()
    image.db.db.collection.assert_not_called()


def test_copy_name_check_looks_up_the_server_and_its_disk_by_name(monkeypatch):
    image, image_api, instance_api, disk_api = _copier(monkeypatch)
    image_api.create.return_value = False  # stop after the name checks; the copy itself is out of scope

    with pytest.raises(OperationTimeout):
        image.copy_shared_image('kali', 'mine')

    instance_api.zones_with_instance.assert_called_once_with('mine')
    disk_api.zones_with_disk.assert_called_once_with('mine-disk')
    image_api.create.assert_called_once()


def test_copy_with_a_free_name_reaches_the_image_copy(monkeypatch):
    image, image_api, _, _ = _copier(monkeypatch)
    image_api.create.return_value = False

    with pytest.raises(OperationTimeout):
        image.copy_shared_image('kali', 'mine')

    image_api.create.assert_called_once()
