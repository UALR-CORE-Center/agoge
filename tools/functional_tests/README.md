# Offline functional tests

Run these scenarios before deploying backend changes, from the repository root
using the same virtual environment as setup:

```powershell
.\venv\Scripts\python.exe -m tools.functional_tests
```

The default runs both community and solo scenarios. Use `--suite community` or
`--suite solo` to focus on one, `--verbose` to show scenario names, or `--list`
to show the selected files.

Every suite also checks API readiness with Cloud Run's internal Host header,
host validation on application routes, and deployment output streaming. These
checks catch startup-probe regressions and hidden subprocess errors locally.

These scenarios execute the application lifecycle and Guacamole configuration
code with in-memory database/cloud services and a local Guacamole transport
fake. They require no account, GCP credentials, remote peer, running VM, or
deployment. A failing scenario returns a nonzero exit code.

The community checks cover one Unit-owned Guacamole proxy, two student
workouts, individual connection permissions, build parking, first-student
start, last-student stop, and resource deletion. The solo scenario covers its
private Guacamole proxy, JDBC authentication, build, stop, start, and deletion.
The community suite also checks the generated startup configuration, signing
key lifecycle, proxy service account permissions, and DHCP lease reuse after
short-lived connection permissions expire.

The fake provider completes operations immediately. These tests catch
application behavior errors; guest startup scripts, IAM, firewall reachability,
and GCP operation timing require the real-cloud debug workflow. To validate the
shared community VMs against GCP, use the prompted
[`tools.debug_lab student-lifecycle`](../debug_lab/README.md) command.
