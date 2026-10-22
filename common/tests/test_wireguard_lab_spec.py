from ipaddress import ip_network

import pytest

from common.exceptions import BadRequest
from common.models.agoge import UnitModel
from common.services.wireguard_lab_spec import (
    UBUNTU_GATEWAY_IMAGE,
    configure_kit_topology,
    default_wireguard_spec,
)


def managed_unit():
    spec = default_wireguard_spec('image-kali-linux-2023', [
        {'display': True, 'protocol': 'rdp', 'username': 'kali', 'password': 'example'}])
    return UnitModel(**spec, id='abcdefghij', instructor_id=['teacher@example.edu'])


def test_managed_topology_replaces_untrusted_routes_and_access_tags():
    unit = managed_unit()
    unit.servers[1].tags = ['student-entry', 'wireguard-gateway', 'extra']
    unit.servers[1].can_ip_forward = True
    configure_kit_topology(unit, '172.30.0.0/24', 51820)

    gateway, student = unit.servers
    assert gateway.image == UBUNTU_GATEWAY_IMAGE
    assert gateway.can_ip_forward is True
    assert student.can_ip_forward is False
    assert student.no_service_account is True
    assert student.tags == ['wireguard-client']
    assert student.nics[0].external_nat is False
    assert student.nics[0].internal_ip is None
    assert [(r.dest_range, r.next_hop_instance, r.tags) for r in unit.routes] == [
        ('172.30.0.0/24', 'wireguard', ['wireguard-client'])]


def test_proxy_ingress_uses_unit_tag_instead_of_guessed_ip_addresses():
    unit = managed_unit()
    configure_kit_topology(unit, '172.30.0.0/24', 51820)
    rules = {rule.name: rule for rule in unit.firewall_rules}

    proxy = rules['allow-proxy-to-students']
    assert proxy.source_tags == ['abcdefghij-student-entry']
    assert proxy.ip_ranges == []
    assert proxy.target_tags == ['wireguard-client']
    assert proxy.priority < rules['deny-student-east-west'].priority
    transit = rules['allow-students-to-gateway']
    assert transit.source_tags == ['wireguard-client']
    assert transit.ip_ranges == []
    assert transit.target_tags == ['wireguard-gateway']
    assert transit.priority < rules['deny-student-east-west'].priority


def test_student_network_avoids_equipment_and_tunnel_ranges():
    unit = managed_unit()
    configure_kit_topology(unit, '10.20.0.0/24', 41194)

    student_subnet = ip_network(unit.networks[0].subnets[0].ip_subnet)
    assert not student_subnet.overlaps(ip_network('10.20.0.0/24'))
    assert not student_subnet.overlaps(ip_network('10.254.254.0/30'))
    assert unit.firewall_rules[0].ports == ['udp/41194']


def test_one_kit_topology_rejects_tunnel_overlap_and_additional_shared_servers():
    unit = managed_unit()
    with pytest.raises(BadRequest, match='tunnel'):
        configure_kit_topology(unit, '10.254.254.0/24', 51820)
    unit.servers.append(unit.servers[1].model_copy(update={'name': 'shared', 'community_server': True}))
    with pytest.raises(BadRequest, match='only its gateway'):
        configure_kit_topology(unit, '172.30.0.0/24', 51820)
