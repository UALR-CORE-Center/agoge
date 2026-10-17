# Agoge Game Master Guide

Agoge can run a capture-the-flag (CTF) exercise built from a lab template. Each team gets its own Workout, which is that team's **board**: Agoge plants a unique set of flags on the team's servers, scores each submission, and gives the instructor running the exercise (the **game master**) a dashboard to control the event.

This guide assumes you already know how to build and manage a Lab. If you don't, read the [Instructor Guide](instructor-guide.md) first.

## Before you begin

- A deployment administrator must turn CTF on. Run `setup.py`, open the environment variables menu, and set `ctf_enabled` to true. The first time it is enabled, this creates the `ctf_flag_seed` secret. That secret is never replaced afterwards, because every flag value is derived from it.
- Once CTF is on, instructors and admins see **Teachers → CTF Events**. While it is off, the menu item is hidden and the `/ctf` API answers 404.
- A team's servers can receive flags only if they were built while this release was deployed, because the plant loader is added at server build time.

## Author the `ctf` block

A lab template becomes CTF-capable when its JSON specification contains a top-level `ctf` block, and it must be a solo lab. Creating an event copies the template into the event's own Lab, so editing the template afterwards does not affect an event that already exists. To change one event's flags, use the **Flags** section of its **Setup** tab instead (see below).

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
| `scoring.reveal_decoy_penalty` | No | Default false. When it is false, the penalty is applied but students never see it: the decoy response shows 0 points, and the team score and public scoreboard leave decoy points out. Your own **Scoreboard** tab always shows the full score. |

### Flag fields

