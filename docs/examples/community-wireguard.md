# Community WireGuard example

[`community-wireguard.json`](community-wireguard.json) is an uploadable starting point for a Community Lab with one shared WireGuard router and one Kali workstation per student.

## Prerequisites

- Check in reusable images named `image-wireguard-server` and `image-kali-linux-2023`, or replace those values with image names from your deployment.
- Configure the project-level WireGuard DNS suffix and its public Cloud DNS zone before building the Lab. The configured parent Cloud DNS zone must be authoritative for this suffix, and the runtime service account must be able to list, create, update, and delete its A records.
- Replace `CHANGE-ME-BEFORE-PUBLISHING` with the credential baked into the Kali image. Do not publish a production credential in a catalog JSON file.
- Replace `172.30.0.0/24` with the network reachable through the remote WireGuard peer. It must not overlap `10.20.0.0/24`, the WireGuard tunnel address range, or another routed VPC range.
- Configure the remote peer with a return route for `10.20.0.0/24`. If a return route is impossible, configure intentional source NAT on the WireGuard gateway instead.

## Security and deployment boundaries

This example intentionally puts every student's Kali VM and the shared gateway in one VPC subnet. Agoge's specification validator adds an `allow-all-local` ingress rule at priority 999 with no target tags. Consequently, every student VM can initiate TCP, UDP, and ICMP traffic to every other student VM and to the gateway. This is appropriate only when east-west access is part of the exercise. A deny rule at priority 1000 does not override the generated rule because lower GCP priority numbers take precedence. If students must be isolated from one another, change the generated firewall policy or use separate trust boundaries before deploying this example.

The five-digit endpoint ID is deliberately public, has only 90,000 possible values, and is enumerable. Treat it as a convenient locator, never as an authorization token. WireGuard public keys remain the authentication boundary. The complete locator is the tenant API origin plus the five-digit ID; IDs are not globally unique across Agoge projects. Apply an actual request quota or rate limit at the API gateway, load balancer, or Cloud Armor edge in front of the resolver, and monitor repeated enumeration attempts; documentation alone does not enforce a limit.

The installer grants `roles/dns.admin` to the Agoge runtime service account on the configured managed zone, not across the parent DNS project. That role can still alter every record in that zone, so prefer a dedicated public zone for WireGuard endpoints; a deployment with stricter requirements can replace it with a custom role containing only the record-list/change permissions the runtime needs. Fresh installs and upgrades fail their WireGuard preflight if the Compute or DNS API cannot be enabled, the zone is missing or private, the suffix is outside that zone, or zone IAM cannot be updated. The five-digit allocation registry is project-local, so Agoge automatically inserts the globally unique GCP project ID as a DNS label. This prevents two Agoge projects that share a parent zone and allocate the same five-digit ID from overwriting one another's A record.

The `wireguard_gateway` flag causes Agoge to allocate a five-digit endpoint ID, a reserved public address, and a DNS name from the configured gateway pool when the Unit is built. Endpoint values are runtime state and therefore do not belong in the catalog template.

For a GCP project named `agoge-class-a`, these project settings allocate names from `wg-10000.agoge-class-a.vpn.example.edu` through `wg-99999.agoge-class-a.vpn.example.edu` and publish port 51820 through the resolver API:

```json
{
  "wireguard_dns_prefix": "wg",
  "wireguard_dns_suffix": "vpn.example.edu.",
  "wireguard_port": 51820
}
```

`wireguard_port` advertises the endpoint; it does not reconfigure the WireGuard daemon or rewrite catalog firewall rules. If you choose a port other than 51820, set the gateway's WireGuard `ListenPort` to that same value and change `udp/51820` in `community-wireguard.json` to `udp/<your-port>`. The daemon, project setting, firewall rule, and remote peer configuration must all agree. File upload and final editor publication reject a Community WireGuard specification without an explicit public UDP listener rule on the project's configured port. The runtime repeats that check after firewall creation and refuses to make the endpoint ID resolvable if a legacy or subsequently changed specification does not match.

A remote peer can resolve the five-digit ID without Agoge authentication:

```http
GET https://api.agoge-class-a.example.edu/wireguard/endpoints/12345/
```

```json
{
  "data": {
    "id": "12345",
    "hostname": "wg-12345.agoge-class-a.vpn.example.edu.",
    "port": 51820,
    "status": "active"
  },
  "redirect": null
}
```

The resolver returns `404` while an endpoint is reserved, building, failed, or being removed. It publishes the mapping only after the gateway address, DNS record, routes, and Community firewall rules are ready, including a listener rule for the allocated endpoint port; a successful response therefore reports `active`.

The route is tagged `wireguard-client`, so it applies to each per-student Kali instance but not every VM in the VPC. The gateway's image must enable Linux IPv4 forwarding, configure WireGuard, and permit forwarding between the `external` NIC and the tunnel interface. Setting `can_ip_forward` enables forwarding at the Google Compute Engine layer; it does not configure the guest operating system.

The example permits UDP port 51820 from any public address because remote peers might have dynamic addresses. Restrict `ip_ranges` when peer egress addresses are known.

The `allow-wireguard-remote-to-kali` rule permits TCP, UDP, and ICMP traffic whose source remains inside `172.30.0.0/24` to reach only VMs tagged `wireguard-client`. Narrow its protocols and ports if the exercise does not require unrestricted traffic from the remote lab. If the gateway source-NATs tunnel traffic, use the translated source range instead.

This topology provides routed Layer 3 connectivity. A Google Cloud VPC does not provide a shared Ethernet broadcast domain, so exercises that require ARP, non-IP frames, broadcast, or multicast need a separate Layer 2 overlay inside the VMs.
