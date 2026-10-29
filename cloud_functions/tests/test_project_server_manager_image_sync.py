"""stop_everything syncs checked-out images to STOPPED in exactly one batch write."""
from types import SimpleNamespace
from unittest.mock import Mock

from cloud_fn_utilities.course_objects.compute.project_server_manager import ProjectServerManager
from common.constants.database import DbCollections, DbOperationTypes
from common.constants.states import ImageStatus, ServerStates
from common.exceptions import NotFound
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


def test_template_servers_outside_the_deployment_zone_are_stopped_in_their_own_zone():
    # A zone fallback leaves the VM out of the deployment-zone instance list, so the sweep stops it by record.
    manager = _manager([
        _image('fallback', zone='zone-b'),
        _image('home', zone='zone'),
        _image('legacy'),
        _image('exempt', zone='zone-c'),
        _image('ctf-host', zone='zone-c'),
    ])

    manager.stop_everything(exempt_prefixes=('ctf-',), exempt_names=('exempt',))

    manager.compute_instance.stop.assert_called_once_with(resource_name='fallback', zone='zone-b', wait=False)


def test_a_failed_stop_in_another_zone_does_not_block_the_state_sync():
    manager = _manager([_image('fallback', zone='zone-b')])
    manager.compute_instance.stop.side_effect = NotFound('gone')

    manager.stop_everything()

    manager.logger.warning.assert_called_once()
    assert len(manager.db.batches) == 1
