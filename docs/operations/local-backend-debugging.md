# Debug API and Cloud Function builds locally

Use `setup.py` for authentication, environment preparation, and uploading the
WireGuard Community Lab template. Use `debug_lab.py` for the repeated backend
build/debug loop. It runs the API's build logic and the Cloud Function entry
point in the same Python process, with synchronous worker execution enabled.
You can step from `api/core/` into `cloud_functions/` in your debugger without
building containers or deploying application revisions.

This is an integration test against **real GCP resources**, not a dry run.
The runner is limited to **`test-dev-787001`** and its **`agoge-v1`** Firestore
database. It explicitly sets the Python clients' project before importing the
application, so a previous gcloud project selection cannot redirect the build.

## Prepare once

1. Use a checkout containing `debug_lab.py`. These changes are on
   `feature/local-backend-debug`, based on `release/2027-spring`, and have not
   been merged into the release. Fetch, switch to that branch, and pull its latest
   changes before running the commands below.
2. From the repository root, install the combined local dependencies into the
   interpreter used by your IDE. In PowerShell:

   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   Use the root requirements file for local execution; it includes the API,
   Cloud Function, and setup dependencies. The runner sets its own source paths,
   so you do not need to configure `PYTHONPATH` to run it.
3. Run `setup.py`, authenticate as your intended GCP operator, and select
   **test-dev**. This refreshes gcloud and Application Default Credentials.
   If you just completed setup successfully, reuse those credentials.
