#!/usr/bin/env python3
"""Local, authenticated one-kit WireGuard client. Requires Linux root + wireguard.

No enrollment token or private key is accepted on the command line. Copy this
module to the Pi; it never downloads or executes application code from the API.
"""

import argparse
import base64
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request


LOG = logging.getLogger("agoge-wireguard-pi")
INTERFACE = "agoge"
FWD_CHAIN = "AGOGE_WG_FWD"
INPUT_CHAIN = "AGOGE_WG_IN"
NAT_CHAIN = "AGOGE_WG_NAT"
MAX_RESPONSE_BYTES = 65536
PRIVATE_NETWORKS = tuple(map(ipaddress.ip_network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))


class ConfigurationUnavailable(Exception):
    """No current authenticated lease is available; disconnect the tunnel."""


def private_file(path):
    """Read only a root-owned regular file that grants no group/other access."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("Credential files must be root-owned regular files with mode 0600")
        value = stream.read(8193)
        if len(value) > 8192:
            raise ValueError("Credential file is too large")
    return value.strip()


def validate_key(value):
    if not isinstance(value, str):
        raise ValueError("WireGuard public key must be a base64 string")
    try:
        key = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("Invalid WireGuard key") from error
    if len(key) != 32 or base64.b64encode(key).decode("ascii") != value:
        raise ValueError("Invalid WireGuard key")
    return value


def run_command(arguments, *, input_text=None, capture=False):
    """Never run a shell or include command output (possibly sensitive) in logs."""
    result = subprocess.run(
        arguments,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("A local WireGuard/network command failed")
    return result.stdout.strip() if capture else None


def ensure_key(key_file):
    path = Path(key_file)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        key = run_command(["wg", "genkey"], capture=True)
        validate_key(key)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(key + "\n")
    private_key = validate_key(private_file(path))
    public_key = run_command(["wg", "pubkey"], input_text=private_key + "\n", capture=True)
    return private_key, validate_key(public_key)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConfigurationUnavailable("API redirects are refused")


def configuration_url(api_url, kit_id):
    url = urllib.parse.urlsplit(api_url)
    if (
        url.scheme != "https" or not url.hostname or url.username or url.password
        or url.query or url.fragment or any(c in api_url for c in "\r\n")
    ):
        raise ValueError("api_url must be a trusted HTTPS API base URL")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}", kit_id):
        raise ValueError("Invalid kit ID")
    return api_url.rstrip("/") + "/wireguard/kits/" + kit_id + "/configuration/"


def fetch_configuration(api_url, kit_id, token_file):
    token = private_file(token_file)
    if not token or any(c.isspace() for c in token):
        raise ValueError("Invalid enrollment token file")
    request = urllib.request.Request(
        configuration_url(api_url, kit_id),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ConfigurationUnavailable("API configuration response is too large")
        data = json.loads(content)
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
            raise ConfigurationUnavailable("API configuration response is invalid")
        return data["data"]
    except (urllib.error.URLError, OSError, ValueError) as error:
        # Do not retain connectivity following any loss of authorization or
        # freshness, and never log the request object, token, or response body.
        raise ConfigurationUnavailable("Authenticated configuration is unavailable") from error


def ipv4_network(value):
    network = ipaddress.ip_network(value, strict=True)
    if network.version != 4 or not any(network.subnet_of(parent) for parent in PRIVATE_NETWORKS):
        raise ValueError("Expected an explicit private IPv4 network")
    return str(network)


def validate_configuration(data, kit_id, public_key):
    """Accept only the enrolled key and explicitly scoped current lease."""
    if data.get("kit_id") != kit_id or data.get("service_ready") is not True:
        raise ConfigurationUnavailable("The kit has no ready authorized gateway")
    if not hmac.compare_digest(validate_key(data.get("peer_public_key")), public_key):
        raise ConfigurationUnavailable("The enrolled public key does not match this Pi")
    unit_id = data.get("unit_id")
    if not isinstance(unit_id, str) or not re.fullmatch(r"[a-z]{10}", unit_id):
        raise ValueError("Invalid lease identifier")
    gateway_key = validate_key(data.get("gateway_public_key"))
    equipment = ipv4_network(data.get("equipment_subnet"))
    subnets = data.get("student_subnets")
    if not isinstance(subnets, list) or not 1 <= len(subnets) <= 16:
        raise ValueError("Expected explicit student networks")
    students = sorted(set(ipv4_network(value) for value in subnets))
    gateway = ipaddress.ip_interface(data.get("gateway_address"))
    peer = ipaddress.ip_interface(data.get("peer_address"))
    if gateway.version != 4 or peer.version != 4 or not all(
        any(address in parent for parent in PRIVATE_NETWORKS) for address in (gateway.ip, peer.ip)
    ):
        raise ValueError("Expected private IPv4 tunnel addresses")
    if gateway.ip == peer.ip or gateway.ip not in gateway.network or peer.ip not in gateway.network:
        raise ValueError("Tunnel endpoints must be distinct addresses in the gateway network")
    networks = [ipaddress.ip_network(equipment), *map(ipaddress.ip_network, students)]
    if any(network.overlaps(gateway.network) for network in networks):
        raise ValueError("Tunnel and routed networks must not overlap")
    if any(ipaddress.ip_network(equipment).overlaps(ipaddress.ip_network(value)) for value in students):
        raise ValueError("Equipment and student networks must not overlap")
    allowed = sorted([*students, str(gateway.ip) + "/32"])
    supplied_allowed = data.get("allowed_ips")
    if not isinstance(supplied_allowed, list) or sorted(set(supplied_allowed)) != allowed:
        raise ValueError("Pi AllowedIPs exceed the authorized lease networks")
    hostname = data.get("hostname")
    if not isinstance(hostname, str) or len(hostname) > 253 or not all(
        re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
        for label in hostname.rstrip(".").split(".")
    ):
        raise ValueError("Invalid gateway hostname")
    port = data.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("Invalid gateway port")
    return {
        "unit_id": unit_id, "gateway_public_key": gateway_key,
        "equipment_subnet": equipment, "student_subnets": students,
        "gateway_address": str(gateway), "peer_address": str(peer),
        "allowed_ips": allowed, "hostname": hostname, "port": port,
    }


def resolve_endpoint(hostname, port):
    """Resolve every poll so restarting a gateway need not restart the Pi."""
    answers = socket.getaddrinfo(hostname.rstrip("."), port, socket.AF_INET, socket.SOCK_DGRAM)
    for answer in answers:
        address = ipaddress.ip_address(answer[4][0])
        if address.is_global:
            return str(address)
    raise ConfigurationUnavailable("The gateway DNS name has no public IPv4 address")


def render_configuration(config, private_key, endpoint_ip):
    validate_key(private_key)
    if not ipaddress.ip_address(endpoint_ip).is_global:
        raise ValueError("The endpoint must be a public IP address")
    return (
        "[Interface]\nPrivateKey = " + private_key + "\n"
        "Address = " + config["peer_address"] + "\n\n[Peer]\n"
        "PublicKey = " + config["gateway_public_key"] + "\n"
        "Endpoint = " + endpoint_ip + ":" + str(config["port"]) + "\n"
        "AllowedIPs = " + ", ".join(config["allowed_ips"]) + "\n"
        "PersistentKeepalive = 25\n"
    )


class Controller:
    def __init__(self, config_file, equipment_interface, nat=False, runner=run_command):
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,15}", equipment_interface):
            raise ValueError("Invalid equipment interface name")
        if equipment_interface == INTERFACE:
            raise ValueError("Equipment and WireGuard interfaces must differ")
        self.config_file = Path(config_file)
        if self.config_file.name != INTERFACE + ".conf":
            raise ValueError("WireGuard configuration filename must be agoge.conf")
        self.equipment_interface = equipment_interface
        self.nat = nat
        self.run = runner
        self.current = None

    def iptables(self, *arguments, table="filter", ignore=False):
        try:
            return self.run(["iptables", "-w", "5", "-t", table, *arguments])
        except (RuntimeError, subprocess.TimeoutExpired):
            if not ignore:
                raise

    def deactivate(self):
        # Installations can resume after a crash, so cleanup must not depend on
        # the in-memory current value. Remove only this application's chains.
        self.current = None
        try:
            self.run(["wg-quick", "down", str(self.config_file)])
        except (RuntimeError, subprocess.TimeoutExpired):
            # Force interface removal when wg-quick cannot read an old config.
            try:
                self.run(["ip", "link", "set", "dev", INTERFACE, "down"])
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            try:
                self.run(["ip", "link", "delete", "dev", INTERFACE])
            except (RuntimeError, subprocess.TimeoutExpired):
                try:
                    self.run(["ip", "link", "show", "dev", INTERFACE])
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass  # Already absent; there is no tunnel left to revoke.
                else:
                    # Never remove the DROP guards while a failed interface
                    # teardown might leave the tunnel able to forward.
                    raise RuntimeError("Unable to deactivate the managed tunnel")
        for direction in ("-i", "-o"):
            self.iptables("-D", "FORWARD", direction, INTERFACE, "-j", FWD_CHAIN, ignore=True)
        self.iptables("-D", "INPUT", "-i", INTERFACE, "-j", INPUT_CHAIN, ignore=True)
        self.iptables("-D", "POSTROUTING", "-o", self.equipment_interface, "-j", NAT_CHAIN, table="nat", ignore=True)
        for table, chain in (("filter", FWD_CHAIN), ("filter", INPUT_CHAIN), ("nat", NAT_CHAIN)):
            self.iptables("-F", chain, table=table, ignore=True)
            self.iptables("-X", chain, table=table, ignore=True)
        self.config_file.unlink(missing_ok=True)

    def apply(self, config, private_key, endpoint_ip):
        rendered = render_configuration(config, private_key, endpoint_ip)
        desired = (config, endpoint_ip)
        if self.current == desired:
            # A failed/lost interface must not look healthy merely because the
            # API content is unchanged.
            self.run(["wg", "show", INTERFACE, "public-key"])
            return False
        self.deactivate()
        try:
            self.config_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(self.config_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(rendered)
            # Scoped DROP chains govern only traffic involving the tunnel;
            # they leave unrelated Pi forwarding policies unchanged.
            self.iptables("-N", FWD_CHAIN)
            for subnet in config["student_subnets"]:
                self.iptables("-A", FWD_CHAIN, "-i", INTERFACE, "-o", self.equipment_interface,
                              "-s", subnet, "-d", config["equipment_subnet"], "-j", "ACCEPT")
                self.iptables("-A", FWD_CHAIN, "-i", self.equipment_interface, "-o", INTERFACE,
                              "-s", config["equipment_subnet"], "-d", subnet,
                              "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT")
            self.iptables("-A", FWD_CHAIN, "-j", "DROP")
            for direction in ("-i", "-o"):
                self.iptables("-I", "FORWARD", "1", direction, INTERFACE, "-j", FWD_CHAIN)
            self.iptables("-N", INPUT_CHAIN)
            gateway_ip = str(ipaddress.ip_interface(config["gateway_address"]).ip) + "/32"
            self.iptables("-A", INPUT_CHAIN, "-s", gateway_ip, "-p", "icmp", "-j", "ACCEPT")
            self.iptables("-A", INPUT_CHAIN, "-j", "DROP")
            self.iptables("-I", "INPUT", "1", "-i", INTERFACE, "-j", INPUT_CHAIN)
            if self.nat:
                self.iptables("-N", NAT_CHAIN, table="nat")
                for subnet in config["student_subnets"]:
                    self.iptables("-A", NAT_CHAIN, "-s", subnet, "-d", config["equipment_subnet"],
                                  "-j", "MASQUERADE", table="nat")
                self.iptables("-I", "POSTROUTING", "1", "-o", self.equipment_interface,
                              "-j", NAT_CHAIN, table="nat")
            self.run(["sysctl", "-w", "net.ipv4.ip_forward=1"])
            self.run(["wg-quick", "up", str(self.config_file)])
            self.current = desired
            return True
        except Exception:
            self.deactivate()
            raise


def poll(settings, stop=None):
    stop = stop or threading.Event()
    api_url, kit_id = settings["api_url"], settings["kit_id"]
    configuration_url(api_url, kit_id)
    interval = int(settings.get("interval", 15))
    if not 5 <= interval <= 60:
        raise ValueError("Polling interval must be between 5 and 60 seconds")
    private_key, public_key = ensure_key(settings.get("key_file", "/etc/wireguard/agoge.key"))
    nat = settings.get("nat", False)
    if not isinstance(nat, bool):
        raise ValueError("nat must be a JSON boolean")
    controller = Controller(
        settings.get("config_file", "/etc/wireguard/agoge.conf"),
        settings["equipment_interface"], nat,
    )
    controller.deactivate()
    try:
        while not stop.is_set():
            try:
                response = fetch_configuration(api_url, kit_id, settings["token_file"])
                config = validate_configuration(response, kit_id, public_key)
                endpoint_ip = resolve_endpoint(config["hostname"], config["port"])
                if controller.apply(config, private_key, endpoint_ip):
                    LOG.info("Applied authorized kit lease %s", config["unit_id"])
            except Exception:
                # No exception bodies: network libraries may include headers
                # or remote responses. Disconnect first, then retry shortly.
                controller.deactivate()
                LOG.warning("No verified current lease; tunnel disconnected; retrying")
            stop.wait(interval)
    finally:
        controller.deactivate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    keygen = subcommands.add_parser("keygen", help="Create/retain the local key and print only its PUBLIC key")
    keygen.add_argument("--key-file", default="/etc/wireguard/agoge.key")
    run = subcommands.add_parser("run", help="Run the authenticated configuration poller")
    run.add_argument("--settings", default="/etc/agoge-wireguard/config.json")
    arguments = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run this utility as root")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if arguments.command == "keygen":
        _, public = ensure_key(arguments.key_file)
        print(public)
        return
    settings = json.loads(private_file(arguments.settings))
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    poll(settings, stop=stop)


if __name__ == "__main__":
    main()
