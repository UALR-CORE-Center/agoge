# Managed WireGuard remote labs

Instructors can build a managed Community Lab in either of two ways:

| Path | When to use it |
| --- | --- |
| **Lab Catalog → Build WireGuard Lab** | Build directly, choosing a student image in the dialog; no catalog upload is required. |
| Select an uploaded **WireGuard template** → **Build Lab** | Reuse a named catalog template with its student image already selected by the setup operator. Existing records may still be named **WireGuard Factory Lab**. |

Both paths create one shared Ubuntu WireGuard gateway, one shared Guacamole
proxy, one enrolled remote peer for a private remote LAN, and a workstation for
each student who claims the lab. No catalog JSON or network
configuration editing is needed.
Existing WireGuard catalog templates also require a registered remote peer when building
a new lab. The selected registration supplies the private LAN default. An
instructor can provide a per-Lab private LAN override; the backend validates its
RFC1918 CIDR and rejects overlaps with the student and WireGuard tunnel networks.

## Deploy this release

Deploy the Cloud Function, API, and frontend from this same revision. Through
`python setup.py`, **Application Installation and Updates → Update Main Application
and Cloud Functions** performs the WireGuard API/DNS preflight and shared app/API
routing setup. The gateway uses the official GCP image family
`ubuntu-os-cloud/ubuntu-2404-lts-amd64` on E2. A preconfigured WireGuard image is
not required. Ubuntu package repositories and Secret Manager must be reachable
from the gateway. A tenant API health callback is not required for bootstrap
or for lab build/start/stop completion.

The shared Guacamole VM uses the target project's TLS-enabled image,
`projects/<project>/global/images/image-guac-<project>`. Prepare it with
**Server Images & Build Specs → Refresh/Create guacamole image and certificate**
if that image or its certificate is missing. The embedded shared-proxy startup
code configures Guacamole/guacd 1.6.0 with JSON authentication; a student join
requires neither another image build nor a proxy restart.

The startup code is maintained in `common/services/wireguard_startup.py` and is
embedded directly in the Compute instance's `startup-script` metadata. It does
not fetch an application script from GitHub, a bucket, or another script URL.
OS packages are installed with apt. Configuration data is retrieved from Secret
Manager using the gateway's own metadata identity.

Required project settings remain `parent_project`, `parent_dnszone`,
`parent_dns_suffix`, `project_path`, `wireguard_dns_suffix`, and `wireguard_port`.
The preflight enables Compute, DNS, Secret Manager, and IAM APIs and checks the
public DNS zone and zone-scoped runtime DNS permission. Guest health reporting
is disabled by default. To enable optional telemetry for new lab configurations,
set `wireguard_health_reporting_enabled: true` in the environment document. Its
API callback defaults to `https://api.<parent_dns_suffix>/<project_path>`;
installations with another API origin can set `wireguard_api_url` to its HTTPS
base URL, including the tenant prefix. Optional reporting failures do not block
bootstrap or the GCP lifecycle.

The application runtime needs the existing Compute/Firestore/DNS permissions,
Secret Manager secret creation/version access/deletion and secret IAM policy
permissions, and service-account creation/get/delete/IAM policy permissions.
`roles/secretmanager.admin` and `roles/iam.serviceAccountAdmin` cover the new
management operations in installations that have replaced the historical broad
runtime role with restricted roles. The runtime is granted `actAs` on the
dedicated gateway and Guacamole accounts. The operator running setup needs
API-enable and DNS-zone IAM permissions. Do not grant secret access to
student VM identities.

Each gateway gets `agoge-wg-<unit ID>@<project>.iam.gserviceaccount.com` and read
access only to `agoge-wg-<unit ID>` in Secret Manager. Managed student VMs have
no attached service account. The shared Guacamole proxy gets
`agoge-guac-<unit ID>@<project>.iam.gserviceaccount.com`, scoped to its own
Guacamole signing-key secret; it cannot read the WireGuard key. Gateway private
keys, Guacamole signing keys, and health callback tokens never enter catalog/Unit
records or instance metadata. Retries reuse these identities; stop/start keeps
the keys and lab number. Successful deletion removes both shared VMs, deletes
their secrets/accounts, revokes the lease, and releases the remote peer.

