"""stop_everything syncs checked-out images to STOPPED in exactly one batch write."""
from types import SimpleNamespace
from unittest.mock import Mock

from cloud_fn_utilities.course_objects.compute.project_server_manager import ProjectServerManager
from common.constants.database import DbCollections, DbOperationTypes
from common.constants.states import ImageStatus, ServerStates
from common.models.model_validators.model_validator import ModelValidator


class FakeDb:
    def __init__(self, images):
        self.images = images
        self.batches = []

    def query(self, collection_name, filters=None, limit=None):
        return [dict(image) for image in self.images]

    def operation(self, collection_name, doc_id, operation_type, data=None):
        return (collection_name, doc_id, operation_type, data)

    def batch_write(self, operations):
        # Copy so a later append to the same list can't rewrite what was recorded
        self.batches.append(list(operations))


def _image(name, **overrides):
    image = {
        'name': name,
        'machine_type': 'e2-medium',
        'description': 'image',
        'tags': [],
        'image': name,
        'os': 'linux',
        'add_disk': '',
        'human_interaction': [{'protocol': 'ssh'}],
        'status': ImageStatus.CHECKED_OUT.value,
        'state': ServerStates.RUNNING.value,
    }
    image.update(overrides)
    return image


def _manager(images):
    manager = object.__new__(ProjectServerManager)
    manager.class_name = 'ProjectServerManager'
    manager.log_name = 'test'
    manager.logger = Mock()
    manager.env = SimpleNamespace(project='proj', zone='zone')
    manager.compute_instance = Mock()
    manager.compute_instance.list.return_value = []
    manager.db = FakeDb(images)
    manager.collection = DbCollections
    manager.validate = ModelValidator
    return manager


def test_three_images_are_written_in_one_batch():
    manager = _manager([_image('img-a'), _image('img-b'), _image('img-c')])

    manager.stop_everything()

    assert len(manager.db.batches) == 1
    assert manager.db.batches[0] == [
        (DbCollections.IMAGE, name, DbOperationTypes.UPDATE, {'state': ServerStates.STOPPED.value})
        for name in ('img-a', 'img-b', 'img-c')
    ]


def test_no_checked_out_images_writes_nothing():
    manager = _manager([])

    manager.stop_everything()

    assert manager.db.batches == []