4. Upload the template using **Server Images & Build Specs → Upload WireGuard
   Community Lab Template**. The examples below use its default catalog ID,
   `wireguard-factory-lab`. See the [upload instructions](wireguard-provisioning.md#upload-a-starter-template-with-setuppy).
5. Have an existing Agoge instructor/admin account in test-dev and an enabled,
   unassigned remote peer authorized for that instructor. The CLI uses the actual user
   record and the usual remote peer authorization/lease checks; it does not invent an
   admin account. The Agoge instructor email can differ from the GCP operator.
   Use the [CLI enrollment flow below](#register-a-remote-peer-once), or register the
   private LAN under **Admins → Build Manager → Remote Labs**, including its
   **Remote LAN (IPv4 CIDR)** and authorized instructor emails. Routing comes from
   that saved registration.
6. Prepare the [project settings and permissions](wireguard-provisioning.md#deploy-this-release)
   and install/enroll the [Pi client](../../build_files/server_config/wireguard_pi/README.md).
   Running a build locally does not enable missing APIs or grant operator IAM
   permissions. Your local ADC identity performs the Compute, Firestore, Secret
   Manager, IAM, and shared DNS operations that the application normally performs.

## Register a remote peer once

Registration describes the physical remote network and is reused across lab builds.
A debug profile selects that registration by ID. Passing `--remote-peer-id` or
the older `--kit-id` does not register a device. A missing-peer error such as the
one for `factory-kit-01` means that ID has no enabled registration in the selected
environment.

From the repository root, create local copies of the checked-in examples:

```powershell
New-Item -ItemType Directory -Force .local/debug-lab | Out-Null
Copy-Item docs/examples/local-backend-debug/remote-peer.example.json .local/debug-lab/remote-peer.json
Copy-Item docs/examples/local-backend-debug/debug-profile.example.json .local/debug-lab/profile.json
```

The `.local/debug-lab/` directory is ignored by Git. Edit `remote-peer.json` using
the actual remote network and device:

```json
{
  "id": "remote-lab-01",
  "device_id": "remote-lab-01-pi",
  "remote_network_cidr": "192.168.50.0/24",
  "peer_public_key": "REPLACE_WITH_DEVICE_WIREGUARD_PUBLIC_KEY",
  "authorized_instructors": ["pdhuff@ualr.edu"]
}
```

- `id` is the registered remote peer ID used by the debug profile and Pi client.
  You can retain an existing name such as `factory-kit-01`; use the exact same ID
  in the profile and device configuration.
- `device_id` identifies this physical device and must be unique.
- `remote_network_cidr` is its actual private IPv4 LAN, with a network address
  such as `192.168.50.0/24`. It must not overlap the student or tunnel networks.
- Replace the public-key placeholder with the device's WireGuard public key.
  The [Pi installer](../../build_files/server_config/wireguard_pi/README.md) creates
  and retains the private key on the Pi and prints its public key. The placeholder
  deliberately fails validation until replaced.
- `authorized_instructors` contains the Agoge sign-in emails allowed to select
  this peer. The example authorizes `pdhuff@ualr.edu`.

Enroll it with an existing **Agoge administrator** account:

```powershell
.\venv\Scripts\python.exe debug_lab.py enroll-peer `
  --admin pdhuff@ualr.edu `
  --spec .local/debug-lab/remote-peer.json `
  --token-out .local/debug-lab/remote-lab-01.token
```

Replace `--admin` if your Agoge administrator uses another email. GCP operator
credentials and an Agoge administrator account serve different purposes; the
command checks the Agoge account's administrator permission as well as using
your local ADC for database access.

Enrollment creates the registration once. An existing peer ID, device identity,
or public key produces a conflict; enrollment does not overwrite or refresh an
existing registration. The command creates no lab or VM. Your run profile and
subsequent builds reuse the saved peer's LAN and authorization settings.

The one-time enrollment token is written to the new `--token-out` file with
owner-only access. Existing output files are never overwritten. Normal command
output contains safe peer metadata and the token file path, not the token.
Transfer the token securely to the Pi's protected token file as described in the
[Pi bootstrap instructions](../../build_files/server_config/wireguard_pi/README.md).
Keep private keys and enrollment tokens outside profiles, catalogs, and source
control. Enrollment/list/profile commands run locally and require no frontend,
Cloud Run, or Cloud Functions deployment; the device and gateway still use the
HTTPS endpoints described below.

List the peers visible to the instructor:

```powershell
.\venv\Scripts\python.exe debug_lab.py list-peers --instructor pdhuff@ualr.edu
```

The result includes registered IDs, private LANs, enabled state, and current lab
assignments, without device tokens or private keys. Choose an enabled,
unassigned peer authorized for the instructor. A peer is assigned to one lab at
a time; deleting the old lab releases it for a subsequent test.

## Reuse a JSON debug profile

Edit `.local/debug-lab/profile.json` to select the registered peer and the
settings for each test build:

```json
{
  "project": "test-dev-787001",
  "template": "wireguard-factory-lab",
  "instructor": "pdhuff@ualr.edu",
  "remote_peer_id": "remote-lab-01",
  "count": 1,
  "expires_hours": 2,
  "student_email": "wireguard-test@example.com"
}
```

For the repeated build/start/stop/delete loop, run the profile interactively:

```powershell
.\venv\Scripts\python.exe debug_lab.py run-lab --profile .local/debug-lab/profile.json
```

An explicit command-line flag overrides its profile value. For example, test
with two workstations and a one-hour expiration:

```powershell
.\venv\Scripts\python.exe debug_lab.py run-lab `
  --profile .local/debug-lab/profile.json --count 2 --expires-hours 1
```

The profile is a flat JSON object. Supported fields are `template`, `instructor`,
`remote_peer_id`, `count`, `expires_hours`, `student_email`, `project`, and
`wireguard_api_url`. The latter two are optional: the project remains limited
to `test-dev-787001`, and the API URL normally comes from the environment.
Use `wireguard_api_url` only for an HTTPS callback override, such as a public
tunnel to the local API. Omit `student_email` or set it to `null` to build only
the shared gateway first. Defaults remain one workstation, a two-hour expiration,
and the `wireguard-factory-lab` template when those fields are omitted.

Malformed JSON, unknown fields, invalid values, and missing instructor/peer
settings fail before cloud access. Relative file paths are resolved from the
directory where the command starts. The runner checks that the selected peer
exists, is enabled, is authorized for the instructor, and is unassigned before
provisioning. If that check fails, inspect `list-peers` or enroll the missing peer
with the administrator account. Peer enrollment data stays in the registration;
the profile only references its ID.

## Run an interactive lifecycle

`run-lab` uses the same profile and lab settings as `create-lab`, then guides
you through a complete test in one debugger session:

1. List recent test labs for the **same instructor and remote peer**, then ask
   whether to delete them before building. The default window is the last
   **24 hours**, based on each lab's creation time. Completed deletions are
   excluded; older records marked deleted with incomplete cleanup can be retried.
   Stop any other build/debugger using those labs before approving deletion.
2. Build the new shared lab and its optional student workout. The new lab ID is
   printed as soon as it is saved, before VM provisioning.
3. Prompt to **start** the lab and the student workout created by this run.
4. Prompt to **stop** that workout and the lab.
5. Prompt to **delete** the new lab and its managed resources, then verify
   cleanup and release of the remote peer's assignment.

At the start and stop prompts, press **Enter** or answer `y` to continue.
Answering `n` or `q` ends the sequence and keeps the lab for inspection.
Deletion prompts default to **No**: answer `y` to delete. Declining the initial
recent-lab cleanup continues to the new build; declining the final deletion
keeps the new lab. Answer `q` at the initial cleanup prompt to cancel before
building anything.

A fresh build already starts its VMs. The first explicit start tests the start
lifecycle path for an already running lab and may skip the Compute Engine start
request. The runner also starts and stops the student workout explicitly so its
display proxy and lifecycle state are handled along with the shared gateway.
Omit `student_email` from the profile to exercise only the shared lab. Use
`--duration-hours 2` to set the workout's start duration; the default is two
hours, and values from 1 through 10 are supported.

Choose how to handle previous runs at the beginning:

```powershell
# Ask about recent labs, then prompt between lifecycle steps.
.\venv\Scripts\python.exe debug_lab.py run-lab --profile .local/debug-lab/profile.json

# Delete matching recent labs automatically before building.
.\venv\Scripts\python.exe debug_lab.py run-lab --profile .local/debug-lab/profile.json --delete-recent

# Skip the recent-lab check and begin the new build.
.\venv\Scripts\python.exe debug_lab.py run-lab --profile .local/debug-lab/profile.json --skip-cleanup
```

`--delete-recent` and `--skip-cleanup` are mutually exclusive. They control only
the initial cleanup; prompts between build, start, stop, and final deletion
remain. Add `--recent-hours 48` to include matching labs created in the last
48 hours; the supported window is more than zero and at most 168 hours. These
controls are command-line options, not JSON profile fields. Even for an
administrator, the automatic selection stays within the selected instructor's
test labs and selected peer in test-dev. Review other or older runs with
[the explicit listing/cleanup commands below](#list-and-delete-previous-debug-runs).
A peer assigned to an older lab still needs that lab cleaned up before reuse.

If pre-build cleanup fails, the new build does not begin. A failed build,
interrupted operation, or declined lifecycle step leaves the new lab available
for debugging; the runner does not delete it unconditionally on exit. Keep the
printed ID, inspect it with `status`, and use `delete-labs` when finished.
The sequence runs from the local checkout without deploying the API or Cloud
Function for each test. Gateway callbacks still need the
[reachable HTTPS API described below](#gateway-health-and-pi-configuration-still-use-https).

## Create a lab and one student workout

Use `create-lab` when you want only the build step and will control the lab
separately. It also accepts `--profile .local/debug-lab/profile.json`.

Run from the repository root. Replace `remote-lab-01` with your enrolled remote peer ID
and the instructor email with its authorized Agoge account:

```powershell
.\venv\Scripts\python.exe debug_lab.py create-lab `
  --template wireguard-factory-lab `
  --instructor pdhuff@ualr.edu `
  --remote-peer-id remote-lab-01 `
  --count 1 `
  --expires-hours 2 `
  --student-email wireguard-test@example.com
```

The runner:

1. Calls `Unit.build(..., debug=True)` in the local API code to create a test lab,
   reserve the remote peer/endpoint, and prepare its secret.
2. Invokes `cloud_functions.main.agoge_cloud_function(..., debug_mode=True)`
   locally to provision the shared gateway and network. Nested build/control
   operations use their synchronous debug paths.
3. Calls `Workout.build` in the local API code with an explicitly injected
   local dispatcher. The normal join-code, student reuse, and capacity logic
   runs, followed by the Cloud Function code that creates the student workout.

The lab ID is printed immediately after its record is saved, before provisioning
begins. Copy it for status, retries, and cleanup. The final output includes
workout ID/state and WireGuard status, without printing configuration secrets.
`--student-email` is optional: omit it to debug the gateway build first. The
student email identifies a claimed workout; it does not send an invitation.

Use `--remote-peer-id` to select the enrolled remote peer. The older `--kit-id`
flag remains an alias for existing commands. The catalog ID
`wireguard-factory-lab` remains unchanged; an older uploaded template may still
be labeled **WireGuard Factory Lab**.

## Claim another workout on an existing lab

After the lab reaches `READY` or `RUNNING`:

```powershell
.\venv\Scripts\python.exe debug_lab.py create-workout `
  --unit-id abcdefghij `
  --student-email wireguard-test@example.com
```

Replace `abcdefghij` with your lab's ten-letter ID. The same student email
reuses its existing workout. To create another workout, increase the lab's
capacity as needed and use another email. This command also works with a lab
created through the frontend in test-dev.

## Set breakpoints in PyCharm

Create a **Python** run/debug configuration:

| Field | Value |
| --- | --- |
| Script path | Your checkout's `debug_lab.py` |
| Python interpreter | Your checkout's `venv\Scripts\python.exe` |
| Working directory | Your Agoge repository root |
| Parameters, full lifecycle | `run-lab --profile .local/debug-lab/profile.json` |
| Parameters, build only | `create-lab --profile .local/debug-lab/profile.json` |
| Parameters, existing lab | `create-workout --unit-id abcdefghij --student-email wireguard-test@example.com` |

Start with the IDE's **Debug** button. Useful breakpoint locations:

- `api/core/unit.py`: `Unit.build` and `Unit.commit`.
- `api/core/workout.py`: `Workout.build` and `_send_or_debug`.
- `debug_lab.py`: `invoke_local_worker`.
- `cloud_functions/main.py`: `agoge_cloud_function`.
- `cloud_functions/handlers/build_handler.py`: `BuildHandler.route`.
- `cloud_functions/cloud_fn_utilities/course_objects/unit/community_unit.py`:
  `_build_unit`.
- `cloud_functions/cloud_fn_utilities/course_objects/compute/lab_server_manager.py`:
  gateway build/start and health wait.
- `cloud_functions/cloud_fn_utilities/course_objects/workout/community_workout.py`:
  student provisioning.

No local HTTP API server or Pub/Sub emulator is needed for this path. It tests
the API's business logic directly; it does not exercise FastAPI authentication,
HTTP routing, Pub/Sub delivery/retries, or the deployed runtime's IAM identity.
Keep a deployed smoke test for those boundaries.

## Gateway health and Pi configuration still use HTTPS

The gateway guest and physical Pi cannot call into your debugger process
directly. By default, gateway health posts and Pi polling use the project's
deployed HTTPS API. That API must contain the WireGuard health/configuration
endpoints from the managed WireGuard feature. Deploy **the API once** if those
endpoints are missing; a deployed frontend and Cloud Function are not required
for subsequent local CLI builds.

To debug those HTTP endpoints locally too:

1. Start the local FastAPI application in a second IDE configuration, or in
   PowerShell from the repository root:

   ```powershell
   $env:GOOGLE_CLOUD_PROJECT = "test-dev-787001"
   $env:GCLOUD_PROJECT = "test-dev-787001"
   $env:PYTHONPATH = "$PWD;$PWD\api;$PWD\cloud_functions"
   $env:DEVELOPMENT = "True"
   .\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```

2. Expose port 8000 through a reachable HTTPS tunnel. Configure the tunnel to
   forward the Host header as `localhost` or `127.0.0.1`, which the local app
   accepts. The tunnel must permit authenticated device/guest POST/GET requests.
3. Start a **new** lab with the public URL as a global argument, for example:

   ```powershell
   .\venv\Scripts\python.exe debug_lab.py `
     --wireguard-api-url https://your-debug-api.example.com `
     create-lab --instructor pdhuff@ualr.edu --remote-peer-id remote-lab-01
   ```

4. Point the Pi client's `api_url` at the same public API base URL. The local
   FastAPI application serves routes at the root, so a direct tunnel normally
   needs no `/test-dev` prefix. Include a prefix only if the tunnel actually
   maps it to the application.

This override changes the local build's environment only; it does not edit the
project's environment document. A gateway's callback URL is fixed in its secret
when its lab is created. Changing the URL later does not repoint an existing
gateway. Keep the tunnel/API running during the build and test. `localhost`
cannot be used as the callback URL because the gateway would interpret it as
the gateway VM itself. Breakpoints in the HTTP callback handler can delay the
gateway readiness check; continue promptly or expect a timeout.

## Tell startup progress from a stalled health callback

A message such as **Successfully built server!** confirms that Compute Engine
created the VM. Ubuntu can still be installing packages and configuring WireGuard.
The managed gateway then waits for a fresh, authenticated **service health** report.
This wait is bounded to 60 checks with five seconds between checks: about five
minutes plus database/request latency. Progress messages at the start, about every
30 seconds, and on success or timeout identify what the worker is waiting for.

The service-health check does not require a WireGuard handshake. An offline Pi or
a temporary peer public key can leave `tunnel_ready` false while gateway service
health succeeds. Repeated reads of the same lab document after VM creation mean
the worker is polling for that health report; they do not show a stalled GCP VM
creation operation.

In a separate terminal, inspect the current run. For the example lab
`kuiatckhzm`:

```powershell
.\venv\Scripts\python.exe debug_lab.py status --unit-id kuiatckhzm
gcloud compute instances get-serial-port-output kuiatckhzm-wireguard --project=test-dev-787001 --zone=us-central1-a --port=1
```

Read the `wireguard` status fields together:

| Status | What to inspect next |
| --- | --- |
| `health_timestamp` is null | No health report has been accepted for this boot. Check guest startup, Secret Manager access, and the configured HTTPS health endpoint. |
| A report exists, but `service_ready` is false | Inspect `health_error` and guest service logs. The callback reached the API, but the guest is not reporting a healthy service. |
| `health_age_seconds` keeps increasing | Check the guest health timer and API/network connectivity; an old successful report cannot establish current readiness. |
| `service_ready` is true with fresh health, but `tunnel_ready` is false | The gateway service is ready. Check the remote device, its actual public key, polling configuration, and connectivity for the tunnel test. |

Inside the gateway, inspect the startup and health service logs:

```bash
sudo journalctl -u google-startup-scripts -u wg-quick@wg0 -u agoge-wireguard-health --no-pager -n 100
```

The guest needs a reachable API containing
`POST /wireguard/gateways/<unit-id>/health/` at its configured API base URL.
Running the build locally does not serve this endpoint to the VM. Check the
[HTTPS setup above](#gateway-health-and-pi-configuration-still-use-https) if the
deployed API is older or you want callbacks to reach your local debugger.
After a timeout, keep the lab ID for inspection or cleanup rather than creating
another run immediately.

## Inspect, resume, and clean up

```powershell
# Read current lab, workout, and WireGuard status.
.\venv\Scripts\python.exe debug_lab.py status --unit-id abcdefghij

# Resume an interrupted shared gateway/network build using the saved lab ID.
.\venv\Scripts\python.exe debug_lab.py unit-action --unit-id abcdefghij --action build

# Start or stop the named student workout locally.
.\venv\Scripts\python.exe debug_lab.py workout-action --workout-id klmnopqrst --action stop
.\venv\Scripts\python.exe debug_lab.py workout-action --workout-id klmnopqrst --action start --duration-hours 2
```

Status includes `remote_peer_id`, `remote_network_cidr`, and the non-secret
`connection_id` (`<project>:<unit-id>`), together with the current gateway
hostname/DNS details and readiness. For example, `test-dev-787001:abcdefghij`
continues to identify the same lab after a gateway restart changes its public
IP. This identifier is not a device credential. A shared HMI lookup/polling API
is deferred; the status command does not implement that future integration.

Stopping at a breakpoint or receiving an exception leaves existing resources in
place for inspection. Status lists workout IDs even if a build failed before
returning one. Use `workout-action --action build` with that ID to resume an
incomplete student build. Delete the lab when finished so its remote peer is released.
The normal Cloud Function budget check also applies to the local entry point;
budget blocks and provisioning failures are surfaced to the debugger. Deletion
remains available when the budget guard blocks builds or other operations.

## List and delete previous debug runs

The runner creates labs with `test: true`. List the test labs accessible to your
Agoge instructor/admin account, including runs created by earlier versions of
the CLI:

```powershell
.\venv\Scripts\python.exe debug_lab.py list-labs --instructor pdhuff@ualr.edu

# Narrow the list to a registered remote peer.
.\venv\Scripts\python.exe debug_lab.py list-labs --instructor pdhuff@ualr.edu --remote-peer-id remote-lab-01

# Include retained records for previously deleted labs.
.\venv\Scripts\python.exe debug_lab.py list-labs --instructor pdhuff@ualr.edu --include-deleted
```

The output shows lab IDs, names, states, creation/expiration timestamps, instructor
ownership, and remote peer IDs. It omits credentials and normally hides deleted
labs. Administrators can inspect other instructors' test labs; instructors see
their own. The `test` flag also covers test labs created outside this CLI, so
review the IDs before selecting a cleanup target.
Use `--include-deleted` to find older runs marked deleted before their remote
peer assignment was released; those IDs can also be selected for retry.

Stop the local build/debugger for a lab before deleting it. Preview deletion of
the example run:

```powershell
.\venv\Scripts\python.exe debug_lab.py delete-labs --instructor pdhuff@ualr.edu --unit-id kuiatckhzm
```

The default is a preview: it validates and lists the selected labs without
deleting resources. Add **`--yes`** to execute the selected deletions:

```powershell
.\venv\Scripts\python.exe debug_lab.py delete-labs --instructor pdhuff@ualr.edu --unit-id kuiatckhzm --yes
```

For several previous runs, repeat `--unit-id`. Replace the example IDs below with
IDs from your list:

```powershell
.\venv\Scripts\python.exe debug_lab.py delete-labs `
  --instructor pdhuff@ualr.edu `
  --unit-id kuiatckhzm `
  --unit-id abcdefghij `
  --yes
```

Every selected lab must belong to `test-dev-787001`, have `test: true`, and be
accessible to the actual Agoge account. The command checks all selected IDs
before starting any deletion and does not select additional labs automatically.
It runs the normal synchronous lifecycle cleanup for student workouts, VMs,
routes, DNS, firewall rules, VPCs, and managed WireGuard resources. The remote
peer's registration remains available; a completed cleanup releases its lab
assignment for the next run.

The result reports each lab separately. Success requires the lab to reach
`DELETED`, its managed lease to be released, and its peer/endpoint to be released
from that lab. A worker returning without completing those steps is reported as
incomplete; partial failures return exit code 1 and can be retried with the same
selected IDs. Already completed deletions are safe to repeat. Lab records and
released endpoint tombstones remain for lifecycle tracking and endpoint reuse
quarantine; cleanup does not purge them or remove Firestore records directly.

The existing lower-level command remains available and starts deletion immediately:

```powershell
.\venv\Scripts\python.exe debug_lab.py unit-action --unit-id kuiatckhzm --action delete
```

Prefer `delete-labs` when cleaning up repeated runs because it checks the test-lab
scope and verifies completion. The listing/cleanup commands and updated wait
messages run from the local checkout; using them requires no Cloud Run or Cloud
Functions deployment.

VM creation, Ubuntu package installation, guest startup, DNS, and the physical
WireGuard handshake still take their normal time. This loop removes container
build/deploy waits between Python edits; it does not emulate the guest OS or Pi.
For pure logic changes, run the hermetic tests before using GCP.