## Register a remote lab and enroll its peer

1. Copy the bundled [`wireguard_pi`](../../build_files/server_config/wireguard_pi/README.md)
   directory to the Pi and run its local installer. It prints the Pi public key
   and retains its private key locally.
2. Open **Admins → Build Manager → Remote Labs** and select **Register a remote
   peer**. Optionally add its name and description, then enter a unique **Remote peer ID**, **Remote
   device identity**, **Remote LAN (IPv4 CIDR)**, **Remote peer WireGuard public
   key**, and **Authorized instructor emails**.
3. Save the one-time enrollment token in the root-only file on the Pi and set its
   API base URL, remote peer ID, and private LAN interface as described in the Pi guide.
4. Start the peer's bundled polling service. A remote peer can be assigned to only one lab
   at a time. The number/hostname identifies a lab; it is not a device credential.

The peer must already have an address on its registered private LAN. Remote devices need a
return route to the student subnet through the Pi, or the Pi poller can enable
scoped source NAT with `nat: true`. NAT applies only to authorized student-to-remote-LAN
traffic. The managed gateway's tunnel network is `10.254.254.0/30`; enrollment
and build validation reject overlaps. The backend selects a nonoverlapping
student subnet automatically.

The **Remote LAN (IPv4 CIDR)** field is the private network behind the remote
peer, for example `192.168.50.0/24`; it is not the public gateway address or the
WireGuard tunnel network. Register one RFC1918 subnet. Agoge derives the cloud
route and restricted forwarding policy from this value. For example, a Pi at
`192.168.50.2` can connect students to devices such as `192.168.50.10` on that LAN.
The registration does not assign those device addresses or change the remote
LAN's router configuration.

The enrollment/list API is **`GET`/`POST /wireguard/remote-peers/`**. Registration
uses `remote_network_cidr` for this subnet; a lab build selects `remote_peer_id`.
Existing `/wireguard/kits/` requests and the Pi client's `kit_id` setting remain
compatible with previous versions. In those older names, a "kit" means the
registered remote peer, not a different kind of network or credential.

### Edit registrations and saved Lab settings

An administrator can edit a remote lab's registration in the same inventory.
Registrations assigned to a Lab are protected against changes that would alter
that Lab's connection; use that Lab's instructor settings for an assignment or
network change. Enrollment tokens are not displayed again by editing.

Instructors can choose an available authorized remote lab and an optional private
LAN override in the build dialog. For an already built Lab, stop all student
Workouts and the gateway, then open **Remote lab settings** on its details card.
Save the selected peer and private LAN. The backend validates authorization,
exclusive assignment, expiration, and subnet overlap before changing records.
It saves a new configuration secret version while the gateway is stopped; the
next student start applies the saved configuration and reconciles its routes.
An update that races with a student start is rejected instead of altering an
active connection. The gateway's connection ID and hostname are retained.

