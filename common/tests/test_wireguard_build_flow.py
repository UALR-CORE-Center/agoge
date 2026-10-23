"""Reference instructor -> leased gateway -> authenticated Pi, without GCP writes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from common.constants.database import DbCollections
from common.exceptions import BadRequest, Unauthorized
from common.models.users import AgogeUser
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.services.wireguard_lab_spec import default_wireguard_spec
from common.services.wireguard_provisioning import WireGuardProvisioningService
from common.services.wireguard_startup import render_wireguard_startup
from common.tests.test_wireguard_provisioning import Database, Secrets, kit_data
from core.unit import Unit
from core.wireguard_lab import WireGuardLab


@pytest.fixture
def flow():
    now = datetime.now(timezone.utc).timestamp()
    env = {'project': 'agoge-test', 'region': 'us-central1', 'zone': 'us-central1-a',
           'parent_dns_suffix': '.example.edu', 'project_path': 'test', 'wireguard_port': 51820}
    db, secret_store = Database(), Secrets()
    # Match real Firestore upserts used by Unit.commit.
    db.update = lambda collection_name, doc_id, data: db.collections.setdefault(
        collection_name.value, {}).setdefault(doc_id, {}).update(data)
    service = WireGuardProvisioningService(env, db=db, secret_store=secret_store, clock=lambda: now)
    teacher = AgogeUser(uid='teacher', email='teacher@example.edu', permissions={'instructor': True}, settings={})
    enrollment = service.enroll(kit_data(), SimpleNamespace(is_admin=True))
    manager = object.__new__(Unit)
    manager.env_dict, manager.db, manager.collection = env, db, DbCollections.UNIT
    manager.log_name = 'api'
    manager.logger, manager.debug = Mock(), True
    connections = [{'display': True, 'protocol': 'rdp', 'username': 'student', 'password': 'image-password'}]
    db.collections[DbCollections.IMAGE.value] = {'image-kali-linux-2023': {
        'status': 0, 'image_exists': True, 'human_interaction': connections}}
    registry = WireGuardEndpointRegistry(env, db=db, timestamp_factory=lambda: now)
    data = {'kit_id': 'kit-one', 'build_count': 2,
            'expires': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    with (patch('core.unit.WireGuardProvisioningService', return_value=service),
          patch('core.unit.WireGuardEndpointRegistry', return_value=registry),
          patch('core.wireguard_lab.WireGuardProvisioningService', return_value=service),
          patch('core.wireguard_lab.Unit', return_value=manager),
          patch('core.wireguard_lab.ComputeImageAPI') as image):
        image.return_value.get.return_value = SimpleNamespace(status='READY', architecture='X86_64',
            self_link='https://www.googleapis.com/compute/v1/projects/agoge-test/global/images/image-kali-linux-2023')
        yield SimpleNamespace(env=env, db=db, service=service, registry=registry, secrets=secret_store,
                              teacher=teacher, manager=manager, data=data, now=now, enrollment=enrollment,
                              image=image)


def test_reference_instructor_to_gateway_to_pi_flow(flow):
    identifier = WireGuardLab(flow.env).build(flow.teacher, flow.data)
    built = flow.db.collections['unit'][identifier]
    assert built['workspace_settings']['count'] == 2
    gateway, student = built['servers']
    assert gateway['wireguard_managed'] and gateway['image'].startswith('projects/ubuntu-os-cloud/')
    assert gateway['nics'][0]['external_ip_name'] is None
    assert built['routes'][0]['dest_range'] == '172.30.0.0/24'
    assert built['wireguard_endpoint']['hostname'].startswith('wg10000.agoge-test.')
    boot = flow.service.prepare_boot(identifier)
    secret = flow.secrets.payloads[identifier]
    flow.service.report_health(identifier, secret['callback_token'], {
        'boot_id': boot, 'service_ready': True, 'tunnel_ready': False})
    flow.registry.stage('10000', identifier, '203.0.113.10')
    flow.registry.activate('10000', identifier, '203.0.113.10')
    config = flow.service.pi_configuration('kit-one', flow.enrollment['enrollment_token'])
    assert config['unit_id'] == identifier
    assert config['gateway_public_key'] == secret['gateway_public_key']
    assert config['allowed_ips'] == ['10.20.0.0/24', '10.254.254.1/32']
    assert not config['tunnel_ready']
    assert 'private_key' not in config
    script = render_wireguard_startup(flow.service.get_lease(identifier).secret_version_name, boot)
    assert secret['private_key'] not in script and secret['callback_token'] not in script
    assert secret['private_key'] not in str(flow.db.collections)


def test_browser_cannot_choose_arbitrary_routes_or_another_kit(flow):
    wrong_teacher = flow.teacher.model_copy(update={'email': 'outsider@example.edu'})
    with pytest.raises(Unauthorized):
        WireGuardLab(flow.env).build(wrong_teacher, flow.data)
    assert not flow.secrets.payloads
    identifier = WireGuardLab(flow.env).build(flow.teacher, {**flow.data, 'routes': [
        {'dest_range': '0.0.0.0/0', 'next_hop_instance': 'wireguard'}]})
    assert flow.db.collections['unit'][identifier]['routes'][0]['dest_range'] == '172.30.0.0/24'


def test_failed_build_compensates_secret_kit_and_number(flow):
    original = flow.service.reserve
    def failed_reserve(*args):
        original(*args)
        raise RuntimeError('failure after transactional lease claim')
    with patch.object(flow.service, 'reserve', side_effect=failed_reserve), pytest.raises(RuntimeError):
        WireGuardLab(flow.env).build(flow.teacher, flow.data)
    assert not flow.secrets.payloads
    assert flow.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] is None
    assert flow.db.collections['wireguard-endpoint'] == {}


def test_committed_unit_keeps_lease_after_publish_failure(flow):
    original = flow.manager.commit
    def committed_then_failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('PubSub unavailable after commit')
    with patch.object(flow.manager, 'commit', side_effect=committed_then_failed), pytest.raises(RuntimeError):
        WireGuardLab(flow.env).build(flow.teacher, flow.data)
    assert len(flow.db.collections['unit']) == 1
    assert len(flow.secrets.payloads) == 1
    assert len(flow.db.collections['wireguard-endpoint']) == 1


@pytest.mark.parametrize('count', [False, 0, -1, 101, '2'])
def test_builtin_flow_validates_student_capacity(flow, count):
    with pytest.raises(BadRequest):
        WireGuardLab(flow.env).build(flow.teacher, {**flow.data, 'build_count': count})
    assert not flow.secrets.payloads


@pytest.mark.parametrize('image_change', [{'status': 1}, {'image_exists': False},
                                      {'human_interaction': []}])
def test_unusable_student_image_fails_before_allocation(flow, image_change):
    flow.db.collections['image']['image-kali-linux-2023'].update(image_change)
    with pytest.raises(BadRequest):
        WireGuardLab(flow.env).build(flow.teacher, flow.data)
    assert not flow.secrets.payloads


def test_arm_student_image_rejected_before_allocation(flow):
    flow.image.return_value.get.return_value.architecture = 'ARM64'
    with pytest.raises(BadRequest, match='AMD64'):
        WireGuardLab(flow.env).build(flow.teacher, flow.data)
    assert not flow.secrets.payloads


def test_registered_template_name_resolves_and_pins_its_different_compute_source(flow):
    record = flow.db.collections['image'].pop('image-kali-linux-2023')
    record['self_link'] = 'https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-kali-custom'
    record['image'] = 'image-kali-custom'
    flow.db.collections['image']['kali-template'] = record
    source = 'https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-kali-custom'
    flow.image.return_value.get.return_value.self_link = source
    identifier = WireGuardLab(flow.env).build(flow.teacher, {**flow.data, 'student_image': 'kali-template'})
    flow.image.return_value.get.assert_called_once_with(resource='image-kali-custom',
        project='shared-images', fallback_to_shared=False)
    assert flow.db.collections['unit'][identifier]['servers'][1]['image'] == source


@pytest.mark.parametrize('include_legacy', [False, True])
def test_remote_peer_build_input_selects_authorized_existing_record(flow, include_legacy):
    data = {**flow.data, 'remote_peer_id': 'kit-one'}
    if not include_legacy:
        data.pop('kit_id')
    identifier = WireGuardLab(flow.env).build(flow.teacher, data)
    lease = flow.db.collections['unit'][identifier]['wireguard_lease']
    assert lease['remote_peer_id'] == lease['kit_id'] == 'kit-one'
    assert lease['remote_network_cidr'] == '172.30.0.0/24'


def test_conflicting_remote_peer_build_inputs_fail_before_any_allocation(flow):
    with pytest.raises(BadRequest, match='conflicts'):
        WireGuardLab(flow.env).build(flow.teacher, {**flow.data, 'remote_peer_id': 'other-peer'})
    assert not flow.secrets.payloads
    assert not flow.db.collections['wireguard-endpoint']


def test_catalog_unit_build_also_rejects_conflicting_remote_peer_aliases(flow):
    with pytest.raises(BadRequest, match='conflicts'):
        flow.manager.build(flow.teacher, {**flow.data, 'remote_peer_id': 'other-peer',
            'build_file': 'builtin-wireguard-factory'}, catalog_override=default_wireguard_spec(
                'projects/agoge-test/global/images/image-kali-linux-2023',
                [{'display': True, 'protocol': 'ssh', 'username': 'student', 'password': 'image-password'}]))
    assert not flow.secrets.payloads
    assert not flow.db.collections['wireguard-endpoint']
