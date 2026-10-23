from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import NotFound as GoogleNotFound
from google.cloud.compute_v1 import Image

from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.operations.images_and_specs import wireguard_lab_template as module
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu
from common.constants.database import DATABASE_NAME, DbCollections
from common.exceptions import Conflict, NotFound
from common.models.agoge import CatalogModel
from common.tests.test_wireguard_endpoint_registry import _FakeDatabase
from common.utilities.gcp.compute.compute_image import ComputeImageAPI as GCPImageAPI


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
        resource='image-kali-linux-2023', project='shared-images', fallback_to_shared=True)
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
        resource='image-cybersecurity1', project='agoge-shared-resources', fallback_to_shared=True)
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


@pytest.mark.parametrize('boot_disk_reference', [False, True])
def test_missing_explicit_image_reports_both_sources_after_shared_retry(upload, capsys, boot_disk_reference):
    record = upload.db.collections['image']['kali-template']
    record['self_link'] = 'projects/ualr-agoge/global/images/image-csec3314-powershell'
    if boot_disk_reference:
        record['disks'] = [{'boot': True, 'initializeParams': {'sourceImage': record.pop('self_link')}}]
    upload.compute.return_value.get.side_effect = NotFound('private-fixture-password')

    assert not upload.operation.run()

    upload.compute.return_value.get.assert_called_once_with(
        resource='image-csec3314-powershell', project='ualr-agoge', fallback_to_shared=True)
    output = capsys.readouterr().out
    assert 'projects/ualr-agoge/global/images/image-csec3314-powershell' in output
    assert 'gcloud compute images describe image-csec3314-powershell --project=ualr-agoge' in output
    assert 'projects/agoge-shared-resources/global/images/image-csec3314-powershell' in output
    assert 'gcloud compute images describe image-csec3314-powershell --project=agoge-shared-resources' in output
    assert 'Shared student images are used directly' in output
    assert 'Check setup credentials, selected-project Firestore' not in output
    assert 'private-fixture-password' not in output
    assert upload.db.collections['catalog'] == {}


def test_missing_unqualified_image_reports_both_projects_checked(upload, capsys):
    upload.db.collections['image']['kali-template'].pop('self_link')
    upload.compute.return_value.get.side_effect = NotFound('private-fixture-password')

    assert not upload.operation.run()

    upload.compute.return_value.get.assert_called_once_with(
        resource='image-kali-linux-2023', project='test-dev-787001', fallback_to_shared=True)
    output = capsys.readouterr().out
    for project in ('test-dev-787001', 'agoge-shared-resources'):
        assert f'projects/{project}/global/images/image-kali-linux-2023' in output
        assert f'gcloud compute images describe image-kali-linux-2023 --project={project}' in output
    assert 'private-fixture-password' not in output
    assert upload.db.collections['catalog'] == {}


def test_missing_firestore_document_is_not_misreported_as_missing_compute_image(upload, capsys):
    upload.db.query = Mock(side_effect=NotFound('private-fixture-password'))
    assert not upload.operation.run()
    output = capsys.readouterr().out
    assert 'selected-project Firestore' in output
    assert 'gcloud compute images describe' not in output
    assert 'private-fixture-password' not in output
    upload.compute.assert_not_called()


def _published_image(name='actual-powershell', project='agoge-shared-resources', **changes):
    return Image(name=name, **{
        'status': 'READY', 'architecture': 'X86_64',
        'self_link': f'https://www.googleapis.com/compute/v1/projects/{project}/global/images/{name}',
        **changes,
    })


def _recovery_inputs(monkeypatch, responses):
    values = iter(['', '', '', 'y', *responses])
    monkeypatch.setattr('builtins.input', lambda prompt: next(values))


