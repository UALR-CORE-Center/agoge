from unittest.mock import MagicMock, patch

import pytest

from core.specifications.utilities.edit_manager import SpecEditManager

PARENT_SSH = {'display': False, 'protocol': 'ssh', 'username': 'instructor', 'password': 'pw', 'ssh_key': 'ssh-rsa AAA'}
KALI_SSH = {'display': True, 'protocol': 'ssh', 'username': 'kali', 'password': 'kpw',
            'alias_index': 0, 'nested_guest': 'kali'}
IMAGE = {'name': 'nested-e2e', 'os': 'linux', 'human_interaction': [PARENT_SSH], 'machine_type': 'n2-standard-4'}


@pytest.fixture
def manager():
    # LabSpecBase.__init__ builds CloudEnv, Firestore, and Pub/Sub clients; none may touch GCP here.
    with patch('core.specifications.utilities.lab_spec_base.CloudEnv'), \
            patch('core.specifications.utilities.lab_spec_base.DocumentDatabaseFactory') as db_factory, \
            patch('core.specifications.utilities.lab_spec_base.PubSubManager'), \
            patch('core.specifications.utilities.lab_spec_base.Logger'):
        database = MagicMock()
        database.query.side_effect = lambda collection_name: [{**IMAGE, 'human_interaction': [dict(PARENT_SSH)]}]
        db_factory.create_db_object.return_value = database
        spec_manager = SpecEditManager(env_dict={})
        spec_manager.spec = {}
        yield spec_manager


def _server(human_interaction):
    return {
        'name': 'nestedhost', 'image': 'image-nested-e2e', 'machine_type': 'n2-standard-4',
        'nics': [{'network': 'external', 'internal_ip': '10.1.1.10', 'ip_aliases': '10.1.1.2',
                  'external_nat': True, 'direct_connect': True}],
        'human_interaction': human_interaction,
    }


def test_editor_guest_connections_survive_after_the_image_connections(manager):
    forged_parent = {**PARENT_SSH, 'display': True, 'username': 'root'}
    manager._parse_servers_form(form={'servers': [_server([forged_parent, KALI_SSH])]}, ignore=[])

    [server] = manager.spec['servers']
    parent = {key: value for key, value in PARENT_SSH.items() if key != 'ssh_key'}
    # The parent's connection is the image's, not the submitted one
    assert server['human_interaction'] == [parent, KALI_SSH]
    assert server['nics'][0]['ip_aliases'] == ['10.1.1.2']


def test_without_guest_connections_the_server_keeps_the_image_connections(manager):
    manager._parse_servers_form(form={'servers': [_server(None)]}, ignore=[])

    [server] = manager.spec['servers']
    assert [connection['username'] for connection in server['human_interaction']] == ['instructor']


def test_submitted_guest_connections_drop_ssh_keys(manager):
    manager._parse_servers_form(form={'servers': [_server([{**KALI_SSH, 'ssh_key': 'ssh-rsa BBB'}])]}, ignore=[])

    assert 'ssh_key' not in manager.spec['servers'][0]['human_interaction'][-1]
