# Agoge Game Master Guide

Agoge can run a capture-the-flag (CTF) exercise on top of an ordinary Lab. Each learner Workout becomes one team's **board**: Agoge plants a unique set of flags on that Workout's servers, scores each submission, and gives the instructor running the exercise (the **game master**) a dashboard to control the event.

This guide assumes you already know how to build and manage a Lab. If you don't, read the [Instructor Guide](instructor-guide.md) first.

## Before you begin

- A deployment administrator must turn CTF on. Run `setup.py`, open the environment variables menu, and set `ctf_enabled` to true. The first time it is enabled, this creates the `ctf_flag_seed` secret. That secret is never replaced afterwards, because every flag value is derived from it.
- Once CTF is on, instructors and admins see **Teachers → CTF Events**. While it is off, the menu item and the **Create CTF Event** button are hidden, and the `/ctf` API answers 404.
- A Workout's servers can receive flags only if they were built while this release was deployed, because the plant loader is added at server build time. Rebuild any older Workouts before you create an event.

## Author the `ctf` block

A lab template becomes CTF-capable when its JSON specification contains a top-level `ctf` block. Building a Lab copies the specification into the Lab, so **add or change the `ctf` block before you build the Lab**. Editing the template afterwards does not affect a Lab that is already built.

### Complete example

The `server` values must match `name` entries in the same specification's `servers` list. All other server fields are omitted here.

```json
{
  "servers": [
    {"name": "web"},
    {"name": "dc"}
  ],
  "ctf": {
    "name": "Spring CTF",
    "description": "Gain a foothold on the web server, then pivot to the domain controller.",
    "rules_url": "https://example.edu/ctf/rules-of-engagement",
    "scoring": {
      "flag_prefix": "agoge",
      "submission_rate_limit": 10,
      "reveal_decoy_penalty": false
    },
    "flags": [
      {
        "id": "web-root",
        "server": "web",
        "slot": 1,
        "category": "Web",
        "location_type": "file",
        "path": "/root/flag.txt",
        "operating_system": "linux",
        "access_level": "root",
        "points": 100,
        "hint": "Look at what the backup job runs as.",
        "hint_cost": 25,
        "file_mode": "0600",
        "file_owner": "root:root"
      },
      {
        "id": "web-env",
        "server": "web",
        "slot": 2,
        "category": "Web",
        "location_type": "env",
        "path": "AGOGE_FLAG",
        "operating_system": "linux",
        "points": 150,
        "unlocks_after": ["web-root"]
      },
      {
        "id": "dc-file",
        "server": "dc",
        "slot": 1,
        "category": "Windows",
        "location_type": "file",
        "path": "C:\\Users\\Public\\flag 1.txt",
        "operating_system": "windows",
        "points": 200
      },
      {
        "id": "dc-reg",
        "server": "dc",
        "slot": 2,
        "category": "Windows",
        "location_type": "registry",
        "path": "HKLM\\SOFTWARE\\Agoge Lab:Flag",
        "operating_system": "windows",
        "access_level": "admin",
        "points": 300,
        "unlocks_after": ["dc-file", "web-env"]
      },
      {
        "id": "dc-ads",
        "server": "dc",
        "slot": 3,
        "category": "Forensics",
        "location_type": "ads",
        "path": "C:\\Windows\\Temp\\notes.txt:hidden",
        "operating_system": "windows",
        "points": 250
      },
      {
        "id": "out-of-scope",
        "server": "dc",
        "slot": 4,
        "location_type": "file",
        "path": "C:\\decoy.txt",
        "operating_system": "windows",
        "points": -50,
        "decoy": true
      }
    ]
  }
}
```

### `ctf` fields

| Field | Required | Rules |
| --- | --- | --- |
| `name` | Yes | Up to 100 characters. Shown on the student banner. |
| `description` | No | Up to 2,000 characters. |
| `rules_url` | No | Linked from the student banner as **Rules of engagement**. Only `http` and `https` links are rendered. |
| `flags` | Yes | 1 to 200 flags. |
| `scoring.flag_prefix` | No | Default `agoge`. 2 to 16 lowercase letters or digits, starting with a letter. |
| `scoring.submission_rate_limit` | No | Default 10, range 1 to 100. The maximum number of submissions per board, per flag id, in each 60-second window. |
| `scoring.reveal_decoy_penalty` | No | Default false. When it is false, a student who submits a decoy sees 0 points even though the penalty is applied. |

### Flag fields

