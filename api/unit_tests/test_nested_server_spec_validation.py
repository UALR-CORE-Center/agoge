import copy
from unittest.mock import MagicMock, patch

import pytest

from common.constants.database import DbCollections
from common.exceptions import AgogeValidationError
from core.specifications.utilities.edit_manager import SpecEditManager
from core.specifications.utilities.file_manager import SpecFileManager
from utilities.infrastructure_as_code.object_validators import NestedServersValidator

EDIT = 'core.specifications.utilities.edit_manager'
FILE = 'core.specifications.utilities.file_manager'

NESTED_IMAGE = {'name': 'ad-lab-host', 'nested': {'exposures': [['dc01', 0], ['ws01', 0]]}}
PLAIN_IMAGE = {'name': 'kali'}

SERVER = {
    'name': 'ad-lab',
    'image': 'image-ad-lab-host',
    'machine_type': 'n2-standard-8',
    'nics': [{'network': 'lab', 'internal_ip': '10.1.1.10', 'ip_aliases': ['10.1.1.20', '10.1.1.21']}],
    'human_interaction': [
        {'display': True, 'protocol': 'rdp', 'username': 'admin', 'password': 'pw', 'alias_index': 1},
        {'display': True, 'protocol': 'vnc', 'password': 'vncpass', 'port': 5902},
    ],
}

SPEC = {
    'build_type': 'unit',
    'instructor_id': ['instructor@example.com'],
    'summary': {'name': 'Nested lab', 'author': 'Instructor', 'description': 'An AD lab on one nested host.'},
    'servers': [SERVER],
}


def _bad_machine_type(spec):
    spec['servers'][0]['machine_type'] = 'e2-standard-8'


def _too_few_aliases(spec):
    spec['servers'][0]['nics'][0]['ip_aliases'] = ['10.1.1.20']
    spec['servers'][0]['human_interaction'][0]['alias_index'] = 0


def _alias_index_out_of_range(spec):
    spec['servers'][0]['human_interaction'][0]['alias_index'] = 2


BAD_CASES = [
    pytest.param(_bad_machine_type, 'needs an N1 or N2 machine type', id='e2-machine-type'),
    pytest.param(_too_few_aliases, 'needs at least 2 ip_aliases; it has 1', id='too-few-aliases'),
    pytest.param(_alias_index_out_of_range, 'alias_index 2', id='alias-index-out-of-range'),
]


def _images(doc_id):
    return {'ad-lab-host': NESTED_IMAGE, 'kali': PLAIN_IMAGE}.get(doc_id)


@pytest.fixture
def db():
    # LabSpecBase.__init__ builds CloudEnv, Firestore, and Pub/Sub clients; none may touch GCP here.
    with patch('core.specifications.utilities.lab_spec_base.CloudEnv') as cloud_env, \
            patch('core.specifications.utilities.lab_spec_base.DocumentDatabaseFactory') as db_factory, \
            patch('core.specifications.utilities.lab_spec_base.PubSubManager'), \
            patch('core.specifications.utilities.lab_spec_base.Logger'):
        cloud_env.return_value.get_env.return_value = {'wireguard_port': 51820}
        database = MagicMock()
        database.get.side_effect = lambda collection_name, doc_id: _images(doc_id)
        db_factory.create_db_object.return_value = database
        yield database


@pytest.fixture
def file_manager(db):
    # Network/server/firewall checks are UnitValidator's; stub it so the nested rules are what is under test.
    with patch(f'{FILE}.UnitValidator'), patch(f'{FILE}.UnitModel'):
        def make(spec):
            manager = SpecFileManager(env_dict={})
            manager.load(spec)
            return manager
        yield make


@pytest.fixture
def edit_manager(db):
    with patch(f'{EDIT}.NetworksValidator'), patch(f'{EDIT}.FirewallRulesValidator') as firewalls, \
            patch(f'{EDIT}.ServersValidator') as servers:
        servers.return_value.load.return_value = {}
        firewalls.return_value.load.return_value = {}

        def make(spec):
            manager = SpecEditManager(env_dict={})
            manager.spec = spec
            return manager
        yield make


@pytest.mark.parametrize('save_path', ['file_manager', 'edit_manager'])
def test_valid_nested_spec_passes_both_save_paths(request, db, save_path):
    manager = request.getfixturevalue(save_path)(copy.deepcopy(SPEC))

    assert manager.is_valid() == (True, 'Spec is valid')
    db.get.assert_called_with(collection_name=DbCollections.IMAGE, doc_id='ad-lab-host')


@pytest.mark.parametrize('save_path', ['file_manager', 'edit_manager'])
@pytest.mark.parametrize('mutate, message', BAD_CASES)
def test_bad_nested_spec_is_rejected_on_both_save_paths(request, save_path, mutate, message):
    spec = copy.deepcopy(SPEC)
    mutate(spec)
    manager = request.getfixturevalue(save_path)(spec)

    valid, error = manager.is_valid()

    assert valid is False
    assert message in error
    assert 'ad-lab' in error


def test_plain_image_server_needs_no_nested_machine_type_or_aliases():
    server = {'name': 'kali', 'image': 'image-kali', 'machine_type': 'e2-medium',
              'nics': [{'network': 'lab', 'internal_ip': '10.1.1.30'}]}

    NestedServersValidator({'servers': [server]}, image_loader=_images).load()


def test_alias_index_is_range_checked_on_a_plain_server_too():
    server = {'name': 'kali', 'image': 'image-kali', 'nics': [{'network': 'lab'}],
              'human_interaction': [{'protocol': 'ssh', 'alias_index': 0}]}

    with pytest.raises(AgogeValidationError, match='alias_index 0, but NIC 0 has 0 ip_aliases'):
        NestedServersValidator({'servers': [server]}, image_loader=_images).load()


def test_missing_and_public_images_are_not_looked_up_as_nested():
    loader = MagicMock(return_value=None)
    servers = [
        {'name': 'a', 'image': 'projects/debian-cloud/global/images/family/debian-12'},
        {'name': 'b'},
        {'name': 'c', 'image': 'image-gone', 'machine_type': 'e2-medium'},
        {'name': 'd', 'image': 'image-gone', 'machine_type': 'e2-medium'},
    ]

    NestedServersValidator({'servers': servers}, image_loader=loader).load()

    # One lookup for the two servers sharing an image; none for the public image or the image-less server
    loader.assert_called_once_with('gone')
