"""Server-side topology for a Community Lab with one registered remote peer."""
from ipaddress import ip_network

from common.exceptions import BadRequest
from common.models.agoge import FirewallRuleModel, NetworkModel, NicModel, RouteModel
from common.services.community_proxy_spec import COMMUNITY_PROXY_NAME


UBUNTU_GATEWAY_IMAGE = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64"
DEFAULT_STUDENT_IMAGE = "image-kali-linux-2023"


def default_wireguard_spec(student_image: str, connections: list) -> dict:
    """No instance-specific keys, addresses, or credentials belong in a catalog."""
    return {
        "version": "1.1", "build_type": "unit", "unit_type": "community",
        "summary": {"name": "WireGuard Remote Lab", "author": "Agoge",
                    "description": "A shared Ubuntu WireGuard gateway connects student workstations to a registered remote peer and its private LAN."},
        "networks": [], "servers": [
            {"name": "wireguard", "image": UBUNTU_GATEWAY_IMAGE,
             "machine_type": "e2-medium", "community_server": True,
             "wireguard_gateway": True, "can_ip_forward": True, "hidden": True},
            {"name": "kali", "image": student_image, "machine_type": "e2-standard-2",
             "community_server": False, "human_interaction": connections},
        ],
    }


def configure_kit_topology(unit, equipment_subnet: str, port: int) -> None:
    """Derive routes/firewalls from the registered remote peer, never a browser CIDR.

    Each Unit gets its own VPC; only selected student VMs use the equipment
    route. Legacy arbitrary routes, NICs, and startup scripts cannot broaden a
    managed gateway's access policy.
    """
    remote = ip_network(equipment_subnet, strict=True)
    if remote.version != 4 or remote.prefixlen == 0:
        raise BadRequest("The registered remote peer must have an explicit IPv4 remote LAN")
    tunnel = ip_network("10.254.254.0/30")
    if remote.overlaps(tunnel):
        raise BadRequest("The remote LAN overlaps the WireGuard tunnel subnet")
    subnet = next((ip_network(cidr) for cidr in
                   ("10.20.0.0/24", "10.21.0.0/24", "172.20.0.0/24")
                   if not ip_network(cidr).overlaps(remote)), None)
    if subnet is None:
        raise BadRequest("Cannot select a student subnet outside the remote LAN")
    gateways = [server for server in unit.servers or [] if server.wireguard_gateway]
    students = [server for server in unit.servers or [] if not server.community_server
                and not server.wireguard_gateway]
    if unit.unit_type != "community" or len(gateways) != 1 or not students:
        raise BadRequest("A managed WireGuard Lab needs one shared gateway and at least one student server")
    if any(server.community_server and server not in gateways
           and not (getattr(server, 'community_proxy', False) and server.name == COMMUNITY_PROXY_NAME)
           for server in unit.servers or []):
        raise BadRequest("A WireGuard remote lab supports only its gateway as a shared server")
    # Shared display services are generated again from trusted code after this
    # topology is selected; catalog startup scripts and NICs are never reused.
    unit.servers = [server for server in unit.servers or [] if not getattr(server, 'community_proxy', False)]
    gateway = gateways[0]
    gateway_ip = str(subnet.network_address + 10)
    unit.networks = [NetworkModel(name="external", subnets=[
        {"name": "default", "ip_subnet": str(subnet)}], reservations=[gateway_ip])]
    unit.firewalls = []
    gateway.image = UBUNTU_GATEWAY_IMAGE
    gateway.machine_type = "e2-medium"
    gateway.community_server = True
    gateway.can_ip_forward = True
    gateway.hidden = True
    gateway.tags = ["wireguard-gateway"]
    gateway.nics = [NicModel(network="external", internal_ip=gateway_ip, external_nat=True)]
    gateway.routes = []
    gateway.firewall_rules = []
    gateway.startup_script = None
    gateway.guacamole_startup_script = None
    gateway.metadata = None
    gateway.human_interaction = []
    for server in students:
        server.can_ip_forward = False
        server.no_service_account = True
        # Do not inherit tags such as student-entry which would grant this
        # workstation the proxy's privileged ingress policy.
        server.tags = ["wireguard-client"]
        server.nics = [NicModel(network="external", external_nat=False)]
        server.routes = []
        server.firewall_rules = []
    unit.routes = [RouteModel(name="wireguard-equipment", network="external",
        dest_range=str(remote), next_hop_instance=gateway.name, tags=["wireguard-client"])]
    # Managed labs deliberately do not inherit the catalog's allow-all-local
    # rule. Student access is via the Guacamole proxy; equipment access is
    # restricted to this remote LAN's source range and selected student VMs.
    unit.firewall_rules = [FirewallRuleModel(**rule) for rule in [
        {"name": "allow-wireguard-ingress", "network": "external", "action": "allow",
         "target_tags": ["wireguard-gateway"], "ports": [f"udp/{port}"],
         "ip_ranges": ["0.0.0.0/0"], "priority": 900},
        {"name": "allow-kit-to-students", "network": "external", "action": "allow",
         "target_tags": ["wireguard-client"], "ports": ["tcp/any", "udp/any", "icmp/any"],
         "ip_ranges": [str(remote)], "priority": 900},
        {"name": "allow-students-to-gateway", "network": "external", "action": "allow",
         "target_tags": ["wireguard-gateway"], "ports": ["tcp/any", "udp/any", "icmp/any"],
         "ip_ranges": [], "source_tags": ["wireguard-client"], "priority": 900},
        {"name": "allow-proxy-to-students", "network": "external", "action": "allow",
         "target_tags": ["wireguard-client"], "ports": ["tcp/22,3389,5900,5901"],
         "ip_ranges": [], "source_tags": [f"{unit.id}-student-entry"],
         "priority": 900},
        {"name": "deny-student-east-west", "network": "external", "action": "deny",
         "target_tags": ["wireguard-client", "wireguard-gateway"],
         "ports": ["tcp/any", "udp/any", "icmp/any"],
         "ip_ranges": [str(subnet)], "priority": 950},
        {"name": "allow-student-entry", "network": "external", "action": "allow",
         "target_tags": ["student-entry"], "ports": ["tcp/80,443,8443,4822"],
         "ip_ranges": ["0.0.0.0/0"], "priority": 1000},
    ]]
