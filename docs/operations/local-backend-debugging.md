# Debug API and Cloud Function builds locally

Use `setup.py` for authentication, environment preparation, and uploading the
WireGuard Community Lab template. Use `python -m tools.debug_lab` for the repeated backend
build/debug loop. It runs the API's build logic and the Cloud Function entry
point in the same Python process, with synchronous worker execution enabled.
You can step from `api/core/` into `cloud_functions/` in your debugger without
building containers or deploying application revisions.

This is an integration test against **real GCP resources**, not a dry run.
The runner is limited to **`test-dev-787001`** and its **`agoge-v1`** Firestore
database. It explicitly sets the Python clients' project before importing the
application, so a previous gcloud project selection cannot redirect the build.

## Prepare once

1. Use a checkout containing the `tools/debug_lab/` package. These changes are on
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
   before building. Install/enroll the [Pi client](../../build_files/server_config/wireguard_pi/README.md)
   when the physical device is available; it is not required for the cloud lifecycle test.
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
.\venv\Scripts\python.exe -m tools.debug_lab enroll-peer `
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
Cloud Run, or Cloud Functions deployment. The Pi uses the HTTPS configuration
endpoint when it is available; gateway health reporting is optional.

List the peers visible to the instructor:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab list-peers --instructor pdhuff@ualr.edu
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
.\venv\Scripts\python.exe -m tools.debug_lab run-lab --profile .local/debug-lab/profile.json
```

An explicit command-line flag overrides its profile value. For example, test
with two workstations and a one-hour expiration:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab run-lab `
  --profile .local/debug-lab/profile.json --count 2 --expires-hours 1
```

The profile is a flat JSON object. Supported fields are `template`, `instructor`,
`remote_peer_id`, `count`, `expires_hours`, `student_email`, `project`, and
`wireguard_api_url`. The project remains limited to `test-dev-787001`; the API URL
normally comes from the environment. Use `wireguard_api_url` only for an optional
health-reporting HTTPS override, such as a public tunnel to a local API. Omit
`student_email` or set it to `null` to build only the shared gateway first.
Defaults remain one workstation, a two-hour expiration, and the
`wireguard-factory-lab` template when those fields are omitted.

The former `gateway_startup_timeout_seconds` profile field and
`--gateway-startup-timeout-seconds` flag are accepted for compatibility but are
deprecated and ignored. Gateway builds no longer wait for guest health reports.

Malformed JSON, unknown fields, invalid values, and missing instructor/peer
settings fail before cloud access. Relative file paths are resolved from the
directory where the command starts. The runner checks that the selected peer
exists, is enabled, is authorized for the instructor, and is unassigned before
provisioning. If that check fails, inspect `list-peers` or enroll the missing peer
with the administrator account. Peer enrollment data stays in the registration;
the profile only references its ID.

## Verify two students and automatic gateway start/stop

The debug tools live in `tools/debug_lab/`. Run them from the repository root
with `python -m tools.debug_lab`; there is no root `debug_lab.py` entry point.
For the full student-driven test, copy the two-student example:

```powershell
Copy-Item docs/examples/local-backend-debug/two-student-profile.example.json .local/debug-lab/two-student-profile.json
.\venv\Scripts\python.exe -m tools.debug_lab student-lifecycle --profile .local/debug-lab/two-student-profile.json
```

Edit the instructor, remote peer, and student email addresses in that local
profile first. It must contain two distinct `student_emails` and a `count` of at
least two. The emails identify test student Workouts; they do not need to be
separate browser sign-ins. The selected peer must be available and authorized.

The command prompts between stages and verifies the gateway's recorded state
and actual Compute Engine instance status:

| Stage | Expected shared gateway |
| --- | --- |
| Build the lab with no active students | Stopped |
| Claim both student Workouts | Stopped; each student's workstation and display proxy are also stopped before READY |
| Start the first student session | Running automatically |
| Start the second student session | Remains running |
| Stop the first student | Remains running for the second student |
| Stop the last student | Stops automatically |
| Confirm final deletion | Managed resources deleted and remote peer released |

This sequence uses student start/stop operations; it never starts or stops the
parent lab to force the expected gateway result. It checks GCP lifecycle state
without requiring the physical Pi, a WireGuard handshake, or a guest callback.
Each claim completes only after its student VMs and display proxy have stopped;
the debug flow also verifies their stopped/running records after each action.
Use the printed student Workouts to inspect the student API/Cloud Function path
in the debugger. Claiming a Workout and starting its session are separate
application operations.

