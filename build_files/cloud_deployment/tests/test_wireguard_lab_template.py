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


@pytest.mark.parametrize('change', [{'status': 1},
    {'human_interaction': []}, {'human_interaction': [
        {'display': True, 'protocol': 'ssh', 'username': 'student', 'ssh_key': 'not-a-password'}]}])
def test_unusable_student_record_does_not_write_catalog(upload, change):
    upload.db.collections['image']['kali-template'].update(change)
    assert not upload.operation.run()
    assert upload.db.collections['catalog'] == {}


@pytest.mark.parametrize('single_connection', [False, True])
def test_legacy_shared_windows_image_uses_its_real_source_and_normalizes_rdp(upload, monkeypatch, capsys, single_connection):
    record = upload.db.collections['image'].pop('kali-template')
    record.update(name='cybersecurity1', image='image-cybersecurity1', status='0', image_exists=False,
        self_link='https://www.googleapis.com/compute/v1/projects/agoge-shared-resources/global/images/image-cybersecurity1')
    record['human_interaction'][0]['protocol'] = 'RDP'
    if single_connection:
        record['human_interaction'] = record['human_interaction'][0]
    upload.db.collections['image']['cybersecurity1'] = record
    upload.compute.return_value.get.return_value.self_link = record['self_link']
    responses = iter(['cybersecurity1', '', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(responses))
    assert upload.operation.run()
    student = upload.db.collections['catalog']['wireguard-factory-lab']['servers'][1]
    assert student['image'] == record['self_link']
    assert student['human_interaction'][0]['protocol'] == 'rdp'
    upload.compute.return_value.get.assert_called_once_with(
        resource='image-cybersecurity1', project='agoge-shared-resources', fallback_to_shared=False)
    output = capsys.readouterr().out
    assert '"cybersecurity1": eligible' in output
    assert 'private-fixture-password' not in output


@pytest.mark.parametrize('change,reason', [
    ({'name': None}, 'missing name field'),
    ({'status': 1}, 'status is not checked in'),
    ({'image_exists': False, 'self_link': '', 'disks': []}, 'image_exists is false'),
    ({'human_interaction': []}, 'human_interaction has no saved connection'),
    ({'human_interaction': [{'display': False, 'protocol': 'rdp', 'username': 'private-user',
                            'password': 'private-password'}]}, 'display is not enabled'),
    ({'human_interaction': [{'display': True, 'protocol': 'rdp', 'username': 'private-user'}]}, 'missing password'),
    ({'human_interaction': [{'display': True, 'protocol': 'private-invalid-protocol', 'username': 'private-user',
                            'password': 'private-password'}]}, 'protocol must be SSH, RDP, or VNC'),
])
def test_rejections_identify_missing_fields_without_printing_credentials(upload, capsys, change, reason):
    upload.db.collections['image']['kali-template'].update(change)
    assert not upload.operation.run()
    output = capsys.readouterr().out
    assert reason in output
    for secret in ('private-user', 'private-password', 'private-fixture-password', 'private-invalid-protocol'):
        assert secret not in output
    assert upload.db.collections['catalog'] == {}
    upload.compute.assert_not_called()


def test_shared_reference_does_not_turn_an_unbuilt_local_template_into_a_published_image(upload, capsys):
    record = upload.db.collections['image']['kali-template']
    record.update(image_exists=False, image='image-new-workstation',
        self_link='https://www.googleapis.com/compute/v1/projects/shared-images/global/images/windows-base')
    assert not upload.operation.run()
    assert 'image_exists is false' in capsys.readouterr().out


def test_valid_windows_profile_still_checks_real_compute_architecture(upload):
    record = upload.db.collections['image']['kali-template']
    record.update(image_exists=False)
    record['human_interaction'][0]['protocol'] = 'RDP'
    upload.compute.return_value.get.return_value.architecture = 'ARM64'
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
