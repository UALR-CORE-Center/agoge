"""Repository-owned, single-proxy topology for community lab displays."""
from ipaddress import ip_address, ip_network
from itertools import chain

from common.constants.build_constants import BuildConstants
from common.exceptions import BadRequest
from common.models.agoge import FirewallRuleModel, NicModel, ServerModel


COMMUNITY_PROXY_NAME = 'display-guacamole-server'


def community_proxy(unit):
    proxies = [server for server in getattr(unit, 'servers', None) or [] if getattr(server, 'community_proxy', False)]
    if len(proxies) > 1:
        raise BadRequest('A community lab may have only one generated Guacamole proxy')
    return proxies[0] if proxies else None


def ensure_community_proxy(unit, dns_suffix, project):
    """Add the canonical proxy and reserve addresses before student DHCP claims.

    Only a public Secret Manager reference is reused. Catalog-supplied images,
    startup code, identities and NICs cannot override this generated service.
    """
    if getattr(unit, 'unit_type', None) != BuildConstants.UnitType.COMMUNITY.value:
        return None
    students = [server for server in getattr(unit, 'servers', None) or [] if not server.community_server
                and any(getattr(item, 'display', False) for item in getattr(server, 'human_interaction', None) or [])]
    previous = community_proxy(unit)
    if not students:
        return None
    if previous and previous.name != COMMUNITY_PROXY_NAME:
        raise BadRequest('The generated community proxy has an invalid server name')
    if any(server.name == COMMUNITY_PROXY_NAME and not getattr(server, 'community_proxy', False)
           for server in getattr(unit, 'servers', None) or []):
        raise BadRequest('display-guacamole-server is reserved for the shared community proxy')
    network_specs = {network.name: network for network in unit.networks or []}
    needed = []
    for server in students:
        if not server.nics:
            raise BadRequest('A displayed community server requires a network interface')
        nic = server.nics[0]
        key = (nic.network, nic.subnet_name or 'default')
        # GCE permits only one NIC per VPC; VPC routing reaches its other subnets.
        if nic.network not in [network for network, _ in needed]:
            needed.append(key)
    if len(needed) > 2:
        raise BadRequest('The shared community proxy supports at most two VPC networks on e2-medium; reduce the displayed server networks')
    nics = []
    for index, (network_name, subnet_name) in enumerate(needed):
        network = network_specs.get(network_name)
        subnet = next((item for item in network.subnets or [] if item.name == subnet_name), None) if network else None
        if not subnet:
            raise BadRequest('The displayed server network is not defined in this community lab')
        cidr = ip_network(subnet.ip_subnet)
        if cidr.version != 4:
            raise BadRequest('Community display networks must use IPv4')
        reserved = {str(value) for value in network.reservations or []}
        occupied = {str(nic.internal_ip) for server in getattr(unit, 'servers', None) or [] if server is not previous
                    for nic in server.nics or [] if nic.network == network_name and nic.internal_ip}
        used = reserved | occupied
        old = next((nic.internal_ip for nic in previous.nics or []
                    if nic.network == network_name and (nic.subnet_name or 'default') == subnet_name), None) if previous else None
        if (old and (previous.guacamole_secret_version_name
                     or getattr(unit, 'community_proxy_cleanup_pending', False)) and ip_address(old) in cidr
                and str(old) not in occupied):
            address = old
        else:
            preferred = [cidr.network_address + 11] if cidr.num_addresses > 15 else []
            candidates = chain(preferred, cidr.hosts())
            address = next((str(candidate) for candidate in candidates
                            if candidate in cidr and candidate not in (cidr.network_address + 1,
                                                                      cidr.broadcast_address - 1, cidr.broadcast_address)
                            and str(candidate) not in used), None)
            if not address:
                raise BadRequest('No address remains for the shared community proxy')
        network.reservations = list(dict.fromkeys([*(network.reservations or []), address]))
        nics.append(NicModel(network=network_name, subnet_name=subnet_name,
                            internal_ip=address, external_nat=index == 0))
    proxy = ServerModel(name=COMMUNITY_PROXY_NAME, community_server=True, community_proxy=True,
        hidden=True, image=f"projects/{project}/global/images/{BuildConstants.MachineImages.GUACAMOLE_SSL.format(project=project)}",
        machine_type=BuildConstants.GoogleMachineTypes.E2_MEDIUM.value,
        hostname=f'{unit.id}-display.{str(dns_suffix).strip(".")}',
        nics=nics, tags=['student-entry', f'{unit.id}-student-entry'], human_interaction=[],
        guacamole_secret_version_name=getattr(previous, 'guacamole_secret_version_name', None))
    unit.servers = [server for server in getattr(unit, 'servers', None) or [] if server is not previous] + [proxy]
    # Ordinary community templates may not already expose the generated proxy.
    rules = list(unit.firewall_rules or [])
    names = {rule.name for rule in rules}
    display_tag = f'{unit.id}-display-target'
    for server in students:
        server.tags = list(dict.fromkeys([*(server.tags or []), display_tag]))
    for network_name, _ in needed:
        name = 'allow-community-proxy' if len(needed) == 1 else f'allow-community-proxy-{network_name}'
        if name not in names:
            rules.append(FirewallRuleModel(name=name, network=network_name, action='allow',
                target_tags=[f'{unit.id}-student-entry'], ports=['tcp/80,443,8443'],
                ip_ranges=['0.0.0.0/0'], priority=900))
        name = f'allow-community-display-{network_name}'
        if name not in names:
            rules.append(FirewallRuleModel(name=name, network=network_name, action='allow',
                target_tags=[display_tag], source_tags=[f'{unit.id}-student-entry'],
                ports=['tcp/22,3389,5900,5901'], ip_ranges=[], priority=900))
    unit.firewall_rules = rules
    return proxy