This is a Lab-specific configuration. It does not change the administrator's
registered LAN default or assign addresses on the remote physical network.
See [the instructor steps](../guides/instructor-guide.md#change-the-remote-lab-for-an-existing-lab).

### Verify the student lifecycle locally

The CLI is packaged under `tools/debug_lab/`. From the repository root, run
`python -m tools.debug_lab student-lifecycle` with a two-student profile to build,
claim two Workouts, test first/last-student transitions for both shared VMs, and
confirm deletion. It verifies that there is exactly one Unit-owned Guacamole
proxy and reads both VMs' Compute Engine status at each stage. It does
not require a Pi or guest health callback. See the
[complete two-student instructions](local-backend-debugging.md#verify-two-students-and-automatic-gateway-startstop).

## Upload a starter template with setup.py

Use this optional setup action when you want the WireGuard lab to appear as a
normal reusable row in the selected site's Lab Catalog. The direct **Build
WireGuard Lab** shortcut remains available without this step.

The uploader was merged into `release/2027-spring` in [PR #16](https://github.com/UALR-CORE-Center/agoge/pull/16).
The remote-peer terminology and connection-ID changes described here are on
**`feature/local-backend-debug`** and have not been merged into the release.
Use that branch for this flow, including the API and frontend deployment.
Before running setup, stop any existing setup process and update your local
checkout from the repository root:

```sh
git status --short --branch
git fetch origin
git switch feature/local-backend-debug
git pull --ff-only origin feature/local-backend-debug
```

Preserve any local edits reported by `git status` before switching branches.
Restart `setup.py` after pulling; an already running process keeps the menu it
loaded at startup. The updated **Server Images & Build Specs** menu has
**7. Upload WireGuard Community Lab Template** and **10. Back to Main Menu**.
If **7** is still **Back to Main Menu**, the running process is using an older
checkout. In an IDE, check that its script path and source roots point to the
updated repository. GCP authentication, IAM permissions, and the selected
project do not control whether this menu option appears.

For repeated backend testing after uploading, use the
[local API/Cloud Function debug runner](local-backend-debugging.md). It can build
a lab and claim a student workout from the command line without deploying each
Python change.

1. Run `python setup.py` from the Agoge source revision deployed to the site.
2. Select the target environment. For the test environment, select project
   **`test-dev-787001`**. Confirm the project ID before continuing; selecting an
   environment controls where the catalog record is written.
3. Choose **Server Images & Build Specs → Upload WireGuard Community Lab
   Template**.
4. Select an existing checked-in Windows or Linux student image from the image records
   listed by setup. Setup checks the actual GCP source image for **READY** and
   **AMD64** after selection and stops without uploading if it is incompatible.
   The image must have a displayed SSH, RDP, or
   VNC connection with a username and password. Select the Agoge image record
   ID shown in the menu, which can differ from its underlying GCP image name.
   If none is listed, import or prepare the student image under **Teachers →
   Manage Servers**, check it in, and rerun this action. The gateway image does
   not need to be imported.
5. Enter the instructor's Agoge sign-in email. Setup defaults to the selected
   environment's `admin_email`; replace it to attribute the starter to another
   instructor. The site's catalog is shared among instructors; remote peer authorization
   still controls who can connect a lab to a particular remote LAN.
6. Accept the default catalog ID **`wireguard-factory-lab`**, or enter a new ID
   when you need a separate starter template. Wait for setup to confirm the
   selected project and saved catalog ID.
7. Open that site's frontend and refresh **Teachers → New Lab**. The starter
   appears under its uploaded template name. Existing records named **WireGuard
   Factory Lab** and the `wireguard-factory-lab` catalog ID remain valid; no
   rename or re-upload is required. For `project_path=test-dev`, the site
   entry point is `https://app.agoge-labs.com/test-dev/`.

The upload writes only the selected project's
`agoge-v1/catalog/<catalog ID>` Firestore document. It does not create a lab,
reserve a remote peer or number, start a VM, or configure the Pi. An identical rerun is
a no-op. A remote peer is required when building a lab, not when uploading its template.
Setup refuses to replace a different existing catalog document; choose
a new catalog ID if the template needs to coexist with an existing definition.
Existing uploaded templates continue to work without re-uploading for this
terminology change; their saved title and description are retained. New
templates use **WireGuard Remote Lab**.
Template connections remain in the site's catalog records, so do not export
production image passwords into a public repository.

### If a shared Windows image is not listed

Kali is only a preferred default; no specific image name or operating system is
required. An interactive Windows image such as `cybersecurity1` can be used with
RDP. The uploader first checks the records in the selected project's
`agoge-v1/image` collection, then verifies the selected Compute image in GCP.

Setup prints an eligibility line for every record, including the exact rejected
fields: missing `name`, a status other than checked-in `0`, an unpublished local
image, missing `human_interaction`, display disabled, unsupported protocol, or
missing username/password. It prints field names, not credential values.
`RDP`/`rdp` and numeric/text `0` are accepted. A single connection object and a
list of connections are both supported.

Legacy shared records with `image_exists: false` can still qualify when their
stored Compute reference identifies the published shared image itself. Setup
does not treat a new local template pointing at a base image as published. The
actual source must still pass the GCP READY/AMD64 check before upload.

Copying a Firestore record does not copy its Compute image. Preserve its source
reference (`self_link` or boot disk `initializeParams.sourceImage`) pointing to
the correct shared project, and use an identity that can read that image.
If eligibility fails, fix the indicated metadata through **Teachers → Manage
Servers** and complete check-in as needed. Do not clear credentials or change
the image's name simply to make it look like Kali.

### If the selected GCP image returns NotFound

Student Compute images can stay in **`agoge-shared-resources`** while the catalog
and lab VMs belong to **`test-dev-787001`**. The upload and built-in WireGuard API
builder first try the image source saved in the Agoge record. If it returns
NotFound, they automatically retry the **same GCP image name** in
`agoge-shared-resources`, including records with an explicit legacy site URL.
For example, a missing
`projects/ualr-agoge/global/images/image-csec3314-powershell` is retried as
`projects/agoge-shared-resources/global/images/image-csec3314-powershell`.

The resolved image must be READY and AMD64. Its returned full image URL is saved
in the catalog or lab specification, so workstations boot directly from the
published shared image. This requires no copy into the lab project and no manual
source selection when the shared image has the same name. Update the feature
branch and restart setup to get this behavior. Older revisions disabled the shared
retry whenever the record contained an explicit source URL.

If both lookups fail, setup offers image recovery. This also covers images
published under a different name or in another project:

1. When setup asks **Choose an existing GCP image for this catalog upload instead?**,
   enter **y**.
2. Enter the GCP project that actually contains your published student image.
   Press Enter to browse **`agoge-shared-resources`**, or enter another project ID.
   You can also paste an exact `projects/PROJECT/global/images/IMAGE` reference or
   full Compute image URL to select it directly without listing the project.
3. When browsing, setup lists only **READY AMD64** images. Choose the actual student
   image by its number or exact GCP image name. A blank selection returns to the
   project prompt; **cancel** stops the upload. If listing fails or the project has
   no compatible images, enter another project or an exact image reference.
4. Setup rechecks the selected image and prints the student boot source saved in
   the catalog, then completes the upload. Choose an image prepared with the saved
   Agoge template's username, password, and connection protocol. Selecting a different
   image does not configure accounts or enable RDP/SSH/VNC inside it.

Recovery uses the selected Compute image in this catalog only and copies the
student connection settings from the chosen Agoge template. It leaves the
`agoge-v1/image` records as saved, so other labs using those records are unaffected.
The catalog still uploads to the selected environment, such as `test-dev-787001`,
and the gateway still uses its default Ubuntu image. If the original server library
record also needs repair, use the steps below.

Using the same account selected in setup, verify the example shared source:

```powershell
gcloud compute images describe image-csec3314-powershell --project=agoge-shared-resources --format="yaml(name,status,architecture,selfLink)"
```

If the source is stale, find the actual published image in the project that owns
your student images. For example, to inspect the configured shared image project:

```powershell
gcloud compute images list --project=agoge-shared-resources --no-standard-images --format="table(name,status,architecture,selfLink)"
```

Use the returned image's exact name and `selfLink`; do not assume it matches the
Agoge record ID. To clean up the saved server-library metadata, update the selected project's
`agoge-v1/image/<student template ID>` record to reference that image. `self_link`
takes precedence, followed by an explicit `image` reference, then the boot disk's
`initializeParams.sourceImage`. Keep those references consistent and preserve
the student connection settings. If a local Compute image is not registered yet,
use **Server Images & Build Specs → Import Custom Images from GCP into App** in
its project, or prepare and check in the student image through Server Manager.

If an existing shared image cannot be read, check the setup account's access to
that image and that its Application Default Credentials use the intended identity.
The deployed backend identity also needs image access when building student VMs.
Automatic retry is limited to the configured shared project after a NotFound;
manually selected recovery references are used exactly as entered. These failures
occur before any catalog write. Using the updated local setup requires no Cloud
Run or Cloud Functions deployment. Deploy the updated API when using its built-in
WireGuard builder, or run it through the local backend debug runner.

References: Google's [image describe command](https://docs.cloud.google.com/sdk/gcloud/reference/compute/images/describe)
and [image list command](https://docs.cloud.google.com/sdk/gcloud/reference/compute/images/list).

## Build from the uploaded template

1. Sign in to the selected site's frontend using the instructor email supplied
   during upload. Confirm that the administrator has enrolled the remote peer and that
   its authorized-instructor list includes this account.
2. Open **Teachers → New Lab**. The page heading is **Lab Catalog**. Refresh the
   page if the newly uploaded template is not yet visible.
3. Select the checkbox for the uploaded WireGuard template, then click **Build
   Lab**. Older records may be named **WireGuard Factory Lab**. The template uses
   the student image chosen during upload.
4. In the dialog, select an available **Remote peer**. Each remote peer belongs to one
   lab at a time; an assigned, disabled, or unauthorized remote peer is unavailable.
5. Set **Expires** and **Max number of students**. For the first test, choose one
   student and a short future expiration; leave **Build with LMS** disabled.
6. Click the dialog's **Build Lab** button. Agoge opens the new lab's detail page
   and provisions the shared Ubuntu gateway. The selected remote peer's registered
   private LAN determines the route automatically.
7. Wait for the lab to reach **Ready** or **Running** after its GCP provisioning
   completes. Check the assigned remote peer, connection ID, lab number, DNS
   suffix, hostname, and UDP port. The Pi and a guest health callback are not
   required to complete this step. Before testing remote traffic, check guest
   startup and connect the enrolled Pi with its polling service running. A lab
   number or hostname alone does not demonstrate a working tunnel.
8. Copy the learner claim URL and join code from the lab detail page. Claim one
   test Workout, open its browser workstation, and verify that it can reach the
   assigned remote devices. Verify that another remote LAN is unreachable before
   distributing the lab to a class.

For example, upload `wireguard-factory-lab` into `test-dev-787001` with a
compatible student image selected in setup, then perform the frontend steps above
on the `test-dev` site. These are deployment instructions; a successful upload
and a successful physical remote LAN connection must each be verified in that
environment.

## Build directly without uploading a template

1. Open **Teachers → New Lab → Build WireGuard Lab**.
2. Select an available **Remote peer** and a **Student workstation image**.
   Choose a checked-in AMD64 student image with a password-based SSH/RDP/VNC
   display connection. If the registered Kali image is available it is selected
   by default; verify the selection before submitting.
3. Set **Expires** and **Max number of students**, then click **Build Lab**.
4. On lab details, complete the same gateway, remote tunnel, and test-student
   verification described above. This shortcut uses the same managed gateway
   provisioning as the catalog-template path.

## Endpoint and student behavior

Choose an available authorized remote peer, a checked-in AMD64 student image with a
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
remote peer, private LAN CIDR, and connection ID. Lab build/start/stop completion
uses successful GCP VM operations together with DNS, routes, and firewall setup;
it does not wait for guest health or a remote handshake. Ubuntu startup may still
be configuring WireGuard after the VM becomes running.

Separate **gateway service** and **remote tunnel** fields describe optional
telemetry, not the lab lifecycle. When enabled, service health checks the current
peer/interface, listener, and forwarding policy; tunnel health additionally checks
a recent handshake. Reports older than 120 seconds are stale. Reporting is
disabled by default, so missing or false telemetry does not block a built lab or
its connection details. The public resolver and authenticated Pi configuration
API continue to refuse stopped, expired, released, or incorrectly assigned
endpoints, without requiring guest health reports. The Pi configuration response
uses `gateway_ready` for this cloud lifecycle result; its `service_ready` and
`tunnel_ready` fields remain optional, fresh telemetry.

The **Connection ID** is the stable, non-secret identifier for this lab:
`<GCP project ID>:<unit ID>`, for example `test-dev-787001:abcdefghij`. The lab
details and debug status associate it with the gateway's current hostname and
DNS suffix. Stop/start keeps the same connection ID even if the public IP
changes. The five-digit gateway number can eventually be recycled after a lab
is deleted, so use the connection ID when referring to a particular lab.

The connection ID does not authenticate a remote peer and does not replace its
enrollment token. A shared HMI connection lookup or polling API is **not
implemented in this change**; that integration remains future work. The current
flow provides instructor-visible connection details and authenticated peer
configuration.

Students claim their normal Workouts and use the shared browser display proxy
to reach their own workstation. The community Lab owns one Guacamole VM,
regardless of student count. Each student receives a separate Guacamole identity
with only that Workout's connection; adding a student does not create another
proxy or restart Guacamole. The API supplies encrypted connection data through
Guacamole JSON authentication. Solo Workouts retain their own proxy and JDBC
authentication. JSON credentials allow new connections for at most two
minutes; deleted student IPs are held for five minutes before reuse.

After the initial community build, both shared VMs stop before the Lab becomes
READY. After an initial student build, its workstation stops before the Workout
becomes READY. The first active student starts the shared WireGuard and
Guacamole VMs together; later students reuse them. Both stop after the last
active student stops. Instructor Lab start/stop controls and Lab deletion also
include both shared VMs. Labs without configured packet mirroring do not create
or start packet collectors.

Routes select only approved student machines and point only
to the assigned private LAN. Gateway/Pi guest rules restrict tunnel forwarding;
the managed cloud rules isolate student machines and permit browser proxy access.
Stop/start refreshes endpoint addressing without reallocating its number. The Pi
refreshes DNS and disconnects on invalid/unavailable authorization rather than
retaining an unverified lease. This intentionally interrupts the tunnel during an
API outage.

## Migration and validation

Existing built labs retain their legacy image, static address, and unmanaged
behavior. Deploying this code does not modify running legacy gateways. Enroll the
remote peer and create a new managed lab to adopt Ubuntu startup provisioning. Existing
five-digit allocations are preserved until their normal lifecycle releases them.
Create a new community Lab to adopt the shared proxy; this deployment does not
convert existing per-Workout proxy VMs in place. New student claims on an older
Lab without the shared proxy require rebuilding the Lab.

Before deploying backend changes, run `python -m tools.functional_tests` from
the repository root. It checks community and solo lifecycle behavior without
GCP credentials. See [the functional runner](../../tools/functional_tests/README.md)
for its scope and focused suite options.

The automated reference flow in
`common/tests/test_wireguard_build_flow.py` exercises instructor creation, remote peer
assignment, cloud endpoint allocation, and authenticated Pi configuration with
fake Firestore/Secret Manager, including missing guest health. Optional telemetry
and current-boot authorization are covered separately. Additional tests cover actual
embedded-script parsing, restricted forwarding, concurrency, lifecycle retries,
HTTP authorization, proxy allocation, revocation, and UI forms. These are
repeatable local tests, not a claim of a live remote LAN connection.

Before closing issue #15, deploy a reference lab and record: the safe connection ID and lab number,
hostname and readiness screen; actual gateway Ubuntu source, empty student
service accounts, and the shared proxy's scoped identity;
`systemctl is-active wg-quick@wg0`; a recent handshake; successful Kali
access to its equipment; denied access to another remote LAN; and stop/start recovery
with updated DNS. Never attach `wg showconf`, private keys, tokens, or full secret
payloads to issue evidence. The dependency on agreed physical remote LAN addressing and
interfaces still applies to this hardware acceptance test.

A failed GCP operation or cloud dependency produces a build/lifecycle error.
Guest startup problems can be inspected independently with
`journalctl -u google-startup-scripts -u wg-quick@wg0`; check package repository
egress and Secret Manager IAM. Optional health callback failures, including HTTP
404 from an older API, do not fail a build. For an existing VM that still runs
the older reporter, `sudo systemctl disable --now agoge-wireguard-health.timer`
stops repeated callback errors. Pi diagnostics are in
`journalctl -u agoge-wireguard-pi`. Never mark telemetry healthy manually merely
because GCP reports the VM running.