To reuse your existing profile instead:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab student-lifecycle --profile .local/debug-lab/profile.json --count 2 --student-email wireguard-student-1@example.com --student-email wireguard-student-2@example.com --delete-recent
```

`--delete-recent` automatically cleans up matching recent test runs before the
new build; omit it to be prompted, or use `--skip-cleanup` to bypass that check.
Final deletion still requires confirmation. A failure or interruption preserves
the lab and prints its inspection and cleanup commands.

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

A managed WireGuard gateway is stopped automatically after its initial build
when no student sessions are active. The explicit lab start in this generic
runner exercises instructor controls. Use `student-lifecycle` below to verify
automatic first/last-student behavior without issuing any lab start/stop command. The runner also starts and stops the student workout explicitly so its
display proxy and lifecycle state are handled along with the shared gateway.
Omit `student_email` from the profile to exercise only the shared lab. Use
`--duration-hours 2` to set the workout's start duration; the default is two
hours, and values from 1 through 10 are supported.

Choose how to handle previous runs at the beginning:

```powershell
# Ask about recent labs, then prompt between lifecycle steps.
.\venv\Scripts\python.exe -m tools.debug_lab run-lab --profile .local/debug-lab/profile.json

# Delete matching recent labs automatically before building.
.\venv\Scripts\python.exe -m tools.debug_lab run-lab --profile .local/debug-lab/profile.json --delete-recent