@pytest.mark.parametrize('boot_disk_reference', [False, True])
@pytest.mark.parametrize('changes', [{}, {'status': 'PENDING'}, {'architecture': 'ARM64'}])
def test_upload_retries_legacy_site_reference_in_shared_project_without_recovery_prompt(
        upload, monkeypatch, capsys, boot_disk_reference, changes):
    record = upload.db.collections['image'].pop('kali-template')
    record.update(name='csec3314-powershell', image='image-csec3314-powershell',
                  self_link='projects/ualr-agoge/global/images/image-csec3314-powershell')
    if boot_disk_reference:
        record['disks'] = [{'boot': True, 'initializeParams': {'sourceImage': record.pop('self_link')}}]
    upload.db.collections['image']['csec3314-powershell'] = record
    original = deepcopy(upload.db.collections['image'])
    shared = _published_image('image-csec3314-powershell', **changes)
    transport = Mock()
    transport.get.side_effect = [GoogleNotFound('private-sdk-error'), shared]
    image_api = GCPImageAPI(upload.env.project, upload.env_data['region'], upload.env_data['zone'])
    image_api.images_client, image_api.logger = transport, Mock()
    upload.compute.return_value = image_api
    responses = iter(['csec3314-powershell', '', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(responses))

    assert upload.operation.run() == (not changes)

    assert [call.kwargs['request'].project for call in transport.get.call_args_list] == [
        'ualr-agoge', 'agoge-shared-resources']
    assert all(call.kwargs['request'].image == 'image-csec3314-powershell'
               for call in transport.get.call_args_list)
    transport.list.assert_not_called()
    assert upload.db.collections['image'] == original
    assert upload.db.records == {} and upload.db.claims == {}
    output = capsys.readouterr().out
    assert 'private-sdk-error' not in output and 'private-fixture-password' not in output
    if changes:
        assert upload.db.collections['catalog'] == {}
        assert 'READY and AMD64' in output
    else:
        catalog = upload.db.collections['catalog']['wireguard-factory-lab']
        assert catalog['servers'][1]['image'] == shared.self_link
        assert catalog['servers'][0]['image'].startswith('projects/ubuntu-os-cloud/')
        assert 'Uploaded: test-dev-787001/agoge-v1/catalog/wireguard-factory-lab' in output


@pytest.mark.parametrize('selection', ['1', 'actual-powershell'])
def test_recovery_browses_real_images_and_uses_selected_source_only_in_catalog(upload, monkeypatch, capsys, selection):
    original = deepcopy(upload.db.collections['image'])
    actual = _published_image()
    client = upload.compute.return_value
    client.get.side_effect = [NotFound('private-sdk-error'), actual]
    client.list.return_value = [
        _published_image('arm-image', architecture='ARM64'), actual,
        _published_image('pending-image', status='PENDING'),
    ]
    _recovery_inputs(monkeypatch, ['', '0', 'wrong-name', selection])

    assert upload.operation.run()

    client.list.assert_called_once_with(project='agoge-shared-resources')
    assert client.get.call_count == 2
    assert client.get.call_args.kwargs == {
        'resource': 'actual-powershell', 'project': 'agoge-shared-resources', 'fallback_to_shared': False}
    student = upload.db.collections['catalog']['wireguard-factory-lab']['servers'][1]
    assert student['image'] == actual.self_link
    assert len(student['human_interaction']) == 1
    for key, value in original['kali-template']['human_interaction'][0].items():
        assert student['human_interaction'][0][key] == value
    assert upload.db.collections['image'] == original
    assert upload.db.records == {} and upload.db.claims == {}
    output = capsys.readouterr().out
    assert '1. actual-powershell' in output
    assert 'arm-image' not in output and 'pending-image' not in output
    assert 'private-sdk-error' not in output and 'private-fixture-password' not in output


@pytest.mark.parametrize('prefix', ['', 'https://www.googleapis.com/compute/v1/'])
def test_recovery_accepts_exact_image_reference_without_listing_or_fallback(upload, monkeypatch, prefix):
    actual = _published_image(project='another-image-project')
    upload.compute.return_value.get.side_effect = [NotFound('missing'), actual]
    _recovery_inputs(monkeypatch, [prefix + 'projects/another-image-project/global/images/actual-powershell'])

    assert upload.operation.run()

    upload.compute.return_value.list.assert_not_called()
    upload.compute.return_value.get.assert_called_with(
        resource='actual-powershell', project='another-image-project', fallback_to_shared=False)
    assert upload.db.collections['catalog']['wireguard-factory-lab']['servers'][1]['image'] == actual.self_link


@pytest.mark.parametrize('responses', [['cancel'], ['', 'cancel']])
def test_recovery_cancel_preserves_existing_catalog_and_image_records(upload, monkeypatch, responses):
    existing = {'id': 'wireguard-factory-lab', 'summary': {'name': 'Existing lab'}}
    upload.db.collections['catalog']['wireguard-factory-lab'] = deepcopy(existing)
    before = deepcopy(upload.db.collections)
    upload.compute.return_value.get.side_effect = NotFound('missing')
    upload.compute.return_value.list.return_value = [_published_image()]
    _recovery_inputs(monkeypatch, responses)

    assert not upload.operation.run()
    assert upload.db.collections == before


@pytest.mark.parametrize('list_error', [False, True])
def test_recovery_can_move_to_another_project_or_exact_reference_after_empty_or_failed_list(upload, monkeypatch, capsys, list_error):
    client = upload.compute.return_value
    actual = _published_image(project='actual-source-project')
    client.get.side_effect = [NotFound('missing'), actual]
    if list_error:
        client.list.side_effect = RuntimeError('private-list-error')
    else:
        client.list.return_value = []
    _recovery_inputs(monkeypatch, ['old-image-project', 'projects/actual-source-project/global/images/actual-powershell'])

    assert upload.operation.run()

    client.list.assert_called_once_with(project='old-image-project')
    client.get.assert_called_with(resource='actual-powershell', project='actual-source-project', fallback_to_shared=False)
    output = capsys.readouterr().out
    assert ('Could not list images' if list_error else 'No READY AMD64 images') in output
    assert 'private-list-error' not in output


@pytest.mark.parametrize('changes', [{'status': 'PENDING'}, {'architecture': 'ARM64'}])
def test_recovery_rechecks_compatibility_of_exact_image_before_catalog_write(upload, monkeypatch, changes):
    upload.compute.return_value.get.side_effect = [NotFound('missing'), _published_image(**changes)]
    _recovery_inputs(monkeypatch, ['projects/agoge-shared-resources/global/images/actual-powershell'])
    assert not upload.operation.run()
    assert upload.db.collections['catalog'] == {}


def test_recovery_can_cancel_if_listed_image_disappears_before_selection(upload, monkeypatch, capsys):
    client = upload.compute.return_value
    client.get.side_effect = [NotFound('missing original'), NotFound('private-second-error')]
    client.list.return_value = [_published_image()]
    _recovery_inputs(monkeypatch, ['', '1', 'cancel'])
    assert not upload.operation.run()
    client.get.assert_called_with(resource='actual-powershell', project='agoge-shared-resources', fallback_to_shared=False)
    output = capsys.readouterr().out
    assert 'projects/agoge-shared-resources/global/images/actual-powershell was not found' in output
    assert 'private-second-error' not in output
    assert upload.db.collections['catalog'] == {}


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