| Field | Required | Rules |
| --- | --- | --- |
| `id` | Yes | 2 to 32 characters: lowercase letters, digits, and `-`, not starting with `-`. Must be unique in the spec. It appears inside the flag value. |
| `server` | Yes | A server `name` in the same specification. |
| `slot` | Yes | 1 to 9, and unique per server. Slot 1 should be reachable from the initial foothold. |
| `category` | No | Up to 32 characters. Students see "General" when it is missing. |
| `location_type` | Yes | `file`, `registry`, `env`, or `ads`. See the table below. |
| `path` | Yes | Must match the pattern for its location type and operating system. |
| `operating_system` | Yes | `linux` or `windows`. All flags on one server must use the same value. |
| `access_level` | No | `user` (default), `root`, or `admin`. For documentation only: the planter always writes as the boot account, so set file permissions with `file_mode` and `file_owner`. |
| `points` | Yes | Must be greater than 0, except on a decoy, which may be 0 or negative. |
| `decoy` | No | Default false. A decoy is never listed to students. Submitting one is recorded as a scope violation and adds its `points` (normally negative). |
| `hint` | No | Up to 1,000 characters. |
| `hint_cost` | No | Default 0, and must be 0 or more. Deducted the first time a team takes the hint. |
| `unlocks_after` | No | Flag ids that must be solved before this flag is listed to the team. They must exist, and they must not form a cycle. |
| `file_mode` | No | Linux `file` flags only. An octal mode such as `0600`. |
| `file_owner` | No | Linux `file` flags only. `user:group`. |

### Flag locations

| `location_type` | OS | `path` format | Example |
| --- | --- | --- | --- |
| `file` | linux | Absolute path made of letters, digits, `_`, `.`, `/`, and `-` | `/root/flag.txt` |
| `file` | windows | Drive path; spaces allowed | `C:\Users\Public\flag 1.txt` |
| `registry` | windows | `HKLM\<key>:<value name>` | `HKLM\SOFTWARE\Agoge Lab:Flag` |
| `env` | linux, windows | Upper-case variable name, up to 64 characters | `AGOGE_FLAG` |
| `ads` | windows | `<file>:<stream>` | `C:\Windows\Temp\notes.txt:hidden` |

On Linux, an `env` flag is written to `/etc/environment`. On Windows, it is set as a machine-scope variable.

The validator rejects any path that does not match its pattern. A rejected specification cannot be saved, and a CTF event cannot be created from it.

### Flag values

Every board gets different values. A flag looks like this:

```
agoge{web-root_3f9a0c1d2b4e5f607182}
```

The value is the prefix, then `{`, the flag id, `_`, 20 hex characters, and `}`. Agoge checks a submission after trimming surrounding whitespace and lowercasing it, and does nothing else to it. Only hashes of the values are stored. An admin can reveal one board's value from the API (`GET /ctf/{ctf_id}/flags/{flag_id}/reveal/?workout_id=`), and every reveal is written to the event log.

## Event lifecycle: create to archive

The dashboard shows the event's state as a chip. These are the states:

| State | Meaning |
| --- | --- |
| `DRAFT` | Created, with nothing planted yet. |
| `ARMING` | Flags are being planted on every board. |
| `ARMED` | At least one board planted; ready to start. |
| `RUNNING` | Submissions and hints are open. |
| `PAUSED` | The clock is stopped and submissions are closed. |
| `ENDED` | The exercise is over and submissions are closed. |
| `ARCHIVED` | Retired. Its boards are released. |
| `BROKEN` | Arming finished, but no board planted successfully. |

### 1. Create the event

1. Build the Lab from a template that has a `ctf` block, and wait for its Workouts to exist.
2. Open the Lab detail page and click **Create CTF Event**. The button appears only for a CTF-capable Lab while CTF is enabled, and it is disabled after the Lab expires.
3. Agoge creates the event in `DRAFT` with one board per Workout, then opens its dashboard. To find the event later, use **Teachers → CTF Events**, which has **Active** and **Archived** tabs.

Creation fails if:

- the Lab has no Workouts;
- it would need more than the deployment's board limit (100 by default);
- a Workout already belongs to another active event;
- the `ctf_flag_seed` secret is missing.

The team name shown on boards is the Workout's team name. If there is none, the student's email is used, and if that is missing too, the Workout id.

### 2. Arm

Make sure every Workout is **running**, then click **Arm**. Agoge plants each board's flags:

- For each flag-bearing server, it writes the plant script into the instance metadata and **restarts the VM**.
- A startup loader writes the flags, reports the result, and Agoge removes the script from the metadata.
- A Workout that is not running fails with "Workout is not running". A stopped server is never started; its flags fail with "Server is not running".

A board is armed if at least one of its flags planted. When the last board finishes, the event moves to `ARMED` if any board armed, and to `BROKEN` if none did. You can click **Arm** again from `ARMED` or `BROKEN`. A re-arm re-plants every board.

### 3. Start, pause, resume

- **Start** (`ARMED` → `RUNNING`) opens submissions and starts the clock.
- **Pause** (`RUNNING` → `PAUSED`) closes submissions and hints. Students see "(paused)" on the banner.
- **Resume** (`PAUSED` → `RUNNING`) adds the paused time to the end time, so pausing never shortens the exercise.

Use **Ends at** in the scoreboard settings to set or change the end time.

### 4. End

**End** (`RUNNING` or `PAUSED` → `ENDED`) closes submissions for good. It cannot be undone, and the confirmation dialog says so. A submission made after the end is recorded with the verdict `closed`.

