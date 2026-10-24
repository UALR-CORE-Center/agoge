# Local lab debugging

Run the API business logic and Cloud Function worker together on your computer,
against real resources in `test-dev-787001/agoge-v1`. From the repository root:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab --help
```

The former root-level `debug_lab.py` entry point has moved into this package.
For an IDE run configuration, select the module `tools.debug_lab`, use the
repository root as the working directory, and put the subcommand/options in
the argument field. Breakpoints in the API and Cloud Function code work in the
same process.

## Two-student gateway lifecycle

Save public test settings in `.local/debug-lab/students.json`:

```json
{
  "template": "wireguard-factory-lab",
  "instructor": "pdhuff@ualr.edu",
  "remote_peer_id": "remote-lab-01",
  "count": 2,
  "expires_hours": 2,
  "student_emails": ["wireguard-one@example.com", "wireguard-two@example.com"]
}
```

Then run:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab student-lifecycle --profile .local/debug-lab/students.json
```

This offers recent-lab cleanup and then builds the lab. It verifies that the
idle shared gateway is stopped, prompts to claim each student workout, prompts
to start each workout, prompts to stop each workout, and finally offers lab
deletion. A student join claims a workout; starting that workout makes the
student active. The checks require:

| Step | Shared gateway |
| --- | --- |
| Build, with no active students | Stopped |
| Claim the two student workouts | Stopped |
| Start the first student | Running |
| Start the second student | Running |
| Stop the first student | Running |
| Stop the last student | Stopped |

The command reads the actual GCP VM status after every step, in addition to
checking saved lab, workout, and gateway states. It never manually starts or
stops the Unit, so those actions cannot conceal a failure of the automatic
student lifecycle. The Pi can remain offline; no guest health callback or
WireGuard handshake is required.

Use `--delete-recent` to automatically delete matching recent test labs before
building, or `--skip-cleanup` to bypass that check. These options do not bypass
the lifecycle prompts. Email flags may replace the profile list by repeating
`--student-email` exactly twice. Capacity must be at least two.

On failure or interruption the command preserves resources and prints the lab
ID, status command, and cleanup command. Deletion is offered only after all
checks pass. You can also inspect and explicitly delete a retained test lab:

```powershell
.\venv\Scripts\python.exe -m tools.debug_lab status --unit-id abcdefghij
.\venv\Scripts\python.exe -m tools.debug_lab delete-labs --instructor pdhuff@ualr.edu --unit-id abcdefghij --yes
```

For account setup, peer enrollment, individual commands, and additional
troubleshooting, see [the operations guide](../../docs/operations/local-backend-debugging.md).
