# Managed WireGuard factory labs

The instructor's **Lab Catalog → Build WireGuard Lab** action creates a Community
Lab with one shared Ubuntu gateway, one enrolled factory kit, and a selected
student server image. No catalog JSON or network configuration editing is needed.
Existing WireGuard catalog templates also require a registered kit when building
a new lab. The backend derives the equipment route from that kit's enrollment;
browser-supplied routes cannot substitute another factory network.

## Deploy this release

Deploy the Cloud Function, API, and frontend from this same revision. Through
`python setup.py`, **Application Installation and Updates → Update Main Application
and Cloud Functions** performs the WireGuard API/DNS preflight and shared app/API
routing setup. The gateway uses the official GCP image family
`ubuntu-os-cloud/ubuntu-2404-lts-amd64` on E2. A preconfigured WireGuard image is
not required. Ubuntu package repositories, Secret Manager, and the tenant HTTPS
API must be reachable from the gateway.

The startup code is maintained in `common/services/wireguard_startup.py` and is
embedded directly in the Compute instance's `startup-script` metadata. It does
not fetch an application script from GitHub, a bucket, or another script URL.
OS packages are installed with apt. Configuration data is retrieved from Secret
Manager using the gateway's own metadata identity.

Required project settings remain `parent_project`, `parent_dnszone`,
`parent_dns_suffix`, `project_path`, `wireguard_dns_suffix`, and `wireguard_port`.
The preflight enables Compute, DNS, Secret Manager, and IAM APIs and checks the
public DNS zone and zone-scoped runtime DNS permission. API callbacks default to
`https://api.<parent_dns_suffix>/<project_path>`; installations with another API
origin can set `wireguard_api_url` in their environment document to its HTTPS base
URL, including the tenant prefix.

The application runtime needs the existing Compute/Firestore/DNS permissions,
Secret Manager secret creation/version access/deletion and secret IAM policy
permissions, and service-account creation/get/delete/IAM policy permissions.
`roles/secretmanager.admin` and `roles/iam.serviceAccountAdmin` cover the new
management operations in installations that have replaced the historical broad
runtime role with restricted roles. The runtime is granted `actAs` on each
dedicated gateway account, not on arbitrary accounts. The operator running setup
needs API-enable and DNS-zone IAM permissions. Do not grant secret access to
student VM identities.

Each gateway gets `agoge-wg-<unit ID>@<project>.iam.gserviceaccount.com` and read
access only to `agoge-wg-<unit ID>` in Secret Manager. Managed students and their
display proxies have no attached service account. Gateway private keys and health
callback tokens never enter catalog/Unit records or instance metadata. Retries
reuse the gateway identity; stop/start keeps its key and lab number. Successful
deletion revokes the lease, releases the kit, and deletes its secret/account.

## Enroll a kit once

1. Copy the bundled [`wireguard_pi`](../../build_files/server_config/wireguard_pi/README.md)
   directory to the Pi and run its local installer. It prints the Pi public key
   and retains its private key locally.
2. Open **Admin → WireGuard Kits**. Register a unique kit ID, device identity,
   RFC1918 equipment subnet, Pi public key, and authorized instructor emails.
3. Save the one-time enrollment token in the root-only file on the Pi and set its
   API base URL, kit ID, and equipment interface as described in the Pi guide.
4. Start the Pi's bundled polling service. A kit can be assigned to only one lab
   at a time. The number/hostname identifies a lab; it is not a device credential.

The Pi must already have an address on its equipment subnet. Equipment needs a
return route to the student subnet through the Pi, or the Pi poller can enable
scoped source NAT with `nat: true`. NAT applies only to authorized student-to-kit
traffic. The managed gateway's tunnel network is `10.254.254.0/30`; enrollment
and build validation reject overlaps. The backend selects a nonoverlapping
student subnet automatically.

## Instructor and student flow

Choose an available authorized kit, a checked-in AMD64 student image with a
password-based SSH/RDP/VNC display connection, student count, and expiration.
The default image selection is the registered Kali image when available. Import
and check in a student image through Server Manager if none exists; the gateway
itself always boots the official Ubuntu image.

The allocator transaction selects the first free number at its cursor, wraps at
99999 to 10000, and skips occupied or quarantined numbers. New hostnames are
`wg<number>.<GCP project ID>.<configured WireGuard suffix>`. The effective
environment suffix includes the immutable project ID, preventing collisions when
multiple tenants share a DNS zone. Existing allocated hostnames remain unchanged.
The public IPv4 address is ephemeral; build/start republishes its current address.

Lab details show the number, effective DNS suffix, endpoint, UDP port, assigned
kit, and separate **gateway service** and **Pi tunnel** readiness. Gateway service
readiness means the current boot has configured the correct peer/interface,
listener, and forwarding policy. Tunnel readiness additionally requires a recent
WireGuard handshake; an offline Pi does not block creating the lab. Health older
than 120 seconds is stale. The public resolver and authenticated Pi configuration
API refuse stopped, expired, released, or stale managed endpoints.

Students claim their normal workouts and use the browser display proxy to reach
their workstation. Routes select only approved student machines and point only
to the assigned kit network. Gateway/Pi guest rules restrict tunnel forwarding;
the managed cloud rules isolate student machines and permit browser proxy access.
Stop/start refreshes endpoint addressing without reallocating its number. The Pi
refreshes DNS and disconnects on invalid/unavailable authorization rather than
retaining an unverified lease. This intentionally interrupts the tunnel during an
API outage.

## Migration and validation

Existing built labs retain their legacy image, static address, and unmanaged
behavior. Deploying this code does not modify running legacy gateways. Enroll the
kit and create a new managed lab to adopt Ubuntu startup provisioning. Existing
five-digit allocations are preserved until their normal lifecycle releases them.

The automated reference flow in
`common/tests/test_wireguard_build_flow.py` exercises instructor creation, kit
assignment, cloud endpoint allocation, current-boot health, and authenticated Pi
configuration with fake Firestore/Secret Manager. Additional tests cover actual
embedded-script parsing, restricted forwarding, concurrency, lifecycle retries,
HTTP authorization, proxy allocation, revocation, and UI forms. These are
repeatable local tests, not a claim of a live factory connection.

Before closing issue #15, deploy a reference lab and record: the safe lab number,
hostname and readiness screen; actual VM Ubuntu source and empty student service
accounts; `systemctl is-active wg-quick@wg0`; a recent handshake; successful Kali
access to its equipment; denied access to another kit; and stop/start recovery
with updated DNS. Never attach `wg showconf`, private keys, tokens, or full secret
payloads to issue evidence. The dependency on agreed physical kit addressing and
interfaces still applies to this hardware acceptance test.

A gateway that cannot report healthy within five minutes produces an actionable
build error. Inspect `journalctl -u google-startup-scripts -u wg-quick@wg0
-u agoge-wireguard-health` on the gateway. Check public egress, Secret Manager
IAM, the tenant callback URL, and package installation. Pi diagnostics are in
`journalctl -u agoge-wireguard-pi`. Resolve the error and retry; do not mark a
gateway healthy manually.