### 5. Archive and delete

**Archive** is allowed from `DRAFT`, `ARMED`, `ENDED`, or `BROKEN`, but not while the event is running or paused. It cannot be undone. Archiving sets every board inactive, so the Workouts can join a new event, and students stop seeing the CTF banner. Settings can no longer be changed once an event is archived.

An admin can delete an event in `DRAFT` or `ARCHIVED`. Deleting removes the event, its boards, and its stored flag hashes. The submission log and the event log are kept.

### During the event

| Tab | Use it to |
| --- | --- |
| **Flags** | See each flag's plant status on every board, and replant one row or a selection. |
| **Hosts** | Reset a team's server (see below). |
| **Scoreboard** | See the unfrozen standings and adjust a team's score by −10,000 to 10,000 points, with a reason. |
| **Event Log** | Review every game master action and its result (`OK`, `DENIED`, `ERROR`). |
| **Submissions** | Review submissions, newest first, filtered by verdict. |

These controls change scoring:

- **Public scoreboard** lets students see standings on their workout page. Teams appear as anonymous "Team n", and the student's own row is highlighted.
- **Freeze scoreboard** hides solves made after the freeze time from the public standings only. Hint costs, decoy penalties, and manual adjustments still show. Your own **Scoreboard** tab is never frozen.

A team's score is its solved points, plus decoy points, minus hint costs, plus manual adjustments. Teams are ranked by score. Ties go to the team that reached that score first, and a team with no solves ranks below a team on the same score that has solves.

How submissions are judged:

| Verdict | When | Student sees |
| --- | --- | --- |
| `correct` | First solve of a flag on the team's own board | "Correct! Flag accepted." and the points |
| `duplicate` | Already solved | "Your team has already solved this flag." |
| `decoy` | A decoy flag | "That flag is out of scope for this exercise." |
| `incorrect` | Not a flag in this event | "Incorrect flag." |
| `cross_submission` | Another team's flag | "Incorrect flag." The match is visible to you in **Submissions**. |
| `rate_limited` | Over `submission_rate_limit` | "Try again in N seconds" |
| `closed` | The event is not running | "Submissions are closed." |

## Host reset modes

On the **Hosts** tab, open a team's server and choose one of these modes. Resets are allowed while the event is `ARMED`, `RUNNING`, `PAUSED`, or `BROKEN`.

| Mode | What it does | Flags afterwards | Use it when |
| --- | --- | --- | --- |
| **Replant** | Plants this server's flags again. The VM restarts. Waits up to 240 seconds for confirmation. | Re-planted with the same values | A flag is `failed` or `stale`, or a team deleted or damaged a flag. Not offered for a server with no flags. |
| **Restart** | Stops and starts the VM. | Unchanged on disk; nothing is re-planted | The server is hung, but its disk is fine. |
| **Rebuild** | Deletes the VM and recreates it from its image. | Marked `stale`; they are not on the new disk | The server is broken beyond repair. Follow up with a **Replant**. Not offered for a server with a WireGuard endpoint, because it would stay deleted. |

A rebuild marks the flags `stale` even if the rebuild itself fails, because you can no longer trust what is on the disk. Flag values never change on a reset, so a team's earlier solves still count.

## What `stale` and `failed` mean

The **Flags** tab shows a plant status for each flag on each board.

| Status | Meaning |
| --- | --- |
| `pending` | Not planted yet; the event has not been armed. |
| `planting` | A plant is in progress. |
| `planted` | The server confirmed the write. |
| `failed` | The plant did not confirm. Hover over the row to see the reason. |
| `stale` | The server was rebuilt after the flag was planted, so the flag is no longer on the disk. |

`failed` and `stale` rows have a warning icon. Both are fixed the same way: click **Replant** on the row, or select rows and replant them together. The **Replant** action on the Hosts tab works too.

Common `failed` reasons:

| Reason | Fix |
| --- | --- |
| "Server is not running" | Start the Workout, then replant. |
| "Server instance not found" | Rebuild the server, then replant. |
| "No plant confirmation within 240 s" | The VM did not finish booting, or the loader is missing because the server was built before CTF was deployed. Replant; if that fails again, rebuild the server first. |
| An error reported by the host | The script could not write the location, for example because the directory is missing from the image. Fix the image or the `path`. |
| "CTF flag seed is not configured" | Ask an administrator to enable CTF through `setup.py`. |

Replanting writes the same value again, so it is safe to repeat.

## Overnight-stop exemption

Agoge's daily maintenance normally stops every running Workout overnight to save cost. A Workout is **not** stopped if it is on an active board of an event in `ARMING`, `ARMED`, `RUNNING`, or `PAUSED`. This way, a multi-day exercise keeps its planted flags and in-game progress on running servers.

Workouts on `DRAFT`, `ENDED`, `ARCHIVED`, or `BROKEN` events get no exemption and are stopped as usual. Exempt VMs keep running and keep costing money, so **End** and **Archive** the event promptly when the exercise is over.
