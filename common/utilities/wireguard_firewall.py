"""Pure helpers for checking a WireGuard gateway's effective VPC listener rule."""

from ipaddress import IPv4Network, ip_network
from typing import Any


DEFAULT_WIREGUARD_PORT = 51820


def has_public_wireguard_ingress(unit: Any, port: int) -> bool:
    """Return whether the Unit explicitly permits its public WireGuard listener.

    The check mirrors the parts of a Google Cloud VPC firewall rule that Agoge
    controls. It intentionally does not synthesize a public rule: opening a UDP
    service must remain an explicit choice in the lab specification.
    """
    if isinstance(port, bool):
        return False
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False
    if not 1 <= port <= 65535:
        return False

    gateway = next(
        (
            server
            for server in _field(unit, "servers", []) or []
            if bool(_field(server, "wireguard_gateway", False))
        ),
        None,
    )
    if gateway is None:
        return False

    # CommunityUnit attaches the reserved public address to the first external
    # NAT NIC, so a rule on a different VPC would not make that address usable.
    public_nic = next(
        (
            nic
            for nic in _field(gateway, "nics", []) or []
            if bool(_field(nic, "external_nat", False))
        ),
        None,
    )
    if public_nic is None:
        return False

    public_network = _field(public_nic, "network")
    gateway_tags = set(_field(gateway, "tags", []) or [])
    for rule in _field(unit, "firewall_rules", []) or []:
        if _field(rule, "network") != public_network:
            continue
        if _enum_value(_field(rule, "direction", "INGRESS")).upper() != "INGRESS":
            continue
        if not _is_allow_rule(rule):
            continue
        if not _beats_implied_ingress_deny(rule):
            continue

        target_tags = set(_field(rule, "target_tags", []) or [])
        # GCE target tags are OR selectors. An empty selector applies the rule
        # to every instance NIC on the rule's VPC.
        if target_tags and not target_tags.intersection(gateway_tags):
            continue
        if not _allows_public_source(rule):
            continue
        if any(
            _selector_allows_udp_port(selector, port)
            for selector in _field(rule, "ports", []) or []
        ):
            return True
    return False


def _is_allow_rule(rule: Any) -> bool:
    action = _field(rule, "action")
    if action not in (None, ""):
        return _enum_value(action).lower() == "allow"

    # Keep compatibility with FirewallManager's legacy action resolution.
    return "deny-outbound" not in set(_field(rule, "target_tags", []) or [])


def _beats_implied_ingress_deny(rule: Any) -> bool:
    priority = _field(rule, "priority", 1000)
    if priority is None:
        priority = 1000
    if isinstance(priority, bool):
        return False
    try:
        return 0 <= int(priority) < 65535
    except (TypeError, ValueError):
        return False


def _allows_public_source(rule: Any) -> bool:
    source_ranges = _field(rule, "ip_ranges")
    if source_ranges is None:
        source_ranges = ["0.0.0.0/0"]
    for source_range in source_ranges:
        try:
            network = ip_network(str(source_range), strict=False)
        except ValueError:
            continue
        if isinstance(network, IPv4Network) and network.is_global:
            return True
    return False


def _selector_allows_udp_port(selector: Any, port: int) -> bool:
    try:
        protocol, port_expression = str(selector).lower().split("/", 1)
    except ValueError:
        return False
    if protocol not in {"udp", "all"}:
        return False

    for value in port_expression.split(","):
        value = value.strip()
        if value == "any":
            return True
        if value.isdigit() and int(value) == port:
            return True
        if "-" in value:
            start, separator, end = value.partition("-")
            if separator and start.isdigit() and end.isdigit():
                if int(start) <= port <= int(end):
                    return True
    return False


def _enum_value(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    if isinstance(enum_value, str):
        return enum_value
    return str(getattr(value, "name", enum_value))


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
