"""Apply a saved remote LAN while its managed gateway is stopped."""
from common.constants.database import DbCollections
from common.exceptions import BadRequest, NotFound
from common.models.agoge import FirewallRuleModel, RouteModel

from ..gcp.route_manager import RouteManager
from ..gcp.firewall_rule_manager import FirewallManager


def apply_saved_wireguard_network(manager, lease):
    if not lease.configuration_pending:
        return
    current = manager._wireguard_provisioning().get_lease(manager.parent_build_id)
    if current.configuration_revision != lease.configuration_revision:
        raise BadRequest('The saved remote lab configuration changed; retry start')
    unit = manager.db.get(collection_name=DbCollections.UNIT, doc_id=manager.parent_build_id) or {}
    routes = [route for route in unit.get('routes') or [] if route.get('name') == 'wireguard-equipment']
    rules = [rule for rule in unit.get('firewall_rules') or [] if rule.get('name') == 'allow-kit-to-students']
    if (len(routes) != 1 or len(rules) != 1 or routes[0].get('dest_range') != lease.equipment_subnet
            or rules[0].get('ip_ranges') != [lease.equipment_subnet]):
        raise BadRequest('Saved remote LAN routes and firewall rules do not match its lease')
    # Both resources have fixed, Unit-owned names. GCE routes are immutable;
    # remove only this stopped lab's old remote route, then build the new one.
    routing = RouteManager(manager.parent_build_id, env_dict=manager.env_dict)
    routing.delete([RouteModel(**route) for route in routes])
    routing.build([RouteModel(**route) for route in routes])
    firewall = FirewallManager(env_dict=manager.env_dict)
    try:
        if firewall.firewalls_client.delete(
                resource_name=f'{manager.parent_build_id}-allow-kit-to-students', wait=True) is False:
            raise ConnectionError('The old remote LAN firewall rule was not removed')
    except NotFound:
        pass
    firewall.build(manager.parent_build_id, [FirewallRuleModel(**rule) for rule in rules])
