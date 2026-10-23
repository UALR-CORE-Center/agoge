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
   Administrators register the private LAN under **Admins → Build Manager →
   Remote Labs**, including its **Remote LAN (IPv4 CIDR)** and authorized
   instructor emails. The CLI derives routing from that registration.
6. Prepare the [project settings and permissions](wireguard-provisioning.md#deploy-this-release)
   and install/enroll the [Pi client](../../build_files/server_config/wireguard_pi/README.md).
   Running a build locally does not enable missing APIs or grant operator IAM
   permissions. Your local ADC identity performs the Compute, Firestore, Secret
   Manager, IAM, and shared DNS operations that the application normally performs.

## Create a lab and one student workout

Run from the repository root. Replace `remote-lab-01` with your enrolled remote peer ID
and the instructor email with its authorized Agoge account:

```powershell
.\venv\Scripts\python.exe debug_lab.py create-lab `
  --template wireguard-factory-lab `
  --instructor pdhuff@ar-core.org `
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
| Parameters, new lab | `create-lab --instructor pdhuff@ar-core.org --remote-peer-id remote-lab-01 --count 1 --expires-hours 2 --student-email wireguard-test@example.com` |
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
     create-lab --instructor pdhuff@ar-core.org --remote-peer-id remote-lab-01
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

## Inspect, resume, and clean up

```powershell
# Read current lab, workout, and WireGuard status.
.\venv\Scripts\python.exe debug_lab.py status --unit-id abcdefghij

# Resume an interrupted shared gateway/network build using the saved lab ID.
.\venv\Scripts\python.exe debug_lab.py unit-action --unit-id abcdefghij --action build

# Start or stop the named student workout locally.
.\venv\Scripts\python.exe debug_lab.py workout-action --workout-id klmnopqrst --action stop
.\venv\Scripts\python.exe debug_lab.py workout-action --workout-id klmnopqrst --action start --duration-hours 2

# Delete the entire named test lab, its student workouts, and managed resources.
.\venv\Scripts\python.exe debug_lab.py unit-action --unit-id abcdefghij --action delete
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
budget blocks and provisioning failures are surfaced to the debugger.

VM creation, Ubuntu package installation, guest startup, DNS, and the physical
WireGuard handshake still take their normal time. This loop removes container
build/deploy waits between Python edits; it does not emulate the guest OS or Pi.
For pure logic changes, run the hermetic tests before using GCP.
