# Troubleshoot Cloud Run deployment and startup

A successful Cloud Build means the container image was built and pushed. The
following Cloud Run deployment can still fail when the new API revision starts.
Inspect the failed revision rather than rerunning the image build for more logs.

## Export API logs and deployment status

Run from PowerShell. These examples target `test-dev-787001` in `us-central1`;
replace the project and region for another site.

```powershell
$agogeLogFilter = 'resource.type=cloud_run_revision AND resource.labels.service_name=agoge-api'

gcloud logging read $agogeLogFilter `
  --project=test-dev-787001 `
  --freshness=24h --limit=500 --format=json |
  Out-File -Encoding utf8 .\agoge-api-logs.json

gcloud run services describe agoge-api `
  --project=test-dev-787001 --region=us-central1 `
  --format="yaml(status)" |
  Out-File -Encoding utf8 .\agoge-api-status.yaml
```

The general `gcloud logging read` command avoids the Cloud Run log formatter,
which can crash with `TypeError: sequence item 1: expected str instance, NoneType
found` for some log entries. If the CLI still fails, use **Logging → Logs
Explorer**, select the project and **Last 24 hours**, and run:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="agoge-api"
```

In **Cloud Run → agoge-api → Revisions**, open the failed revision and copy its
error message. In the status export, compare `latestCreatedRevisionName`,
`latestReadyRevisionName`, and `traffic` to see which revision is actually serving.

## Startup probe returns Invalid host header

If the logs show **Application startup complete** followed by a startup probe
failure with **400 Bad Request / Invalid host header**, the API has started but
host validation is rejecting the probe. Increasing the startup timeout does not
resolve that rejection.

The API provides an exact `GET`/`HEAD /health/ready` endpoint that accepts the
internal Host header used by Cloud Run. It returns 200 only after startup has
loaded the cloud environment; before readiness or after shutdown it returns
503. It reports a fixed status and performs no cloud reads per probe. All other
routes keep their configured host validation. The endpoint is public, contains
no environment details, and is excluded from the API schema.

Use `/health/ready` on the API container's port for an HTTP startup probe. The
path is relative to the container, without the tenant URL prefix. Updating an
existing service can retain its previously configured probe settings. New
services can use Cloud Run's default TCP startup probe or configure this HTTP
endpoint.

Pull the updated feature branch, stop the old setup process, restart `setup.py`,
and rebuild/deploy the API. To complete an interrupted full update, select
**Application Installation and Updates → Update Main Application and Cloud
Functions** again. A failed API deployment stops setup before the frontend and
Cloud Function steps.

## Setup appears stuck without deployment output

Setup streams subprocess stderr and stdout through one pipe and flushes each
line so `gcloud` progress and errors remain visible. Older revisions drained
stdout before stderr, which could hide deployment messages or deadlock when the
stderr pipe filled. Restart setup from the updated checkout to use the corrected
streaming code.

Before deploying again, run the offline checks from the repository root:

```powershell
.\venv\Scripts\python.exe -m tools.functional_tests
```

These include API startup/readiness and host-validation checks in addition to
community and solo lab lifecycles. They require no GCP credentials; the real
Cloud Run revision still needs to pass its deployed probe.
