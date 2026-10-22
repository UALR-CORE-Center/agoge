from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.operations.images_and_specs import wireguard_lab_template as module
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu
from common.constants.database import DATABASE_NAME, DbCollections
from common.exceptions import Conflict
from common.models.agoge import CatalogModel
from common.tests.test_wireguard_endpoint_registry import _FakeDatabase


@pytest.fixture
def upload(monkeypatch):
    db = _FakeDatabase()
    db.collections['catalog'] = {}
    db.collections['image'] = {'kali-template': {
        'name': 'kali-template', 'image': 'image-kali-linux-2023', 'status': 0,
        'image_exists': True,
        'self_link': 'https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-kali-linux-2023',
        'human_interaction': [{'display': True, 'protocol': 'rdp', 'username': 'student', 'password': 'private-fixture-password'}],
    }}
    env_data = {'project': 'test-dev-787001', 'admin_email': 'teacher@example.edu',
                'region': 'us-central1', 'zone': 'us-central1-a', 'wireguard_port': 51821}
    env = SimpleNamespace(project=env_data['project'], get_env=lambda: env_data)
    environment = Mock(return_value=env)
    database = Mock(return_value=db)
    compute = Mock()
    compute.return_value.get.return_value = SimpleNamespace(
        status='READY', architecture='X86_64',
        self_link=db.collections['image']['kali-template']['self_link'])
    monkeypatch.setattr(module, 'CloudEnv', environment)
    monkeypatch.setattr(module.DocumentDatabaseFactory, 'create_db_object', database)
    monkeypatch.setattr(module, 'ComputeImageAPI', compute)
    monkeypatch.setattr('builtins.input', lambda prompt: '')
    return SimpleNamespace(operation=module.WireGuardLabTemplate(env.project), db=db,
                           environment=environment, database=database, compute=compute, env=env,
                           env_data=env_data)


def test_upload_targets_selected_named_database_and_visible_catalog(upload, capsys):
    assert upload.operation.run()
    upload.environment.assert_called_once_with(project='test-dev-787001')
    assert upload.database.call_args.kwargs['project_id'] == 'test-dev-787001'
    assert upload.database.call_args.kwargs['database_name'] == DATABASE_NAME == 'agoge-v1'
    record = upload.db.collections['catalog']['wireguard-factory-lab']
    catalog = CatalogModel.model_validate(record)
    assert catalog.unit_type == 'community' and catalog.build_type == 'unit'
    assert catalog.instructor_id == ['teacher@example.edu']
    assert catalog.servers[0].wireguard_gateway and catalog.servers[0].community_server
    assert catalog.servers[0].image.startswith('projects/ubuntu-os-cloud/')
    assert catalog.servers[1].image == upload.compute.return_value.get.return_value.self_link
    assert any('udp/51821' in (rule.ports or []) for rule in catalog.firewall_rules)
    assert not {'wireguard_lease', 'wireguard_endpoint', 'workspace_settings'} & record.keys()
    assert upload.db.records == {} and upload.db.claims == {}
    upload.compute.return_value.get.assert_called_once_with(
        resource='image-kali-linux-2023', project='shared-images', fallback_to_shared=False)
    output = capsys.readouterr().out
    assert 'private-fixture-password' not in output
    assert 'test-dev-787001/agoge-v1/catalog/wireguard-factory-lab' in output
    assert 'Teachers → New Lab' in output


def test_identical_upload_is_idempotent(upload, capsys):
    assert upload.operation.run()
    before = deepcopy(upload.db.collections['catalog'])
    assert upload.operation.run()
    assert upload.db.collections['catalog'] == before
    assert 'Already current' in capsys.readouterr().out


def test_different_existing_catalog_is_preserved(upload, capsys):
    existing = {'id': 'wireguard-factory-lab', 'summary': {'name': 'Instructor edited template'}}
    upload.db.collections['catalog']['wireguard-factory-lab'] = deepcopy(existing)
    assert not upload.operation.run()
    assert upload.db.collections['catalog']['wireguard-factory-lab'] == existing
    assert 'another catalog document ID' in capsys.readouterr().out


def test_mismatched_environment_stops_before_target_database(upload):
    upload.env.project = 'wrong-project'
    assert not upload.operation.run()
    upload.database.assert_not_called()
    upload.compute.assert_not_called()


@pytest.mark.parametrize('change', [{'status': 1}, {'image_exists': False},
    {'human_interaction': []}, {'human_interaction': [
        {'display': True, 'protocol': 'ssh', 'username': 'student', 'ssh_key': 'not-a-password'}]}])
def test_unusable_student_record_does_not_write_catalog(upload, change):
    upload.db.collections['image']['kali-template'].update(change)
    assert not upload.operation.run()
    assert upload.db.collections['catalog'] == {}


@pytest.mark.parametrize('field,value', [('status', 'PENDING'), ('architecture', 'ARM64')])
def test_cloud_image_validation_fails_before_catalog_write(upload, field, value):
    setattr(upload.compute.return_value.get.return_value, field, value)
    assert not upload.operation.run()
    assert upload.db.collections['catalog'] == {}


def test_operator_can_choose_image_instructor_and_catalog_id(upload, monkeypatch):
    responses = iter(['kali-template', 'another@example.edu', 'another-wireguard-lab'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(responses))
    assert upload.operation.run()
    record = upload.db.collections['catalog']['another-wireguard-lab']
    assert record['instructor_id'] == ['another@example.edu']


@pytest.mark.parametrize('responses', [
    ['not-registered'], ['kali-template', 'bad-email'],
    ['kali-template', 'teacher@example.edu', '../wrong-project'],
])
def test_invalid_input_fails_without_writing_catalog(upload, monkeypatch, responses):
    values = iter(responses)
    monkeypatch.setattr('builtins.input', lambda prompt: next(values))
    assert not upload.operation.run()
    assert upload.db.collections['catalog'] == {}


def test_cloud_exception_bodies_are_not_logged(upload, capsys):
    upload.compute.return_value.get.side_effect = RuntimeError('private-fixture-password')
    assert not upload.operation.run()
    assert 'private-fixture-password' not in capsys.readouterr().out


def test_new_menu_operation_is_project_scoped_and_needs_no_deployment(monkeypatch):
    uploader, app = Mock(), Mock()
    monkeypatch.setattr(setup_manager_module, 'WireGuardLabTemplate', uploader)
    monkeypatch.setattr(setup_manager_module, 'AgogeApp', app)
    setup_manager_module.SetupManager(SetupOptions.WIREGUARD_LAB_TEMPLATE, 'test-dev-787001').run()
    uploader.assert_called_once_with(project='test-dev-787001')
    uploader.return_value.run.assert_called_once_with()
    app.assert_not_called()
    assert SetupOptions.WIREGUARD_LAB_TEMPLATE in [item for item, _ in
        category_menu[SetupCategories.IMAGES_AND_SPECS]['options']]