| Field | Required | Rules |
| --- | --- | --- |
| `id` | Yes | 2 to 32 characters: lowercase letters, digits, and `-`, not starting with `-`. Must be unique in the spec. It appears inside the flag value. |
| `server` | Yes | A server `name` in the same specification. For a flag on a nested guest, this is the guest's parent server. |
| `guest` | No | The `name` of a guest in `nested_guests` on the same `server`. Leave it out for a flag on the server itself. See [Nested lab hosts](#nested-lab-hosts). |
| `slot` | Yes | 1 to 9, and unique per server (per guest, for a guest flag). Slot 1 should be reachable from the initial foothold. |
| `category` | No | Up to 32 characters. Students see "General" when it is missing. |
| `location_type` | Yes | `file`, `registry`, `env`, or `ads`. See the table below. |
| `path` | Yes | Must match the pattern for its location type and operating system. |
| `operating_system` | Yes | `linux` or `windows`. All flags on one server must use the same value. A guest flag uses the guest's operating system, not the parent's. |
| `access_level` | No | `user` (default), `root`, or `admin`. For documentation only: the planter always writes as the boot account, so set file permissions with `file_mode` and `file_owner` on Linux, or `windows_access` on Windows. |
| `points` | Yes | Must be greater than 0, except on a decoy, which may be 0 or negative. |
| `decoy` | No | Default false. A decoy is never listed to students. Submitting one is recorded as a scope violation and adds its `points` (normally negative). |
| `hint` | No | Up to 1,000 characters. |
| `hint_cost` | No | Default 0, and must be 0 or more. Deducted the first time a team takes the hint. |
| `unlocks_after` | No | Flag ids that must be solved before this flag is listed to the team. They must exist, and they must not form a cycle. |
| `file_mode` | No | Linux `file` flags only. An octal mode such as `0600`. |
| `file_owner` | No | Linux `file` flags only. `user:group`. |
| `windows_access` | No | Windows `file` and `ads` flags only. `administrators`, `user`, or `everyone`. Replaces the file's inherited permissions so that SYSTEM and Administrators have full control, plus read access for `windows_user` (`user`) or for every account (`everyone`). When it is omitted, the file keeps the permissions of the folder it is in. For an `ads` flag, it applies to the file that holds the stream. |
| `windows_user` | With `windows_access: user` | The local account given read access: 1 to 20 letters, digits, `.`, `_`, or `-`. The account must exist on the image, or the plant fails with "could not set file access". |
| `hidden` | No | Windows `file` and `ads` flags only. Default false. Sets the file's Hidden attribute. |

Notes on `windows_access`:

- **Administrators** always keep full control, so a student account that is in the local Administrators group can read any of these files. Give students a standard account when a flag should require privilege escalation.
- **Permissions you set in the image are left alone** when `windows_access` is omitted. The planter overwrites the file's contents but keeps its existing access list, so you can still lock a file down by hand in the image.
- **Changing `windows_access` back to omitted** does not restore the folder's permissions on a replant, because the planter no longer touches the access list. Rebuild the server, then replant.
- **Two `ads` flags in the same host file** share that file's permissions and Hidden attribute. If their settings differ, the last flag planted wins, so give them the same settings.

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

1. Open **Teachers → CTF Events** and click **New CTF**.
2. Choose a template (only solo lab templates with a valid `ctf` block are listed), optionally rename the event, and set when its Lab expires. Every team's servers are deleted after that time.
3. Agoge creates the event in `DRAFT` with its own Lab and no teams, then opens its dashboard on the **Setup** tab. No VM exists yet. To find the event later, use **Teachers → CTF Events**, which has **Active** and **Archived** tabs.

Creation fails if the template has no `ctf` block, is a community lab, or the `ctf_flag_seed` secret is missing.

### 2. Set up (DRAFT)

The **Setup** tab has three sections.

**Teams.** Add each team with a name and its members' emails, or **Import CSV** with one `team,email` line per member (lines with the same team name make one team). Adding a team creates its Workout record but starts no VM. Rules:

- Team names are unique within the event.
- An email can be on only one team in any active event.
- The deployment's board limit (100 by default) caps the number of teams.
- Teams can be added or removed only in `DRAFT`, and a team can be removed only while its servers have never been built.
- Members can be changed until the event ends, so a late student can still be added after you arm.

Participants join at `/join` with the event's **join code** (shown on the Setup tab) and the email on their team. Teammates land on the same Workout, so they share one set of servers and one score. An email that is on no team is refused with "This email is not on the roster for this event". The first member to join also builds the team's servers if you have not built them yet.

**Flags.** Review or change the event's name, description, rules link, scoring, and flags. The same rules as the `ctf` block apply, and the server rejects an invalid path or server. Saving regenerates every team's flag values. Flags can be edited only in `DRAFT`.

**Servers.** Shows the Lab's servers. **Build all** builds every team that is not built yet, and **Start all** and **Stop all** act on every team. Running VMs cost money until they are stopped. Stop is not offered while the event is running.

### 3. Arm

Make sure every team's servers are **running**, then click **Arm**. Arm stays disabled until the event has at least one team. Agoge plants each board's flags:

- For each flag-bearing server, it writes the plant script into the instance metadata and **restarts the VM**.
- A startup loader writes the flags, reports the result, and Agoge removes the script from the metadata.
- A Workout that is not running fails with "Workout is not running". A stopped server is never started; its flags fail with "Server is not running".

A board is armed if at least one of its flags planted. When the last board finishes, the event moves to `ARMED` if any board armed, and to `BROKEN` if none did. You can click **Arm** again from `ARMED` or `BROKEN`. A re-arm re-plants every board.

### 4. Start, pause, resume

- **Start** (`ARMED` → `RUNNING`) opens submissions and starts the clock.
- **Pause** (`RUNNING` → `PAUSED`) closes submissions and hints. Students see "(paused)" on the banner.
- **Resume** (`PAUSED` → `RUNNING`) adds the paused time to the end time, so pausing never shortens the exercise.

Use **Ends at** in the scoreboard settings to set or change the end time.

### 5. End

**End** (`RUNNING` or `PAUSED` → `ENDED`) closes submissions for good. It cannot be undone, and the confirmation dialog says so. A submission made after the end is recorded with the verdict `closed`.

### 6. Archive and delete

**Archive** is allowed from `DRAFT`, `ARMED`, `ENDED`, or `BROKEN`, but not while the event is running or paused. It cannot be undone. Archiving sets every board inactive, so the Workouts can join a new event, and students stop seeing the CTF banner. Settings can no longer be changed once an event is archived.

An admin can delete an event in `DRAFT` or `ARCHIVED`. Deleting removes the event, its boards, and its stored flag hashes. The submission log and the event log are kept.

### During the event

| Tab | Use it to |
| --- | --- |
| **Setup** | Change team members (for example, add a late student), and build, start, or stop every team's servers. |
| **Flags** | See each flag's plant status on every board, and replant one row or a selection. |
| **Hosts** | Reset a team's server (see below). |
| **Scoreboard** | See the unfrozen standings and adjust a team's score by −10,000 to 10,000 points, with a reason. |
| **Event Log** | Review every game master action and its result (`OK`, `DENIED`, `ERROR`). |
| **Submissions** | Review submissions, newest first, filtered by verdict. |

These controls change scoring:

- **Public scoreboard** lets students see standings on their workout page. Teams appear as anonymous "Team n", and the student's own row is highlighted.
- **Freeze scoreboard** hides solves made after the freeze time from the public standings only. Hint costs and manual adjustments still show, and so do decoy penalties when `reveal_decoy_penalty` is true. Your own **Scoreboard** tab is never frozen.

A team's score is its solved points, plus decoy points, minus hint costs, plus manual adjustments. Unless `reveal_decoy_penalty` is true, students see that score without the decoy points, and the public scoreboard ranks on that figure. Teams are ranked by score. Ties go to the team that reached that score first, and a team with no solves ranks below a team on the same score that has solves.

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

## Nested lab hosts

A lab server can be a hypervisor: a Linux **parent** that runs its own VMs (**guests**) under libvirt/QEMU-KVM. Guests can be Linux or Windows, and they can sit on networks the parent has no address on. A guest is not a Google Cloud VM, so Agoge cannot reach it over the network or through instance metadata. Instead, the parent **relays** each guest's flags over the hypervisor.

### Prepare the images

On the **parent** image:

- The parent must be a Linux server with at least one NIC that has `ip_aliases`. That is what turns on nested virtualization when Agoge builds the server, and it also installs the **plant watcher** (`agoge-ctf-watcher.service`). The watcher picks up a plant without restarting the parent, so the guests keep running while their flags are planted.
- Install `libvirt` (`virsh`). If any guest uses the `offline` driver, also install `libguestfs-tools` (`virt-customize`, `guestfish`, and, for Windows guests, `virt-win-reg`).
- Mark every guest domain to start on boot with `virsh autostart <domain>`. The relay never starts a guest that is not already running, so a guest without autostart is down after every parent restart, and its flags fail with "guest is not running".

On each **guest** that uses the `qemu-agent` driver:

- Give the domain the guest agent channel. In the domain XML, this is a `<channel type='unix'>` with `<target type='virtio' name='org.qemu.guest_agent.0'/>`. `virt-install` and `virt-manager` usually add it for you; check with `virsh dumpxml <domain>`.
- Install and enable the QEMU guest agent: the `qemu-guest-agent` package on Linux, or the guest agent from the virtio-win guest tools on Windows.
- Allow `guest-exec` and `guest-exec-status`. **RHEL-family guests (RHEL, Rocky, Alma, CentOS, Fedora) block them by default** in `/etc/sysconfig/qemu-ga`. Remove them from `BLACKLIST_RPC`, or add them to the `--allow-rpcs` list in `FILTER_RPC_ARGS`, depending on which one your release uses. Then run `systemctl restart qemu-guest-agent`. Debian, Ubuntu, and Windows allow them by default.
- Test it from the parent: `virsh qemu-agent-command <domain> '{"execute":"guest-ping"}'` should answer `{"return":{}}`.

A guest that uses the `offline` driver needs no agent. Instead, the parent shuts it down, writes the flags into its disk with libguestfs, and starts it again.

For each guest you want to be able to **rebuild** from the **Hosts** tab, take a libvirt snapshot named `agoge-pristine` of its clean state before you save the parent's image:

```
virsh snapshot-create-as <domain> agoge-pristine
```

Take it while the guest is running, after you finish setting it up. The disk must be qcow2 so it can hold an internal snapshot. A guest rebuild reverts to this snapshot and plants the flags again.

### Spec example

Declare each guest once in `ctf.nested_guests`, then point flags at it with `guest`. A flag's `server` is still the parent.

```json
{
  "servers": [
    {
      "name": "hv-host",
      "details": {"os": "linux"},
      "nics": [{"network": "lan", "subnet_name": "default", "ip_aliases": ["10.1.1.10"]}]
    }
  ],
  "ctf": {
    "name": "Nested CTF",
    "nested_guests": [
      {"name": "win-dc", "server": "hv-host", "domain": "win2019-dc", "operating_system": "windows", "driver": "qemu-agent"},
      {"name": "web", "server": "hv-host", "domain": "ubuntu-web", "operating_system": "linux", "driver": "offline"}
    ],
    "flags": [
      {
        "id": "hv-root",
        "server": "hv-host",
        "slot": 1,
        "location_type": "file",
        "path": "/root/flag.txt",
        "operating_system": "linux",
        "points": 100
      },
      {
        "id": "web-root",
        "server": "hv-host",
        "guest": "web",
        "slot": 1,
        "location_type": "file",
        "path": "/root/flag.txt",
        "operating_system": "linux",
        "points": 150,
        "file_mode": "0600",
        "file_owner": "root:root"
      },
      {
        "id": "dc-admin",
        "server": "hv-host",
        "guest": "win-dc",
        "slot": 1,
        "location_type": "registry",
        "path": "HKLM\\SOFTWARE\\Corp:Secret",
        "operating_system": "windows",
        "points": 300
      }
    ]
  }
}
```

In the spec editor, the **Nested guests** section edits this list, and each flag has a **Guest** select that lists the guests on that flag's server.

| `nested_guests` field | Required | Rules |
| --- | --- | --- |
| `name` | Yes | 2 to 32 characters: lowercase letters, digits, and `-`, not starting with `-`. Unique on its server. |
| `server` | Yes | A Linux server in the same specification with an `ip_aliases` NIC. At most 8 guests per server. |
| `domain` | Yes | The libvirt domain name on the parent (what `virsh list --all` shows). |
| `operating_system` | Yes | `linux` or `windows`. Every flag on this guest must use the same value. |
| `driver` | No | `qemu-agent` (default) plants through the guest agent while the guest runs. `offline` shuts the guest down and writes to its disk. |

Each guest counts as its own machine, so slots are unique per guest, and the parent's own flags (no `guest`) have their own slots 1 to 9.

The `offline` driver has limits on Windows guests. Only `file`, `registry`, and `env` flags are allowed, `windows_access` and `hidden` must be left out, and registry paths must start with `HKLM\SOFTWARE\` or `HKLM\SYSTEM\`; the validator rejects anything else. A `file` flag must also be on drive `C:`, or its plant fails with "only drive C: can be written offline". An offline plant restarts the guest, so prefer `qemu-agent` for a guest teams are already working on.

### Planting and resetting guests

Arm and **Replant** on the **Flags** tab work as they do for any server, except that a nested host is planted through the watcher instead of being restarted. If the watcher does not answer within 30 seconds (for example, because the parent was built before this release), Agoge restarts the parent as it would any other server. A nested host's confirmation window is 420 seconds instead of 240.

On the **Hosts** tab, each guest has its own row, indented under its parent. A reset on a guest row acts on that guest only, never restarts the parent, and leaves every other guest and team alone:

| Mode | What it does to the guest | Flags afterwards |
| --- | --- | --- |
| **Replant** | Plants this guest's flags again | Re-planted with the same values |
| **Restart** | `virsh reboot` | Unchanged |
| **Rebuild** | Reverts to the `agoge-pristine` snapshot, then plants this guest's flags | Re-planted with the same values |

A guest reset never falls back to restarting the parent. If the watcher does not answer, the guest's flags fail with "Plant watcher did not respond". A **Rebuild** of the parent itself recreates every guest's disk from the image, so it marks every guest's flags `stale`, as it does for the parent's.

Guest `failed` reasons start with the guest's name:

| Reason | Fix |
| --- | --- |
| "guest is not running" | Start the domain on the parent (and set `virsh autostart`), then replant. |
| "guest agent did not respond" | Check the agent channel and that `qemu-guest-agent` is running in the guest. |
| "guest-exec failed" | `guest-exec` is blocked. See the RHEL note above. |
| "no agoge-pristine snapshot" | Create the snapshot in the image, or use **Replant** instead of **Rebuild**. |
| "guest did not shut down" | An `offline` guest ignored `virsh shutdown` for 120 seconds. Agoge never forces a guest off. Fix the guest's shutdown handling (on Windows, the ACPI power button setting). |
| "virt-customize is not available" (or `virsh`, `guestfish`, `virt-win-reg`) | Install `libvirt` or `libguestfs-tools` on the parent image. |
| "&lt;flag id&gt;: verification failed" | An `offline` write did not read back the same value. Check the path inside the guest. |

### Security warning

**Root on the parent exposes every guest's flags.** A user with root on the parent can run `virsh` against any guest, mount a guest's disk with libguestfs, or read the plant payload while it runs. Flag values never appear in a process argument list, but the parent necessarily handles every guest's values. Treat the parent as the most sensitive host on the board: don't give teams a path to root on it unless capturing every guest's flags is the intended reward.