# Skip the recent-lab check and begin the new build.
.\venv\Scripts\python.exe -m tools.debug_lab run-lab --profile .local/debug-lab/profile.json --skip-cleanup
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
Function for each test. GCP lifecycle completion does not require a guest
callback or a reachable WireGuard API; the [Pi configuration API](#pi-configuration-and-optional-health-use-https)
is needed only when testing the physical peer or optional telemetry.

## Create a lab and one student workout

Use `create-lab` when you want only the build step and will control the lab
separately. It also accepts `--profile .local/debug-lab/profile.json`.

Run from the repository root. Replace `remote-lab-01` with your enrolled remote peer ID
and the instructor email with its authorized Agoge account:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab create-lab `
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
.\venv\Scripts\python.exe -m tools.debug_lab create-workout `
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
| Run configuration | **Module name:** `tools.debug_lab` |
| Python interpreter | Your checkout's `venv\Scripts\python.exe` |
| Working directory | Your Agoge repository root |
| Parameters, full lifecycle | `run-lab --profile .local/debug-lab/profile.json` |
| Parameters, two students | `student-lifecycle --profile .local/debug-lab/two-student-profile.json` |
| Parameters, build only | `create-lab --profile .local/debug-lab/profile.json` |
| Parameters, existing lab | `create-workout --unit-id abcdefghij --student-email wireguard-test@example.com` |

Start with the IDE's **Debug** button. Useful breakpoint locations:

- `api/core/unit.py`: `Unit.build` and `Unit.commit`.
- `api/core/workout.py`: `Workout.build` and `_send_or_debug`.
- `tools/debug_lab/cli.py`: `invoke_local_worker` and `run_lab`.
- `cloud_functions/main.py`: `agoge_cloud_function`.
- `cloud_functions/handlers/build_handler.py`: `BuildHandler.route`.
- `cloud_functions/cloud_fn_utilities/course_objects/unit/community_unit.py`:
  `_build_unit`.
- `cloud_functions/cloud_fn_utilities/course_objects/compute/lab_server_manager.py`:
  gateway Compute operations, DNS, routes, and endpoint publication.
- `cloud_functions/cloud_fn_utilities/course_objects/workout/community_workout.py`:
  student provisioning.

No local HTTP API server or Pub/Sub emulator is needed for this path. It tests
the API's business logic directly; it does not exercise FastAPI authentication,
HTTP routing, Pub/Sub delivery/retries, or the deployed runtime's IAM identity.
Keep a deployed smoke test for those boundaries.

## Pi configuration and optional health use HTTPS

The local build/start/stop loop uses GCP APIs and does not need a guest health
callback. The gateway retrieves its WireGuard configuration from Secret Manager
using its attached identity; it does not need the tenant API to bootstrap.
Guest health reporting is disabled by default.

The physical Pi still polls the authenticated WireGuard configuration API when
it is online. To test that flow, deploy the current API once if its WireGuard
routes are missing, or run the API locally behind a reachable HTTPS tunnel.
A deployed frontend and Cloud Function are not required for subsequent local
CLI builds.

To debug the Pi HTTP endpoint locally:

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
   accepts. The tunnel must permit authenticated device requests.
3. Point the Pi client's `api_url` at that public API base URL. The local
   FastAPI application serves routes at the root, so a direct tunnel normally
   needs no `/test-dev` prefix. Include a prefix only if the tunnel maps it to
   the application.

Optional guest telemetry can be enabled explicitly for new lab configurations
with `wireguard_health_reporting_enabled: true` in the project environment.
Its callback base defaults to the project's deployed API; `wireguard_api_url`
can override it, including a tenant prefix when needed. A CLI override affects
only the local process, for example:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab `
  --wireguard-api-url https://your-debug-api.example.com `
  create-lab --instructor pdhuff@ualr.edu --remote-peer-id remote-lab-01
```

Enabling optional telemetry requires the health endpoint in that API. Its URL
is saved in the lab's configuration secret when the lab is created; changing a
local override does not repoint an existing configuration. Callback failures
remain diagnostic and do not fail the guest configuration or cloud lifecycle.
`localhost` cannot be the remote callback URL because the gateway would interpret
it as the gateway VM itself.

## Diagnose a failure before gateway VM creation

The Unit state `BUILDING_SERVERS` records the last build stage reached; it does
not prove that a VM is running. `status` also reports the gateway's own
`server_name`, `state`, and `state_name` under `gateway`. Bootstrap work such as
granting the gateway service account access to its configuration secret occurs
before VM creation. Check the worker error and gateway state for failures at
this stage; guest journal logs cannot diagnose a VM that has not started. A null
`health_timestamp` is normal when optional reporting is disabled.

An `InvalidArgument` error at this point can have several causes. A newly
created service account not yet recognized by Secret Manager IAM is one
possibility, rather than a conclusion from the exception class alone. The
[Google IAM creation guide](https://docs.cloud.google.com/iam/docs/service-accounts-create)
documents that a new account can take 60 seconds or more to become visible.
The secret-access grant retries only the specific response that identifies the
expected service account as nonexistent: at most eight attempts, with delays
of 1, 2, 4, 8, 16, 32, and 32 seconds (95 seconds total, plus request time).
Progress identifies the request operation, exception class, and attempt.
Other invalid requests and permission denials fail immediately.

`run-lab` failures and unexpected `unit-action` errors print repository-relative
frame locations for tracing the failing call. These diagnostics omit source
lines, local variables, and exception response bodies. Preserve the printed
lab ID and resume the existing build after correcting the cause. An explicit
local build retry can also recover a `BROKEN` managed WireGuard initial build.
Both the lab and lease must remain unexpired, its endpoint must still belong
to it in `reserved` or `error` state, and its named GCP networks/subnets must already exist.
Recovery reuses those networks and follows the normal gateway build/reconcile
path; it does not insert duplicate VPCs. It refuses expired, missing, or
ambiguous resources, runtime workouts, and servers already stopped or retiring.
An old deployed build message cannot trigger this debug-only recovery.

For an eligible retained lab:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab unit-action --unit-id uljrlxqhjm --action build
.\venv\Scripts\python.exe -m tools.debug_lab status --unit-id uljrlxqhjm
```

The command verifies persisted lab and server readiness before reporting
success; a worker returning while the lab remains `BROKEN` is a failure.
Use this resume command directly when preserving the retained lab. A
**No workout ID provided** warning on the shared-lab path does not require a
student workout. When the existing lab reaches
`READY` or `RUNNING`, create the student workout separately if the original run
failed before creating it:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab create-workout --unit-id uljrlxqhjm --student-email wireguard-test@example.com
```

If the lab has expired or you want to clean up and start again, run the full
sequence with recent-lab cleanup. The default expiration is two hours; use a
longer expiration for an extended debugging session:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab run-lab --profile .local/debug-lab/profile.json --delete-recent --expires-hours 4
```

This deletes matching recent test labs before creating a new one. Do not edit
Firestore states manually to bypass recovery checks. Use explicit
`delete-labs` for a retained lab outside the recent-cleanup window.

## GCP lifecycle completion and guest startup

A message such as **Successfully built server!** confirms that Compute Engine
created and started the VM. A managed lab completes its build after the GCP
operation and its DNS, routes, and firewall dependencies succeed, then stops an
idle managed gateway before marking the Lab ready. The first student session
starts that gateway again. Start and stop
complete from their GCP operations as well. The worker does not wait for guest
health, an HTTP callback, or a WireGuard handshake.

Ubuntu can continue installing packages and configuring WireGuard after GCP
reports the VM as running. The lab's lifecycle state describes cloud resources;
it does not establish that the guest or remote LAN is ready for traffic. Keep a
registered remote peer with a syntactically valid public key so the gateway has
a configuration to install. The Pi can stay offline for build/start/stop/delete
testing. Actual remote LAN traffic needs the device online with its matching
private key.

Inspect the cloud lifecycle and guest separately, for example:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab status --unit-id ksqxzoaisa
gcloud compute instances describe ksqxzoaisa-wireguard --project=test-dev-787001 --zone=us-central1-a --format="yaml(name,status)"
gcloud compute instances get-serial-port-output ksqxzoaisa-wireguard --project=test-dev-787001 --zone=us-central1-a --port=1
```

The `gateway.state_name`, lab state, and endpoint status track provisioning.
The `wireguard.service_ready`, `tunnel_ready`, `health_timestamp`, and related
fields are optional telemetry. With reporting disabled, false or null telemetry
is expected even for a successfully built lab; it does not block endpoint
publication or the Pi's authorized configuration lookup. Telemetry is never
filled with a fabricated healthy result simply because a VM is running.

For local guest troubleshooting, use an SSH terminal on the VM:

```bash
sudo journalctl -u google-startup-scripts -u wg-quick@wg0 --no-pager -n 100
sudo systemctl is-active wg-quick@wg0
```

`Finished wg-quick@wg0.service` confirms that the interface started. The systemd
warning that a unit file is **world-inaccessible** is informational and does not
prevent it from running. Leave configuration and credentials protected. Do not
print `wg showconf`, configuration secrets, or HTTP response bodies in shared
logs; those may expose credentials.

### Resume a lab blocked by an older health wait

The `ksqxzoaisa` startup log showed HTTP **404** at `health_callback`; the older
worker then waited for a report that the API could not accept. This was a
callback dependency, not evidence that GCP failed to start the VM.

Stop the old local worker/debugger, pull the current feature branch, and resume
the retained lab while its lease and lab remain unexpired:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab unit-action --unit-id ksqxzoaisa --action build
.\venv\Scripts\python.exe -m tools.debug_lab status --unit-id ksqxzoaisa
```

The retry reuses eligible existing resources and completes from their GCP
lifecycle. The default lab expiration is two hours; if this retained lab has
expired, clean it up and create a new one instead. The longer startup-timeout
flag from older instructions is no longer needed.

An existing VM may still have the older health timer installed. To stop its
repeated callback errors without rebuilding the VM, run inside that VM:

```bash
sudo systemctl disable --now agoge-wireguard-health.timer
```

A guest script from an older revision may have reported failure solely because
of that callback. Inspect `wg-quick@wg0` and the startup journal when testing
actual traffic. New bootstrap code disables health reporting by default and
keeps optional callback failures separate from configuration failures.

## Inspect, resume, and clean up

```powershell
# Read current lab, workout, and WireGuard status.
.\venv\Scripts\python.exe -m tools.debug_lab status --unit-id abcdefghij

# Resume an interrupted shared gateway/network build using the saved lab ID.
.\venv\Scripts\python.exe -m tools.debug_lab unit-action --unit-id abcdefghij --action build

# Start or stop the named student workout locally.
.\venv\Scripts\python.exe -m tools.debug_lab workout-action --workout-id klmnopqrst --action stop
.\venv\Scripts\python.exe -m tools.debug_lab workout-action --workout-id klmnopqrst --action start --duration-hours 2
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
.\venv\Scripts\python.exe -m tools.debug_lab list-labs --instructor pdhuff@ualr.edu

# Narrow the list to a registered remote peer.
.\venv\Scripts\python.exe -m tools.debug_lab list-labs --instructor pdhuff@ualr.edu --remote-peer-id remote-lab-01

# Include retained records for previously deleted labs.
.\venv\Scripts\python.exe -m tools.debug_lab list-labs --instructor pdhuff@ualr.edu --include-deleted
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
.\venv\Scripts\python.exe -m tools.debug_lab delete-labs --instructor pdhuff@ualr.edu --unit-id kuiatckhzm
```

The default is a preview: it validates and lists the selected labs without
deleting resources. Add **`--yes`** to execute the selected deletions:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab delete-labs --instructor pdhuff@ualr.edu --unit-id kuiatckhzm --yes
```

For several previous runs, repeat `--unit-id`. Replace the example IDs below with
IDs from your list:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab delete-labs `
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
.\venv\Scripts\python.exe -m tools.debug_lab unit-action --unit-id kuiatckhzm --action delete
```

Prefer `delete-labs` when cleaning up repeated runs because it checks the test-lab
scope and verifies completion. The listing/cleanup commands and lifecycle
checks run from the local checkout; using them requires no Cloud Run or Cloud
Functions deployment.

VM creation, Ubuntu package installation, guest startup, DNS, and the physical
WireGuard handshake still take their normal time. This loop removes container
build/deploy waits between Python edits; it does not emulate the guest OS or Pi.
For pure logic changes, run the hermetic tests before using GCP.
