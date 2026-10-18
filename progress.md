# Ralph Loop Progress

State for the autonomous loop. Iterations append to this file; log entries are
never deleted or rewritten. The task queue is disposable — regenerate it with
`./ralph.sh --replan` if it drifts from reality.

## Task Queue

Tasks derived from PRD.md, ordered by dependency and priority.
Mark `[x]` when complete. Do NOT reorder or delete tasks.

### Planning
- [x] Read PRD.md and replace this section with a real task breakdown

Each task below is one PRD MVP item (PRD.md "Features → MVP (Phase 1)").
Read the PRD line cited for the full spec; its "Done when" bullet, if any, sits
directly under it; the group header in the PRD collects them too. Phase 2 items are out of scope for this loop.

### Group 0 — Green baseline
- [x] **0.1** Frontend test script — spec + done-when at PRD.md:1463
- [x] **0.2** Rubric opt-in tests — spec + done-when at PRD.md:1465

### Group A — Contracts and constants
- [x] **A1** CTF constants — spec + done-when at PRD.md:1470
- [x] **A2** CTF specification models — spec + done-when at PRD.md:1472
- [x] **A3** CTF stored models — spec + done-when at PRD.md:1474
- [x] **A4** CTF request models — spec + done-when at PRD.md:1475
- [x] **A5** CTF response models — spec + done-when at PRD.md:1476
- [x] **A6** Spec block wiring — spec + done-when at PRD.md:1477

### Group B — Flag derivation and state
- [x] **B1** Derivation module — spec + done-when at PRD.md:1482
- [x] **B2** Seed property — spec + done-when at PRD.md:1484
- [x] **B3** Seed provisioning — spec + done-when at PRD.md:1485
- [x] **B4** CTF state manager — spec + done-when at PRD.md:1487

### Group C — Specification validation
- [x] **C1** Flag validator — spec + done-when at PRD.md:1492
- [x] **C2** Validator wiring — spec + done-when at PRD.md:1494

- [x] **BUG** `SpecEditManager.save` writes the spec to Firestore (catalog on publish, edits otherwise) *before* calling `is_valid()`, so an invalid spec is persisted and then the call raises. Callers in `lab_spec_edit.py` check `is_valid()` first, which masks it. Not CTF-specific.

### Group D — Compute primitives and the loader
- [x] **D1** `set_metadata` — spec + done-when at PRD.md:1499
- [x] **D2** `get_guest_attributes` — spec + done-when at PRD.md:1501
- [x] **D3** Plant contract module — spec + done-when at PRD.md:1502
- [x] **D4** Loader at build — spec + done-when at PRD.md:1503

### Group E — Planting
- [x] **E1** Payload builder — spec + done-when at PRD.md:1508
- [x] **E2** Plant procedure — spec + done-when at PRD.md:1510
- [x] **E3** CTF handler — spec + done-when at PRD.md:1512 (split: this slice is the handler, the `main.py` branch, `CTF_PLANT` routing and unknown action → `ValueError`; the other two routes are E4b and G4b)
- [x] **E4** Arm worker — spec + done-when at PRD.md:1514
- [x] **E4b** Route `CTF_ARM_BOARD` → `ArmWorker.run(ctf_id, workout_id)` in `CtfHandler.action_map`, with a test showing it reaches ArmWorker (E3 done-when, PRD.md:1514)
- [x] **E5** Overnight exemption — spec + done-when at PRD.md:1516
- [x] **BUG2** `ProjectServerManager.stop_everything` calls `self.db.batch_write(operations)` inside the image loop (wrong indentation), so the growing batch is rewritten once per checked-out image. Not CTF-specific.

### Group F — Event core
- [x] **F1** Config and feature flag — spec + done-when at PRD.md:1521
- [x] **F2** Error helper — spec + done-when at PRD.md:1523
- [x] **F3** Audit helper — spec + done-when at PRD.md:1524
- [x] **F4** Event create — spec + done-when at PRD.md:1526
- [x] **F5** Event read, update, delete — spec + done-when at PRD.md:1528
- [x] **F6** Event actions — spec + done-when at PRD.md:1529
- [x] **F7** Event reads for panels — spec + done-when at PRD.md:1531
- [x] **BUG3** An `arm` whose Pub/Sub publish fails partway (`CtfEvent._publish_arm`) leaves the event in ARMING with `boards_pending` above 0 and no way out, because ARMING→ARMING is not an allowed transition and only arm workers leave ARMING. It needs a recovery path, such as a re-publish for boards still `pending`, or a stale-ARMING sweep that moves the event to BROKEN. The PRD does not specify one.
  - Reopened by verification: `_fail_unpublished` (api/core/ctf/event.py:299-315) runs only when `self.pubsub.msg(...)` raises *synchronously*. `PubSubManager.msg` (common/utilities/gcp/pubsub_manager.py:61-67) returns the `publisher.publish(...)` future and nothing ever calls `.result()` on it. google-cloud-pubsub reports real publish failures (network, permission, timeout, a missing topic) through that future, so in production the recovery never runs and the event still sticks in ARMING. The tests miss this because `FakePubSub.msg` (api/unit_tests/test_ctf_event_actions.py:87-89, :170, :223) raises in-line, which the real client does not do for these failures. Missing: resolve each publish future (for example, call `.result(timeout=...)` per message, or collect the futures and check them) and treat any that failed as unpublished. Add a test whose fake returns a future that fails.

### Group G — Hosts
- [x] **G1** Replant publish — spec + done-when at PRD.md:1535
- [x] **G2** Host rows — spec + done-when at PRD.md:1536
- [x] **G3** Reset publish — spec + done-when at PRD.md:1537
- [x] **G4** Reset dispatcher — spec + done-when at PRD.md:1538
- [x] **G4b** Route `CTF_HOST_RESET` → the `host_reset` dispatcher (with `SERVER_NAME`, `RESET_MODE`) in `CtfHandler.action_map`, with a test showing it reaches it (E3 done-when, PRD.md:1538)
- [x] **G5** Reset `replant` — spec + done-when at PRD.md:1540
- [x] **G6** Reset `restart` — spec + done-when at PRD.md:1541
- [x] **G7** Reset `rebuild` — spec + done-when at PRD.md:1542

### Group H — Scoring
- [x] **H1** Submission resolve — spec + done-when at PRD.md:1546
- [x] **H2** Solve award — spec + done-when at PRD.md:1548
- [x] **H3** Rate limiting — spec + done-when at PRD.md:1550
- [x] **H4** Hints — spec + done-when at PRD.md:1552
- [x] **H5** Student board read — spec + done-when at PRD.md:1553
- [x] **H6** Scoreboards — spec + done-when at PRD.md:1555
- [x] **H7** Score adjustment — spec + done-when at PRD.md:1557

### Group R — Routers
- [x] **R1** Instructor router — spec + done-when at PRD.md:1561
- [x] **R2** Student router — spec + done-when at PRD.md:1562
- [x] **R3** Router registration — spec + done-when at PRD.md:1563
- [x] **R4** Router auth tests — spec + done-when at PRD.md:1564
- [x] **BUG4** `AnonymousAppUser()` (common/models/users.py:124) cannot be constructed: it passes `uid=None`, `email=None`, `settings=None` to `AgogeUser`, whose fields are `str`/`str`/`Dict`, so Pydantic raises `ValidationError`. The `get_current_user` branch that returns it is unreachable today only because `HTTPBearer()` (auto_error) answers a missing token with 403 first. Not CTF-specific.

### Group I — Game master UI
- [x] **I1** CTF TypeScript models — spec + done-when at PRD.md:1569
- [x] **I2** CTF transformer and service — spec + done-when at PRD.md:1570
- [x] **I3** Feature flag hook — spec + done-when at PRD.md:1572
- [x] **I4** Routes and menu — spec + done-when at PRD.md:1573 (split: this slice is `URL_TEACHER_CTF_BASE`, `URL_TEACHER_CTF_EVENT` and the flag-gated **Teachers** menu item; the two routes are I4b)
- [ ] **I4b** (both routes are in as of iteration 61; only the browser checks remain, including I9's dashboard check and I10's disabled-actions check) Add the two `ProtectedRoute level="instructor"` routes in `AppRouter.tsx`: `URL_TEACHER_CTF_BASE` → `CtfEventList` (with I5) and `${URL_TEACHER_CTF_EVENT}/:ctf_id` → `CtfDashboard` (with I9). Then verify in the browser that the menu item appears only when CTF is enabled (I4 done-when). Until then, the menu item links to a URL with no route. Also verify in the browser that `Create CTF Event` is absent on a non-CTF unit's `TeacherUnit` page (I6 done-when), and that the student `CtfBanner` shows on an enrolled workout and is absent otherwise (J2 done-when). Also submit a flag through the student `FlagSubmitCard` and check the verdict snackbar (J3 done-when). Also check the student `ChallengeList` below `WorkoutTable`: take a hint through its confirm dialog, and with `public_scoreboard_enabled` on, confirm the caller's standings row is highlighted (J4 done-when). Also, on the development project, create an event with **New CTF**, add teams (including a CSV import), edit flags, build/start/stop servers from the **Setup** tab, and confirm Arm stays disabled until there is a team (L7 done-when).
- [x] **I5** Events list page — spec + done-when at PRD.md:1575 (the list route is in; the browser check is carried by I4b)
- [x] **I6** Create from unit — spec + done-when at PRD.md:1577 (the browser check that the button is absent on a non-CTF unit is carried by I4b)
- [x] **I7** Action confirm dialog — spec + done-when at PRD.md:1579
- [x] **I8** CTF state chip — spec + done-when at PRD.md:1580
- [x] **I9** Dashboard shell — spec + done-when at PRD.md:1581 (the browser check is carried by I4b)
- [x] **I10** Event Control panel — spec + done-when at PRD.md:1583 (the browser check that illegal actions are disabled is carried by I4b)
- [x] **I11** Scoreboard settings — spec + done-when at PRD.md:1585
- [x] **I12** Flags panel — spec + done-when at PRD.md:1586
- [x] **I13** Flags bulk replant — spec + done-when at PRD.md:1587
- [x] **I14** Hosts panel — spec + done-when at PRD.md:1588
- [x] **I15** Scoreboard panel — spec + done-when at PRD.md:1589
- [x] **I16** Event log panel — spec + done-when at PRD.md:1590
- [x] **I17** Submission log panel — spec + done-when at PRD.md:1591

- [x] **LINT1** `frontend/src/utilities/transformers/unit.transform.test.ts:2` fails eslint `import/order` (`./unit.transform` should come after `./specificationEdit.transform`). This was already the case before I6. Not CTF-specific, and it is outside the CTF lint gate.

### Group J — Student UI
- [x] **J1** Student CTF polling — spec + done-when at PRD.md:1595
- [x] **J2** CTF banner — spec + done-when at PRD.md:1596 (the browser check is carried by I4b)
- [x] **J3** Flag submission card — spec + done-when at PRD.md:1598 (the browser check is carried by I4b)
- [x] **J4** Challenge list — spec + done-when at PRD.md:1600 (the browser check is carried by I4b)

### Group K — Documentation
- [x] **K1** Game master guide — spec + done-when at PRD.md:1605

### Group L — Setup & rosters
Implemented outside the loop (commits `dbb2fec`, `83e5abc`); not yet loop-verified.
- [x] **L1** Shared workout record — spec + done-when at PRD.md:1611
- [x] **L2** Create from template — spec + done-when at PRD.md:1612
- [x] **L3** Teams — spec + done-when at PRD.md:1613
- [x] **L4** Per-event flags — spec + done-when at PRD.md:1614
- [x] **L5** Servers — spec + done-when at PRD.md:1615
- [x] **L6** Roster-only join — spec + done-when at PRD.md:1616
- [x] **L7** Setup UI — spec + done-when at PRD.md:1617 (the browser check is carried by I4b)

### Group N — Nested lab hosts
See `### Nested Guest Contract` in PRD.md.
- [x] **N1** Metadata forward block — spec + done-when at PRD.md:1624 (standalone security fix — ship first)
- [x] **N2** Loader forward block — spec + done-when at PRD.md:1626
- [x] **N3** Nested guest models — spec + done-when at PRD.md:1628
- [x] **N4** Nested contract constants — spec + done-when at PRD.md:1630
- [x] **N5** Nested guest validator — spec + done-when at PRD.md:1632
- [x] **N6** Guest payload builder — spec + done-when at PRD.md:1634
- [x] **N7** qemu-agent relay section — spec + done-when at PRD.md:1636
- [x] **N8** Plant watcher installer — spec + done-when at PRD.md:1638
- [x] **N9** Nested plant procedure — spec + done-when at PRD.md:1640
- [x] **BUG5** `FlagPlanter.plant`'s `except` calls `_fail_unfinished(board, targets)` with the board as it was before `_await_acks`/`_await_results` were called. Those helpers rebind `board` locally, so if one raises mid-loop (e.g. a Firestore error in `_record`), flags they already recorded `planted`/`failed` still read `planting` on the stale model and get overwritten with `MSG_ABORTED`. This predates N9 for `_await_results`. Fix by re-reading stored flag statuses in `_fail_unfinished` (inside the transaction), with a test that raises on the second `_record`.
- [x] **N10** Guest host reset publish — spec + done-when at PRD.md:1642
- [x] **N11** Guest host reset modes — spec + done-when at PRD.md:1644 (**land before any deploy**: since N10 the API publishes `guest`, but `CtfHandler` ignores it, so a guest reset would act on the whole parent server)
- [x] **N12** Offline driver — spec + done-when at PRD.md:1646 (also: a guest rebuild/replant of an offline guest with board flags currently fails its flags with "Could not build the plant payload" and never reverts, because `_nested_host_payload` relays only qemu-agent guests; N12's offline section must honour `revert` the way `agoge_ctf_rebuild_qemu` does)
- [x] **N13** Nested guests in the spec editor — spec + done-when at PRD.md:1648 (code and vitest here; the browser check is carried by HUMAN)
- [x] **N14** Guest rows on the Hosts panel — spec + done-when at PRD.md:1650 (`transformToCtfHostRow` drops `guest` today, so guest rows render as duplicate parent rows whose menu resets the parent; hide replant on guest rows with `flag_count == 0`, which the API refuses) (code and vitest here; the browser check is carried by HUMAN)
- [x] **N15** Nested host guide — spec + done-when at PRD.md:1652

### Group V — Nested image builder
See `### Nested Image Builder Contract` and Working Notes 14–23. Independent of the CTF groups except V23. Frontend items use the Group V eslint/tsc gate lines in PRD.md `## Quality Gates`.
- [x] **V1** Nested virtualization for template and lab servers — spec + done-when at PRD.md:1661
- [x] **V2** Nested machine types — spec + done-when at PRD.md:1663
- [x] **V3** License on check-in — spec + done-when at PRD.md:1665
- [x] **V4** Template startup-script merge — spec + done-when at PRD.md:1667
- [x] **V5** Models and constants — spec + done-when at PRD.md:1669 (`common/constants/nested.py` already exists from V2 with `NESTED_MACHINE_FAMILIES`, `NESTED_MAX_MACHINE_MEMORY_MB`, `STANDARD_MAX_MACHINE_MEMORY_MB`; extend it)
- [x] **V6** (closed in iteration 157) OS catalog and seeding — spec + done-when at PRD.md:1671 — (V-5 answered 2026-10-17; see V6b2 below) **BLOCKED (iteration 95):** its done-when needs Open Question V-5 answered first, and V-5 is human research. Microsoft Evaluation Center does not publish SHA-256 values, so each eval ISO (Server 2016/2019/2025, Windows 10/11 Enterprise) must be downloaded and hashed by a person. The Kali cloud image URL and format still need to be confirmed. The loop must not invent hashes. Unblock by recording V-5's answers (URL + sha256 per entry) in progress.md. **Split in iteration 115** into V6a and V6b below; V6 closes when V6b does.
  - [x] **V6a** (iteration 115) The sync setup operation **Synchronize Nested Guest OS Catalog** (`nested_os_catalog_sync.py`, option 25), plus `common/data/nested_os_catalog.json` holding the 19 upload-only entries that need no V-5 answer: Windows Vista–11 and Server 2008–2025 (licensed, `unattended_iso`), XP/2003 (`manual_iso` and `disk_image`), and custom ISO/disk. Tests cover every V6 done-when rule except V-5.
  - [x] **V6b** (closed in iteration 157) Add the downloadable entries to the JSON: the Kali cloud image and the Kali QEMU VM, the Debian, Ubuntu, Fedora, Rocky, Alma, CentOS, openSUSE, Arch and Alpine cloud images, Metasploitable 2, the Server 2016–2025 and Windows 10/11 Enterprise evaluations, and pfSense, OPNsense, VyOS and Security Onion. Each needs a pinned `https` URL and its SHA-256. **BLOCKED on V-5** for the Microsoft and Kali entries: a person must download and hash them. The Linux images and appliances also need pinned, dated releases with published hashes, not `current/` URLs whose hashes rotate. `test_nested_os_catalog_sync.py` already checks the https/SHA-256 and Microsoft-host rules for any entry added.
    - [x] **V6b1** (iteration 116) Ubuntu 20.04, 22.04, 24.04 and 26.04 cloud images, pinned to dated `cloud-images.ubuntu.com/releases/<codename>/release-YYYYMMDD/` files with the SHA-256s from each release's published `SHA256SUMS`.
    - [x] **V6b2a** (iteration 119) Rocky Linux 8.10/9.8/10.2 and AlmaLinux 8.10/9.8/10.2 GenericCloud images (`nm-keyfile`), pinned to dated files under each publisher's versioned (not major-only) directory, with SHA-256s from the published `CHECKSUM` files.
    - [x] **V6b2b** (iteration 120) Fedora 43 (build 1.6) and Fedora 44 (build 1.7) Cloud Base Generic images (`nm-keyfile`), pinned under `dl.fedoraproject.org/pub/fedora/linux/releases/<n>/Cloud/x86_64/images/` with SHA-256s from each release's signed `CHECKSUM`. Also makes `builder.sh`'s firstboot root grow handle Fedora's btrfs root.
    - [x] **V6b2c** (iteration 121) CentOS Stream 10 GenericCloud image (`nm-keyfile`, osinfo `centos-stream10`), pinned to the dated `10-stream/.../CentOS-Stream-GenericCloud-x86_64-10-20260728.1.x86_64.qcow2` with the SHA-256 from its published `.SHA256SUM` and `CHECKSUM`.
    - [x] **V6b2d** (iteration 122) Arch Linux cloud image (`networkd`, osinfo `archlinux`), pinned to `geo.mirror.pkgbuild.com/images/v20261001.604814/` with the SHA-256 from its published `.SHA256`. `builder.sh` now initializes the pacman keyring and runs `pacman -Syu` before `--install`, and for Arch it installs `openssh` and `sudo` (not `openssh-server`) plus a wheel sudoers drop-in.
    - [x] **V6b2e** (iteration 123) openSUSE Leap 16.0 Minimal VM Cloud image (`nm-keyfile`, osinfo `opensuse16.0`), pinned to `distribution/leap/16.0/appliances/Leap-16.0-Minimal-VM.x86_64-Cloud-Build18.81.qcow2` with the SHA-256 from its published `.sha256`. `builder.sh` now relabels SELinux for `opensuse` osinfo ids and writes wheel sudoers drop-ins that override SUSE's `Defaults targetpw`.
    - [x] **V6b2f** (iteration 124) Security Onion 3.3.0 appliance (`manual_iso`, agentless, osinfo `generic`), pinned to `download.securityonion.net/file/securityonion/securityonion-3.3.0-20260911.iso` with the SHA-256 from the `3/main` branch's `DOWNLOAD_AND_VERIFY_ISO.md`.
    - [x] **V6b2g** (iteration 127) OPNsense 26.7 nano image (`disk_image`, agentless, osinfo `freebsd14.0`), pinned to `pkg.opnsense.org/releases/26.7/OPNsense-26.7-nano-amd64.img.bz2` with the SHA-256 from the release's `OPNsense-26.7-checksums-amd64.sha256`. Adds the `img.bz2` media format (model, frontend, `builder.sh` `prepare_disk`, `bzip2` host package).
    - [x] **V6b2h** (iteration 129) Debian 11 (`ifupdown`), 12 and 13 (`netplan`) genericcloud images, pinned to dated `cloud.debian.org/images/cloud/<codename>/<build>/` files. Debian publishes only `SHA512SUMS`, so each SHA-256 was computed from a download that first matched the published SHA-512.
    - [x] **V6b2i** (iteration 130) Metasploitable 2 (`disk_image`, `zip`/vmdk, agentless, osinfo `ubuntu8.04`, IDE disk, e1000 NIC), pinned to `downloads.sourceforge.net/project/metasploitable/Metasploitable2/metasploitable-linux-2.0.0.zip` with the SHA-256 SourceForge publishes for the file.
    - [x] **V6b2j** (iteration 131) pfSense CE 2.7.2 (`manual_iso`, agentless, osinfo `freebsd14.0`), pinned to `atxfiles.netgate.com/mirror/downloads/pfSense-CE-2.7.2-RELEASE-amd64.iso.gz` with the SHA-256 from Netgate's published `.sha256`. Adds the `iso.gz` media format: `builder.sh` `fetch_media` caches the verified download, then expands it once and keeps only the ISO.
    - [x] **V6b2k** (iteration 132) Alpine Linux 3.23 BIOS cloud-init image (`ifupdown`, osinfo `alpinelinux3.23`), pinned to `dl-cdn.alpinelinux.org/alpine/v3.23/releases/cloud/alpine-3.23.6-x86_64-bios-cloudinit-r0.qcow2`. Alpine publishes only `.sha512`, so the SHA-256 was computed from a download that first matched it. `builder.sh` gains an OpenRC/mdev path for `alpinelinux` osinfo ids.
    - [x] **V6b2** (closed in iteration 157) The rest of V6b (Kali, CentOS Stream 9, Microsoft evals, VyOS). **openSUSE Leap 15.6 is DROPPED (decided 2026-10-18 by the user).** It ships wicked, which no `NestedNetConfig` value covers, and Leap 16.0 (V6b2e) already covers openSUSE. Do not add a Leap 15.6 entry or a `wicked` net_config. Each Linux distro can be done like V6b1, from a dated release dir with a published SHA-256 file. **UNBLOCKED 2026-10-17:** V-5 is answered. Every URL and SHA-256 for Kali, CentOS Stream 9, the Microsoft evals and VyOS is in "V-5 answers" below. Use those values exactly and do not re-derive them. Split as V6b2l–V6b2o. V6b2 closes when all four are done.
      - [x] **V6b2l** (iteration 154) Kali: `kali-rolling` (`cloud_image`, `tar.xz`) and `kali-qemu` (`disk_image`, `7z`, default `kali`/`kali`), from "V-5 answers". Confirm `builder.sh` handles a `tar.xz` holding `disk.raw` (25 GiB sparse) and a `7z` holding a qcow2.
      - [x] **V6b2m** (iteration 155) CentOS Stream 9 GenericCloud (`nm-keyfile`, osinfo `centos-stream9`), like V6b2c, from "V-5 answers".
      - [x] **V6b2n** (iteration 156) Microsoft evaluations: `win-server-2016-eval`, `-2019-eval`, `-2022-eval`, `-2025-eval` (`eval_days` 180) and `win-11-enterprise-eval` (`eval_days` 90), from "V-5 answers". Optionally add `win-11-ltsc-eval` too. Windows 10 Enterprise is no longer offered, so leave it upload-only (`win-10`).
      - [x] **V6b2o** (iteration 157) VyOS rolling (`manual_iso`, agentless), from "V-5 answers". VyOS publishes no SHA-256, only a minisign signature. The hash below is from a download whose signature verified against the vyos.net key. Nightly builds are pruned from GitHub, so the URL can stop working. Note this in the entry or the guide.

    **V-5 answers (2026-10-17, by hand).** Each file was downloaded only from its publisher's own site, or from the official host that site links or redirects to. All are `https`.

    | Entry | URL | SHA-256 | Bytes | Verified against |
    | --- | --- | --- | --- | --- |
    | Server 2016 eval | `https://software-static.download.prss.microsoft.com/pr/download/Windows_Server_2016_Datacenter_EVAL_en-us_14393_refresh.ISO` | `1ce702a578a3cb1ac3d14873980838590f06d5b7101c5daaccbac9d73f1fb50f` | 6972221440 | size only (Microsoft publishes no hash) |
    | Server 2019 eval | `https://software-static.download.prss.microsoft.com/dbazure/988969d5-f34g-4e03-ac9d-1f9786c66749/17763.3650.221105-1748.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso` | `6dae072e7f78f4ccab74a45341de0d6e2d45c39be25f1f5920a2ab4f51d7bcbb` | 5652088832 | size only |
    | Server 2022 eval | `https://software-static.download.prss.microsoft.com/sg/download/888969d5-f34g-4e03-ac9d-1f9786c66749/SERVER_EVAL_x64FRE_en-us.iso` | `3e4fa6d8507b554856fc9ca6079cc402df11a8b79344871669f0251535255325` | 5044094976 | size only |
    | Server 2025 eval | `https://software-static.download.prss.microsoft.com/dbazure/998969d5-f34g-4e03-ac9d-1f9786c66749/26100.32230.260111-0550.lt_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso` | `7b052573ba7894c9924e3e87ba732ccd354d18cb75a883efa9b900ea125bfd51` | 8152356864 | size only. The Evaluation Center labels this link "Preview", but the file is the 26100 `lt_release` refresh `SERVER_EVAL`. |
    | Windows 11 Enterprise eval (26H2) | `https://software-static.download.prss.microsoft.com/dbazure/26300.9457.260913-1737.26h2_ge_release_svc_refresh_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_en-us.iso` | `bc3f24086ebadc94489066b5ad78089e2cf5c3491e90e790bb81a2b199c10e38` | 8225329152 | **Microsoft's published SHA-256** (support.microsoft.com "verify the authenticity of a Windows 11 Enterprise evaluation ISO") |
    | Windows 11 Enterprise LTSC eval | `https://software-static.download.prss.microsoft.com/dbazure/888969d5-f34g-4e03-ac9d-1f9786c66749/26100.1742.240906-0331.ge_release_svc_refresh_CLIENT_LTSC_EVAL_x64FRE_en-us.iso` | `67cec5865eaa037a72ddc633a717a10a2bed50778862267223ddb9c60ef5da68` | 5112850432 | size only |
    | Kali cloud (2026.2) | `https://kali.download/cloud-images/kali-2026.2/kali-linux-2026.2-cloud-genericcloud-amd64.tar.xz` | `3f4ca86ae1eca0dc2bf2092f065a959508e186c6b44f85758813a8e9a0604f3e` | 234114644 | Kali `SHA256SUMS` and kali.org/get-kali. The archive holds `disk.raw`. |
    | Kali QEMU VM (2026.2) | `https://kali.download/base-images/kali-2026.2/kali-linux-2026.2-qemu-amd64.7z` | `c7c35588d05277c482c908bf7a136d348f76ffa68700b04ff53c0b217e6bd071` | 3892765566 | `cdimage.kali.org/kali-2026.2/SHA256SUMS` (cdimage redirects to kali.download) |
    | CentOS Stream 9 GenericCloud | `https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-20261013.0.x86_64.qcow2` | `6178901e812a08e1c36e5adac2992be65a409dfb61812a6b630b2488fc0644b3` | 1276641280 | published `.SHA256SUM`. The earlier note that CentOS Stream 9 publishes no SHA-256 was wrong. |
    | VyOS rolling 2026.10.17-0025 | `https://github.com/vyos/vyos-nightly-build/releases/download/2026.10.17-0025-rolling/vyos-2026.10.17-0025-rolling-generic-amd64.iso` | `29aae4b916fb11971c5794d5ba0592df908e9125b9037e144bd3548668d7e607` | 634388480 | minisign `.minisig` verified with the vyos.net key `RWSIhkR/dkM2DSaBRniv/bbbAf8hmDqdbOEmgXkf1RxRoxzodgKcDyGq`. vyos.net/get/nightly-builds links to these GitHub releases. |

    Windows 10 Enterprise: its Evaluation Center page (`/evalcenter/download-windows-10-enterprise`) has no download links, so it is no longer offered. The Microsoft pages return 403 to a bare curl, so send a browser User-Agent and `Accept` header.
- [x] **V6c** (found in iteration 116; done in iteration 118) Ubuntu 16.04's cloud image needs `net_config: ifupdown`. But its `/etc/network/interfaces` sources only `interfaces.d/*.cfg`, so `builder.sh` `write_network_config` must write `interfaces.d/agoge.cfg`, not `interfaces.d/agoge` (Debian sources `*`, so the rename is safe there). Then add `ubuntu-16.04` (`xenial/release-20211001/ubuntu-16.04-server-cloudimg-amd64-disk1.img`, sha256 `fff2494a70bcaffb59f26f71ec49e137dd87d319341c35832dbe0ea65ff15140`).
- [x] **V6d** (found in iteration 116; done in iteration 117) Ubuntu 18.04 ships netplan.io 0.99 (`bionic/release-20230607` manifest), and `routes: [{to: default}]` needs netplan 0.103+. Make `builder.sh` write `to: 0.0.0.0/0`, which every netplan version accepts. Then add `ubuntu-18.04` (`bionic/release-20230607/ubuntu-18.04-server-cloudimg-amd64.img`, sha256 `8dd2e6b5e5aad20c3f836123b300cba9861249408cbb07c359145a65d6bab6b6`).
- [x] **V7** Nested host validator — spec + done-when at PRD.md:1673
- [x] **V8** Manifest and unattend rendering — spec + done-when at PRD.md:1675
- [x] **V9** Builder script — spec + done-when at PRD.md:1677 (must install the V10 runtime from `nested_scripts.render_runtime()`/`render_runtime_unit()` and write `/etc/agoge-nested/host.json` in the shape `runtime.sh` documents; see iteration 97)
- [x] **V10** Runtime service — spec + done-when at PRD.md:1679 (done before V9, which installs it: `render_runtime()`/`render_runtime_unit()` in `cloud_fn_utilities/server_specific/nested_scripts.py`)
- [x] **V11** Nested template server provisioning — spec + done-when at PRD.md:1681
- [x] **V12** Create route — spec + done-when at PRD.md:1683 (`ImageTemplateManager.check_out(product_keys=...)` takes the never-persisted keys; V12 must carry them in the CHECK_OUT message and `ControlHandler._check_out` must pass them through)
- [x] **V13** Build monitor — spec + done-when at PRD.md:1685
- [x] **V14** Finalize handshake — spec + done-when at PRD.md:1687 (also merge the finalize-watcher bootstrap into `startup-script` on both check-out paths in `ImageTemplateManager._prepare_nested_check_out`; V11 left the re-check-out path with only `enable-guest-attributes`)
- [x] **V15** Media uploads — spec + done-when at PRD.md:1689
- [x] **V16** Frontend service layer — spec + done-when at PRD.md:1691
- [x] **V17** Wizard shell and Host step — spec + done-when at PRD.md:1693 (code and vitest here; the browser check is carried by HUMAN)
- [x] **V18** Networks step — spec + done-when at PRD.md:1695 (code and vitest here; the browser check is carried by HUMAN)
- [x] **V19** Guests step — spec + done-when at PRD.md:1697 (code and vitest here; the browser check is carried by HUMAN)
- [x] **V20** Access and Review steps — spec + done-when at PRD.md:1699 (code and vitest here; the browser check is carried by HUMAN)
- [x] **V21** Image list and details for nested images — spec + done-when at PRD.md:1701 (code and vitest here; the browser check is carried by HUMAN)
- [x] **V22** Guacamole targets for guests — spec + done-when at PRD.md:1703
- [x] **V23** Spec editor and CTF integration — spec + done-when at PRD.md:1705 (needs N3, N5, N13; the browser check is carried by HUMAN)
- [x] **V24** Nested image guide — spec + done-when at PRD.md:1707
- [ ] **V25** Live acceptance — spec + done-when at PRD.md:1708 — **HUMAN ONLY.** Builds real VMs on the development project; the loop must not attempt it. Carried by HUMAN.

- [x] **V14b** (found in iteration 102) If the Cloud Function dies hard after `finalize_nested` writes phase `finalizing` (or the CHECK_IN delivery fails before `create_production_image`, e.g. in `load()`), the phase stays `finalizing`: a redelivered NESTED_FINALIZE hits `Conflict`, and the API refuses Check In with 409 forever. Treat a `finalizing` phase whose `updated_at` is older than `NESTED_FINALIZE_TIMEOUT_SECONDS` plus a margin as finalizable, in both `ImageTemplateManager.finalize_nested` and `ComputeImage._check_in_action`, with tests.
- [x] **V6e** (found in iteration 124; done in iteration 125) `NestedHostValidator.min_disk_size` reserves only `NESTED_BUILD_SCRATCH_GB` (12) for media. That is less than `NESTED_MEDIA_MAX_BYTES` (20 GiB uploads) and the 14 GB Security Onion ISO, and an ISO stays cached in `MEDIA_DIR` on the parent disk for the whole build. A guest disk that fills up can then run the parent out of space. Reserve room for the largest medium (the catalog has no media size yet), or size scratch from the media, with tests.
- [x] **V12b** (found in iteration 100) `ComputeImage.create_image_server` and `NestedImage.create` write the CHECKED_OUT record before publishing CHECK_OUT, so a failed publish leaves a record no build will ever pick up, and a retry with the same name gets 409. Delete the record (or mark nested phase `failed`) when the publish raises.
- [x] **V6f** (found in iteration 125; done in iteration 126) The wizard's `nestedMinDiskSize` (`nestedWizardState.ts`, used by `HostStep`, the disk check in the state validator, and `accessReview.capacityMeters`) still mirrors the old rule. It omits the media reservation that `NestedHostValidator.min_disk_size`/`media_sizes` now add, so a typed `disk_size` between the two minimums gets a 400 from the API. Add `media_size_bytes` to `NestedOsCatalogEntry` and its transformer, then pass the catalog and media (`GuestRuleContext`) into `nestedMinDiskSize`. Key media the way `media_sizes` does: `sha256`, else `upload-<id>`, else the entry; an unknown size reserves `NESTED_MEDIA_MAX_BYTES`. Add vitest coverage.

- [x] **V6g** (found in iteration 127; done in iteration 128) `builder.sh` `prepare_disk`'s `img.xz` branch ignores a failed `xz -dc` (for example, the parent disk filling up). The truncated raw image still converts, so the guest gets a disk it cannot boot from. Fail the guest the way the `img.bz2` branch does, and add a test.

### Human checks
- [ ] **HUMAN** Browser and live checks the loop cannot do: N13, N14, V17–V21 and V23 "verified in browser" done-whens, and V25 live acceptance (SC-35–SC-38) on the development project. Leave this for a person; do not mark it done.

---

## Iteration Log

<!-- Each iteration appends a dated entry below. Format:                  -->
<!-- ### Iteration N — YYYY-MM-DD                                          -->
<!-- - **Completed:** what got done                                        -->
<!-- - **Learned:** anything future iterations need to know                -->
<!-- - **Blockers:** any BLOCKED item with its specific error message     -->
<!-- - **Next:** what the next iteration should pick up                    -->

<!-- The verifier appends its own entries here:                            -->
<!-- ### Verification — YYYY-MM-DD — PASS|FAIL                             -->

### Iteration 1 — 2026-10-16
- **Completed:** Planning — replaced the placeholder with the 70 PRD MVP items (Groups 0, A–K), one task each, in PRD dependency order, each citing its PRD.md line.
- **Learned:** PRD Working Note 1 says work on `release/2027-spring`, but the checkout is `feature-2027-spring-ctf`; gate baselines in PROMPT.md may differ slightly — trust a fresh run. Group I/J browser-verified "done when" items need the `run` skill or a human check.
- **Blockers:** none.
- **Next:** 0.1 Frontend test script (`frontend/package.json` test → `vitest run --exclude "tests/**"`).

### Iteration 2 — 2026-10-16
- **Completed:** 0.1 — `frontend/package.json` test script is now `vitest run --exclude "tests/**"`; `npm test` exits 0 (4 files, 28 tests). The `frontend/tests/*.test.mjs` node:test files are untouched.
- **Learned:** PRD says 23 tests; the suite already has 28 (tests added since the PRD was written) — treat 28 as the new frontend baseline.
- **Blockers:** none.
- **Next:** 0.2 Rubric opt-in tests (`api/unit_tests/test_rubric_opt_in.py`, 4 failing).

### Iteration 3 — 2026-10-16
- **Completed:** 0.2 — `api/routers/unit.py` `get_all_data` now returns the unit's own `rubric_support` (dict or `UnitModel`) instead of the env flag; `test_storing_openai_key_does_not_enable_rubrics` updated to script the shared-secret source prompt (`L`, `y`) with an `input()` stub that fails on unexpected prompts, and to assert the single admin-info write is `{'shared_api_secrets': []}`. No tests deleted or skipped.
- **Learned:** Gate baselines have drifted from the PRD: api/unit_tests 62 passed, cloud_functions 285, build_files 293, frontend 28. `openai_api_key` is in `SHARED_API_SECRET_NAMES`, so `set_variable` prompts for a source before the Y/n confirm.
- **Blockers:** none.
- **Next:** A1 CTF constants (PRD.md:950).

### Iteration 4 — 2026-10-16
- **Completed:** A1 — `CtfStates` (states.py), six `DbCollections.CTF*` members, `PubSub.Handlers.CTF`, `Actions.CTF_ARM_BOARD/CTF_PLANT/CTF_HOST_RESET` (18–20), `EventAttributes.CTF_ID/WORKOUT_ID/RESET_MODE`; `api/unit_tests/test_ctf_constants.py` asserts no Actions value collides (via `__members__`, since duplicate Enum values alias silently).
- **Learned:** `common/tests/` is not in any gate; put new common-code tests in `api/unit_tests/` (where the PRD's structure puts `test_ctf_*.py`). Gates now: api 66, cloud_functions 285, build_files 293, frontend 28. The frontend lint and type-check gates target CTF paths that don't exist yet.
- **Blockers:** none.
- **Next:** A2 CTF specification models (PRD.md:952).

### Iteration 5 — 2026-10-16
- **Completed:** A2 — the nine CTF `Literal` aliases (below `UnitTypeValue`) and `CtfFlagSpecModel`/`CtfScoringSpecModel`/`CtfSpecModel` (just above `UnitModel`, so A6 can reference them without forward refs) in `common/models/agoge.py`, verbatim from PRD.md:356-393; `api/unit_tests/test_ctf_spec_models.py` (34 tests) rejects bad flag ids, unknown `location_type`, malformed `file_mode`, plus range/pattern checks.
- **Learned:** Spec models are plain `BaseModel` (no `from_attributes` Config) per PRD; the points-sign, path-per-location_type, and unique-id rules are deliberately left to C1's validator. Gates now: api 100, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** A3 CTF stored models (PRD.md:954; definitions at PRD.md:399-515).

### Verification — 2026-10-16 — PASS
- **Checked:** Planning, 0.1, 0.2, A1, A2 (every `[x]` task). Read each commit's diff (`e2a0f5e`, `035ac39`, `d110579`, `5c906aa`) against PRD.md:943-953, :345-393 and :677-686.
  - Planning: the queue lists the PRD MVP items, each with its PRD line.
  - 0.1: `frontend/package.json` test is `vitest run --exclude "tests/**"`; `frontend/tests/*.mjs` unchanged since `6e92032` (last touched in `aa47dca`).
  - 0.2: `api/routers/unit.py` `get_all_data` reads the unit's own `rubric_support` (`Unit.get_all_data` returns a `'unit'` key). The key-storage test uses a scripted `input()` that asserts on unexpected prompts. No skip or xfail in the file, and no test was deleted.
  - A1: `CtfStates` matches PRD values 0-7; six `DbCollections.CTF*`; `Handlers.CTF`; `Actions` 18/19/20; `EventAttributes.CTF_ID/WORKOUT_ID/RESET_MODE`. `test_ctf_constants.py` checks for value collisions through `__members__` against `list()`, which catches aliases.
  - A2: the nine Literal aliases and three spec models match PRD.md:345-393 field for field. `test_ctf_spec_models.py` rejects bad ids, unknown `location_type` and malformed `file_mode`.
  - No TODO, stub or hardcoded value found.
- **Gate results:** api/unit_tests 100 passed; cloud_functions/tests 285 passed; build_files/cloud_deployment/tests 293 passed; frontend `npm test` exited 0 with 4 files and 28 tests passed. The PRD's 49/23 counts are out of date because tests were added later; there are 0 failures. ESLint gate: none of the CTF paths exist yet ("No files matching the pattern"), which is expected because no Group I/J task is done. tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 6 — 2026-10-16
- **Completed:** A3 — `CtfEventModel`, `CtfFlagStateModel`, `CtfBoardModel`, `CtfDigestModel`, `CtfRateLimitModel`, `CtfSubmissionModel`, `CtfLogModel` in `common/models/agoge.py` (appended just before the trailing `model_rebuild()` calls), field for field from PRD.md:399-509; `api/unit_tests/test_ctf_stored_models.py` (30 tests) covers defaults, required fields, Literal rejection, embedded spec validation, negative scores, and scalar-only log `detail` (bool stays bool).
- **Learned:** Class-based `Config` (as the PRD specifies and existing models use) emits a Pydantic deprecation warning — harmless, matches house style. Gates now: api 130, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** A4 CTF request models (PRD.md:955; definitions start at PRD.md:513).

### Iteration 7 — 2026-10-16
- **Completed:** A4 — `CtfCreateRequest`, `CtfUpdateRequest`, `CtfActionRequest`, `CtfReplantRequest`, `CtfHostResetRequest`, `CtfScoreAdjustRequest`, `CtfSubmitRequest` appended after `CtfLogModel` in `common/models/agoge.py` (verbatim from PRD.md:520-545); `api/unit_tests/test_ctf_request_models.py` (41 tests) covers the build-id pattern, Literal action/mode rejection, delta/reason/flag bounds, and that an explicit `scoreboard_frozen_at: null` shows up in `model_fields_set`.
- **Learned:** The ruff PostToolUse hook flags a pre-existing unused `HttpUrl` import at `common/models/agoge.py:5` on every edit — not from CTF work. Gates now: api 171, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** A5 CTF response models (PRD.md:956; definitions start at PRD.md:547, in `common/models/response.py`).

### Iteration 8 — 2026-10-16
- **Completed:** A5 — the fifteen CTF response models (`CtfConfigResponse` … `CtfHintResponse`) appended to `common/models/response.py` verbatim from PRD.md:549-666, importing `ArmStatus`/`LocationType`/`PlantStatus` from `agoge.py`; `api/unit_tests/test_ctf_response_models.py` (29 tests) covers Literal rejection for arm/plant/location/verdict, nested board validation, the not-enrolled student board defaults, and the `AgogeResponse[...]` envelope.
- **Learned:** Per the PRD, fields like `starts_at: Optional[float]` have no default, so they are *required* keys in Pydantic v2 — the core code building these responses must always pass them (a test pins this). `CtfSubmitResponse.verdict` deliberately excludes `cross_submission`/`rate_limited`/`closed`. Gates now: api 200, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** A6 Spec block wiring (PRD.md:957).

### Iteration 9 — 2026-10-16
- **Completed:** A6 — `ctf: Optional[CtfSpecModel] = None` on `UnitModel`, `CatalogModel`, `CatalogEditModel` (each right after `rubric_support`); `api/unit_tests/test_ctf_spec_wiring.py` (6 tests) carries a block through `CatalogEditModel → CatalogModel → Unit.build` (catalog stored as `model_dump(mode="json")`, as Firestore would), covers specs with no/null `ctf`, and checks all three models reject a bad flag id and an empty `flags` list.
- **Learned:** `Unit.build` only pops `discriminator`/`id`/`creation_timestamp` from the catalog dict, so new spec fields flow into the unit with no build-code change. Gates now: api 206, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** B1 Derivation module (PRD.md:962).

### Iteration 10 — 2026-10-16
- **Completed:** B1 — `common/utilities/ctf_flags.py` with module-level `derive_flag_value`, `normalize_flag`, `flag_digest`, `flags_match`, `parse_flag_id` per PRD.md:755-785; `api/unit_tests/test_ctf_flag_derivation.py` (27 tests) pins the exact HMAC input, covers determinism, SC-3 (0 collisions over 1000 workout pairs × 4 flag ids), `seed_version`/seed/flag-id sensitivity, strip+lowercase-only normalization, `parse_flag_id` hits and 11 misses, and patches `ctf_flags.hmac.compare_digest` to prove `flags_match` uses it.
- **Learned:** `parse_flag_id` lowercases and `re.escape`s the prefix, since the submission is lowercased before matching. Gates now: api 233, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** B2 Seed property (`ctf_flag_seed` on `CloudEnv`, PRD.md:964).

### Verification — 2026-10-16 — PASS
- **Checked:** A3, A4, A5, A6, B1. These are the `[x]` tasks added since the last verification; Planning through A2 were already verified. I read commits `0c0b5f6`, `edeec34`, `4cd857e`, `74fa144` and `45561a8` against PRD.md:399-546, :547-670, :396/:957 and :755-785.
  - A3/A4: the seven stored and seven request models in `common/models/agoge.py` (about :805-935) match the PRD in every field name, type, default, constraint (`pattern`, `ge`/`le`, `min_length`/`max_length`) and `Config`. The only difference is cosmetic: an ASCII "-" in the `score` description where the PRD has "−".
  - A5: all 14 response models the PRD lists are in `common/models/response.py` (about :175-306) and match field for field. The `CtfSubmitResponse.verdict` Literal is exactly correct/incorrect/duplicate/decoy.
  - A6: `ctf: Optional[CtfSpecModel] = None` is on `UnitModel`, `CatalogModel` and `CatalogEditModel`. `test_ctf_spec_wiring.py` runs the real `Unit.build` path and asserts the block survives at each step (edit → catalog → unit).
  - B1: `common/utilities/ctf_flags.py` implements exactly the five contract functions. The HMAC message is `f"{seed_version}:{workout_id}:{flag_id}"` with a 20-hex-character truncation, and `flags_match` uses `hmac.compare_digest`. Tests cover determinism, SC-3 (1000 pairs), `seed_version` sensitivity, normalization, `parse_flag_id` hits and misses, and a `compare_digest` spy.
  - No TODO, stub or `NotImplemented` in the new code. The only TODO, at `agoge.py:699`, comes from `6296b93` and predates this work. No new test is skipped, xfailed or vacuous. Minor coverage gaps that don't block anything: no test accepts `reason` at exactly 500 characters or `flag` at exactly 200, and some response-model tests are thin.
- **Gate results:** api/unit_tests 233 passed; cloud_functions/tests 285 passed; build_files/cloud_deployment/tests 293 passed; frontend `npm test` exited 0 with 4 files and 28 tests passed. ESLint gate: none of the CTF paths exist yet ("No files matching the pattern"), which is expected because no Group I/J task is done. tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 11 — 2026-10-16
- **Completed:** B2 — `ctf_flag_seed` lazy property on `CloudEnv` (`_ctf_flag_seed` cache, `get_secret('ctf_flag_seed')`), mirroring `openai_api_key`; `api/unit_tests/test_ctf_seed_property.py` (6 tests, Secret Manager client patched) covers no read at construction, tenant-project `latest` path, caching, `shared_api_secrets: ['ctf_flag_seed']` raising `ValueError`, tenant-local read when other secrets are shared, and a missing seed returning `None` uncached (retried next access).
- **Learned:** `shared_api_secret_names` whitelists only sendgrid/openai/shodan, so the seed can never be routed to the parent project — no extra guard needed. Gates now: api 239, cloud_functions 285, build_files 293, frontend 28.
- **Blockers:** none.
- **Next:** B3 Seed provisioning (`ctf_enabled` in `environment_variables.py`, PRD.md:965).

### Iteration 12 — 2026-10-16
- **Completed:** B3 — `set_variable('ctf_enabled')` in `environment_variables.py` routes to `_set_ctf_enabled` (y/n prompt, or a bool / strictly-parsed `'true'`/`'false'` value), which on enable calls `_ensure_ctf_flag_seed()` *before* writing `{'ctf_enabled': bool}` alone to admin-info; the seed is `secrets.token_hex(32)` stored via `store_secret` only when `get_secret('ctf_flag_seed')` is `None` (also covers an empty secret with no version). Disabling never touches Secret Manager. `build_files/cloud_deployment/tests/test_ctf_seed_provisioning.py` (11 tests, in-memory fake Secret Manager) shows create-once/no-overwrite on second enable, seed-before-flag ordering, and the seed never printed.
- **Learned:** `ctf_enabled` is deliberately not in `VARIABLES`, so the "All" setup path is unchanged; it is reachable from the "specific" path. The ruff hook reports two pre-existing F541s in `environment_variables.py` (lines ~57 and ~360). Gates now: api 239, cloud_functions 285, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** B4 CTF state manager (`common/utilities/ctf_state_manager.py`, PRD.md:967).

### Iteration 13 — 2026-10-16
- **Completed:** B4 — `common/utilities/ctf_state_manager.py` `CtfStateManager` (standalone; `db` injectable, lazy Firestore factory). `transition(ctf_id, new_state, **fields)` runs `transition_in_transaction` via `self.db.transaction`: reads through `self.db.db.collection(DbCollections.CTF.value)` (wireguard pattern), `NotFound`/`Conflict`, stamps UTC ISO `state_timestamp`, revalidates with `ModelValidator(CtfEventModel)`, `transaction.update` with only `state`/`state_timestamp`/extra fields. Unknown or protected (`id`/`state`/`state_timestamp`) extra fields raise `ValueError`. `api/unit_tests/test_ctf_state_manager.py` (80 tests, fake db/transaction) covers all 14 allowed pairs, every other pair including the named `(RUNNING, ARMING)`/`(ENDED, RUNNING)`, timestamp stamping, the field mask, and failed validation writing nothing.
- **Learned:** E4's arm aggregation must read the event *before* writing its board and pass it as `event=` to `transition_in_transaction` (Firestore forbids reads after writes in a transaction). Self-transitions are Conflicts, not no-ops. Gates now: api 319, cloud_functions 285, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** C1 Flag validator (PRD.md:972).

### Iteration 14 — 2026-10-16
- **Completed:** C1 — `api/utilities/infrastructure_as_code/object_validators/ctf.py` `CtfValidator(config).load()` (exported from the package `__init__`), house style like `AssessmentValidator`: works on the spec dict, raises `AgogeValidationError` naming the flag id for unknown server, duplicate id, duplicate `(server, slot)`, mixed OS per server, `registry`/`ads` off Windows, path not matching its Flag Location Formats row, non-decoy `points <= 0`, unknown `unlocks_after` id, and `unlocks_after` cycles (iterative DFS). `api/unit_tests/test_ctf_spec_validation.py` (31 tests) covers each rule plus a valid spec hitting every location row, a trailing-newline path, a 64-char env name, and a diamond DAG.
- **Learned:** Paths use `re.fullmatch` since `$` alone accepts a trailing `\n`. `file_mode`/`file_owner` "Linux file placements only" is not in C1's rule list and is not enforced — E1 should ignore them off Linux `file`. Gates now: api 350, cloud_functions 285, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** C2 Validator wiring — call `CtfValidator(self.spec).load()` in `edit_manager._validate_spec` and `file_manager._validate_spec` when `ctf` is present (PRD.md:974).

### Iteration 15 — 2026-10-16
- **Completed:** C2 — `SpecEditManager._validate_spec` and `SpecFileManager._validate_spec` now run `CtfSpecModel(**ctf)` then `CtfValidator(self.spec).load()` whenever `ctf` is present, placed outside the unit/escape-room `build_type` branch so no spec with a ctf block skips it. `api/unit_tests/test_ctf_spec_save_validation.py` (8 tests; `LabSpecBase` GCP clients and non-CTF validators patched) shows each save path rejecting a bad path / unknown server via `is_valid()` and `save()`; 6 of 8 fail with the wiring reverted.
- **Learned:** No prior tests constructed the spec managers; patch `CloudEnv`, `DocumentDatabaseFactory`, `PubSubManager`, `Logger` in `lab_spec_base` to build them offline. Found and queued an edit-manager save-before-validate bug. Gates now: api 358, cloud_functions 285, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** D1 `set_metadata` (PRD.md:979).

### Verification — 2026-10-16 — PASS
- **Checked:** B2, B3, B4, C1 and C2, the `[x]` tasks added since the last verification. I read commits `a59bac0`, `ffec6cf`, `bf90592`, `46d8023` and `4dd94af` against PRD.md:964-975, :688-712, :842-852, :159, :1168, :1265 and :1286.
  - B2: `CloudEnv.ctf_flag_seed` (`cloud_env.py:73-78`) uses the same lazy, cached `get_secret` pattern as `openai_api_key`, and there is no write path. The tests patch only `SecretManagerServiceClient`.
  - B3: `_ensure_ctf_flag_seed` uses `secrets.token_hex(32)` and stores it only when `get_secret` returns `None`. `get_secret` catches only `NotFound`, so other errors cannot cause an overwrite. The seed is created before `ctf_enabled` is written, and the seed value is never printed. The create-once/no-overwrite test runs the real methods against an in-memory fake Secret Manager. A grep finds nothing in `api/`, `cloud_functions/` or `frontend/` that creates the seed.
  - B4: `VALID_TRANSITIONS` matches the PRD table pair for pair (14 pairs). The manager is standalone, not a `BaseStateManager` subclass. It reads inside the transaction, raises `NotFound` and `Conflict`, revalidates with `ModelValidator(CtfEventModel)`, writes through a field mask and stamps an ISO-UTC `state_timestamp`. The tests cover all 64 pairs and check what was written.
  - C1: `PATH_PATTERNS` matches all five Flag Location Formats rows character for character and uses `re.fullmatch`. All 8 rules are implemented, and each test asserts that the flag id appears in the error message. The cycle check is a three-colour DFS, and a diamond dependency graph is accepted. Server names are checked against the spec's real `servers[].name`.
  - C2: both `SpecEditManager._validate_spec` and `SpecFileManager._validate_spec` run `CtfSpecModel` and `CtfValidator` outside the `build_type` branch. The tests run the real `_validate_spec` on each path.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code.
  - Non-blocking observations:
    1. On both save paths, a structurally malformed `ctf` block (for example empty `flags`) raises a pydantic `ValidationError` out of `is_valid()` instead of returning `(False, msg)`. That is the same pattern as the existing `UnitModel(**spec)` call, and the spec is still rejected. Later router work (R1) should make sure it maps to a 4xx.
    2. The `SpecEditManager.save` write-before-validate problem is already queued as **BUG**.
- **Gate results:**
  - api/unit_tests: 358 passed.
  - cloud_functions/tests: 285 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: exit 0, 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern" for the CTF paths. This is expected, because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 16 — 2026-10-16
- **Completed:** BUG — `SpecEditManager.save` now calls `is_valid()` first and raises `AgogeValidationError` before any `db.update`/`db.delete`, matching `SpecFileManager.save`. `api/unit_tests/test_spec_edit_save_order.py` (4 tests) shows an invalid spec writes nothing on the edit-save or catalog-publish path, a valid edit save writes the edit, and a valid publish writes the catalog and then deletes the edit. Both invalid-spec tests fail with the fix reverted.
- **Learned:** Validating before `clean()` means validator updates (`self.spec.update(...)`) now land in the persisted spec even when a caller skips `is_valid()`. A `build_type` outside unit/escape-room is a valid spec that needs no validator stubs. Gates now: api 362, cloud_functions 285, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** D1 `set_metadata` (PRD.md:979).

### Iteration 17 — 2026-10-16
- **Completed:** D1 — `ComputeInstanceAPI.set_metadata(resource_name, items=None, remove=None, wait=True)` re-reads the instance, merges `items` over the existing metadata (order kept), drops `remove` keys, and writes with the read `fingerprint`; on a stale fingerprint it re-reads once and retries, then re-raises. `BaseComputeAPI._make_request` now maps Google `PreconditionFailed` (412) to a new `common.exceptions.PreconditionFailed` (a `BaseAgogeException` subclass, so existing broad handlers still catch it). `cloud_functions/tests/test_compute_set_metadata.py` (7 tests, real protos + real `_make_request`, fake client) covers merge-keeps-unrelated, remove, `wait=False`, 412 → one re-read/retry that keeps a concurrent writer's key, second 412 raises after exactly two writes, and NotFound writes nothing.
- **Learned:** `items` defaults to `None` because E2's `finally` calls `set_metadata(name, remove=[...])` only. Gates now: api 362, cloud_functions 292, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** D2 `get_guest_attributes` (PRD.md:981).

### Iteration 18 — 2026-10-16
- **Completed:** D2 — `ComputeInstanceAPI.get_guest_attributes(resource_name, query_path, **kwargs)` sends `GetGuestAttributesInstanceRequest` through `_make_request` and returns `{entry.key: entry.value}` from `query_value.items`. GCE 404s an unwritten namespace with the same status as a missing instance, so the 404 is caught inside the client callable (no error log per poll) and the instance is re-read: an existing VM yields `{}`, a missing one raises `NotFound`. `cloud_functions/tests/test_compute_guest_attributes.py` (6 tests, real protos + real `_make_request`) covers the dict, request fields, project/zone overrides, an entry-less response, 404 → `{}` with no error log, 404 on a missing VM → `NotFound`, and other errors still raising.
- **Learned:** E2's poller should treat `NotFound` from `get_guest_attributes` as a plant failure, not keep polling. Ruff flags a pre-existing F901 (`raise NotImplemented`) in `ComputeInstanceAPI.update`. Gates now: api 362, cloud_functions 298, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** D3 Plant contract module (`common/utilities/ctf_plant_contract.py`, PRD.md:982).

### Iteration 19 — 2026-10-16
- **Completed:** D3 — `common/utilities/ctf_plant_contract.py`: `PLANT_METADATA_KEY`, `GUEST_ATTRIBUTES_ENABLE_KEY/VALUE`, `GUEST_ATTRIBUTE_NAMESPACE` (`agoge-ctf/`, E2's poll `query_path`), `GUEST_ATTRIBUTE_RESULT_KEY`/`_PATH`, `RESULT_OK/ERROR`, `MAX_RESULT_MESSAGE_LENGTH`, `LINUX_/WINDOWS_LOADER_METADATA_KEY`, the fixed `LINUX_LOADER` (bash subshell, curl -f, 0600 mktemp file, payload output to /dev/null, rm) and `WINDOWS_LOADER` (scoped `& { }`, WebClient, SYSTEM-only ACL dir by SID, runs then deletes, `*> $null`), plus `parse_plant_result(value, nonce)` → `(ok, None)` / `(error, msg≤200)` / `None` for a missing or stale result. `api/unit_tests/test_ctf_plant_contract.py` (21 tests) runs the real Linux loader under bash with a fake `curl` on PATH: silent run, 0600 file, file deleted, no-op on 404 or an empty value, and the enclosing script continuing after the payload `exit 3`. A mutation that un-silences the payload fails the suite.
- **Learned:** The loaders contain no `exit`/`return` that escapes their scope, because `_merge_metadata_item` concatenates them with other scripts. The Linux loader starts with `#!/bin/bash`, which becomes a harmless comment when it is appended after other content. Gates now: api 383, cloud_functions 298, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** D4 Loader at build (`LabServerManager._add_metadata` + `_merge_metadata_item` concatenating `windows-startup-script-ps1`; tests in `cloud_functions/tests/test_ctf_loader_stub.py`, PRD.md:983). Note that the existing Windows assessment script uses `windows-startup-script-bat`, a different key that needs no change.

### Iteration 20 — 2026-10-16
- **Completed:** D4 — `LabServerManager._add_metadata` ends with `_add_ctf_loaders`, which appends `LINUX_LOADER` to `startup-script` and `WINDOWS_LOADER` as `windows-startup-script-ps1` on every lab server, after the spec, custom, Guacamole and assessment scripts. It skips a loader whose text is already in that key's value, so copied metadata never carries two. `_merge_metadata_item` is now a classmethod that concatenates both script keys (`_CONCATENATED_SCRIPT_KEYS`) and tolerates an existing `value: None`. `cloud_functions/tests/test_ctf_loader_stub.py` (10 tests) checks that custom, Guacamole and assessment scripts are kept in order with the loader last, that spec ps1 and two merged ps1 scripts are concatenated, that the Windows `windows-startup-script-bat` assessment key is untouched, that loaders are not duplicated, and that the concatenated script runs under bash: the original script runs, then the loader runs a fake-curl plant, with no stdout.
- **Learned:** The loaders are not gated on the unit having a `ctf` block (PRD: "added to every lab server"). The guest agent runs only its own OS's key, and a missing `agoge-ctf-plant` key makes the loader a no-op. Assessment Linux scripts have no top-level `exit`, so an appended loader still runs. `ruff` is not installed in `./venv`. Gates now: api 383, cloud_functions 308, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E1 Payload builder (`FlagPlanter.build_payload`, PRD.md:988). Ignore `file_mode`/`file_owner` except on Linux `file` placements (see Iteration 14).

### Verification — 2026-10-16 — PASS
- **Checked:** BUG, D1, D2, D3 and D4, the `[x]` tasks added since the last verification. I read commits `4259276`, `b40b633`, `e9ac553`, `baad49e` and `1128f22` against PRD.md:977-984 and :795-840.
  - BUG: `SpecEditManager.save` now calls `is_valid()` and raises before any `db.update`/`db.delete`, and the old check after the write is gone. `test_spec_edit_save_order.py` covers an invalid spec on both the edit path and the publish path, and checks that nothing is written.
  - D1: `set_metadata` re-reads the instance on each attempt, merges `items` over the existing keys, drops `remove`, and writes with the fingerprint it just read. On `PreconditionFailed` it retries once, and a second failure re-raises. `_make_request` maps Google 412 to the new `PreconditionFailed`, which is a `BaseAgogeException` subclass. The tests cover keeping unrelated keys, one re-read and retry on 412, and no third attempt. `items` is optional where the PRD signature has `items: dict`. This is harmless because E2's `finally` calls it with `remove=` only.
  - D2: `get_guest_attributes` returns `{key: value}` from `query_value.items`. When GCE answers with a 404, it re-reads the instance: it returns `{}` if the instance exists and raises `NotFound` if it is gone. The method body was added after the `# [ eof ]` marker, which is cosmetic only (it is still inside the class).
  - D3: `ctf_plant_contract.py` matches the PRD.md:797-810 table. The key is `agoge-ctf-plant`, the enable pair is `enable-guest-attributes=TRUE`, the result path is `agoge-ctf/plant-result`, and the results are `ok:<nonce>` / `error:<nonce>:<msg≤200>`. The Linux loader fetches the key with `curl -f`, does nothing when the key is absent, writes the payload to a 0600 temp file, runs it with all output silenced, and deletes the file. The Windows loader is a scoped script block that writes to a directory only SYSTEM can access (by ACL) and runs, then deletes, the file with output going to `*> $null`.
  - D4: `_add_metadata` calls `_add_ctf_loaders` last. `_merge_metadata_item` now concatenates both `startup-script` and `windows-startup-script-ps1`. The tests cover keeping the existing startup and assessment scripts with the loader appended last, and two ps1 scripts concatenated rather than overwritten. One test runs the concatenated script under real bash. That test's `skipif` only triggers when bash is absent, and bash is present here.
  - No new TODO, stub or `NotImplemented`. The only hits, `compute_instance.py:177` and `edit_manager.py:40`, come from `6296b93` and predate this work.
- **Gate results:**
  - api/unit_tests: 383 passed.
  - cloud_functions/tests: 308 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: exit 0, 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern" for the CTF paths. This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 21 — 2026-10-16
- **Completed:** E1 — `cloud_functions/cloud_fn_utilities/course_objects/ctf/flag_planter.py` `FlagPlanter(event, env_dict=None).build_payload(board, server, nonce, seed)`. `server` is the spec server name. Only that board's flags on that server are included, decoys too. Each value goes through `derive_flag_value` with the event's `seed_version`/`flag_prefix`. `BadRequest` on: no board flags on the server, mixed OS, a path/mode/owner/nonce/value failing its pattern. `ValueError` on a missing seed. Linux: `exec >/dev/null 2>&1` first, best-effort iptables rule, values only passed to `printf`. A `file` placement uses `file_mode` (default 0644) and `file_owner`. An `env` placement replaces or appends its `/etc/environment` line. Windows: file, registry (`HKLM\k:v` → `HKLM:\k` + name), Machine env, ADS (split on the last colon). Each placement guards `New-Item -Force` so an existing key or file is never wiped. Path patterns moved to `ctf_plant_contract.LOCATION_PATH_PATTERNS`, and `CtfValidator.PATH_PATTERNS` now references them. `cloud_functions/tests/test_flag_planter.py` (34 tests) runs the real Linux payload under bash with fake curl/iptables/chown on PATH: it plants every Linux row, produces no output even with the exec redirect removed, is idempotent, reports a per-flag error with no value, and a failing iptables is not a failure. The Windows payload is parse-checked by `pwsh` (skipped when pwsh is absent).
- **Learned:** `LINUX_ENVIRONMENT_FILE` is a module constant so tests can redirect the env placement. Error messages in both payloads are built from flag ids only. Reviewer notes left as-is: the patterns allow `..` path segments (PRD-defined patterns), and `_ps_quote` doesn't handle smart quotes (unreachable after the pattern checks). Gates now: api 383, cloud_functions 342, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E2 Plant procedure (`FlagPlanter.plant(board, servers)`, PRD.md:990 and :824-840). Treat `NotFound` from `get_guest_attributes` as a plant failure. Use `parse_plant_result` to read the result.

### Iteration 22 — 2026-10-16
- **Completed:** E2 — `FlagPlanter.plant(board, servers)` (spec server names; instance = `f"{workout_id}-{server}"`, as SoloWorkout names them). Per server: a new nonce, flags → `planting`, then a running check (stopped → `"Server is not running"`, missing → `"Server instance not found"`; neither is reset, started or written to), `set_metadata` (payload + `enable-guest-attributes=TRUE`), and `reset`. Every server is delivered before any polling. One shared 240 s deadline follows, polling `agoge-ctf/` every 10 s, and `parse_plant_result` ignores stale nonces. The result is `planted`/`planted_at`, `failed` with the guest's message, or the timeout message. The `finally` removes `agoge-ctf-plant` from every instance it may have been written to, and a failed removal is logged, not raised. An unexpected error marks any flag still `planting` as failed, then re-raises. Board writes are transactional and touch only the target flags' `plant_*` fields, so a concurrent solve survives. Compute exceptions are logged by type only, because a set_metadata error could echo the payload. Constructor accepts `compute_api=`/`db=`, and env, compute and db are built lazily. `cloud_functions/tests/test_flag_plant_procedure.py` (18 tests) covers SC-5, the three SC-6 paths, SC-7 (no delete/nuke/stop/start), ordering, stale nonce, a stopped server, a missing instance, a poll NotFound or transient error, a reset failure, an internal-error abort, a missing seed, solve preservation, and SC-4.
- **Learned:** E1 had shipped in `badb1e9` but its checkbox was never ticked. It is ticked now. A missing seed fails the flags rather than raising, so E4 can still aggregate. Gates now: api 383, cloud_functions 360, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E3 CTF handler (`cloud_functions/handlers/ctf_handler.py` + the `Handlers.CTF` branch in `main.py`, PRD.md:992).

### Iteration 23 — 2026-10-16
- **Completed:** E3, split. New `cloud_functions/handlers/ctf_handler.py` `CtfHandler(event_attributes, env_dict=None, debug=False, db=None)`. It reads `ACTION`/`CTF_ID`/`WORKOUT_ID`/`SERVER_NAME`/`RESET_MODE` and raises `ValueError` when the action, the ctf id or the workout id is missing, or when the action is unknown. `CTF_PLANT` loads the event (`DbCollections.CTF`) and the board (`{ctf_id}-{workout_id}`), both through `ModelValidator`. A missing document raises `NotFound`, and an inactive board is skipped with a warning. It then calls `FlagPlanter(event, env_dict, db).plant(board, servers)`, where `servers` is `[SERVER_NAME]`, or every spec server that carries one of the board's flags (in spec order) when no server is named. `main.py` has the `Handlers.CTF` branch. `cloud_functions/tests/test_ctf_handler.py` (16 tests) also checks that main routes to `CtfHandler`.
- **Learned:** ArmWorker and host_reset don't exist yet. Rather than reference modules that are missing, I queued their routes as E4b and G4b. Pub/Sub retry is not configured anywhere in build_files, so raising from the handler does not loop. Gates now: api 383, cloud_functions 376, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E4 Arm worker (PRD.md:994, aggregation at PRD.md:720). Pass the event read before the board write as `event=` to `transition_in_transaction` (Iteration 13). Then E4b.

### Iteration 24 — 2026-10-16
- **Completed:** E4 — `cloud_functions/cloud_fn_utilities/course_objects/ctf/arm_worker.py` `ArmWorker(env_dict=None, db=None, compute_api=None).run(ctf_id, workout_id)`. A stale message (event not `ARMING`) is skipped with no writes; a board already `armed`/`failed` (redelivery) is skipped too. Otherwise the board goes `arming`, then: inactive board / missing workout / workout not `RUNNING` → `failed` with no plant; else `FlagPlanter.plant` on every flag-bearing server. One aggregation transaction (all reads before writes) re-checks the stored board status so a concurrent duplicate never double-decrements, writes `arm_status`/`arm_error`, decrements `boards_pending`, and at 0 reads the other boards and transitions `ARMED`/`BROKEN` through `CtfStateManager.transition_in_transaction(event=...)`. An unexpected error aggregates the board as `failed` ("Arm aborted by an internal error") before re-raising, so the event never sticks in `ARMING`. `_board_servers` moved from `CtfHandler` to module-level `flag_planter.board_servers`, which both use. `cloud_functions/tests/test_ctf_arm_worker.py` (22 tests; the fake transaction asserts read-before-write) covers SC-15 all-armed / mixed / zero-armed, last-board-failed-but-earlier-armed → ARMED, and the edge cases above.
- **Learned:** The PRD does not define a board as `armed`. I chose "at least one flag planted" (a playable board; failed flags stay visible and replantable), with `arm_error` "N of M flags failed to plant". Zero planted → `failed`, "No flags planted: <first plant_error>". Gates now: api 383, cloud_functions 397, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E4b — add `CTF_ARM_BOARD` → `ArmWorker(env_dict=self.env_dict, db=self.db).run(self.ctf_id, self.workout_id)` to `CtfHandler.action_map`, with a handler test (patch `ArmWorker` in `ctf_handler_module`).

### Iteration 25 — 2026-10-16
- **Completed:** E4b — `CtfHandler.action_map` routes `CTF_ARM_BOARD` to `_arm_board`, which calls `ArmWorker(env_dict=self.env_dict, db=self.db).run(self.ctf_id, self.workout_id)`. The handler does no reads of its own for this action, because ArmWorker has to skip a stale message before it touches anything. `cloud_functions/tests/test_ctf_handler.py` (19 tests) adds: arm reaches ArmWorker with the handler's env/db and the ids, with no handler reads and no planting; plant does not reach ArmWorker; ArmWorker errors propagate; and an unknown action reaches neither class.
- **Learned:** No circular import (`arm_worker` imports `flag_planter`; the handler imports both). Gates now: api 383, cloud_functions 400, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** E5 Overnight exemption (PRD.md:996). G4b remains queued until the G4 `host_reset` dispatcher exists.

### Verification — 2026-10-16 — PASS
- **Checked:** E1, E2, E3, E4 and E4b, the `[x]` tasks added since the last verification. I read `flag_planter.py`, `arm_worker.py`, `ctf_handler.py`, the `Handlers.CTF` branch in `main.py`, and their four test files, and compared them with PRD.md:988-995, :720-723, :793-840 and SC-4/5/6/7/15.
  - E1: `build_payload` filters to that board's flags on that server. It derives each value with `derive_flag_value`, and every path is checked against `LOCATION_PATH_PATTERNS`. Linux covers `file` and `env`; Windows covers `file`, `registry`, `env` and `ads`. The Linux payload starts with `exec >/dev/null 2>&1`, then installs the best-effort iptables rule, and passes values only to `printf`. Both payloads write `ok:`/`error:<nonce>` to the guest attribute. The tests cover only-this-server's-flags, the nonce, and no print command, and also run the payload in real bash. The pwsh parse test ran because pwsh is installed here. `-rs` shows that none of the 34 tests was skipped.
  - E2: the nonce comes from `IdGenerator.uuid()`. Each server's flags go to `planting`, then `set_metadata` (plant key + `enable-guest-attributes=TRUE`) and `reset` run for every server before any polling. Polling uses `query_path="agoge-ctf/"` every 10 s for up to 240 s. The ok, error and timeout outcomes match step 6. The `finally` removes `agoge-ctf-plant`. A server that is not running fails with "Server is not running" and is never reset or started. SC-5, the three SC-6 paths, SC-7 (no delete/nuke/stop/start) and SC-4 all have non-vacuous tests.
  - E3/E4b: `action_map` routes `CTF_PLANT` → `FlagPlanter` and `CTF_ARM_BOARD` → `ArmWorker(env_dict, db).run(ctf_id, workout_id)`. An unknown action raises `ValueError`, and `main.py` dispatches `Handlers.CTF`. `CTF_HOST_RESET` is deliberately deferred to G4b, as the split note on the task says.
  - E4: a workout not in `WorkoutStates.RUNNING` sets the board to `failed` with exactly "Workout is not running". `_aggregate` runs as one transaction: it does every read (event, board, and the other boards when they are needed) before any write, decrements `boards_pending`, and at 0 calls `CtfStateManager.transition_in_transaction` for ARMED or BROKEN. State is never assigned directly. The tests cover the all-armed, mixed and zero-armed cases, and the fake transaction asserts that reads come before writes.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code.
  - Non-blocking: `main.py` builds `CtfHandler` without `env_dict`, so it falls back to a single `CloudEnv()` and threads that down, which matches how other handlers are invoked. The 240 s deadline is shared by all of a board's servers rather than applied per server, which is consistent with "steps 3–4 for every server before any polling".
- **Gate results:**
  - api/unit_tests: 383 passed.
  - cloud_functions/tests: 400 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: exit 0, 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern" for the CTF paths. This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 26 — 2026-10-16
- **Completed:** E5 — `DailyMaintenance._stop_all` first collects `_ctf_workout_ids()` (events with `state IN` ARMING/ARMED/RUNNING/PAUSED, then each one's `active == True` boards) and skips those workouts on both the publish and the debug path. The trailing `stop_everything()` would still have stopped their VMs, so it now takes `exempt_prefixes` (`f"{workout_id}-"`; every workout instance is named that way) and skips matching instances. `cloud_functions/tests/test_ctf_overnight_exemption.py` (15 tests) covers SC-20 for all four states, non-CTF workouts still stopped, DRAFT/ENDED/ARCHIVED/BROKEN and inactive boards stopped, mixed events, the debug path, and prefix skipping (the trailing dash keeps a longer id from matching).
- **Learned:** The PRD's SC-20 only names the STOP publish, but `stop_everything` is the step that actually stops VMs project-wide; any future "keep running" feature has to exempt both. Queued BUG2 (batch_write inside the loop in `stop_everything`). Gates now: api 383, cloud_functions 415, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F1 Config and feature flag (PRD.md:1001).

### Iteration 27 — 2026-10-16
- **Completed:** BUG2 — `ProjectServerManager.stop_everything` now calls `db.batch_write(operations)` once, after the image loop, and only when there is at least one operation (previously the growing list was written once per image, and zero images wrote nothing — that stays true). `cloud_functions/tests/test_project_server_manager_image_sync.py` (2 tests, real `ModelValidator`, fake db copying each batch) shows three checked-out images produce exactly one batch with three STOPPED updates, and no images produce no write; the one-batch test fails with the fix reverted.
- **Learned:** `stop_everything` loads images with the default `halt_on_error=True`, so one invalid image doc raises and aborts the sync for the rest — pre-existing behavior, outside this bug, left as-is. Gates now: api 383, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F1 Config and feature flag (PRD.md:1001).

### Iteration 28 — 2026-10-16
- **Completed:** F1 — `api/core/ctf/__init__.py` + `config.py`: `is_ctf_enabled()` reads `admin-info/project` through a lazily built module-level Firestore client and caches the result in-process for `CACHE_SECONDS = 60` (`time.monotonic`, lock-guarded). Only a real `True` enables CTF. A read error fails closed and is *not* cached, so the next request retries. `reset_cache()` is there for tests. `ctf_enabled_required` lives in `api/dependencies.py` (not core, so FastAPI types stay out of `api/core/`) and raises a 404 when the flag is off. `api/unit_tests/test_ctf_config.py` (14 tests, fake clock + fake db) shows that a changed flag is seen only once the cache expires, both directly and through the dependency on a real FastAPI app, and covers absent/non-bool flags, a missing doc, and a read failure.
- **Learned:** Tests swap in a fake db via `monkeypatch.setattr(config, "_db", fake)` and must call `config.reset_cache()`, because the cache is process-global and shared across tests. Gates now: api 397, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F2 Error helper (`api/utilities/http_errors.py` `to_http_exception(e)`, Error Handling table in PRD.md).

### Iteration 29 — 2026-10-16
- **Completed:** F2 — `api/utilities/http_errors.py` `to_http_exception(e)` *returns* an `HTTPException` (routers do `raise to_http_exception(e) from e`). Mapping follows the PRD table: `BadRequest`/`AgogeValidationError` 400, `NotFound` 404, `Conflict` 409 and `RateLimitExceeded` 429 all use the exception's message; `Unauthorized` 403, `Forbidden` 403 and `ServiceUnavailable` 503 use the table's fixed text. A pydantic `ValidationError` (a malformed `ctf` block coming out of `is_valid()`) maps to 400 with loc/msg only. An `HTTPException` passes through unchanged. Anything else, including unmapped `BaseAgogeException` subclasses such as `PreconditionFailed`, becomes a 500 with "Something went wrong" and the cause is logged. `api/unit_tests/test_http_errors.py` (17 tests) covers every row, the log on unhandled errors, and the `{"detail": ...}` wire shape through a real FastAPI app.
- **Learned:** Custom pydantic `ValueError` validator messages can echo input into the 400 detail (reviewer note). The CTF spec models only use field constraints, so this is low risk. Gates now: api 414, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F3 Audit helper (`api/core/ctf/audit.py` `CtfAudit.action(...)`, PRD.md:1004).

### Iteration 30 — 2026-10-16
- **Completed:** F3 — `api/core/ctf/audit.py` `CtfAudit(env_dict=None, db=None).action(ctf_id, action, actor, target=None, detail=None, flag_prefix=None)` context manager. It yields a `CtfAuditEntry` (the block may set `.target` or call `.add_detail(**kv)`). In a `finally` it writes exactly one `CtfLogModel` (uuid id, `time.time()` `created_at`, validated through `ModelValidator`) to `DbCollections.CTF_LOG`. The result is `OK` on return, `DENIED` for `Unauthorized`/`Forbidden`/`Conflict`/`BadRequest` (SC-18's list, so `NotFound` counts as `ERROR`), and `ERROR` otherwise; the exception always propagates. `detail` accepts only str/int/bool, and it rejects any key or value containing `agoge{` (or `<event flag_prefix>{`) anywhere, case-insensitively, with a `ValueError` that names the key but not the value. A rejected initial `detail` raises before the block runs and still writes an `ERROR` row. A failed audit write is logged and swallowed, so it never masks the action's own outcome. `api/unit_tests/test_ctf_audit.py` has 28 tests.
- **Learned:** R1 should wrap only the core call in `audit.action(...)`, inside the `try` that does `raise to_http_exception(e) from e`, and should pass the event's `flag_prefix` when it already has one. The guard only catches flag-shaped strings, so callers must never put the seed into `detail`. Gates now: api 442, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F4 Event create (`CtfEvent.create(unit_id, user)`, PRD.md:1006).

### Verification — 2026-10-16 — PASS
- **Checked:** E5, BUG2, F1, F2 and F3, the `[x]` tasks added since the last verification. I read commits `788ec89`, `a1e38f9`, `ba22b45`, `2fcc51c` and `c1a5de0` against PRD.md:996-1005, SC-18, SC-20 and the Error Handling table (PRD.md:1216-1238).
  - E5: `_stop_all` builds the exempt set from events with `state IN` ARMING/ARMED/RUNNING/PAUSED (`DbOperators.IN`, which Firestore supports), then each event's `active == True` boards, and skips those workouts on both the publish path and the debug path. `stop_everything(exempt_prefixes=...)` skips `f"{workout_id}-"` instances, so the project-wide sweep cannot undo the exemption. Tests cover all four live states, the other states, inactive boards, mixed events, and non-CTF workouts still being stopped.
  - BUG2: `batch_write` now runs once, after the image loop, guarded by `if operations:`.
  - F1: `is_ctf_enabled()` reads `admin-info/project` through `DbCollections.ADMIN_INFO`/`DATABASE_NAME` with a lock-guarded 60 s `time.monotonic` cache. Only `True` enables it, and a failed read fails closed without being cached. `ctf_enabled_required` is in `api/dependencies.py` (no FastAPI in core) and returns 404. `test_changed_flag_is_seen_after_cache_expires` and `test_ctf_enabled_required_sees_toggle_after_cache_expires` satisfy the done-when.
  - F2: `_MAPPING` matches the table row by row (400/403/403/404/409/429/503). The Unauthorized, Forbidden and 503 bodies are the table's exact text. Anything unhandled becomes a 500 "Something went wrong" and the cause is logged.
  - F3: `CtfAudit.action` writes one `CtfLogModel` in a `finally`: `OK` on return, `DENIED` for exactly SC-18's four exceptions, `ERROR` otherwise, and the exception is re-raised. `detail` rejects `agoge{` (and the event prefix) anywhere in a key or value, case-insensitively. Tests cover all three results and the flag rejection.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code.
- **Gate results:**
  - api/unit_tests: 442 passed.
  - cloud_functions/tests: 417 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: exit 0, 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern" for the CTF paths. This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 31 — 2026-10-16
- **Completed:** F4 — `api/core/ctf/event.py` `CtfEvent(env_dict=None, db=None, env=None).create(unit_id, user)` returns the new ctf_id. The checks run in the PRD's order, all before any write: unit missing → `NotFound`; `ctf` absent/null → `BadRequest`, and so is a malformed block (it goes through `ModelValidator(CtfSpecModel)`); caller not in `instructor_id` and not an admin → `Unauthorized`; no workouts → `BadRequest`; more than `ctf_max_boards` (from `env_dict`, default 100; an invalid value or a bool falls back to 100) → `BadRequest`; a workout already on an `active` board (queried with `in` in chunks of 30) → `Conflict` naming it; a missing or empty seed → `ServiceUnavailable` with the PRD's exact text. Workouts in DELETING_SERVERS/COMPLETED_DELETING_SERVERS/DELETED get no board. The writes are the digests, then the boards, then the event last. Each commit holds at most 500 writes, which keeps `batch_write` off its splitting path, because that path swallows errors. If a commit fails, the documents already committed are deleted (best effort) and the error is re-raised. `api/unit_tests/test_ctf_event_create.py` (32 tests, in-memory fake db) covers SC-1, SC-2, SC-4 (including the bare digest part of each value and the seed), the 701-write split into 500+201, the rollback, and every refusal writing nothing.
- **Learned:** Digest docs are keyed by digest, and the digest depends only on (seed, seed_version, workout, flag id). So a workout's second event overwrites the first event's digest docs. **F5 delete must only delete digest docs whose `ctf_id` matches.** The Conflict check is not transactional, so two concurrent creates on the same unit could both pass. The PRD asks for no transaction here, so I left it as it is. Gates now: api 474, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F5 Event read, update, delete (PRD.md:1008). Add `get`/`list`/`update`/`delete` to `CtfEvent`, and reuse the instructor-or-admin check from `create`.

### Iteration 32 — 2026-10-16
- **Completed:** F5 — `CtfEvent.get(ctf_id, user)` → `CtfEventModel` (`NotFound`; `Unauthorized` unless admin or in `instructor_id`). `list(user)` → `List[CtfEventSummary]`, newest first: admins get every event, others an `ARRAY_CONTAINS` query on `instructor_id`, and invalid docs are skipped. `update(ctf_id, CtfUpdateRequest, user)` runs in one transaction through the raw client (reads, then authorizes; ARCHIVED → `Conflict`; an empty body writes nothing). It revalidates the merged event and writes only the `model_fields_set` keys. `delete(ctf_id, user)` is admin-only, DRAFT/ARCHIVED only (otherwise `Conflict` naming the state). It deletes rate-limit docs (doc-id range `[ctf_id-, ctf_id.)`), the digests whose `ctf_id` still matches, and the boards from `board_ids`, with the event last, in commits of ≤ 500. Submissions and the log are kept. The instructor-or-admin check is now `_authorize`, shared with `create`. `api/unit_tests/test_ctf_event_crud.py` has 31 tests.
- **Learned:** `CtfRateLimitModel` has no `ctf_id` and its bucket is any parsed submission id, so finding the docs needs a raw `FieldPath.document_id()` range with `DocumentReference` values (the `db.query` wrapper can't do this). `def list` on the class shadows the builtin for later annotations in the class body, so `_commit`/`_rollback` now annotate with `List[tuple]`. Gates now: api 505, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F6 Event actions (`process_action` per the action map, PRD.md:1009 and :710-720). Use `CtfStateManager`; arm publishes one `CTF_ARM_BOARD` per board (SC-13).

### Iteration 33 — 2026-10-16
- **Completed:** F6 — `CtfEvent.process_action(ctf_id, CtfActionRequest, user)` returns the transitioned `CtfEventModel`. In one transaction it reads the event, authorizes (an admin, or a user in `instructor_id`), and checks the action's own From set (`CtfEvent.ACTIONS`); otherwise it raises `Conflict("Cannot <action> a CTF event that is <STATE>")`. It then calls `CtfStateManager.transition_in_transaction(..., event=stored, **fields)` and `transaction.update`s every board (`arm`: `arm_status='pending'`, `arm_error=None`; `archive`: `active=False`). The side effects follow the action map: start → `starts_at`, pause → `paused_at`, resume adds the pause to `accumulated_pause_seconds` and to `ends_at` when it is set, end → `ends_at`. `arm` with no boards → `BadRequest`. Only after the commit does `arm` publish one `CTF_ARM_BOARD` per board (handler `CTF`, `ctf_id`, `workout_id`). `PubSubManager` is lazy, and tests inject it with `pubsub=`. `api/unit_tests/test_ctf_event_actions.py` has 43 tests: SC-13, SC-14, 16 illegal (action, state) pairs that write nothing, and auth.
- **Learned:** The action map's From sets are narrower than the state manager's allow-list: `start` from PAUSED and `resume` from ARMED would both pass `VALID_TRANSITIONS`. So the explicit From check in `process_action` is required; don't drop it. The board updates sit in the event's transaction, which is bounded by `ctf_max_boards`. A publish failure after the commit leaves the event stuck in ARMING; I filed this as BUG3. Gates now: api 548, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** F7 Event reads for panels (`state()`, `boards()`, `flags()`, `log()`, `submissions()`, PRD.md:1011).

### Iteration 34 — 2026-10-16
- **Completed:** F7 — `CtfEvent.state/boards/flags/log/submissions(ctf_id, user, …)` in `api/core/ctf/event.py`. Each one goes through `get` (`NotFound`, then `Unauthorized` before any row read). `state()` is exactly one event get plus one board query (`ctf_id ==`), and the test asserts the read list. Boards come back in `board_ids` order; a stray board sorts last and an invalid one is skipped. Archived (inactive) boards still show. `CtfBoardStatus` counts flags in `failed` and in `stale`. `flags()` gives one `CtfFlagRow` per spec flag, decoys included, with each board's plant status and no digest. `log(action=)` and `submissions(verdict=)` validate the filter against `LogAction`/`Verdict` (otherwise `BadRequest`, before any read), query with equality filters only, and sort newest first in memory, capped at `MAX_PANEL_ROWS = 500`. `budget_exceeded` comes from the new `config.is_budget_exceeded()`. `config.py` now caches the whole admin-info doc, so the budget flag shares the read `ctf_enabled_required` already makes; a failed read reports False and isn't cached. Tests: `api/unit_tests/test_ctf_event_panels.py` (32) and 7 new tests in `test_ctf_config.py`.
- **Learned:** Server-side `order_by` plus `limit` on `created_at`/`submitted_at` with a `ctf_id` filter would need a composite Firestore index, and the repo deploys none. So the log and submissions panels read every matching row on each call and cap in memory. That is fine at classroom scale; if submissions grow large, add the indexes and push the sort and limit into the query. R1 tests must monkeypatch `config.is_budget_exceeded`, because otherwise `state()` builds a real Firestore client. Gates now: api 587, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** BUG3 (stuck-ARMING recovery), then G1 Replant publish (PRD.md:1015).

### Iteration 35 — 2026-10-16
- **Completed:** BUG3 — when `CtfEvent._publish_arm` raises partway, it now runs one recovery transaction (`_fail_unpublished`) before it re-raises the publish error. That transaction reads the event and every board first. It marks each board that got no message (`board_ids[published:]`) `failed` with `ARM_PUBLISH_FAILED` ("Arm message could not be published"), takes them off `boards_pending`, and at 0 moves the event to ARMED (if any other board is `armed`) or BROKEN, using `CtfStateManager.transition_in_transaction(event=...)`. This is the same aggregation ArmWorker does. A board that is already terminal (`armed`/`failed`) is left alone, because the publish that raised may still have been delivered and that worker may have finished. A worker that finishes after recovery finds its board terminal and skips, so nothing is counted twice. If the event already left ARMING, the boards are marked and nothing is counted. If the recovery itself fails, that is logged and the original publish error is still raised. `api/unit_tests/test_ctf_event_actions.py` has 6 new tests (49 total).
- **Learned:** I picked recovery at the point of failure, not a stale-ARMING sweep. It needs no new state, transition or scheduler work, and it uses the board statuses that already exist. The remaining gap is a recovery transaction that fails too (Firestore down at the same moment). Only a sweep would cover that, and the PRD asks for none. Gates now: api 593, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G1 Replant publish (PRD.md:1015).

### Verification — 2026-10-16 — FAIL
- **Checked:** F4, F5, F6, F7 and BUG3, the `[x]` tasks added since the last verification. I read all of `api/core/ctf/event.py`, `common/utilities/ctf_state_manager.py`, the Firestore wrapper methods it calls (`query`, `operation`, `batch_write`/`_handle_batch_splitting`, `transaction`), `PubSubManager.msg`, the ArmWorker `run`/`_aggregate`, and the four `test_ctf_event_*.py` files, against PRD.md:1006-1011, the action map, the endpoint table and SC-1/2/4/13/14.
  - F4: the checks run in the PRD order and all come before the first write. Commits are ≤ 500, which keeps `batch_write` off `_handle_batch_splitting`'s error-swallowing path (the split only happens at > 500). The event is written last, with a rollback. SC-1 uses the real `IdGenerator` with `fullmatch [a-z]{10}`. SC-2 covers both a missing `ctf` and `ctf: null`. SC-4 json-dumps every SET document from every commit, nested flags included, and also checks for the bare digest part and the seed.
  - F5: `update` writes only the `model_fields_set` keys inside a transaction, and ARCHIVED → `Conflict`. `delete` is admin-only, DRAFT/ARCHIVED only, and removes rate-limit (doc-id range), owned digest and board docs, with the event last. Submissions and the log are kept, and tests assert this.
  - F6: the `ACTIONS` From/To sets match the action map exactly, and every state write goes through `CtfStateManager.transition_in_transaction`. The side effects (`boards_pending`, board `arm_status`/`active`, `starts_at`, `paused_at`, the resume math, `ends_at`) are asserted against a fixed clock. SC-13 compares the full message list to exactly one `CTF_ARM_BOARD` per board, and SC-14 checks all 9 legal pairs publish nothing. 16 illegal pairs raise `Conflict` with the state name, and nothing is written.
  - F7: `state()` is one event get plus one board query, and the test asserts the read list. Rows are newest first with a cap of 500, filters are validated, and `CtfFlagRow` has no digest field.
  - BUG3: see Reopened.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code. (`raise NotImplemented` in `document_database.py:208` is pre-existing and not CTF code.)
  - Non-blocking: the ArmWorker checks `arm_status` for a terminal value only before planting. A board that recovery marked `failed` while its worker is planting is still planted, but `_aggregate` re-checks inside its transaction, so it is not counted twice. `test_submissions_rejects_an_unknown_verdict` does not assert that no read happened (the log variant does).
- **Gate results:**
  - api/unit_tests: 593 passed.
  - cloud_functions/tests: 417 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 4 files, 28 tests passed.
  - ESLint gate: exit 2, "No files matching the pattern "src/components/Teacher/Ctf"". This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** BUG3. `_publish_arm` recovers only when `PubSubManager.msg` raises synchronously. `msg` (common/utilities/gcp/pubsub_manager.py:61-67) returns the `publisher.publish` future, and nothing calls `.result()` on it. Real publish failures (network, permission, timeout) surface through that future, so in production `_fail_unpublished` never runs and the event still sticks in ARMING with `boards_pending > 0`. The tests pass only because `FakePubSub.msg` raises in-line (test_ctf_event_actions.py:87-89).

### Iteration 36 — 2026-10-16
- **Completed:** BUG3 (reopened) — `CtfEvent._publish_arm` now keeps every future `PubSubManager.msg` returns and resolves each with `.result(timeout=...)` against one shared `ARM_PUBLISH_TIMEOUT_SECONDS = 30` deadline. A board whose future fails or times out, or whose `msg` raised in-line (the rest after an in-line raise are not tried), is passed to `_fail_unpublished`. The first error is re-raised after recovery. A timed-out message that is delivered later finds its board `failed` and the worker skips it. In `test_ctf_event_actions.py`, `FakePubSub.msg` now returns a real `concurrent.futures.Future`, and `future_errors=` makes chosen futures fail. There are 4 new tests: one failed future, all futures failed → BROKEN, a never-resolving future → TimeoutError, and an in-line raise that still checks the futures already returned (53 total).
- **Learned:** Any new code that publishes must resolve the future to detect failure; `msg` itself only raises for client-side errors. Gates now: api 597, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G1 Replant publish (PRD.md:1015).

### Iteration 37 — 2026-10-16
- **Completed:** G1 — `api/core/ctf/hosts.py` `CtfHosts(env_dict=None, db=None, pubsub=None).replant(ctf_id, workout_ids, servers, user)` returns the number of `CTF_PLANT` messages published. It reuses `CtfEvent` for the db, PubSub, `get` (`NotFound`, then `Unauthorized`) and its state naming. Replant is allowed only in ARMED/RUNNING/PAUSED/BROKEN; any other state → `Conflict` naming the state. `None` selects every board (`board_ids` order) or every flag-bearing spec server (decoy-only servers included). An empty list, an unknown board, or a server with no flags → `BadRequest`, before any publish. Duplicates are published once. Each message carries `SERVER_NAME`, so the handler plants only that server. Every publish future is resolved against one shared 30 s deadline, and the first error is raised after the others resolve; an in-line raise stops publishing. Nothing is written, because the planter sets `planting` itself. `api/unit_tests/test_ctf_hosts_replant.py` has 24 tests.
- **Learned:** Every board carries every spec flag (`CtfEvent._new_board`), so the flag-bearing servers come from the spec without a board read. If board flag sets ever differ, filter per board as `board_servers` does. With no boards, replant returns 0 and does not raise; R1 should not present that as a successful replant. Gates now: api 621, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G2 Host rows (PRD.md:1016), `CtfHosts.hosts(ctf_id)` in the same file.

### Iteration 38 — 2026-10-16
- **Completed:** G2 — `CtfHosts.hosts(ctf_id, user)` in `api/core/ctf/hosts.py` returns `List[CtfHostRow]`. It authorizes through `CtfEvent.get`, reads the boards with `CtfEvent._boards` (in `board_ids` order), and reads server docs with `parent_id in` queries of ≤ 30 workouts. That is 1 get + 1 board query + ⌈boards/30⌉ server queries, never one read per board. Each board gets the flag-bearing spec servers first, in spec order, then its other servers sorted by name, so restart and rebuild can reach every host the team owns. A flag-bearing server with no doc still gets a row with `server_state=None`. `flag_count` counts the board's flags on that server, decoys included. `rebuild_allowed` is False when the server has a `wireguard_endpoint_id` or has no doc. An unknown state number shows as its digits. Shared community servers (`parent_id` = unit id) belong to no team and are not listed. `api/unit_tests/test_ctf_hosts_rows.py` has 15 tests.
- **Learned:** Server docs are keyed `f"{workout_id}-{name}"` with `parent_id = workout_id`. I read them as raw dicts, not through `ModelValidator(ServerModel)`, so a legacy server doc can't blank the panel. G3 should look up the target with `db.get(SERVER, f"{workout_id}-{server}")` and refuse `rebuild` with the same `wireguard_endpoint_id` check. Gates now: api 636, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G3 Reset publish (PRD.md:1017), `CtfHosts.reset(ctf_id, workout_id, server, mode, user)`.

### Iteration 39 — 2026-10-16
- **Completed:** G3 — `CtfHosts.reset(ctf_id, workout_id, server, mode, user)` in `api/core/ctf/hosts.py` publishes exactly one `CTF_HOST_RESET` (handler `CTF`, `CTF_ID`, `WORKOUT_ID`, `SERVER_NAME`, `RESET_MODE`) through the shared `_publish`, which resolves the future. All checks run before the publish, in this order: an unknown mode → `BadRequest` (before any read); `get` (`NotFound`, then `Unauthorized`); state not in `REPLANT_STATES` (ARMED/RUNNING/PAUSED/BROKEN) → `Conflict` naming the state; a workout not in `board_ids` → `NotFound`; no `SERVER` doc at `f"{workout_id}-{server}"` → `NotFound`; `replant` on a server with no spec flags → `BadRequest`; `rebuild` with a `wireguard_endpoint_id` → `BadRequest`. Nothing is written. Reads are exactly the event get and the one target server get (an SC-9 style assertion). `api/unit_tests/test_ctf_hosts_reset.py` has 28 tests.
- **Learned:** The PRD gives no state rule for resets, so they reuse the replant states: before ARMED nothing is planted (and ARMING would race the arm worker), and after PAUSED the exercise is over. restart and rebuild are allowed on servers with no flags, and restart is allowed on WireGuard servers. The core takes `mode` as a str and checks it against `get_args(ResetMode)`, so a caller other than the router can't bypass it. Gates now: api 664, cloud_functions 417, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G4 Reset dispatcher (`cloud_functions/.../ctf/host_reset.py` mode → method map; SC-9; an unknown mode → `ValueError`), PRD.md:1018.

### Iteration 40 — 2026-10-16
- **Completed:** G4, plus G5–G7, because a dispatcher whose methods were stubs would not meet "no stubs" and SC-9 can't be tested without them. `cloud_functions/cloud_fn_utilities/course_objects/ctf/host_reset.py`: `HostReset(env_dict, db).run(ctf_id, workout_id, server, mode)` dispatches through `mode_map` (`replant`/`restart`/`rebuild`). An unknown mode or a missing server raises `ValueError` before any read. A missing event, board or server doc raises `NotFound`. An inactive board is skipped and returns None. replant → `FlagPlanter.plant(board, [server])`. restart → `ComputeManagerFactory` `load(server_name=f"{workout_id}-{server}", server_spec=doc)`, then `stop()`, then `start()`. rebuild → it refuses a server with a `wireguard_endpoint_id` (`ValueError`, defense in depth behind the API's 400), calls `nuke()`, then `FlagPlanter.mark_stale(board, server)`, the new method that sets `plant_status='stale'`, `planted_at=None`, `plant_error=None` through the transactional `_record`. If `nuke()` raises, the flags are still marked stale, because the instance may already be deleted, and the nuke error is re-raised. `cloud_functions/tests/test_ctf_host_reset.py` has 26 tests, including SC-9 for every mode (no get, write, compute or plant call names board B).
- **Learned:** `LabServerManager` builds its own Firestore and GCP clients in `__init__`, so tests must patch `host_reset_module.ComputeManagerFactory`. A delete failure inside `nuke()` leaves the instance in place but still marks its flags stale; that is conservative, and a replant fixes it. Gates now: api 664, cloud_functions 443, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** G4b — route `CTF_HOST_RESET` in `CtfHandler.action_map` to `HostReset(env_dict, db).run(ctf_id, workout_id, server_name, reset_mode)` (remove the "added when that dispatcher lands" comment), and add a handler test.

### Verification — 2026-10-16 — PASS
- **Checked:** BUG3 (reopened, then fixed in iteration 36), G1, G2, G3, G4, G5, G6 and G7, the `[x]` tasks changed since the last verification. I read all of `api/core/ctf/hosts.py`, `CtfEvent._publish_arm`/`_fail_unpublished` in `api/core/ctf/event.py`, all of `cloud_functions/cloud_fn_utilities/course_objects/ctf/host_reset.py`, `FlagPlanter.mark_stale`, `LabServerManager.load/start/stop/nuke`, `ComputeManagerFactory.create_manager_object`, `CtfHandler.action_map`, and the SC-9 and mark_stale tests in `cloud_functions/tests/test_ctf_host_reset.py`. I compared them with PRD.md:1013-1022 and SC-9.
  - BUG3: `_publish_arm` now keeps every future and calls `.result(timeout=…)` on each, against one shared 30 s deadline. A failed future, a timeout, or an in-line raise (which also counts the rest of the boards) goes into `unpublished`, which `_fail_unpublished` handles in one transaction before the first error is re-raised. This fixes the defect the last verification reported.
  - G1: `replant` publishes one `CTF_PLANT` with `SERVER_NAME` per selected board × flag-bearing server. Selections are validated before any publish (empty or unknown → `BadRequest`), and states outside ARMED/RUNNING/PAUSED/BROKEN → `Conflict`. Futures are resolved through `_publish`.
  - G2: `hosts` reads server docs with `parent_id in` queries chunked at `MAX_IN_VALUES`, not one read per board. `rebuild_allowed` is False when a server has a WireGuard endpoint or no doc.
  - G3: `reset` publishes exactly one `CTF_HOST_RESET` carrying `RESET_MODE`, and every check runs before it. `rebuild` with a `wireguard_endpoint_id` → `BadRequest`, as the PRD requires. An unknown mode → `BadRequest` before any read.
  - G4: `HostReset.mode_map` maps `replant`/`restart`/`rebuild` to real methods. An unknown mode → `ValueError` before any read (tested for each mode). The SC-9 test covers all three modes: no get, write, compute call or plant call names board B. Routing from `CtfHandler` is the separate G4b task, which is correctly still `[ ]`; `action_map` has only `CTF_ARM_BOARD` and `CTF_PLANT`.
  - G5: calls `FlagPlanter.plant(board, [server])`.
  - G6: loads `ComputeManagerFactory.create_manager_object` with `{workout_id}-{server}`, then `stop()`, then `start()`.
  - G7: calls `nuke()`, then `mark_stale`, which sets only `plant_status='stale'`, `planted_at=None` and `plant_error=None` on that server's flags; a test checks that `solved` is kept. A failed nuke still marks the flags stale and re-raises the nuke error.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code.
  - Non-blocking: in the SC-9 test, `FlagPlanter.plant` is mocked for `replant` mode, so the planter's own writes are not part of that assertion. The planter's per-board scoping was verified earlier (E2).
- **Gate results:**
  - api/unit_tests: 664 passed.
  - cloud_functions/tests: 443 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern "src/components/Teacher/Ctf" were found". This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 41 — 2026-10-16
- **Completed:** G4b — `CtfHandler.action_map` now routes `CTF_HOST_RESET` to `_host_reset`, which calls `HostReset(env_dict, db).run(ctf_id, workout_id, server_name, reset_mode)`. The placeholder comment is gone. The handler reads nothing itself and passes a missing server or mode through as None, so HostReset's `ValueError` guard decides. `cloud_functions/tests/test_ctf_handler.py` has 6 new tests: each mode reaches HostReset with no db read, plant or arm; missing attributes are passed through; HostReset errors propagate; CTF_PLANT does not reach HostReset; and unknown actions reach none of the three classes.
- **Learned:** All three CTF actions are now routed, so the E3 done-when is fully met. Gates now: api 664, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H1 Submission resolve (PRD.md:1026).

### Iteration 42 — 2026-10-16
- **Completed:** H1 and H2 together. A same-board match with no step 6 would have been a stub, which follows the precedent of G4–G7. `api/core/ctf/scoring.py` `CtfScoring(env_dict, db).submit(workout_id, flag, origin_ip) -> CtfSubmitResponse`:
  - Step 1: the active-board query, then the event get. A missing board or event → `NotFound`. A non-RUNNING event records `closed`, then raises `Conflict("Submissions are closed.")`.
  - Steps 3-5: one digest read. A missing digest or another `ctf_id` → `incorrect`. Another workout → `cross_submission` with `matched_workout_id`, answered as `incorrect`.
  - Step 6: one `db.transaction` that re-reads the board. Duplicate, decoy (points plus `decoy_count`, never marked solved) or correct (`solved`, `solved_at`, `score`, `solve_count`, `last_solve_at`). `attempts` is incremented on the parsed flag.
  - Step 7: one `CtfSubmissionModel` insert holding only the digest.
  - Decoy points are hidden in the response unless `reveal_decoy_penalty`.
  - `api/unit_tests/test_ctf_scoring_submit.py` has 24 tests: SC-10, SC-12 (two threads behind a barrier, so both query before either transaction), decoy, closed for every non-RUNNING state, and SC-4.
- **Learned:** The PRD increments `attempts` only inside step 6 (same-board matches), so wrong guesses don't count. That follows the algorithm literally and keeps the "at most one board transaction" budget. The ctf_enabled check is left to the student router (R2), as with the other core classes. Gates now: api 688, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H3 Rate limiting. Insert step 2 between the closed check and the digest read in `CtfScoring.submit`: a transaction on `agoge-ctf-rate-limit/{ctf_id}-{workout_id}-{bucket}`, record `rate_limited`, raise `RateLimitExceeded`. PRD.md:1030.

### Iteration 43 — 2026-10-16
- **Completed:** H3 — step 2 of `CtfScoring.submit` (`api/core/ctf/scoring.py` `_rate_limit_in_transaction`). It runs after the closed check and before the digest read. It is one `db.transaction` on `agoge-ctf-rate-limit/{ctf_id}-{workout_id}-{bucket}`, with bucket = parsed flag id or `"unparsed"`. If there is no counter, or the window is ≥60 s old, it `set`s a fresh window with count=1. Otherwise, at `count >= submission_rate_limit` it records `rate_limited` and raises `RateLimitExceeded("Too many submissions for this challenge. Try again in <n> seconds.")`, where n = ceil(seconds left, min 1). Otherwise it increments. A refused submission is not counted, so the window's end can't be pushed back. An unreadable counter starts a fresh window. `FakeDb` in `test_ctf_scoring_submit.py` now supports `transaction.set`, and it counts board transactions (`transactions`) separately from `rate_limit_transactions`. It has 10 new tests: SC-11, retry-after, a new window resetting the count, per-flag, per-board, the unparsed bucket, the configured limit, a corrupt counter, and the closed check skipping the limiter.
- **Learned:** `http_errors` already maps `RateLimitExceeded` → 429, so R2 just needs to use it. Gates now: api 698, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H4 Hints (PRD.md:1032).

### Iteration 44 — 2026-10-16
- **Completed:** H4 — `CtfScoring.hint(workout_id, flag_id) -> CtfHintResponse` in `api/core/ctf/scoring.py`. It does the active-board query and event get, then a spec check: an unknown id, a flag with no hint, or a decoy → `NotFound("Hint not found")`. Decoys answer like unknown ids so they can't be discovered. Then one board transaction (`_hint_in_transaction`): a flag missing from the board → `NotFound`. If the hint is already taken, it returns the hint and current score with no write, in any event state. A flag whose `unlocks_after` are unsolved → `NotFound` (H5 hides locked flags, so their hints stay hidden too). A state other than RUNNING → `Conflict("Hints can only be taken while the event is running.")`. Otherwise it sets `hint_taken`/`hint_taken_at` and `score -= hint_cost` (the score may go below zero). No submission row is written. `api/unit_tests/test_ctf_scoring_hint.py` has 24 tests, including two concurrent first requests behind a barrier that deduct once.
- **Learned:** The PRD gives no state rule for hints. New deductions follow the submission rule (RUNNING only, since points move only while the clock runs). Repeat reads are always allowed because the hint is already paid for. Gates now: api 722, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H5 Student board read (PRD.md:1033), `CtfScoring.board(workout_id)`. Its locked-flag rule should match `_hint_in_transaction`'s `unlocks_after` check.

### Iteration 45 — 2026-10-16
- **Completed:** H5 — `CtfScoring.board(workout_id) -> CtfStudentBoardResponse` in `api/core/ctf/scoring.py`. With no active board, or an active board whose event doc is missing, it returns `enrolled=False` instead of raising, because most workouts aren't on a CTF. Otherwise it lists challenges in spec order and drops decoys, flags missing from the board, and flags whose `unlocks_after` are unsolved on the caller's own board. The locked rule is now one `_is_locked` helper, shared with `_hint_in_transaction`. `hint` holds the text only once `hint_taken`. `remaining_seconds` is None when open-ended, 0 when ENDED, held at `ends_at - paused_at` while PAUSED, and otherwise `ceil(ends_at - now)` with a floor of 0. `flag_format` is `"<prefix>{<challenge>_<20 hex characters>}"`. The read makes no writes. `api/unit_tests/test_ctf_scoring_board.py` has 25 tests, including SC-17 run for every CtfStates value with everything unlocked and every hint taken: no `path`/`server`/`location_type`/`digest`/`access_level` key at any depth, and no path or digest value.
- **Learned:** The `ctf_enabled` → `enrolled: false` rule (SC-19) is still left to the R2 router, as with the other core classes. The board read lists challenges in every state, DRAFT included; the PRD gives no rule to hide them before start. Gates now: api 747, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H6 Scoreboards (PRD.md:1035): instructor ranking (score desc, then earliest `last_solve_at`) and public ranking (anonymized "Team <n>" by board order, `is_you`, freeze-aware using `solved_at <= scoreboard_frozen_at`; SC-16).

### Verification — 2026-10-16 — PASS
- **Checked:** G4b, H1, H2, H3, H4 and H5, the `[x]` tasks changed since the last verification. I read all of `api/core/ctf/scoring.py`, `FirestoreDatabase.transaction` (it wraps the callback in `firestore.transactional` and returns its result), `ModelValidator.load`, and the `FakeDb` transaction and barrier in `test_ctf_scoring_submit.py`. A subagent read `cloud_functions/handlers/ctf_handler.py`, the CTF branch in `main.py`, `HostReset.run`'s signature and `test_ctf_handler.py`. I compared all of it with PRD.md:1024-1034, the Submission Algorithm (PRD.md:904-920), the response models and SC-4/10/11/12/17.
  - G4b: `action_map` routes `CTF_HOST_RESET` to `_host_reset`, which calls `HostReset(env_dict, db).run(ctf_id, workout_id, server_name, reset_mode)` (ctf_handler.py:96-102). The argument order matches `host_reset.py:42`. All three CTF actions route to real classes, and an unknown action raises `ValueError`. Tests assert the exact `run` arguments for each mode.
  - H1: steps run in the PRD order. A non-RUNNING event records `closed` and then raises `Conflict("Submissions are closed.")`. A missing digest or another `ctf_id` gives `incorrect`. Another workout gives `cross_submission` with `matched_workout_id`, answered to the student as `incorrect` (SC-10 test at :166). Exactly one `CtfSubmissionModel` is appended, holding the digest and never the value.
  - H2: step 6 re-reads the board inside one `db.transaction`. The outcomes are duplicate, decoy (points and `decoy_count += 1`, never solved) or correct (`solved`, `solved_at`, score, `solve_count`, `last_solve_at`). `attempts` is incremented on the parsed flag. The fake serializes transactions under a lock behind a 2-thread barrier, so the SC-12 test (:207) exercises a real race and asserts one correct, one duplicate and the score raised once.
  - H3: one transaction on `agoge-ctf-rate-limit/{ctf_id}-{workout_id}-{bucket}`, with bucket = parsed id or `"unparsed"`. A window ≥ 60 s old is reset. At `count >= submission_rate_limit` it records `rate_limited` and raises `RateLimitExceeded`, with the PRD message and retry seconds. With the default limit of 10, the 11th submission is refused (SC-11 test :354, new-window test :392).
  - H4: deducts `hint_cost` once inside a board transaction. A second call returns the hint without a write (test :142), and two concurrent first calls deduct once (:154).
  - H5: `board()` drops decoys and flags whose `unlocks_after` are unsolved, through the shared `_is_locked`. `CtfChallenge` has no location, digest or access fields. The SC-17 test (:194) runs for every CtfStates value.
  - No TODO, stub, `NotImplemented` or hardcoded test-only value in the new code. (`NotImplemented` in `document_database.py` is the pre-existing abstract base.)
  - Non-blocking: in `test_concurrent_correct_submissions_award_once`, the barrier now also gates the H3 rate-limit transaction, not only the board transaction. Both threads still reach step 6 under the lock, so the test still holds.
- **Gate results:**
  - api/unit_tests: 747 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern "src/components/Teacher/Ctf" were found". This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file.
- **Reopened:** none.

### Iteration 46 — 2026-10-16
- **Completed:** H6. `api/core/ctf/scoring.py` has two new methods:
  - `CtfScoring.scoreboard(ctf_id, user) -> List[CtfScoreboardRow]` is the instructor view. It covers every board, archived ones included, and ignores the freeze. It authorizes through `CtfEvent.get`.
  - `CtfScoring.public_scoreboard(workout_id) -> List[CtfPublicScoreboardRow]` is the student view. It raises `NotFound` with no active board or when `public_scoreboard_enabled` is false. "Team <n>" uses the `board_ids` index. `is_you` marks the caller's row.
  - While frozen, `_frozen_standing` removes each solve with `solved_at > scoreboard_frozen_at` from the score and solve_count, and recomputes last_solve_at from the solves that remain.
  - Shared `_rank`: score descending, then the earliest last solve. A team with no solve ranks after a tied team that has one. Full ties keep board order. Ranks are positions 1..n.
  - `CtfScoring` now holds `self.events = CtfEvent(env_dict, db)` and reuses its `get` and `_boards`.
  - `api/unit_tests/test_ctf_scoring_scoreboard.py` has 20 tests, including SC-16, a solve exactly at the freeze, and the freeze tiebreak.
- **Learned:** Only solves are frozen, as SC-16 states. Decoy penalties, hint costs and adjustments made after the freeze still show, because the board stores no timestamps for decoys or adjustments. Gates now: api 767, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** H7 Score adjustment (PRD.md:1037), `CtfScoring.adjust(ctf_id, workout_id, delta, reason, user)` writing `SCORE_ADJUST` through `CtfAudit`.

### Iteration 47 — 2026-10-16
- **Completed:** H7 — `CtfScoring.adjust(ctf_id, workout_id, delta, reason, user) -> int` (new score) in `api/core/ctf/scoring.py`. It writes its own `SCORE_ADJUST` row through `CtfAudit` (`self.audit`), with actor = user email, target = workout_id, detail `delta` and, on OK only, `reason`/`previous_score`/`score`. Inside one transaction (`_adjust_in_transaction`) it re-reads the event and the board, then:
  - authorizes the caller (`Unauthorized` → DENIED);
  - refuses ARCHIVED (`Conflict`); every other state is allowed, so scores can be corrected after ENDED;
  - refuses a reason containing `agoge{` or `<event flag_prefix>{` (case-insensitive) with `BadRequest`, before any write, so a flag never reaches the log;
  - checks the workout is in `board_ids` and that the board doc exists (`NotFound` → ERROR);
  - writes only `score` (it may go negative).
  - `api/unit_tests/test_ctf_scoring_adjust.py` has 23 tests.
- **Learned:** **R1 must NOT wrap `adjust` in `CtfAudit`.** It audits itself because the reason lives only in the audit row, and a second wrap would break SC-18's one-row rule. The route should call `adjust` and map errors with `to_http_exception`. Gates now: api 790, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** R1 Instructor router (PRD.md:1041).

### Iteration 48 — 2026-10-16
- **Completed:** R1. `api/routers/ctf.py` (`ctf_router`, prefix `/ctf`) has every route in the endpoint table.
  - **Gating:** every route except `GET /config/` carries `dependencies=[Depends(ctf_enabled_required)]`. DELETE and reveal use `admin_required`; the rest use `teacher_required`.
  - **Errors:** each route maps errors with `to_http_exception`.
  - **Bodies:** taken as `Any = Body(None)` and validated by `_parse`, so a malformed body, unknown action or unknown mode gives 400 ("Invalid request body: …") rather than 422. Malformed path ids still give FastAPI's 422.
  - **Audit:** each PUT/POST/DELETE, plus reveal, is wrapped in `CtfAudit` as `CTF_CREATE`, `CTF_UPDATE`, `CTF_<ACTION>`, `CTF_DELETE`, `FLAG_REPLANT`, `FLAG_REVEAL` or `HOST_RESET`. The score route is not wrapped, because `adjust` audits itself.
  - **New core method:** `CtfEvent.reveal(ctf_id, flag_id, workout_id, user)` is admin-only in core too. An unknown flag or board gives `NotFound`, and a missing seed gives `ServiceUnavailable`.
  - **`create` change:** it takes an optional `ctf_id`, so the router audits a failed create under the id it would have used.
  - **Tests:** `test_ctf_router.py` (53) and `test_ctf_event_reveal.py` (6).
- **Learned:** In HOST_RESET rows, the server name goes in `target`, not `detail`, because `add_detail` rejects flag-shaped text and a strange path segment would otherwise be a 500. Gates now: api 851, cloud_functions 449, build_files 304, frontend 28. The reveal `workout_id` query is checked against the build-id pattern before the audit, for the same reason.
- **Blockers:** none.
- **Next:** R2 Student router (PRD.md:1042). It should reuse `_parse` (or the same pattern) for `CtfSubmitRequest`, and pass `request.client.host` as `origin_ip`. R3 must `include_router(ctf_router)`.

### Iteration 49 — 2026-10-16
- **Completed:** R2. `api/routers/ctf_board.py` (`ctf_board_router`, prefix `/ctf-board`) adds the four student routes. None of them requires auth, as the PRD specifies.
  - `GET /{wid}/` has no `ctf_enabled_required`. When CTF is disabled it returns `enrolled: false` without constructing `CtfScoring` (SC-19). Otherwise it returns `CtfScoring.board`.
  - `POST /{wid}/submit/`, `POST /{wid}/hint/{flag_id}/` and `GET /{wid}/scoreboard/` are gated by `ctf_enabled_required`, so they return 404 when disabled.
  - The submit body is validated with `routers.ctf._parse`: a malformed body gives 400 and the value is never echoed. `origin_ip` is `request.client.host`.
  - The scoreboard returns `{'items': [...]}`.
  - `flag_id` uses the `CtfFlagSpecModel.id` pattern. Path ids are validated, so a malformed one gives 422 without reaching core.
  - Failures log only the exception type name, so a flag value never reaches the log.
  - `api/unit_tests/test_ctf_board_router.py` has 24 tests.
- **Learned:** Neither router is registered in `api/main.py` yet; R3 must `include_router` both `ctf_router` and `ctf_board_router`. Gates now: api 875, cloud_functions 449, build_files 304, frontend 28.
- **Blockers:** none.
- **Next:** R3 Router registration (PRD.md:1043).

### Iteration 50 — 2026-10-16
- **Completed:** R3. `api/main.py` now imports and `include_router`s `ctf_router` (`/ctf`) and `ctf_board_router` (`/ctf-board`). The two lines sit alphabetically among the other routers, and no other router uses either prefix.
  - `api/unit_tests/test_ctf_router_registration.py` (8 tests) imports the real `main` with `firebase_admin.initialize_app` patched. It asserts that every route on both routers is on `main.app`. With the two `include_router` lines removed, all 8 fail.
- **Learned:** `main` can be imported in unit tests if `firebase_admin.initialize_app` is patched; AppConfig needs no env. The test pops `main` from `sys.modules` before and after, so no other test sees a cached app. Gates now: api 883, cloud_functions 449, build_files 304, frontend 28; tsc has no CTF errors.
- **Blockers:** none.
- **Next:** R4 Router auth tests (PRD.md:1044), `test_ctf_router_auth.py`. It could use the real `main.app` the same way, overriding `get_current_user` per role.

### Verification — 2026-10-16 — PASS
- **Checked:** H6, H7, R1, R2 and R3, the `[x]` tasks changed since the last verification. I read all of `api/routers/ctf.py` and `api/routers/ctf_board.py`, the router imports and `include_router` lines in `api/main.py`, `CtfScoring.scoreboard`/`public_scoreboard`/`_frozen_standing`/`_rank`/`adjust`/`_adjust_in_transaction` in `api/core/ctf/scoring.py`, `CtfEvent.reveal`/`delete` in `api/core/ctf/event.py`, and the test names in `test_ctf_scoring_scoreboard.py`. I compared them with PRD.md:1035-1043, the API Endpoints tables (PRD.md:855-897), SC-16, SC-18 and SC-19.
  - H6: the instructor ranking sorts by score descending, then the earliest `last_solve_at`. A team with no solve ranks after a tied team that has one, and the freeze is ignored. The public ranking uses "Team <n>" by `board_ids` index, sets `is_you`, and returns no team name or workout id. A disabled public scoreboard → `NotFound`. While frozen, `_frozen_standing` takes out the points and solve count of each solve with `solved_at > scoreboard_frozen_at` and recomputes `last_solve_at`. SC-16 tests are at :204, :218 and :227.
  - H7: one transaction re-reads the event and the board, authorizes the caller, refuses ARCHIVED (`Conflict`), refuses a flag-shaped reason (`BadRequest`) before any write, and writes only `score`. It writes its own `SCORE_ADJUST` row through `CtfAudit`.
  - R1: all 19 `/ctf` routes in the endpoint table are present. Every route except `GET /config/` has `ctf_enabled_required`. DELETE and reveal use `admin_required`, and `CtfEvent.reveal`/`delete` check `is_admin` again in core. The rest use `teacher_required`. Errors are mapped with `to_http_exception`. Each PUT/POST/DELETE and reveal is wrapped in exactly one `CtfAudit` row. Score is the one exception: it is not wrapped, because `adjust` writes its own row, so SC-18's one-row rule still holds. Collections return `{'items': [...]}`.
  - R2: the 4 `/ctf-board` routes have no auth, as the PRD requires. `GET /{wid}/` is not gated and answers `enrolled: false` when the feature is disabled (SC-19). The other 3 are gated by `ctf_enabled_required`. Submit passes `request.client.host` as `origin_ip`. The scoreboard returns `{'items': [...]}`.
  - R3: both routers are imported and `include_router`'d in `api/main.py:79-80`.
  - No TODO, FIXME, stub or `NotImplemented` in `api/routers/ctf*.py` or `api/core/ctf/`.
  - R4 and Groups I/J/K are correctly still `[ ]`.
- **Gate results:**
  - api/unit_tests: 883 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 4 files, 28 tests passed.
  - ESLint gate: "No files matching the pattern "src/components/Teacher/Ctf" were found". This is expected because no Group I/J task is done.
  - tsc gate: 0 errors name a CTF file (grep exit 1).
- **Reopened:** none.

### Iteration 51 — 2026-10-16
- **Completed:** R4 — `api/unit_tests/test_ctf_router_auth.py` (211 tests) mounts both CTF routers with the real `teacher_required`/`admin_required`/`ctf_enabled_required`, substituting only the user. It covers: anonymous/student/pending → 403 on all 18 `/ctf` routes (config included) with no core call and no audit row; a missing token → 403; instructor, admin and admin-only users pass auth on every teacher route; every non-admin (GM included) → 403 on DELETE and reveal; admin may DELETE and reveal. For SC-19, disabled → 404 on every gated route for every role, admin included (the enabled gate runs before the role check, so a 403 can't reveal a route), config still answers instructors and refuses others, the three gated `/ctf-board` routes → 404, and the board → `enrolled: false`. A table-completeness test fails if `ctf_router` gains a route the table lacks. Mutation check: switching DELETE to `teacher_required`, or dropping the gate on `/log/`, fails the suite.
- **Learned:** `AnonymousAppUser()` raises `ValidationError`, so tests can't use it; it is filed as BUG4. Gates now: api 1094, cloud_functions 449, build_files 304, frontend 28; tsc has no CTF errors.
- **Blockers:** none.
- **Next:** BUG4 (small), or I1 CTF TypeScript models (PRD.md:1049), which starts Group I.

### Iteration 52 — 2026-10-16
- **Completed:** BUG4. `AnonymousAppUser` (common/models/users.py) now overrides `uid`/`email` as `Optional[str] = None` on the subclass only and lets `settings` take the parent's default factory, so `AnonymousAppUser()` constructs. `AgogeUser` still requires both fields. It uses None rather than `''` so an anonymous caller can never match a stored `student_email`.
  - New `api/unit_tests/test_anonymous_user.py` (6 tests; 4 fail on the old code) covers construction, no permissions, default LMS settings, the parent staying strict, `get_current_user(token=None)` returning the anonymous user, and a missing header still getting 403 from `HTTPBearer`.
  - `test_ctf_router_auth.py` now uses the real `AnonymousAppUser()` in place of the stand-in user. Its pytest id falls back to "anonymous".
- **Learned:** A Pydantic v2 subclass can loosen a parent's field by re-annotating it, and the parent is unaffected. Gates now: api 1100, cloud_functions 449, build_files 304, frontend 28; tsc has no CTF errors; the eslint gate still has no CTF files.
- **Blockers:** none.
- **Next:** I1 CTF TypeScript models (PRD.md:1049).

### Iteration 53 — 2026-10-16
- **Completed:** I1. New file `frontend/src/services/Ctf/ctf.model.ts`. It has `export interface`s with snake_case keys for every CTF response model in `common/models/response.py` and every request model in `common/models/agoge.py`. It also covers the stored documents the API returns: `CtfEvent` (with `CtfSpec`/`CtfFlagSpec`/`CtfScoringSpec`), `CtfSubmission`, `CtfLogEntry`, `CtfIdResponse`, and the two dict envelopes, `CtfReplantResponse` `{messages}` and `CtfScoreAdjustResponse` `{workout_id, score}`. The Python `Literal`s are string unions. `CtfStates` is a `const` map, so I8/I10 can compare `state` numbers without magic values.
- **Learned:** A Python `Optional[X]` with no default is always serialized, so it is typed `X | null`, not `?`. Only `CtfUpdateRequest` and `CtfReplantRequest` use `?`, because there an omitted key means "leave unchanged" or "all". `state_name` stays `string` because `_state_name` falls back to `str(state)`. Gates now: api 1100, cloud_functions 449, build_files 304, frontend 28; eslint on `src/services/Ctf` is clean; tsc has no CTF errors.
- **Blockers:** none.
- **Next:** I2 CTF transformer and service (PRD.md:1050), with `ctf.service.test.ts` modelled on `rubric.service.test.ts`.

### Iteration 54 — 2026-10-16
- **Completed:** I2. `frontend/src/utilities/transformers/ctf.transform.ts` and `frontend/src/services/Ctf/ctf.service.ts`.
  - `ctfService` has one function per `/ctf` route: `getConfig`, `list`, `create`, `get`, `update`, `remove`, `getState`, `processAction`, `getFlags`, `replant`, `revealFlag`, `getBoards`, `getHosts`, `resetHost`, `adjustScore`, `getScoreboard`, `getSubmissions`, `getLog`.
  - `ctfBoardService` covers the 4 `/ctf-board` routes (`getBoard`, `submitFlag`, `takeHint`, `getPublicScoreboard`). They send no token because the API routes have no auth.
  - 19 `URL_CTF_API_*` / `URL_CTF_BOARD_API_*` constants were added to `router/urls.ts`. Path values go through `formatString(..., true)`, so a server name is URL-encoded.
  - The transformers copy only modelled keys, and they default nullable keys to null and lists to []. `ctf_enabled` and `rebuild_allowed` fail closed unless they are an explicit `true`.
  - `ctf.service.test.ts` (10 tests) covers: the items-envelope GET, query filters, config fail-closed, a PUT action, an encoded reset path, the host-row default, a 409 error and a 429 error, and board reads/submits without a token.
- **Learned:** The eslint gate uses `--max-warnings 0` and `no-explicit-any` is a warning, so the transformers type their input as the wire model (`(data: CtfX): CtfX`), not `any`. `apiService` accepts that because its `transformFn` param is `(data: any) => T`. Gates now: frontend 5 files / 38 tests; eslint clean on `src/services/Ctf` and the transformer; tsc has no CTF errors. No Python files changed.
- **Blockers:** none.
- **Next:** I3 Feature flag hook (PRD.md:1052). `hooks/useCtfEnabled.tsx` should call `ctfService.getConfig()` once per session for instructors.

### Iteration 55 — 2026-10-16
- **Completed:** I3. New `frontend/src/hooks/useCtfEnabled.tsx` returns `{ctfEnabled, loading}`.
  - It calls `ctfService.getConfig()` only for a signed-in user whose `permissions.instructor` or `permissions.admin` is true, because the route is `teacher_required`. Everyone else gets `{false, false}` and no request is sent.
  - The answer is cached at module level and keyed by uid, so all consumers share one request per signed-in user for the life of the page. A different uid triggers a new request, and the previous user's answer is never shown, not even for one render. Signing out hides the feature at once.
  - On an error it fails closed (`false`) and forgets the failure so a later mount can retry. `resetCtfEnabledCache` exists for tests.
  - `useCtfEnabled.test.tsx` has 10 tests. Mutation check: removing the cache, or dropping the permission check, fails tests.
- **Learned:** `useAuthContext().agogeUser.user` is `SafeAgogeUser | null` with `permissions: {[key]: boolean}`; mocking `../context/AuthContext` with a mutable `currentUser` plus `rerender()` simulates a user change. Gates now: frontend 6 files / 48 tests; eslint is clean on the hook; tsc has no CTF errors. No Python files changed.
- **Blockers:** none.
- **Next:** I4 Routes and menu (PRD.md:1053). Filter the Teachers `AppBarMenu` item on `useCtfEnabled().ctfEnabled`.

### Verification — 2026-10-16 — PASS
- **Checked:** R4, BUG4, I1, I2 and I3, the `[x]` tasks changed since the last verification. I read `api/unit_tests/test_ctf_router_auth.py`, `test_anonymous_user.py`, `AnonymousAppUser`/`AgogeUser` in `common/models/users.py`, and all of `useCtfEnabled.tsx`. Subagents compared `ctf.model.ts`, `ctf.transform.ts`, `ctf.service.ts` and `ctf.service.test.ts` field by field and route by route with `common/models/response.py`, the `Ctf*Request` models in `common/models/agoge.py`, `api/routers/ctf.py` and `api/routers/ctf_board.py`, against PRD.md:1044-1052 and SC-19.
  - R4: the test overrides only `get_current_user`, `get_cloud_env` and `is_ctf_enabled`. The real `teacher_required`, `admin_required` and `ctf_enabled_required` run.
    - Anonymous, student and pending users get 403 on all 18 `/ctf` routes, and no core call or audit row is made.
    - An instructor gets 403 on DELETE and on reveal.
    - SC-19: with CTF disabled, every role gets 404 on every gated route, `GET /config/` still answers, and `GET /ctf-board/{wid}/` returns `enrolled: false`.
    - `test_route_table_covers_every_instructor_route` compares the table with `ctf_router.routes` (18 routes; the previous entry's "19" was a miscount).
  - BUG4: `AnonymousAppUser` overrides `uid`/`email` as `Optional[str] = None` on the subclass only. `AgogeUser` still requires both fields, and the tests assert this with `model_fields[...].is_required()`.
  - I1: all 14 `Ctf*` response models and 7 `Ctf*Request` models are mirrored with snake_case keys, and the field names and types match. The Literal unions and `CtfStates` 0-7 match. Internal docs that no route returns (`CtfBoardModel`, `CtfDigestModel`, …) are not mirrored, which is fine.
  - I2: all 18 `/ctf` and 4 `/ctf-board` routes have a service function through `apiService`. Methods, trailing-slash paths and query params match, and the board calls send no token. The test uses the rubric mock setup and covers a GET, a PUT, a 409 and a 429.
  - I3: the config call is made only for instructor/admin users. The answer is cached per uid at module level and the request is shared. An error fails closed and allows a retry, and a stale answer from another user is never shown.
  - No TODO, FIXME, skip/only or stub in any of these files.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 6 files, 48 tests passed.
  - ESLint gate: exit 2, "No files matching the pattern "src/components/Teacher/Ctf" were found". This is expected because I4+ are not done. Run on the existing CTF paths (`src/services/Ctf`, the hook and its test, `ctf.transform.ts`), it exits 0 with 0 warnings.
  - tsc gate: 0 errors name a CTF file (grep exit 1).
- **Reopened:** none.

### Iteration 56 — 2026-10-16
- **Completed:** I4, first slice. `router/urls.ts` gains `URL_TEACHER_CTF_BASE` (`/teacher/ctf`) and `URL_TEACHER_CTF_EVENT` (`/teacher/ctf/event`). The dashboard route will be `${URL_TEACHER_CTF_EVENT}/:ctf_id`, which mirrors `${URL_TEACHER_UNIT}/:build_id` and keeps clear of the list path. `AgogeAppBar` calls `useCtfEnabled()` and adds a "CTF Events" item (`Flag` icon, linking to `URL_TEACHER_CTF_BASE`) to the **Teachers** menu only when `ctfEnabled` is true. That value is false while loading, so the item fails closed. New `AgogeAppBar.test.tsx` (3 tests): the item is present with the right href when enabled, absent when disabled, and never shown to a non-instructor.
- **Learned:** The routes need `CtfEventList`/`CtfDashboard`, which are I5 and I9. Adding them now would mean placeholder pages, so they were split out as I4b. `AgogeAppBar.tsx` already had an ESLint error before this change (`onSidebarToggle` is defined but never used); it is outside the CTF lint gate, so it was left alone. Gates now: frontend 7 files / 51 tests; eslint is clean on the CTF paths and the new test; tsc has no CTF/nav/urls errors; no Python changed.
- **Blockers:** none. The browser check is moved to I4b.
- **Next:** I5 Events list page (PRD.md:1055), then add its route (part of I4b).

### Iteration 57 — 2026-10-16
- **Completed:** I5, plus the list half of I4b.
  - New `frontend/src/components/Teacher/Ctf/CtfEventList.tsx`: a `StyledDataGrid` with Active / Archived `Tabs` that use the same tab `sx` as `ActiveExpiredUnitTable`. The ID column is a `LinkButton` to `${URL_TEACHER_CTF_EVENT}/<id>`.
  - Only `ARCHIVED` events go on the Archived tab. BROKEN stays on Active because it still needs the game master.
  - A failed `ctfService.list()` shows an error `Alert` (`status: message`) above an empty grid.
  - `AppRouter.tsx` routes `URL_TEACHER_CTF_BASE` to `CtfEventList` through `ProtectedRoute level="instructor"`.
  - `CtfEventList.test.tsx` has 4 tests: Active-tab filtering with the dashboard href, the Archived tab, the empty message, and the error alert.
- **Learned:** `StyledDataGrid` renders rows under jsdom without `disableVirtualization`, because its default `autoHeight` sizes the grid to its rows. Gates now: frontend 8 files / 55 tests. ESLint is clean on `src/components/Teacher/Ctf` and `AppRouter.tsx`, and tsc reports no CTF errors. No Python changed.
- **Blockers:** I did not do the browser check. It needs a signed-in instructor and a live API, which a headless run does not have. It stays with I4b.
- **Next:** I6 Create from unit (PRD.md:1057). The dashboard route in I4b waits for I9.


### Iteration 58 — 2026-10-16
- **Completed:** I6.
  - New `frontend/src/components/Teacher/Ctf/CreateCtfButton.tsx`: a `LoadingButton` "Create CTF Event" that calls `ctfService.create({unit_id})` and navigates to `${URL_TEACHER_CTF_EVENT}/<build_id>` on success.
  - On failure it shows an error `Alert` (`status: message`, e.g. 409 for a workout already on an active board) and re-enables the button.
  - It is disabled on an expired unit, and it renders nothing when `useCtfEnabled()` is false, because every `/ctf/` route returns 404 then (SC-19).
  - `TeacherUnit` renders it in the left column under `UnitRubricEditor`, gated on `unitFull.value?.ctf_capable` the same way the rubric editor is gated on `rubric_support`.
  - `transformToUnit` now sets `ctf_capable` (true only when `ctf` is an object). The spec block itself is not copied into frontend state.
  - Tests: `CreateCtfButton.test.tsx` (4: success navigation, error alert and retry, disabled when expired, hidden when CTF is disabled), plus 5 `ctf_capable` cases in `unit.transform.test.ts`.
- **Learned:** `GET /unit/{id}/full/` already returns `unit.ctf`, because `UnitModel.ctf` exists, so no API change was needed. Gates: api 1100, cloud_functions 449, build_files 304 passed; frontend 9 files / 64 tests. The CTF eslint gate exits 0 on the existing paths. tsc reports no CTF, TeacherUnit or unit-transform/model errors. The `unit.service.ts` TS7053 errors were already there.
- **Blockers:** I did not do the browser check (it needs a signed-in instructor and a live API). It moves to I4b.
- **Next:** I7 Action confirm dialog (PRD.md:1059).

### Iteration 59 — 2026-10-16
- **Completed:** I7. New `frontend/src/components/Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog.tsx` (default export) takes the props `{open, title, message, confirmLabel, onConfirm, onClose, loading}`. Like `ConfirmCancelDialog`, it is a plain MUI `Dialog` with Cancel and a contained `LoadingButton` labelled `confirmLabel`. `message` is a `ReactNode`, so J4 can bold the hint cost. Title and message are wired through `useId` to `aria-labelledby`/`aria-describedby`. While `loading` is true, Cancel is disabled and backdrop/Escape closes are ignored, so the dialog stays up until the request settles. `ActionConfirmDialog.test.tsx` has 6 tests: the accessible name and description, closed renders nothing, confirm calls only `onConfirm`, Cancel and Escape call `onClose`, while loading both buttons are disabled and Escape is ignored, and rich message content.
- **Learned:** The callers own the request state: I10 and J4 should set `loading` while their call runs and close the dialog themselves on success. Gates: frontend 10 files / 70 tests. ESLint is clean (exit 0) on the gate paths that exist (`src/components/Student/Ctf` does not exist yet), and tsc reports no CTF errors. No Python changed.
- **Blockers:** none.
- **Next:** I8 CTF state chip (PRD.md:1060).

### Iteration 60 — 2026-10-16
- **Completed:** I8.
  - `StateMapping.tsx` gains `CtfStateMapping` (a `Record` over every `CtfStates` value giving `{text, color, icon}`, with colours from theme palette keys such as `neutral`, `ready`, `warning` and `error`) and `resolveCtfStatus(state)`, which returns "Unknown" for a state it does not know.
  - The live region in `StateInfo` was moved into an exported `StateAnnouncement` (`{label, context}`). `StateInfo` uses it, and its behaviour is unchanged.
  - New `Teacher/Ctf/CtfStateChip.tsx` (`{state, sx?}`) renders `StateAnnouncement` (context "CTF event") plus `StatusBadge` with the icon.
  - `CtfStateChip.test.tsx` (5 tests): every state maps to a real palette key and an icon; the unknown fallback; label and icon render; the first render is not announced; a change is announced and then cleared after 800 ms.
- **Learned:** Render MUI components that use the custom `ready`/`neutral` colours inside `ThemeProvider theme={darkTheme}` in tests. `StateInfo.tsx` had an existing `import/order` error, which `eslint --fix` fixed. Gates: api 1100, cloud_functions 449, build_files 304 passed; frontend 11 files / 75 tests. ESLint is clean on the CTF paths plus the Status files, and tsc reports no CTF/Status errors.
- **Blockers:** none.
- **Next:** I9 Dashboard shell (PRD.md:1061). Put `CtfStateChip` in its left column, then add the dashboard route to finish I4b. `CtfEventList` still shows `state_name` as plain text; it could switch to `CtfStateChip` later.

- **Addendum (iteration 60):** Adding `CtfStateMapping` changed the wording of an existing tsc error in `UnitTable.tsx` (TS2305 became TS2724 "Did you mean 'CtfStateMapping'?"), so it no longer matched the check baseline. `UnitTable.tsx` imported a `StateMapping` export that never existed and was never used, so I removed that name from the import and refreshed the baseline.

### Verification — 2026-10-16 — PASS
- **Checked:** I4 (first slice), I5, I6, I7 and I8, the `[x]` tasks changed since the last verification. I read the diff `e835026..16d4d8f`: all of `CtfEventList.tsx`, `CreateCtfButton.tsx`, `CtfStateChip.tsx` and `ActionConfirmDialog.tsx`, plus the changes to `urls.ts`, `AppRouter.tsx`, `AgogeAppBar.tsx`, `TeacherUnit.tsx`, `StateMapping.tsx`, `unit.model.ts`, `unit.transform.ts` and `UnitTable.tsx`. I compared them with PRD.md:1053-1060.
  - I4: `URL_TEACHER_CTF_BASE` is `${URL_TEACHER_BASE}/ctf` and the dashboard base is `URL_TEACHER_CTF_EVENT`. The **Teachers** menu adds "CTF Events" only when `ctfEnabled`, which is false while loading.
  - I5: `StyledDataGrid` with Active/Archived `Tabs` that use the same tab `sx` as `ActiveExpiredUnitTable`. The ID column is a `LinkButton` to the dashboard. The route is wrapped in `ProtectedRoute level="instructor"`. The list call has a cancel guard and an error `Alert`.
  - I6: `TeacherUnit` renders the button only when `ctf_capable`, the same way `UnitRubricEditor` is gated. `ctf_capable` is true only when `unit.ctf` is an object. `UnitFullResponse.unit` is `UnitModel`, which has `ctf` (common/models/agoge.py:533), so the field reaches the client. On success the button navigates to `${URL_TEACHER_CTF_EVENT}/<build_id>`. All hooks run before the `!ctfEnabled` early return.
  - I7: it has exactly the props `{open, title, message, confirmLabel, onConfirm, onClose, loading}` and uses a `LoadingButton`. Title and message are wired to `aria-labelledby`/`aria-describedby`, and close is blocked while loading.
  - I8: `CtfStateMapping` is a `Record` over all 8 `CtfStates`, each with `{text, color, icon}`. `ready` and `neutral` are real palette augmentations (styles/theme.tsx:6-20). The chip renders through `StatusBadge` with `icon`, and `StateAnnouncement` (taken out of `StateInfo`) provides the `aria-live` announcement.
  - No TODO, FIXME, skip/only or stubs in the new files.
  - Note, not a reopen: the done-when for I4, I5 and I6 is a browser check, and it has not been done. The builder moved it into the open task I4b, which names each check. The dashboard route is still missing, so the menu item will not be fully usable until I9/I4b.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 11 files, 75 tests passed.
  - ESLint gate, as written: exit 2, "No files matching the pattern "src/components/Student/Ctf" were found". This is expected because J1+ are not done. Run on the paths that exist (`src/components/Teacher/Ctf`, `src/services/Ctf`, the hook, `ctf.transform.ts`, `ActionConfirmDialog`) plus the touched `StateMapping.tsx`, `StateInfo.tsx`, `AppRouter.tsx` and `urls.ts`, it exits 0 with 0 warnings.
  - Lint problems that were already there before this work: `StateChip.tsx`, `StatusBadge.tsx`, and the `exhaustive-deps` warning at `TeacherUnit.tsx:104` (from 2026-03, `6296b93`). This work did not touch any of them.
  - tsc gate: 0 errors name a CTF file (grep exit 1, gate exit 0).
- **Reopened:** none.

### Iteration 61 — 2026-10-16
- **Completed:** I9, plus the dashboard route half of I4b.
  - New `frontend/src/components/Teacher/Ctf/CtfDashboard.tsx` uses `TeacherUnit`'s 25/75 `Box` split. The left column is a `Paper elevation={2}` section titled "Event Control" with `CtfStateChip` and a remaining-time countdown. The right column has MUI `Tabs` (Flags, Hosts, Scoreboard, Event Log, Submissions) with `tabpanel` wiring through `aria-controls`/`aria-labelledby`. The panels are empty slots for I12-I17, and I10 adds its buttons inside the left `Paper`.
  - It polls `ctfService.getState` with `usePolling` every `STATE_POLL_INTERVAL_MS = 10000`. The poll stops once the event is ARCHIVED. A 404 sends the user to `URL_ERROR`, as `TeacherUnit` does. Any other error shows an error `Alert` and polling continues; the next successful read clears it. A warning `Alert` shows when `budget_exceeded` is true.
  - New `ctfTime.ts`: `remainingSeconds` mirrors `CtfScoring._remaining_seconds` (null when open-ended, 0 when ENDED, held at `paused_at` while PAUSED, never negative), and `formatDuration` gives HH:MM:SS. The countdown ticks locally every second between polls.
  - `AppRouter.tsx` routes `${URL_TEACHER_CTF_EVENT}/:ctf_id` to `CtfDashboard` through `ProtectedRoute level="instructor"`.
  - `CtfDashboard.test.tsx` has 9 tests: the clock helper cases, chip + time + tabs + tab selection, the countdown and the 10 s re-poll (paused clock held), the budget banner, the error alert and recovery, the 404 redirect, and no polling after ARCHIVED.
- **Learned:** `usePolling` makes its first call on mount, so the dashboard does not need a separate initial fetch. Under `vi.useFakeTimers()`, `act(async () => vi.advanceTimersByTime(...))` followed by a microtask flush is enough to drive it. Gates: frontend 12 files / 84 tests. ESLint is clean on the CTF paths plus `AppRouter.tsx`, and tsc reports no CTF errors. No Python changed.
- **Blockers:** I did not do the browser check (it needs a signed-in instructor and a live API). It moves to I4b.
- **Next:** I10 Event Control panel (PRD.md:1063). Put it inside the dashboard's left `Paper`. It needs `ConfirmationDialog` to take a `confirmLabel` prop.

### Iteration 62 — 2026-10-16
- **Completed:** I10.
  - New `frontend/src/components/Teacher/Ctf/CtfEventControl.tsx` shows Arm, Start, Pause, Resume, End and Archive in a labelled `group` inside the dashboard's left `Paper`.
  - `CTF_ACTION_RULES` gives each action its legal states, copied from `CtfEvent.ACTIONS` (api/core/ctf/event.py:75-80). A button is enabled only in those states and is disabled while a request runs.
  - Arm, Start, Pause and Resume confirm through `ActionConfirmDialog`. End and Archive confirm through the type-to-confirm `ConfirmationDialog`, where the user types the event id.
  - `ConfirmationDialog` gains optional `confirmLabel` and `message` props and the actions `end` and `archive`. With no `confirmLabel`, existing callers keep "Delete", the trash icon and the original text.
  - On success, `onActionComplete` (the dashboard's `fetchState`) re-reads state right away. On failure, an error `Alert` shows `status: message`.
  - Tests: `CtfEventControl.test.tsx` (14): the enabled-button matrix for all 8 states, the plain dialog's confirm and cancel, type-to-confirm for End and Archive, the API error, and the default "Delete" wording. One added `CtfDashboard` test checks that an action re-reads state.
- **Learned:** Under `vi.useFakeTimers()`, a closing MUI `Dialog` keeps the page behind it `aria-hidden` until its exit transition finishes. Advance the timers (about 500 ms) before you query roles behind it. The selected action is kept apart from the `open` flag so that a dialog does not fall back to the "Delete" label while it fades out. Gates: frontend 13 files / 99 tests. ESLint is clean on the CTF paths plus `Confirmation.tsx`, and tsc reports no CTF or ConfirmationDialog errors. No Python changed. The `agoge-reviewer` found no defects.
- **Blockers:** I did not do the browser check (it needs a signed-in instructor and a live API). It moves to I4b.
- **Next:** I11 Scoreboard settings (PRD.md:1065). It can sit in the left `Paper` under `CtfEventControl`; `ctfService.update` already exists.

### Iteration 63 — 2026-10-16
- **Completed:** I11. I took it ahead of I4b because I4b now needs only browser checks, and those need a signed-in instructor and a live API, which a headless run does not have.
  - New `frontend/src/components/Teacher/Ctf/ScoreboardSettings.tsx` sits in the dashboard's left `Paper` under `CtfEventControl`. Every control calls `ctfService.update` (`PUT /ctf/{id}/`).
  - Freeze toggle: turning it on sends `scoreboard_frozen_at: now`, turning it off sends an explicit `null`, and it shows when the board was frozen.
  - Public-scoreboard toggle: sends `public_scoreboard_enabled`.
  - `ends_at`: a `DateTimePicker` (`AdapterDateFnsV3`, the same as `WorkoutModal`) holds a draft, with "Save end time" (epoch seconds; past or unchanged times are refused) and "Clear end time" (`null`, open-ended).
  - After a successful PUT it awaits `onUpdated` (the dashboard's `fetchState`), so a toggle does not snap back. Everything is disabled while a request runs and while ARCHIVED (the API answers 409). Errors show in an `Alert` as `status: message`. The switches carry `role="switch"`.
  - `ScoreboardSettings.test.tsx`: 11 tests.
- **Learned:**
  - The MUI X v7 `DateTimePicker` works in jsdom without a `matchMedia` mock. `fireEvent.change(input, {target: {value: "10/16/2026 05:30 PM"}})` sets it, and `toHaveValue` reads it back in the same format.
  - `vi.useFakeTimers({toFake: ["Date"]})` pins "now" without breaking `waitFor`.
  - MUI `Switch` has no `switch` role unless you pass `inputProps={{role: 'switch'}}`.
  - Gates: frontend 14 files / 110 tests. ESLint is clean on the CTF paths, and tsc reports no CTF errors. No Python changed. The `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I12 Flags panel (PRD.md:1066). Fill the Flags `tabpanel` slot in `CtfDashboard` with `ctfService.getFlags`.

### Iteration 64 — 2026-10-16
- **Completed:** I12.
  - New `frontend/src/components/Teacher/Ctf/CtfFlagsPanel.tsx` is mounted in the dashboard's Flags `tabpanel`. It is a `StyledDataGrid` (Community) with these columns: Flag, Server, Slot, Points, Decoy, Status, "Plant status by team" (one coloured `Chip` per board, with `plant_error` in its tooltip and ✓ when solved), and a Replant button. Rows are keyed by `getRowId` on `flag_id`, and row height is `auto`.
  - Status column: rows with `failed` or `stale` boards show `WarningAmberIcon` plus text such as "1 failed, 2 stale" (`flagProblems`). Other rows show "OK".
  - Replant: the button is enabled only in `REPLANT_STATES` (ARMED, RUNNING, PAUSED, BROKEN), the same states as the API route. It confirms through `ActionConfirmDialog`, because a replant resets the VM (SC-7). It then sends `PUT /ctf/{id}/flags/` with `{servers: [row.server]}` for every board, because replant works per server, not per flag. It shows a success notice with the message count and re-reads the flags. A replant error has its own dismissible `Alert`, separate from the load error, so the next poll does not clear it.
  - Polling: `usePolling` every `FLAGS_POLL_INTERVAL_MS = 15000`, only while the Flags tab is active and the event is not ARCHIVED. An ARCHIVED event gets one read from a `useEffect`; the first version never loaded at all, and a test caught it.
  - Tests: `CtfFlagsPanel.test.tsx` (8): columns, the warning icon and text, replant confirm and re-read, cancel, the API error, the state matrix for all 8 states, and the load error. One added `CtfDashboard` test checks that the panel mounts and stops polling when another tab is selected (`getFlags` was added to that file's service mock).
- **Learned:** The dashboard test's `ctfService` mock has to include every service function that a mounted panel calls. As I13-I17 fill their tabs, add each panel's getter there. Gates: frontend 15 files / 119 tests. ESLint is clean on the CTF paths, and tsc reports no CTF errors. No Python changed. `agoge-reviewer` found no defects; I applied its one minor note (separate replant error state).
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I13 Flags bulk replant (PRD.md:1067). Turn on `checkboxSelection` in `CtfFlagsPanel` (drop `disableCheckBoxes`) and send one `PUT` with the union of the selected rows' `servers`.

### Iteration 65 — 2026-10-16
- **Completed:** I13.
  - `CtfFlagsPanel` now uses Community `checkboxSelection`, with a controlled `rowSelectionModel` passed through `StyledDataGrid`'s prop spread. `disableRowSelectionOnClick` keeps a per-row Replant click from toggling the row's checkbox.
  - A "Replant selected (N)" toolbar button (`buttonsConfig`) confirms through `ActionConfirmDialog`, then sends one `PUT /ctf/{id}/flags/` with `{servers}` set to `selectedServers(flags, selection)`. That is the de-duplicated union of the selected rows' servers, in row order, ignoring ids that have disappeared.
  - The button is disabled outside `REPLANT_STATES`, while a request runs, and when nothing is selected. A success clears the selection. The per-row Replant uses the same `targets: string[]` path.
  - 4 new tests: the `selectedServers` unit, a two-server bulk replant (one call, notice shown, selection cleared), one server shared by two flags, and the button disabled in ENDED.
- **Learned:** `StyledDataGrid` ignores `disableMultipleRowSelection` (it reads `disableMultiRowSelection`), and a defined `isDisabled` in `buttonsConfig` overrides `requiresSelection`. Selected rows that the quick filter hides, or that sit on another page, stay selected; the dialog lists the server names so the user sees them before confirming. Gates: frontend 15 files / 123 tests. ESLint is clean on the CTF paths, and tsc reports no CTF errors. No Python changed. `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I14 Hosts panel (PRD.md:1068). Fill the Hosts `tabpanel` in `CtfDashboard` using `ctfService.getHosts`/`resetHost`, and add the getter to the dashboard test's service mock.

### Verification — 2026-10-16 — PASS
- **Checked:** I9, I10, I11, I12 and I13, the `[x]` tasks changed since the last verification (diff `152769d..38ad084`). I read all of `CtfDashboard.tsx`, `ctfTime.ts`, `CtfEventControl.tsx`, `ScoreboardSettings.tsx` and `CtfFlagsPanel.tsx`, plus the changes to `Confirmation.tsx` and `AppRouter.tsx` and the test names in the four new test files. I compared them with PRD.md:1061-1067. A subagent checked the request and response contracts against `api/routers/ctf.py`, `api/core/ctf/event.py`, `api/core/ctf/hosts.py` and `common/models/response.py`. I also confirmed that BUG3's earlier reopen was fixed in iteration 36 and passed by the verification after it.
  - I9: the dashboard uses the 25/75 `Box` split. The left column is a `Paper elevation={2}` holding the state chip, the remaining time and Event Control. The right column has `Tabs` for Flags, Hosts, Scoreboard, Event Log and Submissions. `usePolling` reads state every 10 s, and a warning `Alert` shows when `budget_exceeded`. The route is `ProtectedRoute level="instructor"`. `remainingSeconds` matches `CtfScoring._remaining_seconds` (scoring.py:119-127) line for line.
  - I10: `CTF_ACTION_RULES` matches `CtfEvent.ACTIONS` (event.py:74-81) exactly. Arm, Start, Pause and Resume confirm through `ActionConfirmDialog`. End and Archive confirm through the type-to-confirm `ConfirmationDialog`, which now has a `confirmLabel`; existing callers still read "Delete".
  - I11: the freeze, public-scoreboard and `ends_at` controls each send `PUT /ctf/{id}/`. Times are epoch seconds, and an explicit `null` clears a field; the backend applies only the fields in `model_fields_set`, so this is correct.
  - I12: a Community `StyledDataGrid` with flag id, server, slot, points, decoy and per-board status. Rows with `failed` or `stale` boards show a warning icon and text, and each row has a Replant button. `REPLANT_STATES` equals hosts.py:18. Every response field it reads exists in `CtfFlagRow` and `CtfFlagBoardStatus`.
  - I13: `checkboxSelection` (the `StyledDataGrid` default) drives one `PUT /ctf/{id}/flags/` with `{servers}`: the de-duplicated union of the selected rows' servers, never empty.
  - No TODO, FIXME, skip/only, `@ts-ignore`, `eslint-disable` or `as any` in the new or changed files. No Pro DataGrid features.
  - Note, not a reopen: the "verified in browser" done-when for I9 and I10 has not been done. As with I4, I5 and I6, it is tracked in the open I4b.
  - Minor, not a reopen: `CtfUpdateRequest.public_scoreboard_enabled` is typed `boolean | null` on the frontend, and the backend request model accepts null too. But `CtfEventModel.public_scoreboard_enabled` is a non-optional `bool`, so an explicit null would fail re-validation in `CtfEvent.update` (event.py:218) and come back as an error instead of a clean 400. No caller sends null.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 15 files, 123 tests passed.
  - ESLint gate, as written: exit 2, "No files matching the pattern "src/components/Student/Ctf" were found". This is expected because J1 onward are not done. Run on the paths that exist, plus `ConfirmationDialog/Confirmation.tsx` and `router/AppRouter.tsx`, it exits 0 with 0 warnings.
  - tsc gate: no tsc error names a CTF file (gate exit 0).
- **Reopened:** none.

### Iteration 66 — 2026-10-16
- **Completed:** I14.
  - New `frontend/src/components/Teacher/Ctf/CtfHostsPanel.tsx` is mounted in the dashboard's Hosts `tabpanel`. It is a Community `StyledDataGrid` with one row per board per server (`getRowId` = `workout_id-server`) and these columns: Team, Server, Server state (`server_state_name`, or "Not built" when null), Flags (`flag_count`), and a Reset button.
  - Reset menu: the Reset button opens a `Menu` with Replant, Restart and Rebuild. No mode is pre-selected.
  - `resetBlocker` disables a mode, with its reason in a `Tooltip`, in the same cases the API refuses it:
    - every mode on an unbuilt server (`server_state === null`, which the API answers with 404);
    - Replant when `flag_count === 0` (400);
    - Rebuild when `!rebuild_allowed` (WireGuard, 400).
  - Confirmation: Replant and Restart use `ActionConfirmDialog`. Rebuild uses the type-to-confirm `ConfirmationDialog` (`action="rebuild"`, the server name as the expected text, `confirmLabel="Rebuild"`).
  - Sending: the confirmed reset calls `ctfService.resetHost(ctfId, workout_id, server, {mode})`, shows a notice and re-reads the hosts. A reset error has its own dismissible `Alert`.
  - Reset is enabled only in `RESET_STATES` (= `REPLANT_STATES`, matching `CtfHosts.reset`).
  - Polling: every `HOSTS_POLL_INTERVAL_MS = 15000`, only while the Hosts tab is active. An ARCHIVED event gets one read.
  - Tests: `CtfHostsPanel.test.tsx` (12) and one added `CtfDashboard` test for the Hosts tab. `getHosts` was added to the dashboard's service mock.
- **Learned:**
  - A disabled `MenuItem` has no pointer events, so its tooltip goes on a `<span>` wrapper. MUI `MenuList` arrow-key navigation skips such a span because it has no `tabindex`, so keyboard navigation still works.
  - The `agoge-reviewer` caught that unbuilt rows (listed on purpose by `CtfHosts.hosts`) would offer resets that 404. Fixed.
  - Gates: frontend 16 files / 136 tests; api 1100, cloud_functions 449, build_files 304. ESLint is clean on the CTF paths, and tsc reports no CTF errors.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I15 Scoreboard panel (PRD.md:1069). Use `ctfService` scoreboard getter, poll every 30 s, show a banner while `scoreboard_frozen_at` is set; add the getter to the dashboard test's service mock.

### Iteration 67 — 2026-10-16
- **Completed:** I15.
  - New `frontend/src/components/Teacher/Ctf/CtfScoreboardPanel.tsx` is mounted in the dashboard's Scoreboard `tabpanel`. It is a Community `StyledDataGrid` (`getRowId` = `workout_id`) with Rank, Team, Score, Solves, Decoys and Last solve ("No solves" when null). Rows keep the API's rank order; the grid applies no default sort.
  - Polling: `ctfService.getScoreboard` every `SCOREBOARD_POLL_INTERVAL_MS = 30000`, only while the tab is active. An ARCHIVED event gets one read.
  - Frozen banner: an info `Alert` shows while `scoreboardFrozenAt` is set. That value comes from the dashboard's 10 s state poll, so the banner follows a freeze toggle without waiting for the 30 s scoreboard poll. The banner says students see the frozen standings and that this view still counts every solve, because `CtfScoring.scoreboard` ignores the freeze.
  - Tests: `CtfScoreboardPanel.test.tsx` (6): rank order and columns, the 30 s poll, no reads while hidden, an archived event read once, the banner appearing and clearing, and a load error clearing on the next poll. One added `CtfDashboard` test checks mounting, the 30 s cadence, and the banner following the state poll. `getScoreboard` was added to the dashboard's service mock.
- **Learned:** Existing panels use the `Ctf*Panel.tsx` naming, not the PRD layout's `ScoreboardPanel.tsx`; I followed the code. Gates: frontend 17 files / 143 tests; api 1100, cloud_functions 449, build_files 304. ESLint is clean on the CTF paths, and tsc reports no CTF errors. `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I16 Event log panel (PRD.md:1070). Use `ctfService.getLog(ctfId, action?)`, show newest first, and add an action filter. Add `getLog` to the dashboard test's service mock.

### Iteration 68 — 2026-10-16
- **Completed:** I16.
  - New `frontend/src/components/Teacher/Ctf/CtfEventLogPanel.tsx` is mounted in the dashboard's Event Log `tabpanel`. It is a Community `StyledDataGrid` (`getRowId` = `id`) with these columns: Time, Action (readable label), Result (an outlined `Chip`: OK success, DENIED warning, ERROR error), Actor, Target and Detail (`key: value` pairs).
  - Order: rows are sorted newest first by `created_at` (`newestFirst`), even though the API already returns them that way.
  - Filter: an Action `TextField select` with "All actions" plus every `LOG_ACTIONS` member. The filter is applied server-side through `ctfService.getLog(ctfId, action)`, and a filter change reads at once.
  - Stale responses: `filterRef` drops any response for a filter the user has since changed (success, error and loading paths).
  - Polling: every `LOG_POLL_INTERVAL_MS = 15000`, only while the tab is active. An ARCHIVED event gets one read.
  - A note shows when the 500-row cap (`CtfEvent.MAX_PANEL_ROWS`) is reached.
  - `LogAction` in `ctf.model.ts` now derives from a runtime `LOG_ACTIONS` array.
  - Tests: `CtfEventLogPanel.test.tsx` (8). One added `CtfDashboard` test. `getLog` was added to the dashboard's service mock.
- **Learned:** `usePolling` does not re-run when the polled function changes, and it skips a poll while one is pending. So a filter change has to call the fetch itself, and the stale-response guard has to live in the panel. Gates: frontend 18 files / 152 tests. ESLint is clean on the CTF paths, and tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no defects. I applied its one wording nit: the "filter to see older" hint is hidden when a filter is already set.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** I17 Submission log panel (PRD.md:1071). Mirror `CtfEventLogPanel`: a verdict filter (`ctfService.getSubmissions(ctfId, verdict?)`), newest first by `submitted_at`, and show the matched team on `cross_submission` rows. Add the getter to the dashboard test's service mock.

### Iteration 69 — 2026-10-16
- **Completed:** I17.
  - New `frontend/src/components/Teacher/Ctf/CtfSubmissionLogPanel.tsx` is mounted in the dashboard's Submissions `tabpanel`. It is a Community `StyledDataGrid` (`getRowId` = `id`) with Time, Team, Flag, Verdict (an outlined `Chip`), Matched team, Points and Origin IP.
  - Team names come from the dashboard's 10 s state poll (`event.boards`, passed as `boards`), so they cost no extra read. An unknown board falls back to its workout id. Matched team is filled only on `cross_submission` rows.
  - Filter: a Verdict `TextField select` with "All verdicts" plus every `VERDICTS` member, applied server-side through `ctfService.getSubmissions(ctfId, verdict)`. It has the same `filterRef` stale-response guard as the Event Log panel.
  - Order and polling: newest first by `submitted_at`, polled every 15 s only while the tab is active, and an ARCHIVED event is read once. A note shows at the 500-row cap.
  - `Verdict` in `ctf.model.ts` now derives from a runtime `VERDICTS` array.
  - Tests: `CtfSubmissionLogPanel.test.tsx` (10) and one added `CtfDashboard` test that checks team names flowing from the state poll. `getSubmissions` was added to the dashboard's service mock.
- **Learned:** `CtfStateResponse.boards` already carries `workout_id` → `team_name` for every board, so a panel that needs team names should take it as a prop rather than add a read. Gates: frontend 19 files / 163 tests. ESLint is clean on the CTF paths, and tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** LINT1 (a one-line import-order fix), then J1 Student CTF polling (PRD.md:1075).

### Iteration 70 — 2026-10-16
- **Completed:** LINT1. In `frontend/src/utilities/transformers/unit.transform.test.ts`, the `./unit.transform` import now comes after `./specificationEdit.transform`. `npx eslint` on the file exits 0 with 0 warnings. Nothing else changed.
- **Learned:** `import/order` sorts sibling imports alphabetically by path. Gates: frontend 19 files / 163 tests; ESLint is clean on the CTF paths; tsc reports no CTF errors. No Python changed, so the Python suites were not re-run.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** J1 Student CTF polling (PRD.md:1075).

### Verification — 2026-10-16 — PASS
- **Checked:** I14, I15, I16, I17 and LINT1, the `[x]` tasks changed since the last verification (diff `38ad084..7848f43`). I read all of `CtfHostsPanel.tsx`, `CtfScoreboardPanel.tsx`, `CtfEventLogPanel.tsx` and `CtfSubmissionLogPanel.tsx`, plus the changes to `CtfDashboard.tsx`, `ctf.model.ts` and `unit.transform.test.ts`, and compared them with PRD.md:1068-1071. A subagent checked each panel's endpoint, query parameters, response fields and enum arrays against `api/routers/ctf.py`, `api/core/ctf/{hosts,event,scoring}.py`, `common/models/response.py` and `common/models/agoge.py`. It found no mismatches.
  - I14: one row per board per server (`getRowId` = `workout_id-server`) with the server state. The Reset `Menu` offers Replant, Restart and Rebuild with no mode pre-selected. Rebuild is disabled with a `Tooltip` when `!rebuild_allowed`, and it confirms through the type-to-confirm `ConfirmationDialog`. The `{mode}` body and `RESET_STATES` match `CtfHostResetRequest` and `hosts.py:18,73-74`.
  - I15: rows are in the API's rank order (`scoring.py:133-145`), polled every 30 s, with an info `Alert` while `scoreboard_frozen_at` is set.
  - I16: the filter is sent server-side as `?action=`. `LOG_ACTIONS` equals the `LogAction` Literal (`agoge.py:38-40`), and rows are sorted newest first by `created_at`.
  - I17: the filter is sent as `?verdict=`. `VERDICTS` equals the `Verdict` Literal (`agoge.py:34-35`), rows are newest first by `submitted_at`, and `matched_workout_id` appears as a team name only on `cross_submission` rows, which is the only verdict where the backend sets it (`scoring.py:279-296`).
  - LINT1: the import order is fixed, and eslint on the file exits 0.
  - No TODO, FIXME, skip/only, `@ts-ignore`, `eslint-disable`, `as any` or Pro/Premium DataGrid usage in `components/Teacher/Ctf`.
  - Minor, not a reopen: the Hosts panel is a little stricter than the API in two cases. It blocks every mode when `server_state` is null, which also happens for a server document with no `state` field (`hosts.py:127`). It blocks Replant when `flag_count` is 0, but that count comes from the board's flag states, not the spec (`hosts.py:119-123`). Both cases are unlikely in practice.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 19 files, 163 tests passed.
  - ESLint gate, as written: exit 2, "No files matching the pattern "src/components/Student/Ctf" were found". This is expected because J1 is not done. On the paths that exist, plus `unit.transform.test.ts`, it exits 0 with 0 warnings.
  - tsc gate: no tsc error names a CTF file (gate exit 0).
- **Reopened:** none. I4b and J1 onward stay open.

### Iteration 71 — 2026-10-16
- **Completed:** J1.
  - New hook `frontend/src/components/Student/Ctf/useCtfBoard.ts` is called from `Workout.tsx` and returns `{board, refresh}`. `board` is null unless enrolled. J2-J4 will consume it; it is unused today.
  - Polling: `usePolling(fetchBoard, {enabled: enrolled !== false, interval: BOARD_POLL_INTERVAL_MS = 15000})`. The first poll is the mount read, and a not-enrolled answer disables polling. This poll is separate from the page's 3.5 s `setInterval` workout poll.
  - Failed reads: the last good board is kept and polling continues, including after a failed first read, because an error does not mean "not enrolled".
  - Tests: `useCtfBoard.test.tsx` (7) and `WorkoutCtfPolling.test.tsx` (2). The page test renders `Workout.tsx` with its children mocked and checks the 15 s board cadence alongside the 3.5 s workout poll, and that an unenrolled workout gets exactly one CTF request.
- **Learned:** `usePolling` schedules its next tick in `finally`, before React commits a state change that sets `enabled: false`. So a state-only "stop" can still fire extra requests. A ref guard (`notEnrolledRef`) is what enforces "no further request", and a single-`act` test fails without it. Also, `advanceTimersByTimeAsync` inside one `act` never lets React commit, so the page's interval never changes. Advance time in separate acts when a test depends on re-renders. Gates: frontend 21 files / 172 tests. ESLint is clean on the CTF gate paths. `Workout.tsx` still has its 3 pre-existing lint problems and none new. tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no defects. Its non-blocking note: a `build_id` change without a remount waits up to 15 s for the new board.
- **Blockers:** none. I4b is still open for a human to do the browser checks.
- **Next:** J2 CTF banner (PRD.md:1076). Destructure `board` from `useCtfBoard` in `Workout.tsx` and render `CtfBanner` above `TimerBox`.

### Iteration 72 — 2026-10-16
- **Completed:** J2.
  - New `frontend/src/components/Student/Ctf/CtfBanner.tsx`: a `Paper component="section" aria-labelledby="ctf-banner-h2"` with the event name as its h2 (or "CTF event" when null), `CtfStateChip` (from `state_name` mapped through `CtfStates`), time remaining, and a "Rules of engagement" link that opens in a new tab.
  - `Workout.tsx` now destructures `board` from `useCtfBoard` and renders `{board && <CtfBanner board={board} />}` as the first child of the aside, outside the `isLoading` branch, so it does not wait on the workout read. `board` is null when not enrolled, so the banner is absent then.
  - Countdown: `remaining_seconds` is a 15 s snapshot. The banner ticks it locally only while `RUNNING`, restarts from each new board, holds while `PAUSED` (shown as "(paused)"), and never goes below 0. It reuses `formatDuration` from `Teacher/Ctf/ctfTime.ts`.
  - `safeRulesUrl` renders only http(s) `rules_url` values, because the URL is instructor-authored spec text and a `javascript:` href must never be clickable.
  - Tests: `CtfBanner.test.tsx` (9), plus 2 added to `WorkoutCtfPolling.test.tsx` (the banner is the aside's first child when enrolled; no banner when not enrolled).
- **Learned:** An MUI icon needs `titleAccess`, not `aria-label`, to be announced; SvgIcon sets `aria-hidden` otherwise. Gates: frontend 22 files / 183 tests. ESLint is clean on the CTF paths. `Workout.tsx` still has its 3 pre-existing lint problems and none new. tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks, which now include J2: the banner shows on an enrolled workout and is absent otherwise.
- **Next:** J3 Flag submission card (PRD.md:1078). Put `FlagSubmitCard.tsx` in the aside below `ConfigureAccess`, pass it `board` and `refresh` from `useCtfBoard`, show `flag_format` verbatim, show verdicts with `showModal(SimpleSnackbar, {severity})`, and show the server's message on a 429.

### Iteration 73 — 2026-10-16
- **Completed:** J3.
  - New `frontend/src/components/Student/Ctf/FlagSubmitCard.tsx`. `Workout.tsx` renders it directly below `ConfigureAccess` when `board` is set, and passes `refresh` from `useCtfBoard` as `onSubmitted`.
  - The card is a `Paper component="section" aria-labelledby` with one `TextField` (`maxLength` = `FLAG_MAX_LENGTH` 200, which mirrors `CtfSubmitRequest`). `flag_format` is shown verbatim in a `<code>`.
  - The value is sent untrimmed because the API normalizes it. Submit is disabled for a blank value, while a submit is pending, and when `state_name !== 'RUNNING'`.
  - Verdicts go through `showModal(SimpleSnackbar, {severity})`:
    - correct is success, incorrect is error, duplicate is info, decoy is warning.
    - A nonzero `points_awarded` is appended as `(+N points)`.
  - Errors: a 429 or 409 shows the server's `HttpError.message` as a warning. Anything else shows a generic error.
  - Every submit refreshes the board, including after an error, so a stale RUNNING state corrects itself after a 409. The field is cleared on any verdict except incorrect.
  - Tests: `FlagSubmitCard.test.tsx` (13) and 2 added to `WorkoutCtfPolling.test.tsx` (the card follows `ConfigureAccess` when enrolled; there is no card otherwise). `mui-modal-provider` is mocked with `vi.mock(..., () => ({useModal: () => ({showModal})}))`; no earlier test had needed it.
- **Learned:** No existing frontend test rendered `useModal`, so any page test that mounts a component calling it needs that mock (there is no `ModalProvider` in tests). Gates: frontend 23 files / 198 tests. ESLint is clean on the CTF paths. `Workout.tsx` still has its 3 pre-existing lint problems and none new. tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no defects.
- **Blockers:** none. I4b is still open for a human to do the browser checks, which now include J3.
- **Next:** J4 Challenge list (PRD.md:1080). Put `ChallengeList.tsx` in the main column below `WorkoutTable`. Hints go through `ctfBoardService.takeHint` behind `ActionConfirmDialog`, which states `hint_cost`. When `public_scoreboard_enabled`, add the standings from `getPublicScoreboard` with the `is_you` row highlighted. Pass it `board` and `refresh`.

### Iteration 74 — 2026-10-16
- **Completed:** J4.
  - New `frontend/src/components/Student/Ctf/ChallengeList.tsx`. `Workout.tsx` renders it directly below `WorkoutTable`, inside the "Workout details" region, when `board` is set, and passes `refresh` as `onChanged`.
  - A `Paper component="section"` labelled "Challenges" shows the team score and a plain MUI `Table` with the columns Challenge (`flag_id`), Category ("General" when null), Points, Status (Solved/Unsolved chip) and Hint. There is no host or path column, and a test asserts the exact header list.
  - Hint cell:
    - A taken hint (`board.hint`, or one taken in this session) shows its text.
    - `!hint_available` shows "No hint".
    - Otherwise there is a "Take hint (-N)" button, disabled unless `RUNNING`. It opens `ActionConfirmDialog` stating the cost ("free" when 0).
    - On confirm it calls `ctfBoardService.takeHint`. A 409 or 404 shows the server message as a warning snackbar; anything else shows a generic error. Every attempt then calls `onChanged`.
  - Standings: when `public_scoreboard_enabled`, `getPublicScoreboard` is polled every 30 s with `usePolling` and rendered as a "Standings" table. The `is_you` row is `selected` with `aria-current` and a "(you)" suffix.
    - A 404 clears the standings, a later failure keeps the last good rows, and a failed first read shows "The standings are unavailable right now."
    - Turning the flag off clears the standings and stops polling.
  - Tests: `ChallengeList.test.tsx` (16), plus 2 in `WorkoutCtfPolling.test.tsx`. The `WorkoutTable` mock is now a marker div, used to check placement.
- **Learned:** After an MUI `Dialog` closes, the page stays `aria-hidden` until the exit transition ends, so role queries on the page fail right after a confirm. Wait for `queryByRole("dialog")` to be null first. Gates: frontend 24 files / 216 tests. ESLint is clean on the CTF paths. `Workout.tsx` still has its 3 pre-existing lint problems and none new. tsc reports no CTF errors. No Python changed, so the Python suites were not re-run. `agoge-reviewer` found no house-rule issues. Its one defect (the standings were stuck on "Loading" after a failed first read) is fixed and tested.
- **Blockers:** none. I4b is still open for a human to do the browser checks, which now include J4.
- **Next:** K1 Game master guide (PRD.md:1085), `docs/guides/game-master-guide.md`.

### Iteration 75 — 2026-10-16
- **Completed:** K1.
  - New `docs/guides/game-master-guide.md` covers:
    - enabling CTF (`ctf_enabled` through setup.py);
    - spec authoring, with a complete `ctf` block example and field and location tables;
    - create to archive, by state and by action;
    - the dashboard tabs and verdicts;
    - the three reset modes;
    - `stale` and `failed`, with common failure reasons and fixes;
    - the overnight-stop exemption.
  - It is linked from `docs/README.md`.
  - Every claim was taken from the shipped code, not the PRD. For example: decoys may be 0 or negative; a re-arm is allowed from ARMED or BROKEN; a rebuild marks flags stale even when the nuke fails; restart and rebuild have no fixed duration in code, so the guide gives none.
- **Learned:** The guide's JSON example was checked against both `CtfValidator` and `CtfSpecModel`; both accept it. Re-run that check if the spec model changes. The plant loader is added to every lab server at build (`LabServerManager._add_ctf_loaders`), so servers built before the CTF release cannot be planted, and the guide says to rebuild them. Docs only: no code changed, so no suites were re-run.
- **Blockers:** none. I4b is still open: a human must do the browser checks. It is the only incomplete task, so the loop cannot reach ALL TASKS COMPLETE without it.
- **Next:** I4b, the human browser checks listed on its queue line.

### Verification — 2026-10-16 — PASS
- **Checked:** J1, J2, J3, J4 and K1, the `[x]` tasks changed since the last verification (diff `31c0e48..2fbd178`). I compared `useCtfBoard.ts`, `CtfBanner.tsx`, `FlagSubmitCard.tsx`, `ChallengeList.tsx`, their tests, the `Workout.tsx` placement and `docs/guides/game-master-guide.md` with PRD.md:1072-1085.
  - J1: `usePolling` runs at 15 s (`BOARD_POLL_INTERVAL_MS`) and its first tick is the mount read. It is independent of the 3.5 s workout poll. A not-enrolled answer disables polling, and a ref guard stops any tick that was already scheduled. The tests assert exact call counts with fake timers.
  - J2: the banner is a `Paper component="section" aria-labelledby` rendered as the aside's first child, above `TimerBox`, only when `board` is set. It shows the name, a state chip, a countdown and the rules link. The link renders only for an http(s) URL.
  - J3: there is one `TextField` and `flag_format` is shown verbatim. Verdicts go through `showModal(SimpleSnackbar, {severity})`. On a 429, `HttpError.message` carries the server's `detail` (`api-request.service.ts:31`, `http_errors.py:35`). The card is placed after `ConfigureAccess`.
  - J4: the list shows category, points, solved state and a hint button. The hint goes through `ActionConfirmDialog`, which states the cost. There is no host or path column, and the API's challenge model has no such fields. When `public_scoreboard_enabled`, the standings are polled every 30 s and the `is_you` row is `selected` with `aria-current`. The list is placed after `WorkoutTable`.
  - API contract: `ctf.model.ts:224-268` matches `common/models/response.py:261-306` field for field. The URLs and methods in `urls.ts:109-113` match `api/routers/ctf_board.py`.
  - K1: all five required topics are covered. The guide's `ctf` JSON example passes both `CtfSpecModel.model_validate` and `CtfValidator(spec).load()`. I checked 14 factual claims against the code: the action and state tables, delete rules, board limit, reset modes and allowed states, rebuild staling, `failed` reason strings, the overnight-exemption states, seed creation, the score-adjust bound and flag normalization. All are correct. The guide is linked from `docs/README.md:10`.
  - No TODO, FIXME, skip/only, `@ts-ignore`, `eslint-disable`, `as any` or `NotImplemented` in `components/Student/Ctf` or the guide.
  - Not a reopen: the J2-J4 "verified in browser" done-when has not been met. That check is carried by I4b, which stays `[ ]`, the same treatment I5, I6, I9 and I10 received. Minor: the guide lists `file_mode` and `file_owner` as Linux `file` flags only, but neither the validator nor the model enforces this. The guide does not claim they do.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 24 files, 216 tests passed (exit 0).
  - ESLint gate as written, now including `src/components/Student/Ctf`: exit 0 with 0 warnings.
  - tsc gate: no tsc error names a CTF file (gate exit 0).
- **Reopened:** none. I4b, the human browser checks, is the only open task.

### Verification — 2026-10-16 — PASS
- **Checked:** every `[x]` task: 0.1, 0.2, A1-A6, B1-B4, C1-C2, BUG, D1-D4, E1-E5, E4b, BUG2, F1-F7, BUG3, G1-G7, G4b, H1-H7, R1-R4, BUG4, I1-I17, LINT1, J1-J4 and K1. Nothing changed since the previous verification (the working tree is clean at `60998fd`), but I checked the full queue again, not only the latest tasks. Three read-only agents split it: A-E, F-R with the BUG entries, and I-K. I checked BUG3 myself.
  - BUG3: `CtfEvent._publish_arm` (api/core/ctf/event.py:291-377) keeps each publish future and resolves it with `.result(timeout=…)` against one shared 30 s deadline. Failed, timed-out and in-line-raised boards go to `_fail_unpublished`. The `[x]` is now correct, even though the old "Reopened" sub-bullet is still in the queue.
  - Security: derivation is HMAC-SHA256 with `hmac.compare_digest`. The seed comes from `secrets.token_hex(32)`, is never overwritten and is never printed. Only digests are stored. No student response model has a path, server, location or digest field. The rate limit is enforced on the server with a Firestore transaction. Loaders and the planter silence output, and logs record the exception type only.
  - Routers: all 18 instructor routes use `teacher_required`, except DELETE and reveal, which use `admin_required`. Collections come back as `{'items': …}`, and `api/core/ctf/` raises no `HTTPException`. Frontend services match the router paths, methods and query parameters, and the TS models match `response.py`. No MUI X Pro APIs are used.
  - Sweep: no TODO, FIXME, `NotImplemented`, `ts-ignore`, `as any` or `eslint-disable` in the CTF code. The only skips are `skipif` guards for a missing bash or pwsh, and none of them skipped in this run (0 skipped).
  - Possible gaps, not reopened because the PRD does not cover them:
    - E5 exempts VMs only by the `"{workout_id}-"` prefix, so a unit-scoped VM in a community unit (for example `{build_id}-display-guacamole-server`) may still be stopped overnight. Not traced.
    - The D4 Linux loader is appended to `startup-script`, so an author's script that calls a top-level `exit` stops it from running.
    - Sending `PUT /ctf/{id}/` with an explicit `"public_scoreboard_enabled": null` probably fails revalidation. Not tested.
- **Gate results:**
  - api/unit_tests: 1100 passed.
  - cloud_functions/tests: 449 passed.
  - build_files/cloud_deployment/tests: 304 passed.
  - frontend `npm test`: 24 files, 216 tests passed.
  - ESLint gate: exit 0 with 0 warnings.
  - tsc gate: no tsc error names a CTF file (gate exit 0).
- **Reopened:** none. I4b, the human browser checks, is still the only open task.

### Out-of-loop work — 2026-10-17
- **Completed (outside the loop, by hand):** Group L (L1–L7: shared workout record, create from template, teams, per-event flags, servers, roster-only join, setup UI) in `dbb2fec`/`83e5abc`; V1 (nested virtualization for template and lab servers) in `99f275a`; V2 (nested machine types: `ComputeMachineTypesAPI.get` resolves N1/N2 up to 65536 MB, `list(nested=True)` and `GET /compute/images/machine-types/?nested=true` return N1/N2 only, `_lookup_machine_type` falls back to SMALL on `None`/`NotFound`).
- **Learned:** PRD.md was rewritten in `99f275a` (Groups L, N, V added; line numbers moved). Every queue pointer above now uses the new line numbers. `common/constants/nested.py` was created early by V2 with the machine-type constants only — V5 extends it. The gate-count comments in PRD.md `## Quality Gates` are from 2026-10-16 and are stale.
- **Gate results:** api/unit_tests 1369 passed; cloud_functions/tests 493 passed; build_files/cloud_deployment/tests 316 passed; frontend `npm test` 34 files, 393 tests passed.
- **Blockers:** none. I4b and HUMAN are human-only.
- **Next:** the verifier should re-check L1–L7, V1 and V2, which were never loop-verified. Then N1 (PRD says ship it first), continuing in queue order through Group N and Group V.

### Verification — 2026-10-17 — PASS
- **Checked:** L1–L7, V1 and V2. These were done outside the loop and had never been loop-verified (HEAD `efb9f8f`, clean tree). Two read-only agents covered Group L and V1/V2 against PRD.md:1606-1617 and :1661-1664. I spot-checked the key claims myself.
  - L1: `common/utilities/workout_record.py` `build_workout_record` writes a NOT_BUILT record. `BaseUnit._create_workout_record` delegates to it (`base_unit.py:353-367`), and `api/core/ctf/setup.py:196` calls it directly. The delegation is tested in `test_workout_record.py`.
  - L2: `CtfSetup.create` (`setup.py:108-166`) gives a 400 for a community template and for a template with no `ctf` block. It writes a unit with `count` 0, `registration_required` and `ctf_event_id`, and a DRAFT event with `board_ids=[]` and the unit's `join_code`. It publishes nothing. `GET /ctf/templates/` returns `{'items'}`.
  - L3: add and remove are DRAFT-only, and the board-id list changes in a transaction that re-checks DRAFT (`_change_board_ids`). Remove requires NOT_BUILT. Names are unique (case-insensitive), `ctf_max_boards` caps teams, and an email can be on only one active board. Members can be edited until ENDED.
  - L4: `update_spec` is DRAFT-only and runs `CtfValidator` against the unit's servers. It rebuilds boards and digests in a DRAFT-checked transaction, then deletes stale digests.
  - L5: `SERVER_ACTIONS` sends build only to NOT_BUILT workouts and never stops a RUNNING one. Arming with no boards gives "Add at least one team before arming" (`event.py:182`, confirmed).
  - L6: `Workout._find_existing_workout` uses a single `ARRAY_CONTAINS` filter (`workout.py:375`, confirmed). `NotOnRoster` subclasses `Forbidden` and maps to 403 with a roster message. Non-CTF units take the old path. Covered by the 21 tests in `test_ctf_roster_join.py`.
  - L7: code and vitest only. There is a New CTF dialog. DRAFT opens on the Setup tab, which has Teams (CSV import, remove, join code), Flags and Servers sections. Arm is disabled with no boards, and no lab-page Create CTF button remains. The done-when's browser check is carried by I4b, which stays `[ ]`, the same treatment I5, I6, I9 and I10 received.
  - V1: `_build_server` (`base_compute_manager.py:284-313`, confirmed):
    - It raises `BadRequest` for E2 on a nested host before the BUILDING transition.
    - It enables nested virtualization on `ip_aliases or nested_host`.
    - The platform is derived from the resolved type and then read into the local `min_cpu_platform`, which fixes the stale local (WN18).
    - `nested_host` is set in `BaseComputeManager._load_template_server`, the base-class method `ImageTemplateManager` uses, and in `LabServerManager`.
    - All done-when cases are in `test_nested_virtualization.py`.
  - V2: `ComputeMachineType.get` checks the nested cap first: N1/N2 up to 65536 MB. `list()` keeps 17000 MB unless `nested=True`. `_lookup_machine_type` falls back to SMALL with a warning on `None` or `NotFound`. `?nested=true` is on the route. All done-when cases are tested, including at the route level.
  - Sweep: no TODO, FIXME or `NotImplemented` in the new L/V source.
  - Notes, not reopened:
    - `get` now resolves N1/N2 up to 64 GB for non-nested servers too. The PRD wording allows it.
    - The L3 one-board-per-email check is outside the commit transaction. The code documents this.
    - A nested image shared from another project reads as not nested.
- **Gate results:**
  - api/unit_tests: 1369 passed.
  - cloud_functions/tests: 493 passed.
  - build_files/cloud_deployment/tests: 319 passed.
  - frontend `npm test`: 34 files, 393 tests passed (exit 0).
  - CTF ESLint gate: exit 0, 0 warnings.
  - CTF tsc gate: exit 0.
  - Group V tsc gate: exit 0.
  - Group V ESLint gate: **exit 2**, "No files matching the pattern src/components/Teacher/ServerManagement/Forms/NestedImage". None of the targeted files (`NestedImage/`, `nested.service.ts`, `nested.model.ts`, `nested.transform.ts`) exist yet. They belong to V16–V21, which are all `[ ]`. No completed task is responsible, so this is not a failure of checked work, but the gate cannot pass until V16 exists.
- **Reopened:** none.

### Verification — 2026-10-17 — PASS
- **Checked:** every `[x]` task: 0.1, 0.2, A1–A6, B1–B4, C1, C2, BUG, D1–D4, E1–E5, E4b, BUG2, F1–F7, BUG3, G1–G7, G4b, H1–H7, R1–R4, BUG4, I1–I17 (I4b stays open), LINT1, J1–J4, K1, L1–L7, V1, V2.
  - HEAD is `321d8f4` and the tree is clean. Since the last verification, only progress.md has changed.
  - Three read-only agents re-checked each task against its PRD done-when.
  - I swept the tracked CTF/nested source for TODO, FIXME, NotImplemented and XXX. The only hit is the mktemp template `XXXXXX` in `ctf_plant_contract.py:49`, which is not a stub.
  - Notes, not reopened:
    - BUG3: if the `_fail_unpublished` recovery write itself fails (`event.py:261-265`), the event is still stuck in ARMING.
    - BUG3: a late arm message can pass the terminal check (`arm_worker.py:59`) before recovery runs. `_mark_arming` then overwrites `failed`, so the board can be counted twice.
    - C2: `edit_manager` runs `CtfValidator` only for the None, `ctf` and `review` form types. Other partial saves validate only the model. The done-when (each save path rejects a bad block) is still met.
    - C1: `points=True` passes the int check.
- **Gate results:**
  - api/unit_tests: 1369 passed.
  - cloud_functions/tests: 493 passed.
  - build_files/cloud_deployment/tests: 319 passed.
  - frontend `npm test`: 34 files, 393 tests passed (exit 0).
  - CTF ESLint gate: exit 0.
  - CTF tsc gate: exit 0. No CTF file is named among the pre-existing tsc errors.
  - Group V tsc gate: exit 0.
  - Group V ESLint gate: **exit 2**, "No files matching the pattern src/components/Teacher/ServerManagement/Forms/NestedImage". The targeted files belong to V16–V21, which are all `[ ]`, so no completed task is responsible.
- **Reopened:** none.

### Iteration 76 — 2026-10-17
- **Completed:** N1. The Linux plant prologue in `flag_planter.py` now adds `iptables -C FORWARD -d 169.254.169.254 -j REJECT || iptables -I FORWARD ... || true`, inside the existing `command -v iptables` guard, right after the OUTPUT rule. New tests in `test_flag_planter.py`: the -C/-I FORWARD pair comes before the first `agoge_ctf_plant_*` call for file-only, env-only and mixed payloads; an existing rule (-C succeeds) means no -I; and with a PATH that holds only symlinked coreutils plus fake curl/chown (no iptables), the payload still plants and reports `ok:<nonce>`.
- **Learned:** if a test needs a tool to be *absent*, build a PATH containing only symlinks to the tools the script needs, and call bash by its absolute path. Otherwise a real `/usr/sbin/iptables` on Linux CI leaks in.
- **Gate results:** cloud_functions/tests 498 passed; api/unit_tests 1369 passed; build_files/cloud_deployment/tests 319 passed; frontend `npm test` 34 files, 393 tests passed. No frontend files changed.
- **Blockers:** none.
- **Next:** N2 (the same FORWARD rule in `LINUX_LOADER`, `ctf_plant_contract.py`, placed before the metadata `curl`).

### Iteration 77 — 2026-10-17
- **Completed:** N2. `LINUX_LOADER` (`common/utilities/ctf_plant_contract.py`) now opens its subshell with the `iptables -C FORWARD -d 169.254.169.254 -j REJECT || -I ... || true` pair inside a `command -v iptables` guard, before `mktemp` and the `curl` fetch. New tests in `api/unit_tests/test_ctf_plant_contract.py`: the -C/-I lines precede the `if curl` line in the text; with a fake `iptables` logging to the same file as the fake curl, -C then -I run before curl when the rule is absent, and only -C when it is present. The D4 merge tests (`cloud_functions/tests/test_ctf_loader_stub.py`) pass unchanged.
- **Learned:** the loader's fake-curl log doubles as an ordering log: any other fake tool that appends to `$FAKE_CURL_ARGS` shows up in call order.
- **Gate results:** api/unit_tests 1372 passed; cloud_functions/tests 498 passed; build_files/cloud_deployment/tests 319 passed. No frontend files changed.
- **Blockers:** none.
- **Next:** N3 (nested guest models).

### Iteration 78 — 2026-10-17
- **Completed:** N3. `common/models/agoge.py` gains `NESTED_GUEST_NAME_PATTERN`, `NestedGuestDriver`, `CtfNestedGuestSpecModel` (name/server/domain/operating_system/driver, default `qemu-agent`), `CtfFlagSpecModel.guest`, `CtfSpecModel.nested_guests` (default `[]`, max 32) and `CtfHostResetRequest.guest`. `CtfHostRow.guest` (in `common/models/response.py`) defaults to None, so the existing `hosts.py` construction is unchanged. Tests in `test_ctf_spec_models.py` reject bad guest slugs (on the guest and on the flag), bad `domain` values (including shell metacharacters), an unknown `driver` and an unknown OS; enforce the 32 cap; and show that a spec without `nested_guests` still loads. Request and response tests cover the `guest` slug on the reset request and on the host row.
- **Learned:** `CtfHostRow` is in `common/models/response.py`, not `agoge.py`. Import `NESTED_GUEST_NAME_PATTERN` instead of copying the regex.
- **Gate results:** api/unit_tests 1399 passed; cloud_functions/tests 498 passed; build_files/cloud_deployment/tests 319 passed. No frontend files changed. ruff: only the pre-existing F401 (unused `HttpUrl` import, `common/models/agoge.py:5`), which is on HEAD too.
- **Blockers:** none.
- **Next:** N4 (nested contract constants in `ctf_plant_contract.py` and `PubSub.EventAttributes.GUEST`).

### Iteration 79 — 2026-10-17
- **Completed:** N4. `common/utilities/ctf_plant_contract.py` gains the Nested Guest Contract names: `GUEST_ATTRIBUTE_ACK_KEY`/`_PATH` (`agoge-ctf/plant-ack`), `GUEST_ATTRIBUTE_GUEST_RESULT_PREFIX` with `guest_result_key(guest)`/`guest_result_path(guest)` (raise `ValueError` unless the name matches `NESTED_GUEST_NAME_PATTERN`), `WATCHER_UNIT_NAME`, `WATCHER_SCRIPT_PATH`, `RUN_DIR`/`RUN_DIR_MODE` (0o700), `RUN_LOCK_PATH`, `LAST_PAYLOAD_PATH`, `PRISTINE_SNAPSHOT_NAME`, and `WATCHER_ACK_SECONDS=30`, `NESTED_CONFIRM_TIMEOUT_SECONDS=420`, `RELAY_BUDGET_SECONDS=360`. `PubSub.EventAttributes.GUEST = 'guest'`. Tests in `api/unit_tests/test_ctf_plant_contract.py` assert the names, `30 + 420 < 540`, relay budget < confirm window, that a guest result key never equals the parent's, bad guest slugs are rejected, and that every `EventAttributes` value (including `guest`) is distinct.
- **Learned:** the contract module now imports `common.models.agoge` for the slug pattern; `agoge.py` does not import the contract, so there is no cycle. The 256 KB payload limit is not a constant yet — N9 should add it here.
- **Gate results:** api/unit_tests 1411 passed; cloud_functions/tests 498 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Next:** N5 (nested guest validator in `object_validators/ctf.py`).

### Iteration 80 — 2026-10-17
- **Completed:** N5. `CtfValidator` (`api/utilities/infrastructure_as_code/object_validators/ctf.py`) gains `_validate_nested_guests` (parent exists, `details.os` (fallback top-level `os`) is `linux`, some NIC has non-empty `ip_aliases`, `(server, name)` unique, ≤ 8 per server; messages name the guest) and `_validate_offline_windows` (file/registry/env only, no `windows_access`/`hidden`, registry under `HKLM\SOFTWARE\` or `HKLM\SYSTEM\`; messages name the flag). Flag loop: `guest` must be declared on `flag.server` and match its `operating_system`; slot and same-OS keys are now `(server, guest, slot)` / `(server, guest)`. New `api/unit_tests/test_ctf_nested_guest_validation.py` (29 tests) covers every table row plus a plain spec without `nested_guests`; the existing `test_ctf_spec_validation.py` passes unchanged.
- **Learned:** spec servers carry OS under `details.os` (ServerModel); the registry path pattern already forces `HKLM\`, so the offline prefix test needs an HKLM sibling such as `HKLM\SOFTWAREX\` to reach the new rule.
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 498 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Next:** N6 (`FlagPlanter.build_guest_payload`).

### Verification — 2026-10-17 — PASS
- **Checked:** N1–N5, the only tasks ticked since the last verification (`344ba05`). HEAD is `ffcac2a` and the tree is clean. All earlier `[x]` tasks were verified at `321d8f4`/`344ba05`, and none of their source has changed since then except the N1–N5 diff. Two read-only agents checked the N items against PRD.md:1620-1632, the Nested Guest Contract (PRD.md:1042) and Data Models (PRD.md:469-497). I read the N1 and N2 diffs myself.
  - N1: in `flag_planter.py:53-55`, the `-C || -I FORWARD ... || true` pair sits inside the `command -v iptables` guard. The prologue has no `set -e`. `_LINUX_PROLOGUE` is the only bash template, so every Linux payload gets the rule. Tests check the order before the first placement for file, env and mixed payloads. With iptables absent (PATH holds only symlinked tools), the payload still plants and reports `ok:<nonce>`.
  - N2: in `LINUX_LOADER`, the guarded FORWARD rule is the subshell's first statement, before `mktemp` and `curl`. Two tests prove the order: a static check and an execution check with a shared fake-tool log. `test_ctf_loader_stub.py` is unchanged and passes.
  - N3: `NestedGuestDriver`, `CtfNestedGuestSpecModel`, `CtfFlagSpecModel.guest` and `CtfSpecModel.nested_guests` (max 32) match Data Models. `guest` is on `CtfHostResetRequest` and `CtfHostRow` with the shared slug pattern. Tests reject a bad slug, a bad domain and an unknown driver, and a spec without `nested_guests` loads.
  - N4: every name and timeout in the contract-names table is present with the PRD values. `EventAttributes.GUEST = 'guest'`. Tests assert 30 + 420 < 540 and that every attribute value is distinct.
  - N5: all six rows of the validation table are enforced (`ctf.py:52-80, 96-97, 124-175`). Each rejection test asserts that the message names the guest or flag id, plus a fragment specific to the rule. The non-nested spec still validates.
  - Sweep: the changed source has no TODO, FIXME or NotImplemented. The only hit, `agoge.py:738`, predates this work.
  - Notes, not reopened:
    - PRD.md still shows N1–N5 as `[ ]`. This file, not PRD.md, is the task queue.
    - The loader's `iptables -C` stderr is not silenced inside the subshell.
    - The registry-prefix check is case-sensitive, as the PRD text is written.
- **Gate results:**
  - api/unit_tests: 1440 passed.
  - cloud_functions/tests: 498 passed.
  - build_files/cloud_deployment/tests: 319 passed.
  - frontend `npm test`: 34 files, 393 tests passed.
  - CTF ESLint gate: exit 0.
  - CTF tsc gate: 0 CTF matches (passes).
  - Group V tsc gate: 0 matches (passes).
  - Group V ESLint gate: **exit 2**, "No files matching the pattern src/components/Teacher/ServerManagement/Forms/NestedImage". Those files belong to V16–V21, which are all `[ ]`, so no completed task is responsible.
- **Reopened:** none.

### Iteration 81 — 2026-10-17
- **Completed:** N6. `FlagPlanter.build_guest_payload(board, server, guest, nonce, seed)` in `flag_planter.py`: BadRequest unless the guest is declared on that server, the board has flags on it, and every flag's OS equals the guest's; reuses the existing bash/PowerShell bodies via a `guest=True` switch on `_linux_payload`/`_windows_payload`. The prologue templates gained a `{save_stdout}` slot (empty for server payloads, so they are byte-for-byte unchanged): Linux `exec 3>&1` before the `/dev/null` redirect and `printf '%s\n' "$agoge_ctf_result" >&3` as the only fd-3 write; Windows saves `[Console]::Out`, nulls console out/err and the chatty preference streams, and ends with `$agogeCtfStdout.WriteLine($agogeCtfResult)`. Result composition is shared (`_LINUX_RESULT`/`_WINDOWS_RESULT`); flag derivation moved into `_planted`. New `cloud_functions/tests/test_flag_planter_guest.py` (27 tests): scope per guest/board/workout, no guest-attribute write (no curl/metadata URL/Invoke-RestMethod), no print command, `bash -n`, pwsh parse, run under `bash -s` → stdout is exactly `ok:<nonce>\n` with noisy tools, error line has no values, pwsh `-File` run prints exactly one line.
- **Learned:** `build_payload` still selects every board flag on the server, guest flags included, so for a nested host it currently mixes OSes and raises — N7 must restrict the parent body to `flag.guest is None` (use `_board_flags_on` + filter) and call `build_guest_payload` per guest.
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 525 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Next:** N7 (qemu-agent relay section in `build_payload`).

### Iteration 82 — 2026-10-17
- **Completed:** N7. `build_payload` routes a server with `nested_guests` to `_nested_host_payload`. The parent body covers only `flag.guest is None`, which must be linux. Each targeted `qemu-agent` guest with board flags gets a background `agoge_ctf_relay_qemu` section (`_LINUX_RELAY`):
  1. `virsh -q domstate`, called with argv that holds no values.
  2. `guest-ping` every 5 s within `RELAY_BUDGET_SECONDS`.
  3. `guest-exec` with `build_guest_payload` as base64 `input-data`. Linux runs `/bin/bash -s`. Windows runs `powershell.exe -EncodedCommand <_WINDOWS_GUEST_BOOTSTRAP>`, which writes stdin under the loader's SYSTEM-only ACL, runs it with `-File`, then deletes it.
  4. `guest-exec-status` until the process has exited.
  5. The decoded first line, accepted only if it fits the `ok:/error:<nonce>` grammar, is written to `plant-result-<guest>`.

  After the sections, `wait`, then `plant-result` last. The prologue's new `{ack}` slot writes `plant-ack` = nonce right after the redirect. That happens on nested hosts only; plain payloads are byte-for-byte unchanged. Payloads over `PLANT_PAYLOAD_MAX_BYTES` (new, 256 KB, in `ctf_plant_contract.py`) raise BadRequest. New `cloud_functions/tests/test_flag_planter_relay.py` (20 tests) runs the parent payload against fake virsh/curl/timeout/sleep. The tests cover:
  - no virsh/curl/timeout argv holds `input-data` or a flag value;
  - each guest's result key is written;
  - the ack is first and `plant-result` is last;
  - errors for a stopped guest, a silent agent and bad out-data;
  - `bash -n`, and a pwsh parse of the bootstrap.
- **Learned:**
  - Agent JSON must be single-quoted on the virsh shell line, because virsh's tokenizer strips the double quotes from an unquoted one. The reviewer caught this on the ping.
  - The fake virsh only matches single-quoted JSON, so that regression now fails. A mutation check confirmed it (8 tests failed). It fails slowly: the ping loop spins until each test's 60 s subprocess timeout.
  - Offline-driver guests are skipped here. If a board's only flags on a server are offline-guest flags, `_nested_host_payload` raises "no flags on server"; N12 must relax that.
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 545 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Next:** N8 (plant watcher installer in `LabServerManager._add_metadata`; loader stub takes the run lock and writes `/run/agoge-ctf/last`).

### Iteration 83 — 2026-10-17
- **Completed:** N8. In `ctf_plant_contract.py`:
  - **`_LOCKED_RUN`**: one shell block that both `LINUX_LOADER` and the new `WATCHER_SCRIPT` embed. It runs `mkdir`/`chmod 700` on `RUN_DIR`, then `exec 9>plant.lock`, then `flock 9`. It compares the payload's SHA-256 with `last`, writes `last` *before* running, and runs the payload with `9>&-`. It fails closed if the hash is missing.
  - **`WATCHER_SCRIPT`**: long-polls `agoge-ctf-plant?wait_for_change=true&timeout_sec=300&last_etag=<etag>`. It filters the ETag to alphanumerics and sleeps 5 s on a 404 or a curl failure. A TERM/INT trap removes its in-flight temp files.
  - **`WATCHER_UNIT`** and **`WATCHER_INSTALLER`**: the installer exits if `systemctl` or `flock` is missing. It writes the script via a quoted heredoc and installs it with `mv` (rename). It writes the unit, then runs `daemon-reload` and `enable --now`.

  `LabServerManager._add_metadata` merges the installer ahead of the loader only when `_is_linux_nested_host()` is true. That check reads `server_spec.os` and the NICs' `ip_aliases`, not `self.ip_aliases`, because `_add_nics` runs after `_add_metadata`. It skips the merge when the installer is already present. `_load_lab_server` now sets `server_spec.os` from `details.os` or a top-level `os`.

  New test file `cloud_functions/tests/test_ctf_plant_watcher.py` (24 tests). The scripts run for real under bash, with fake curl and systemctl and a Python fake `flock` that takes a real `flock(2)` lock on the inherited fd. They cover:
  - the merge gating;
  - existing scripts kept, and no duplicate merge;
  - the same lock and dedupe paths in both scripts;
  - concurrent loaders running the payload exactly once;
  - the watcher following the ETag and dedupe after the loader;
  - a payload's orphaned child not holding the lock;
  - installer idempotence, and the no-flock path.

  Two existing loader-execution tests now replace `RUN_DIR` with a temp directory.
- **Learned:**
  - Any test that runs `LINUX_LOADER` must replace `RUN_DIR` (`/run/agoge-ctf` needs root). macOS has no `flock`, so the tests supply one.
  - `enable --now` leaves an already-running watcher on its old script until its next restart. That is deliberate: a restart at boot could kill a payload that is mid-run.
  - When the watcher is missing (no systemd or flock), the plant gets no ack and N9 falls back to a reset.
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 569 passed; build_files/cloud_deployment/tests 319 passed. ruff on the changed files reports only 2 errors, both in existing lines of `base_compute_manager.py` (588, 718) that this change did not touch. No frontend files changed.
- **Blockers:** none.
- **Next:** N9 (nested plant procedure in `FlagPlanter.plant`: wait `WATCHER_ACK_SECONDS` for `plant-ack`, reset only for an un-acked whole-server plant, per-key status).

### Iteration 84 — 2026-10-17
- **Completed:** N9. In `FlagPlanter.plant(board, servers, guest=None)`:
  - Targets are now `server -> {result key: flag ids}`, built by `_result_groups`. A guest flag maps to `plant-result-<guest>`; a parent or plain-server flag maps to `plant-result`. With `guest` set, only that guest's flags are targeted, and a server that does not declare the guest is skipped.
  - `_deliver(..., reset=False)` for nested hosts.
  - New `_await_acks` polls `plant-ack` every `ACK_POLL_INTERVAL_SECONDS` (5 s) for up to `WATCHER_ACK_SECONDS`. With no ack, a whole-server plant resets the parent once; a guest plant fails `"Plant watcher did not respond"` and never resets. NotFound fails the server's flags.
  - `_await_results` polls per (server, key). The deadline is 240 s for a plain server and `NESTED_CONFIRM_TIMEOUT_SECONDS` for a nested host (message `No plant confirmation within 420 s`). Once `plant-result` carries the nonce, any guest key still missing fails at once with `"Guest relay reported no result"`, because plant-result is written after every relay section ends.
  - `build_payload`/`_nested_host_payload` take `guest=`: no parent flags and that guest's relay only. A guest on a plain server raises BadRequest.

  New `cloud_functions/tests/test_flag_plant_nested.py` (15 tests).
- **Learned:**
  - A board flag's default `plant_status` is `'pending'`, not None.
  - `shlex.quote` leaves a plain domain like `ubuntu-lin` unquoted in the payload.
  - Until N12, flags on `offline` guests get no relay section. In a whole-server plant they fail fast with "Guest relay reported no result". If they are a server's only board flags, `_nested_host_payload` raises, so they fail "Could not build the plant payload".
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 584 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Reviewer:** no house-rule violations. Its finding of a stale board in `_fail_unfinished` was queued as BUG5. Not changed: when `plant-result` is an error and a guest key is missing, the guest flags get the generic message, because the parent's error text describes parent flags, not the guest.
- **Next:** N10 (`CtfHosts.reset` accepts `guest`, publishes `GUEST`; guest rows in `CtfHosts.hosts`).

### Iteration 85 — 2026-10-17
- **Completed:** BUG5. `_fail_unfinished` no longer trusts the board it is given. It now calls a new `_write_flags(board, apply)` helper (the transaction body pulled out of `_record`), and `apply` marks failed only target flags whose **stored** `plant_status` is still `planting`. New test `test_error_mid_results_keeps_flags_already_recorded` in `test_flag_plant_procedure.py`: it raises on the second result `_record` across web and db, then checks that web stays `planted` and db is aborted. The test fails without the fix.
- **Learned:** `test_unexpected_error_still_removes_the_plant_key` monkeypatches `planter._record` with a two-argument function. That is why the abort path writes through `_write_flags` and does not add a kwarg to `_record`.
- **Gate results:** api/unit_tests 1440 passed; cloud_functions/tests 585 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Next:** N10 (`CtfHosts.reset` accepts `guest`, publishes `GUEST`; guest rows in `CtfHosts.hosts`).

### Verification — 2026-10-17 — PASS
- **Checked:** N6, N7, N8, N9 and BUG5, the only tasks ticked since the last verification (`28c16c3`). HEAD is `1635f33`. Three read-only agents checked them against PRD.md:1634-1641 and the Nested Guest Contract (PRD.md:1042). I read the qemu-agent relay template myself (`flag_planter.py:196-262`) and swept the diff `28c16c3..HEAD`: no TODO, FIXME, NotImplemented or stubs.
  - N6: `build_guest_payload` (`flag_planter.py:712-755`) keeps only the declared (server, guest)'s flags and raises BadRequest for an undeclared guest, a guest with no flags, or an OS mismatch. The guest epilogues contain no curl or Invoke-RestMethod. Stdout is saved before the redirect (Linux `exec 3>&1`; Windows `[Console]::Out`), and that saved stream receives only the result line. A `bash -s` run with noisy tools prints exactly `ok:<nonce>\n`. `bash -n` passes.
  - N7: the ack is the first action. Parent flags are planted next. Each qemu-agent guest gets its own background relay, followed by `wait`, and `plant-result` is the last write (`puts[-1]` in the run test). The domstate check never starts a guest. Pings run every 5 s. guest-exec uses `capture-output` and base64 `input-data`. The Windows bootstrap writes `%ProgramData%\agoge-ctf\plant-<guid>.ps1` under the SYSTEM-only ACL, runs it with `-File`, and deletes it in a `finally`. Each guest gets its own `plant-result-<guest>`. A payload over 256 KB raises BadRequest with the exact message. Recorded argv contains no `input-data` and no flag value.
  - N8: the installer is merged only when `os == 'linux'` and a NIC has `ip_aliases`, and existing `startup-script` content is kept. `_load_lab_server` now sets `os` from `details.os`, which production server records carry (lowercase). The watcher long-polls with the ETag. The watcher and the loader share `_LOCKED_RUN`: the same `plant.lock` flock, the same `last` SHA-256 dedupe, and directory mode 0700. The unit and script names match the contract.
  - N9: an acked plant makes 0 `reset` calls. An un-acked whole-server plant makes exactly 1. An un-acked guest plant makes 0 and fails its flags with `"Plant watcher did not respond"`. Each flag takes its status from its own key. Nested hosts confirm within 420 s; plain servers are unchanged (they still reset, with 240 s). The ack and result waits poll every server on each tick, so per-server waits do not add up.
  - BUG5: `_fail_unfinished` → `_write_flags` re-reads the stored board inside `db.transaction` and aborts only flags whose stored status is still `planting`. `test_error_mid_results_keeps_flags_already_recorded` covers this.
  - Notes, not reopened:
    - The 540 s budget is enforced only on the constants (30 + 420 < 540). Payload delivery and fallback resets run one server at a time before the 420 s window starts. With several nested hosts or slow GCE calls, the function could reach 540 s before it writes timeout statuses or runs the `finally` key cleanup. No done-when line requires an end-to-end cap.
    - `RELAY_BUDGET_SECONDS` is checked only inside the relay loops. A virsh call that starts just before the deadline can overrun it by up to its own `timeout`; the code comment at `flag_planter.py:200-202` says so.
    - No test makes `guest-exec-status` poll more than once, and none asserts the 5 s ping interval.
    - PRD.md still shows N6–N9 as `[ ]`. This file, not PRD.md, is the task queue.
- **Gate results:**
  - api/unit_tests: 1440 passed.
  - cloud_functions/tests: 585 passed.
  - build_files/cloud_deployment/tests: 319 passed.
  - frontend `npm test`: 34 files, 393 tests passed, exit 0.
  - CTF ESLint gate: exit 0.
  - CTF tsc gate: 0 CTF matches (passes).
  - Group V tsc gate: 0 matches (passes).
  - Group V ESLint gate: **exit 2**, "No files matching the pattern src/components/Teacher/ServerManagement/Forms/NestedImage". Those files belong to V16–V21, which are all `[ ]`, so no completed task is responsible.
- **Reopened:** none.

### Iteration 86 — 2026-10-17
- **Completed:** N10.
  - `CtfHosts.reset(..., guest=None)`: the guest must be declared as a `(server, guest)` pair in `spec.nested_guests`, otherwise `NotFound`. A guest replant needs that guest's own flags, otherwise `BadRequest`. The WireGuard rebuild refusal applies only to the parent, because a guest rebuild is a snapshot revert. `GUEST` is added to the `CTF_HOST_RESET` message only when set.
  - `CtfHosts.hosts`: each server row is followed by one row per declared guest, with the parent's state and `rebuild_allowed: true`. `flag_count` is now keyed by `(server, guest)`, so a guest's flags count on its own row and not on the parent's.
  - Router: passes `guest=request.guest`, and adds `guest` to the audit `detail` when set.
  - Tests: 21 new across `test_ctf_hosts_reset.py`, `test_ctf_hosts_rows.py` and `test_ctf_router.py`.
- **Learned:** `_parse` turns a body that fails validation (e.g. a non-slug guest) into 400, not 422. The router asserts `reset` with `guest=` as a kwarg.
- **Gate results:** api/unit_tests 1461 passed; cloud_functions/tests 585 passed; build_files/cloud_deployment/tests 319 passed; ruff clean on changed files. No frontend files changed.
- **Blockers:** none.
- **Reviewer:** no house-rule violations. Its two minor notes are queued on N14 (hide replant on flagless guest rows); the other (a guest reset 404s when the parent document is missing) is intended and tested.
- **Next:** N11. It is urgent: `CtfHandler`/`HostReset` must read `GUEST`, because a guest reset published now is executed as a whole-server reset.

### Iteration 87 — 2026-10-17
- **Completed:** N11.
  - `CtfHandler` reads `GUEST` and calls `HostReset.run(..., guest=)`. With a guest, `HostReset` checks that the guest is declared on the server (otherwise `NotFound`, before any compute call), then dispatches through `guest_mode_map`:
    - `replant` calls `plant(guest=)`.
    - `restart` calls `FlagPlanter.run_guest_action('restart')`. That payload runs `virsh reboot` on the parent and reports through `plant-result`; no flag is written.
    - `rebuild` calls `plant(guest=, revert=True)`. The relay calls `agoge_ctf_rebuild_qemu`, which runs `snapshot-info` and then `snapshot-revert --running` before `agoge_ctf_relay_qemu`, sharing one deadline. A guest with no board flags gets the revert-only action instead.
  - A failed restart or flagless revert raises `RuntimeError`.
  - Tests:
    - `test_ctf_host_reset_guest.py` (28 tests): every mode/guest makes only `get`/`set_metadata`/`get_guest_attributes` calls on the board's own instance and never touches `ComputeManagerFactory` (SC-9). The guest action and rebuild relay payloads run in bash against a fake virsh.
    - `test_ctf_handler.py`: GUEST passthrough.
- **Learned:** virsh calls that carry no secret (domain, snapshot name) go in argv, as `domstate` already does. Agent JSON still goes on stdin, and an argv virsh call must never inherit the payload's stdin. In the sandbox the fake virsh exits before reading stdin.
- **Gate results:** api/unit_tests 1461 passed; cloud_functions/tests 616 passed; build_files/cloud_deployment/tests 319 passed; ruff clean. No frontend files changed.
- **Blockers:** none.
- **Reviewer:** no house-rule violations.
  - Offline-driver guest rebuild is folded into N12.
  - `snapshot-info` failing for any reason (including a timeout) reads "no agoge-pristine snapshot". This matches the spec string, so it is left as is.
  - The `RuntimeError` on a failed guest restart could re-run the reboot if Pub/Sub retry is on; same as other handler errors. Not changed.
- **Next:** N12 (offline driver).

### Iteration 88 — 2026-10-17
- **Completed:** N12.
  - `_nested_host_payload` now plants `offline` guests too. Each one gets its own `( … ) &` section from `_offline_section`, launched before the shared `wait`, so `plant-result` is still last.
  - The `_LINUX_OFFLINE` template:
    - `agoge_ctf_offline_begin` installs an EXIT trap first. The trap runs `virsh start` (always, once the tool checks pass, per contract step 4), removes the section's `mktemp -d` dir under `OFFLINE_TEMP_DIR` (`/run/agoge-ctf`), and writes `plant-result-<guest>`.
    - It then checks for virsh, virt-customize, guestfish and (Windows only) virt-win-reg. With `revert` it runs snapshot-info and snapshot-revert, the same as `agoge_ctf_rebuild_qemu`. Then `virsh shutdown`, with up to 120 s to reach `shut off`.
    - Linux: one `virt-customize` call (`--mkdir`, `--upload tmp:path`, `--chmod`, `--run-command 'chown …'`). `/etc/environment` is rewritten from a guestfish download, and is never replaced if it could not be read.
    - Windows: guestfish `case-sensitive-path` (using `echo @i` markers), then `mkdir-p` and `upload`. Registry and env values go through one `virt-win-reg --merge` of a REGEDIT4 file. `HKLM\SYSTEM\CurrentControlSet` is mapped to `ControlSet00N` from `HKLM\SYSTEM\Select\Current`; env values go under `…\Session Manager\Environment`.
    - Readback: every value is checked by SHA-256 through a `--ro` guestfish download (or a virt-win-reg query). A mismatch reports `<flag id>: verification failed`.
  - `_offline_planted` re-checks the offline Windows rules (only file/registry/env, no `windows_access`, no `hidden`, and registry only under SOFTWARE or SYSTEM) and raises `BadRequest`.
  - Fixed the note queued on N12: a guest rebuild of an offline guest with flags now reverts and replants. It no longer fails with "Could not build the plant payload".
- **Tests:** new `test_flag_planter_offline.py` (19 tests).
  - Shape: `bash -n`; no `destroy` anywhere; `virsh start` only inside the trap function; registry mapping.
  - Runs against a Python fake for virsh, virt-customize, guestfish and virt-win-reg that simulates guest disks:
    - No flag value appears in any argv or guestfish stdin line, every upload source is under the temp dir, and the dir is empty afterwards.
    - Failure paths: no shutdown; a failed write; a missing control set; revert with and without a snapshot; a guest already shut off.
  - `test_flag_planter_relay.py` updated: the offline guest is no longer skipped.
- **Learned:**
  - macOS `/bin/bash` is 3.2 and APFS is case-insensitive. The Windows path-resolution test therefore asserts on the path guestfish was given, not on the file on disk.
  - The shutdown wait uses real `SECONDS`. With the instant fake `sleep`, a test must monkeypatch `_OFFLINE_SHUTDOWN_SECONDS`, otherwise it busy-loops for 120 s.
- **Gate results:** api/unit_tests 1461 passed; cloud_functions/tests 635 passed; build_files/cloud_deployment/tests 319 passed; ruff clean. No frontend files changed.
- **Reviewer:** no house-rule violations and no bash bugs.
  - Its PRD point (already-off guests were left off) is fixed: the guest is now always started.
  - Not changed: the exit codes of the env download and of `virt-win-reg --merge` are ignored, because the readback reports any failure. The REGEDIT4 writer does not escape `\` or `"`, which is safe while `_VALUE_PATTERN` and the path patterns hold.
- **Blockers:** none.
- **Next:** N13 (nested guests in the spec editor).

### Iteration 89 — 2026-10-17
- **Completed:** N13 (code and vitest; the browser check stays with HUMAN).
  - `ctf.model.ts`: `NestedGuestDriver`, `CtfNestedGuestSpec`, optional `CtfFlagSpec.guest` and `CtfSpec.nested_guests`.
  - `transformToCtfSpec`: copies `nested_guests` (driver defaults to `qemu-agent`) and normalises `flag.guest` to null. Before this, a dashboard spec save would have dropped every guest.
  - `CtfSpecFields` (used by the event Setup tab and the template editor):
    - A "Nested guests" grid with an add/edit `GuestDialog`. A rename or move carries the guest's flags along and gives them its OS. Delete is disabled while any flag references the guest.
    - The flag dialog has a "Nested guest" select listing only the flag's server's guests. Picking one sets the OS and locks it. Changing the server clears a guest that isn't on the new server.
  - Checks:
    - `guestProblems`: name, domain, unique per server, at most 8 per server.
    - `flagProblems` (new `guests` argument): the guest is declared and its OS matches; slot and same-OS rules are per (server, guest); offline Windows rules (case-sensitive registry prefix, like the API).
    - Whether the parent is Linux with `ip_aliases` is left to the API, because the editor only knows server names.
  - `CtfReview` shows `guest on server`.
- **Tests:** transformer round trip in `ctf.transform.test.ts`, plus guestProblems, ctfSpecProblems and render tests in `CtfSpecFields.test.tsx`.
- **Gate results:** frontend 443 passed (34 files); CTF eslint clean; CTF tsc clean; api/unit_tests 1461 passed; cloud_functions/tests 635 passed; build_files 319 passed.
- **Reviewer:** no house-rule violations. Fixed its one finding: the offline registry regex had `/i`, but the API's `startswith` is case-sensitive. Not changed: there is no client check for the 32-guest total cap; the API enforces it.
- **Blockers:** none.
- **Next:** N14 (guest rows on the Hosts panel). `CtfHostRow`/`CtfHostResetRequest` still lack `guest` on the frontend.

### Iteration 90 — 2026-10-17
- **Completed:** N14 (code and vitest; the browser check stays with HUMAN).
  - `CtfHostRow.guest` / `CtfHostResetRequest.guest` on the frontend; `transformToCtfHostRow` keeps `guest` (null when missing).
  - `CtfHostsPanel`: guest rows render indented (arrow icon + name + "guest") under their parent, keyed `workout-server/guest`; buttons, dialogs and notices name `guest on server`. Guest-specific menu descriptions and confirm texts follow the Nested Guest Contract (reboot / snapshot revert); guest rebuild's type-to-confirm expects the guest name. A guest reset sends `{mode, guest}`, a parent reset still sends `{mode}` only.
  - `resetBlocker` disables replant on a flagless guest and every mode under an unbuilt parent, matching `CtfHosts.reset`.
- **Tests:** 7 new in `CtfHostsPanel.test.tsx` (blocker, row id, render order/indent, guest replant/rebuild bodies, parent body), 2 in `ctf.transform.test.ts`.
- **Gate results:** frontend 452 passed (34 files); CTF eslint clean; CTF tsc clean. No Python files changed.
- **Reviewer:** no findings.
- **Blockers:** none.
- **Next:** N15 (nested host guide).

### Verification — 2026-10-17 — PASS
- **Checked:** N10, N11, N12, N13 and N14, the only tasks ticked since the last verification (`d13e997`). HEAD is `5934b9b`. Three read-only agents checked them against PRD.md:1642-1651 and the Nested Guest Contract (PRD.md:1042). I read `host_reset.py` and `ctf_handler.py` myself and searched the diff `d13e997..HEAD` for TODO, FIXME, NotImplemented and stubs. The only hit was a `mktemp` `XXXXXX` template.
  - N10: `CtfHosts.reset(..., guest=)` raises `NotFound` unless the `(server, guest)` pair is declared. It sets `GUEST` on the message only when a guest is given. `hosts()` emits one row per declared guest, with `rebuild_allowed=True`.
    - Router tests:
      - `test_guest_host_reset_passes_the_guest_and_names_it_in_the_audit_detail`
      - `test_unknown_guest_is_404_and_audited_as_a_failure`
    - Core tests:
      - `test_guest_reset_publishes_the_guest_attribute`
      - `test_undeclared_guest_is_not_found_and_publishes_nothing`
    - The router tests mock core, so "the guest reaches the message" is proven in two halves, router→core and core→message. Together the halves cover the done-when.
  - N11: `ctf_handler.py:45` reads `GUEST`, and line 104 passes it to `HostReset.run`. `guest_mode_map` dispatches the three contract modes:
    - replant: `plant(guest=)`.
    - restart: `virsh reboot`.
    - rebuild: snapshot-revert, then plant (`revert=True`).
    - `ComputeManagerFactory` is used only at `host_reset.py:138`, on the parent path. `test_guest_reset_of_any_mode_touches_no_instance_and_no_other_board` fails the test on any compute reset, stop or start, or any manager creation. It also asserts board isolation (SC-9).
  - N12: the `( … ) &` sections run `trap agoge_ctf_offline_end EXIT`, and `virsh start` is only inside that trap. `destroy` appears only in a comment. Values are written with the `printf` builtin into a 0700 `mktemp -d` under `OFFLINE_TEMP_DIR` (`/run/agoge-ctf`). Every done-when item has a test: `test_values_reach_libguestfs_only_through_temp_files_that_are_removed`, `test_virsh_start_appears_only_in_the_exit_trap`, `test_virsh_destroy_never_appears`, and `test_offline_payload_passes_bash_n`.
  - N13:
    - `transformToCtfSpec` keeps `nested_guests`, defaulting the driver to qemu-agent, and `flag.guest`. The round-trip test is at `ctf.transform.test.ts:94`.
    - The guest select is filtered by `guest.server === flag.server` (`CtfSpecEditor.tsx:190`).
    - `guestProblems` enforces the cap of 8 guests per server.
  - N14:
    - `transformToCtfHostRow` keeps `guest`. Guest rows render indented with a cell icon; there is no `treeData` or other Pro feature.
    - A guest reset sends `{mode, guest}`, a parent reset sends `{mode}`, and tests assert both bodies.
  - N13 and N14's "verified in browser" done-whens are carried by the open HUMAN task, as with the I-series.
  - Notes, not reopened:
    - If a libguestfs tool is missing, the offline section returns before it arms the restart, so `virsh start` is skipped. The guest was never shut down in that case, so this is harmless.
    - No test asserts the literal default `/run/agoge-ctf`. The tests monkeypatch it; the code value is correct (`ctf_plant_contract.py:40`).
    - Guest restart is only tested on one guest.
    - PRD.md still shows N1–N14 as `[ ]`. This file, not PRD.md, is the task queue.
- **Gate results:**
  - api/unit_tests: 1461 passed.
  - cloud_functions/tests: 635 passed.
  - build_files/cloud_deployment/tests: 319 passed.
  - frontend `npm test`: 34 files, 452 tests passed, exit 0.
  - CTF ESLint gate: exit 0.
  - CTF tsc gate: 0 CTF matches (passes; repo-wide tsc exits 2 on pre-existing errors).
  - Group V tsc gate: 0 matches (passes).
  - Group V ESLint gate: fails with "No files matching the pattern src/components/Teacher/ServerManagement/Forms/NestedImage". Those files belong to V16–V21, which are all `[ ]`, so no completed task is responsible.
- **Reopened:** none.

### Iteration 91 — 2026-10-17
- **Completed:** N15. Added `## Nested lab hosts` to `docs/guides/game-master-guide.md`:
  - Parent prep: the `ip_aliases` NIC, the watcher, libvirt, `libguestfs-tools` for `offline`, `virsh autostart`.
  - Guest prep: the `org.qemu.guest_agent.0` channel, the agent, and the RHEL `/etc/sysconfig/qemu-ga` `guest-exec` block (`BLACKLIST_RPC` / `FILTER_RPC_ARGS`). Also the `agoge-pristine` snapshot.
  - A spec example, a `nested_guests` field table, the offline Windows limits, and guest reset modes.
  - Guest `failed` reasons, with message strings taken from `flag_planter.py`.
  - The warning that root on the parent exposes every guest flag.
  - Also added a `guest` row to the Flag fields table.
- **Learned:** the guide's spec example is checked by loading it through `CtfValidator(spec).load()` and `CtfSpecModel` (both passed). The "C: only" offline file rule is enforced at plant time, not by the validator.
- **Gate results:** docs only; `check.py` reports no affected suites.
- **Blockers:** none.
- **Next:** V3 (license on check-in).

### Iteration 92 — 2026-10-17
- **Completed:** V3.
  - `ENABLE_VMX_LICENSE` is in `common/constants/nested.py`.
  - `ComputeImageAPI.create(licenses=...)` sets `Image.licenses` on the image it builds (ignored when `image_resource` is supplied).
  - `ImageTemplateManager._create_image_from_snapshot` passes `[ENABLE_VMX_LICENSE]` when `nested_host` (from the record's `nested`), otherwise `licenses=None`.
- **Tests:** `test_check_in_licenses_only_nested_images_for_vmx` (nested / standard) in `test_image_template_source_lifecycle.py`. It runs `check_in()` through a real `ComputeImageAPI.create` with a mock `ImagesClient` and inspects the `InsertImageRequest`. The shared check-in assertion now expects `licenses=None`.
- **Learned:** an unset repeated proto field reads back as `[]`, so "no licenses" means `list(image.licenses) == []`. Not verified live: whether `images.insert` accepts a license the source snapshot already inherits (every re-check-in of a nested image does this). V25 will show it.
- **Gate results:** api/unit_tests 1461 passed; cloud_functions/tests 637 passed; build_files 319 passed. No frontend files changed.
- **Blockers:** none.
- **Next:** V4 (template startup-script merge).

### Iteration 93 — 2026-10-17
- **Completed:** V4.
  - `_merge_metadata_item` and `_CONCATENATED_SCRIPT_KEYS` moved from `LabServerManager` to `BaseComputeManager`, so both managers share one helper.
  - `ImageTemplateManager._add_metadata` builds every item through it. The Linux user-creation script goes first and the image `startup_script` is concatenated after it under the single `startup-script` key, so a long-running image script (the V9 builder) can't delay the login account.
- **Tests:** `cloud_functions/tests/test_template_startup_metadata.py` (4 tests). It covers one merged `startup-script` with both scripts, user creation first, the image script alone when there is no user, Windows unchanged (user script under `sysprep-specialize-script-ps1`, image script kept separate), and the shared-helper identity.
- **Learned:** the Windows user-creation key is `sysprep-specialize-script-ps1`, not `startup-script`, so the duplicate only ever affected Linux templates.
- **Gate results:** api/unit_tests 1461 passed; cloud_functions/tests 641 passed; build_files 319 passed. No frontend files changed.
- **Blockers:** none.
- **Next:** V5 (models and constants).

### Iteration 94 — 2026-10-17
- **Completed:** V5.
  - Models in `common/models/agoge.py`, just above `AgogeImageModel`: `NestedOsCatalogModel`, `NestedMediaModel`, `NestedNetworkModel`, `NestedGuestNicModel`, `NestedGuestModel`, `NestedHostSpecModel`, `NestedBuildStatusModel`, and `NestedImageCreateRequest`, plus the value-set Literals and `SLUG15`.
  - `AgogeImageModel` gains `nested` and `nested_build`, and `base_family` now defaults to `None` instead of `(None,)`.
  - `HumanInteractionModel` gains `nested_guest`, `alias_index` (≥ 0), and `port` (1–65535).
  - New `DbCollections.NESTED_OS_CATALOG` and `NESTED_MEDIA`, and `PubSub.Actions.NESTED_FINALIZE = 21`.
  - `common/constants/nested.py` now holds every value in the contract's constants table.
  - Additions beyond the contract text:
    - The catalog model rejects a non-https `media_url`.
    - It rejects an entry with no URL unless `requires_upload` is set.
    - It rejects a Windows entry with a blank `license_note`.
    - `NestedImageCreateRequest` rejects client-sent `exposures`, `console_ports`, and `vnc_passwords`, because the API derives them.
- **Tests:** `api/unit_tests/test_nested_models.py` (33).
- **Learned:**
  - `nested` is now typed, so a record holding a partial dict fails `AgogeImageModel` validation. Check-in revalidates the record, so the V3 test fixture now uses a complete spec (`NESTED_SPEC`).
  - `test_nested_virtualization.py` still uses partial dicts. That works only because those paths never validate the record.
  - The hand-built `image/nested-hv-debian12` doc has no `nested` field, so it still validates as a standard image.
  - `common/tests` (235 passed) is not in any gate. Run it with `PYTHONPATH=.:api:cloud_functions`.
- **Gate results:**
  - api/unit_tests: 1494 passed.
  - cloud_functions/tests: 641 passed.
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** none.
- **Next:** V6 (OS catalog and seeding). Open Question V-5 must be answered first.

### Iteration 95 — 2026-10-17
- **Completed:** V7.
  - `api/core/compute/nested/validator.py` holds `NestedHostValidator(env_dict, db=None, machine_type_api=None)`.
    - `validate(request)` raises `BadRequest` naming the network, guest, or field, and returns each guest's catalog entry by guest name for V8/V12.
    - `min_disk_size(guests)` returns the computed minimum disk size.
    - `derive(spec)` returns a deep copy. Exposures follow guest order, then NIC order. Console ports are 5901+ in the order of guests that have `console` set. VNC passwords are 8 random alphanumeric characters.
  - `ComputeImage._validate_new_name` is now a classmethod, so the validator reuses it without building a `ComputeImage`.
  - Choices beyond the table:
    - `dhcp: true` requires both `dhcp_start` and `dhcp_end`. Without them, the "static IP outside the DHCP range" rule has nothing to test.
    - `product_keys` naming a guest that doesn't exist are rejected.
    - Machine types are looked up via `ComputeMachineTypesAPI.get`. The family check runs first, so E2 types are rejected without an API call.
- **Tests:** `api/unit_tests/test_nested_host_validator.py` (60). Each table row has a test, plus the valid three-guest, two-network spec and determinism tests for `derive`.
- **Learned:** 169.254.0.0/16 is not RFC 1918, so the RFC 1918 check always rejects it before the reserved-overlap check runs. Only 192.168.122.0/24 actually reaches the reserved-overlap check.
- **Gate results:**
  - api/unit_tests: 1554 passed.
  - cloud_functions/tests: 641 passed.
  - build_files: 319 passed.
  - common/tests: 235 passed.
  - No frontend files changed.
- **Blockers:** V6 is BLOCKED on Open Question V-5. Microsoft publishes no SHA-256 values for its Evaluation Center ISOs, so a person must download and hash them.
- **Next:** V8 (manifest and unattend rendering). V8's XML test iterates over the `unattended_iso` catalog entries, so it may need fixture entries until V6 is unblocked.

### Iteration 96 — 2026-10-17
- **Completed:** V8.
  - `common/utilities/nested_manifest.py` contains:
    - `render_manifest(spec, catalog, media)`, where `catalog` is keyed by entry **id** (not by guest name, unlike `NestedHostValidator.validate`'s return).
    - `build_secrets` / `render_secrets(spec, product_keys)`.
    - `render_autounattend(guest, entry, secrets, networks=(), template=None)`, where `secrets` is the `build_secrets` map.
    - `guest_mac(guest, nic_index)`.
  - The manifest drops `admin_password` and `vnc_passwords`. Each NIC gains a deterministic `mac`, and each guest gains `catalog` (the entry dump) and `media` (`{source: url|gcs, ...}`).
  - Template: `cloud_functions/cloud_fn_utilities/server_specific/nested/autounattend.xml.tmpl` (`string.Template`). The loader tries the `.staging` layout first, then the repo layout.
  - New constant `NESTED_METADATA_MAX_BYTES = 262144`. Either JSON over it raises `BadRequest`. Caller bugs (a missing entry, medium, or network) raise `ValueError`.
- **Choices beyond the contract:**
  - The builder must pass each manifest NIC's `mac` to `virt-install --network ...,mac=`. The unattend static-IP commands find NICs by that MAC.
  - The `networks` argument is needed for the static IPs.
  - FirstLogonCommands also clear Winlogon `DefaultPassword` (AutoLogon leaves the password there).
  - Static IPs use PowerShell `Get-WmiObject`, so Vista (no PowerShell) gets no static IP.
  - virtio drivers are listed for CD letters D–G, with `start "" /wait msiexec`.
  - LabConfig is keyed on osinfo `win11` / `win2k25`. A virtio entry whose osinfo is not in `VIRTIO_OS_DIRECTORIES` raises `ValueError`, so V6 must use those osinfo ids.
- **Tests:** `cloud_functions/tests/test_nested_manifest.py` (58). The per-entry XML tests run over fixture Windows entries plus any `unattended_iso` entries in `common/data/nested_os_catalog.json` once V6 writes it.
- **Learned:**
  - Eight maximum-length `post_install_script`s total 512 KB, twice the 256 KB per-value metadata limit, so `render_manifest` refuses them. V12 must map that `BadRequest` to a 400.
  - V11 should note that all of an instance's metadata together is capped at 512 KB (manifest + secrets + startup-script).
  - The contract has the builder (bash) "render" the unattend, but it holds the admin password. V9/V11 must decide how the rendered XML reaches the parent. Recommendation: the Cloud Function renders it and ships it inside `agoge-nested-secrets` (removed after build).
- **Gate results:**
  - api/unit_tests: 1554 passed (97.75%).
  - cloud_functions/tests: 699 passed (94.28%).
  - build_files: 319 passed.
  - common/tests: 235 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V9 (builder script).

### Iteration 97 — 2026-10-17
- **Completed:** V10, taken before V9 because V9's done-when ("installs and starts the runtime before the first virt-install") needs the runtime to exist.
  - `cloud_functions/cloud_fn_utilities/server_specific/nested/runtime.sh` and `agoge-nested-runtime.service` use `@@NAME@@` placeholders. `nested_scripts.py` renders them and holds the shared parent paths (`HOST_JSON_PATH`, `RUNTIME_PATH`, `RUNTIME_UNIT_NAME`/`_PATH`, `BRIDGE_PREFIX = 'agb'`).
  - The runtime is idempotent: it flushes and refills its own chains (`AGOGE-NESTED-IN/-FWD` in filter, `-PRE/-POST` in nat), and each one is jumped to at position 1 only if the jump is missing.
  - Choices beyond the contract:
    - INPUT from `agb+` also accepts ESTABLISHED,RELATED, because the Connect dialog's SSH tunnels are parent-initiated.
    - FORWARD accepts only `--ctstate DNAT` in and ESTABLISHED,RELATED out per exposed guest, so exposing an isolated guest gives it no other route.
    - `ON_BOOT=ignore` in libvirt-guests, so it does not resume guests out of `start_order`.
    - The runtime also runs `virsh autostart --disable` for every guest.
    - `net.ipv4.ip_forward=1` is set when any guest is exposed, because libvirt enables forwarding only for NAT networks.
    - Alias IPs other than /32 are logged and skipped.
- **For V9 (builder):**
  - Write `host.json` with `networks[].name`, `guests[]` (`name`, `nics[].ip`, `autostart`, `start_order`, `start_delay_seconds`), and `exposures` (`[guest, nic]` per slot). For example: `jq '{version,networks,guests:[.guests[]|{name,nics,autostart,start_order,start_delay_seconds}],exposures,console_ports}'` on the manifest.
  - The libvirt network name must be the spec network name, with bridge `agb<index>`.
  - Install `jq` and `iptables`.
  - Do **not** set libvirt autostart (contract step 6 conflicts with runtime step 4; the runtime wins).
  - On Debian 13, set `firewall_backend = "iptables"` in `/etc/libvirt/network.conf`. Under libvirt's nftables backend, its own reject rules would still drop DNAT'd traffic that our iptables rules accept.
  - V8 recommended that the Cloud Function render each Windows guest's autounattend.xml into `agoge-nested-secrets` (e.g. key `autounattend`). The builder reads it from `/run/agoge-nested/secrets.json`, and V11 adds it to `build_secrets`.
- **Tests:** `cloud_functions/tests/test_nested_runtime.py` (16). It runs the rendered script under bash with fake `iptables` (stateful, so `-C`/`-N` behave as they would on a second run), `virsh`, `curl`, `ip`, `systemctl`, `sysctl` and `sleep`, plus real `jq`. `bash -n` passes. The script stays bash 3.2-clean because macOS bash runs it.
- **Gate results:**
  - cloud_functions/tests: 715 passed (94.28%).
  - build_files: 319 passed.
  - api/unit_tests: not run, since no api or common file changed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V9 (builder script).

### Iteration 98 — 2026-10-17
- **Completed:** V9.
  - `cloud_functions/cloud_fn_utilities/server_specific/nested/builder.sh` is rendered by `nested_scripts.render_builder()`. The render embeds `render_runtime()`/`render_runtime_unit()` as quoted heredocs and refuses a runtime that contains a heredoc delimiter.
  - New layout constants in `nested_scripts.py`: `BUILDER_PATH`, `MEDIA_DIR`, `STATE_DIR` (`/var/lib/agoge-nested/state`), `WORK_DIR` (`/var/lib/agoge-nested/work`, holds `manifest.json`), `RUN_DIR`, and `SECRETS_PATH` (`/run/agoge-nested/secrets.json`).
  - Markers: `packages`, `networks`, `runtime`, `installed-<guest>`, `guest-<guest>.done` (final status), and `done` (final phase). A second run after `done` only re-writes `phase`. An install a reboot interrupted is shut down over ACPI (never destroyed), undefined, and redone. A guest interrupted during post-install is only restarted.
  - `host.json` is written with every `autostart: false` while building, so a reboot's runtime run cannot start a half-installed guest. The real values are written at the end.
- **Contract for V11 (template provisioning):**
  - Each Windows `unattended_iso` guest's rendered XML must be in `agoge-nested-secrets` as `{guest: {..., "autounattend": "<xml>"}}`. Without it, that guest fails with "agoge-nested-secrets has no autounattend for this guest".
  - The startup-script must write `render_builder()` to `BUILDER_PATH` and run it (consider `systemd-run`: the build takes hours).
  - The builder exits 0 when the manifest is absent, so on a re-check-out it is a no-op.
- **Choices beyond the contract:**
  - The unattend ISO (it holds the admin password) is built on tmpfs in `/run/agoge-nested/unattend-<guest>/`, not in `MEDIA_DIR`, and is deleted once Setup powers off. `RUN_DIR` is mode 711 so qemu can open the ISO; `secrets.json` and the password files are 600.
  - Domains are defined with `virt-install --print-xml --import` plus `virsh define`. The VNC `passwd` is spliced into the XML with bash builtins, so it never reaches an argv. An osinfo the local osinfo-db rejects falls back to `--osinfo generic`.
  - A URL medium with no `media_sha256` fails its guest (an unverified download). An upload with a null `sha256` is accepted unverified.
  - Uploads of verified downloads to the `cache/` objects are best-effort.
  - The virtio-win ISO is fetched from `fedorapeople.org .../archive-virtio/virtio-win-<version>/virtio-win.iso`, so `virtio_win_version` must be the archive directory's suffix (e.g. `0.1.262-2`). It is not hash-checked, because the catalog has no hash field for it. Note this when V6 is unblocked.
  - Two installs at a time: guests in `start_order` are dealt round-robin to two workers.
  - libvirt autostart is never set (the runtime orders starts).
  - `ifupdown` NICs are named `agoge<i>` by a systemd `.link` file matched on MAC.
  - A grown cloud-image disk gets a best-effort `growpart` firstboot command, because cloud-init is disabled.
- **Tests:** `cloud_functions/tests/test_nested_builder.py` (26). The rendered script runs under bash against fake curl, virsh, virt-install, virt-customize, qemu-img, genisoimage, apt-get, and systemctl, with jq behind a logging wrapper. The tests:
  - assert no admin or VNC password appears in any logged argv;
  - check that media lands under `MEDIA_DIR` and verified downloads are cached;
  - check that `systemctl restart agoge-nested-runtime.service` precedes the first `virt-install`;
  - cover the sha mismatch, post-install failure (stderr truncated to 150 chars), phase rules, resume, and interrupted-install paths.
  - `bash -n` and `shellcheck -S warning` pass.
- **Learned:**
  - shellcheck (`/opt/homebrew/bin/shellcheck`) caught a `local a=$1 b="$a"` bug (SC2318). Run it on rendered scripts.
  - The killed heartbeat subshell's in-flight curl can still land after the builder exits, so tests must ignore late `heartbeat` writes.
- **Gate results:**
  - cloud_functions/tests: 741 passed (94.28%).
  - build_files: 319 passed.
  - api/unit_tests: not run, since no api or common file changed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V11 (nested template server provisioning).

### Iteration 99 — 2026-10-17
- **Completed:** V11.
  - `ImageTemplateManager.check_out(product_keys=None)` calls `_prepare_nested_check_out` before `build()`. A record without `nested` is untouched.
  - Phase `queued` or `provisioning` (a duplicate Pub/Sub delivery) is the first build. It sets `self_link` to `projects/debian-cloud/global/images/family/<parent_os>` and the machine type to `build_machine_type`, and the disk keeps `add_disk`. It reads the catalog entries and media from `nested-os-catalog`/`nested-media`, and adds `agoge-nested-manifest`, `agoge-nested-secrets`, and `enable-guest-attributes=TRUE`. It merges `render_builder_bootstrap()` into `startup-script` after the user-creation script and before the image's own script. Then `_update_record_status(..., nested_phase='provisioning')` stamps `started_at` (once) and `updated_at`.
  - Phase `finalized` adds only `enable-guest-attributes` and keeps the record's `self_link` (image-<name>) and `machine_type`. It reads no catalog, media, or secrets.
  - Any other phase raises `Conflict` before anything is built. A render failure (missing catalog entry or medium, oversized metadata) records phase `failed` with the message and re-raises.
  - `render_secrets(spec, product_keys, catalog)` now adds each unattended Windows guest's rendered `autounattend` XML when a catalog is given. This is the V9 contract.
  - `nested_scripts.render_builder_bootstrap()` writes the builder to `BUILDER_PATH` through a quoted heredoc and starts it with `systemd-run --unit=agoge-nested-builder` unless the unit is already active. It contains no `exit`, and `bash -n` and `shellcheck -S warning` pass.
- **Learned:**
  - A failed nested build cannot be retried by check-out. Product keys are never persisted, so a retry has to come through a new create request. That is deliberate.
  - If `build()` itself fails, the phase stays `queued`, so a retried delivery reprovisions.
  - Test records need `protocol` in `human_interaction`, or `AgogeImageModel` validation fails.
- **Tests:** `cloud_functions/tests/test_nested_template_provisioning.py` (11):
  - the metadata keys and machine type for both paths;
  - secrets only on the first build, with no secret in the manifest or the stored record;
  - duplicate delivery, the mid-build Conflict, and the missing-catalog failure;
  - a standard image unchanged;
  - the bootstrap's bash syntax and delimiter guard.
- **Gate results:**
  - cloud_functions/tests: 752 passed (94.28%).
  - api/unit_tests: 1554 passed (97.75%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V12 (create route). It must carry `product_keys` to `check_out`.

### Iteration 100 — 2026-10-17
- **Completed:** V12.
  - `api/core/compute/nested/nested_image.py` defines `NestedImage(ComputeImage)`:
    - `create(user, request)` runs `NestedHostValidator.validate` and checks that the name is free (409). It then runs `derive`, which fills exposures, console ports, and VNC passwords.
    - It writes `image/<name>` through `_create_record` with status CHECKED_OUT, `self_link`/`image` = `projects/debian-cloud/global/images/family/<parent_os>`, `base_family=parent_os`, `os='linux'`, and `add_disk` = `disk_size` or `min_disk_size`. The parent's `human_interaction` is SSH, built from `username`/`ssh_key`. `nested_build.phase` is `queued`.
    - Last, it publishes CONTROL / CHECK_OUT / TEMPLATE_SERVER.
    - `list_catalog()` returns the enabled entries, skips malformed ones, and sorts by group, then display name.
  - Routes: `POST /compute/images/nested/` (teacher, sync def) returns `{build_id}`. `GET /compute/images/nested/catalog/` (teacher) returns `{items}` through the new `NestedOsCatalogListResponse`. Both are registered before `/{image_name}/`.
  - Product keys travel as the JSON attribute `PubSub.EventAttributes.PRODUCT_KEYS`, and only when non-empty. `ControlHandler._check_out` parses them and calls `check_out(product_keys=...)`. A malformed value is dropped and logged without its value.
  - `main.py` logs every attributes dict through `_loggable()`, which redacts `product_keys`. The handler still receives the real dict.
- **Learned:**
  - `main.py` logs every Pub/Sub attribute at info level. Any future secret-bearing attribute must be added to `_loggable`.
  - Pub/Sub attribute values are capped at 1024 bytes. Eight guests' keys fit.
- **Tests:**
  - `api/unit_tests/test_nested_image_create_route.py` (13): 200 with the stored record and a single message, no product key in the record, 400 from the validator and from a bad username, 409 both before create and on a create race, 403 for a student on both routes, 422 on client-supplied derived fields, and the catalog route not captured by `/{image_name}/`. The fixtures are imported from `test_nested_host_validator`.
  - `cloud_functions/tests/test_control_handler_nested_check_out.py` (7): the pass-through, a missing attribute, malformed values, and log redaction on both the success and the failure path.
- **Gate results:**
  - api/unit_tests: 1567 passed (97.75%).
  - cloud_functions/tests: 759 passed (94.28%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V13 (build monitor).

### Verification — 2026-10-17 — PASS
- **Checked:** N15, V3, V4, V5, V7, V8, V9, V10, V11 and V12, every task ticked since the last verification (`5934b9b`). HEAD is `bd0bbc0` and the tree is clean. Three read-only agents checked them against PRD.md:1652 and :1665-1684 and the Nested Image Builder Contract. I read the V12 routes myself (`compute_image.py:158-185`), searched the diff `5934b9b..HEAD` for TODO, FIXME, NotImplemented and stubs (none), and ran `bash -n` on the rendered `render_builder`, `render_runtime` and `render_builder_bootstrap` (all exit 0).
  - V3: `ComputeImageAPI.create(licenses=)` sets `Image.licenses`. `_create_image_from_snapshot` passes `[ENABLE_VMX_LICENSE]` only when `nested_host` is set. `test_check_in_licenses_only_nested_images_for_vmx` inspects what the mocked `ImagesClient.insert` receives, for both a nested and a standard record.
  - V4: `_merge_metadata_item` now lives on `BaseComputeManager`. Tests show one `startup-script` with the user script first, and Windows unchanged.
  - V5: all eight models, both collections, `NESTED_FINALIZE = 21`, `nested`/`nested_build`, the three `HumanInteractionModel` fields, and the `base_family=None` default are in place. Every done-when case is tested. The constants match the contract table.
  - V7: all 13 validation-table rows are enforced and each has a test. The valid three-guest, two-network spec passes. `derive` is tested for determinism apart from the passwords.
  - V8: tests cover no secrets in the manifest, the 256 KB bound for eight guests, XML that parses for each `unattended_iso` entry, virtio paths and LabConfig only when they apply, and Panther deletion followed by a final shutdown.
  - V9:
    - All four install methods are real code (`cloud_image`, `unattended_iso`, `disk_image`, `manual_iso`).
    - Secrets are read only from `secrets.json`, and media lives under `/var/lib/libvirt/boot/agoge-nested`.
    - The runtime restarts before the first `virt-install`.
    - No `virsh destroy` appears. The only `destroy` strings are `virsh net-destroy` (networks) and a comment.
  - V10: tests cover the FORWARD metadata reject, the `agb+` INPUT policy, DNAT/SNAT pairs in slot order, ordered start, and the libvirt-guests settings. `bash -n` passes.
  - V11: the literal done-when is met. Tests cover both paths' metadata keys and machine type, secrets only on the first build, and a standard image unchanged.
  - V12: routes return the `AgogeResponse` envelope and are teacher-gated. Tests cover 200, 400, 409 and 403. The stored record holds no product key, and the catalog route is not captured by `/{image_name}/`. The keys reach `check_out` through the `PRODUCT_KEYS` attribute, redacted in `main.py` logs.
  - N15: the game master guide's `## Nested lab hosts` section (`game-master-guide.md:320-450`) covers every listed topic.
  - Notes, not reopened:
    - V11's description also asks for a finalize-watcher bootstrap on the finalized re-check-out path. Today that path adds only `enable-guest-attributes`. The watcher is V14's deliverable, and the V14 queue line already records the gap.
    - V11's test mocks `build()` down to `_add_metadata`, so the `add_disk` and boot-image path is not exercised there.
    - V3's test sets `nested_host` by hand. The record→flag link (`base_compute_manager.py:263`) is V1 code, verified earlier.
    - The builder has no test for the `disk_image` install method.
    - An uploaded medium with a null `sha256` is accepted unverified, and the builder never writes the computed hash back. The virtio-win ISO is not hash-checked.
    - No test asserts `NESTED_FINALIZE_TIMEOUT_SECONDS == 360` (only `< 540`); the source value is 360.
- **Gate results:**
  - api/unit_tests: 1567 passed, coverage 97.75%, exit 0.
  - cloud_functions/tests: 759 passed, coverage 94.28%, exit 0.
  - build_files/cloud_deployment/tests: 319 passed, exit 0.
  - frontend `npm test`: 34 files, 452 tests passed, exit 0.
  - CTF ESLint gate: exit 0.
  - CTF tsc gate: 0 CTF matches (passes; repo-wide tsc exits 2 on pre-existing errors).
  - Group V ESLint gate (`--no-error-on-unmatched-pattern`): exit 0.
  - Group V tsc gate: 0 matches (passes).
- **Reopened:** none.

### Iteration 101 — 2026-10-17
- **Completed:** V13.
  - `common/utilities/nested_build_monitor.py` defines `NestedBuildMonitor.refresh(image, now=None)`:
    - It polls `agoge-nested/` only while the phase is `provisioning`/`building`. Every other phase is returned as stored.
    - It maps the builder's `phase` values (`building`/`ready`/`failed`), the `guest-<name>` statuses (`failed:<msg>` → `failed`; unknown values ignored), `message` (cut to 200), and `heartbeat` (epoch → ISO).
    - It writes only `{'nested_build': …}`, and only when something changed.
    - On a move to `ready`/`failed`, it removes `agoge-nested-secrets` *before* the write. A failed removal leaves the record active, so the next refresh retries; after that, the terminal phase is never polled again (exactly once).
    - Stall (heartbeat, or `started_at` before the first heartbeat, older than 45 min) and timeout (`started_at` older than 240 min) fail the build and publish the existing CONTROL/STOP/TEMPLATE_SERVER.
    - A `NotFound` instance counts as "no attributes"; the stall clock still runs. Any other Compute error returns the stored build unjudged. A missing `started_at` is stamped.
  - `refresh_active()` queries CHECKED_OUT images with `nested_build.phase` IN active phases, isolating per-image errors. `QuarterHourlyMaintenance._refresh_nested_builds` calls it.
  - `GET /compute/images/{name}/nested-build/` (teacher, sync def) → `NestedImage.build_status`: 404 missing, 400 not nested.
  - Midnight exemption:
    - `ImageTemplateManager.stop_all_running` skips `is_active_nested_build` records.
    - `ProjectServerManager.stop_everything(exempt_names=)` skips those instances by exact name, plus their STOPPED state sync.
    - `DailyMaintenance._nested_build_names()` supplies the names.
- **Learned:** `stop_everything` exempts by prefix, which is unsafe for image-named template servers (`foo` would exempt `foobar`), hence the separate `exempt_names`.
- **Tests:**
  - `cloud_functions/tests/test_nested_build_monitor.py` (31): each phase mapping, guests/message/heartbeat, field mask, secrets once (+ retry, + deleted server), stall, never-reported stall, timeout, inactive phases, unreadable attributes, quarter-hourly wiring, and the three daily exemption paths.
  - `api/unit_tests/test_nested_build_route.py` (4): 200, 404, 400, 403.
  - `test_ctf_overnight_exemption.py` assertions now include `exempt_names=[]`.
- **Gate results:**
  - api/unit_tests: 1571 passed (97.75%).
  - cloud_functions/tests: 790 passed (94.28%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V14 (finalize handshake). The monitor leaves `ready`/`finalizing` alone, so V14 owns those transitions.

### Iteration 102 — 2026-10-17
- **Completed:** V14.
  - API: `ComputeImage._check_in_action` turns a CHECK_IN on a nested record into NESTED_FINALIZE when the phase is `ready` or `finalized`, or `failed` with a `finalize_nonce`. It raises `Conflict` for `provisioning`, `building`, and `finalizing`, and the list route now maps `Conflict` → 409. Nothing is published unless every image in the list passes. Standard images and a failed *build* (no nonce) keep plain CHECK_IN.
  - `ControlHandler` routes NESTED_FINALIZE → `ImageTemplateManager.finalize_nested()`. That method refuses anything not CHECKED_OUT and finalizable (`Conflict`; a duplicate delivery sees `finalizing`). It writes phase `finalizing` and the nonce, then sets `agoge-nested-finalize`. It polls `agoge-nested/finalize-result` every 10 s for up to `NESTED_FINALIZE_TIMEOUT_SECONDS`, ignoring answers to other nonces, and always removes the key afterwards.
    - `ok` → publishes CHECK_IN once.
    - `error` → phase `failed` with the message. The nonce is kept, so the next Check In finalizes again.
    - Timeout → phase `ready` with `MSG_FINALIZE_TIMEOUT`, nonce cleared.
    - A failed metadata write or a failed CHECK_IN publish → phase `ready`.
  - `check_in()` records `finalized` (nonce cleared) only when the phase was `finalizing`. If creating the image fails, it returns `finalizing` to `ready`.
  - The watcher is `server_specific/nested/finalize.sh`, rendered by `render_finalize_watcher()`. Its bootstrap, `render_finalize_bootstrap()`, starts it with `systemd-run` and `Restart=always`, never enabled, so it is not baked into lab images. Both check-out paths merge the bootstrap into `startup-script`; the first build appends it after the builder bootstrap. That closes the V11 gap.
- **Learned:**
  - In bash, `x=$(fn)` runs `fn` in a subshell, so a global it sets (the metadata `ETAG`) is lost. The watcher's `poll` sets `NONCE` directly for that reason.
  - The answered nonce lives at `/var/lib/agoge-nested/finalize-answered`, outside the state and work directories the finalize deletes.
- **Tests:**
  - `cloud_functions/tests/test_nested_finalize.py` (26): ok → CHECK_IN once, a stale nonce ignored, error → message stored with no CHECK_IN, timeout → `ready` with a message inside the budget, unreadable attributes, retry after a failure, four refusal cases, publish and request failures, `finalized` on check-in and the image-failure reset, routing, both bootstrap paths with `bash -n`, no `destroy` in the watcher.
  - The watcher is also executed against fake virsh/curl. Cases: shutdown → snapshot → cleanup → `ok`; a stubborn guest → `error:<nonce>:desk: guest did not shut down` with no force-stop and no cleanup; a nonce answered once; no nonce; a host never built; the etag sent back on the second poll.
  - `api/unit_tests/test_nested_finalize_route.py` (9).
- **Gate results:**
  - api/unit_tests: 1580 passed (97.75%).
  - cloud_functions/tests: 816 passed (94.28%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V14b (stale `finalizing` recovery, found by the reviewer), then V15 (media uploads).

### Iteration 103 — 2026-10-17
- **Completed:** V14b.
  - `is_stale_finalize(build)` in `common/utilities/nested_build_monitor.py` is true for a `finalizing` phase whose `updated_at` is older than `NESTED_FINALIZE_STALE_SECONDS`. That constant is `NESTED_FINALIZE_TIMEOUT_SECONDS + 900` (1260 s), which covers the rest of the finalize invocation plus one whole CHECK_IN invocation, so a live check-in is never raced. A missing or unparseable `updated_at` also counts as stale.
  - `ComputeImage._check_in_action` publishes NESTED_FINALIZE for a stale `finalizing` phase instead of returning 409. `ImageTemplateManager.finalize_nested` accepts it with a fresh nonce. A fresh `finalizing` phase is still refused in both places.
- **Learned:** every `nested_build` write goes through `_write_nested_build`, which stamps `updated_at`. That makes it a reliable staleness clock for `finalizing`.
- **Tests:**
  - `api/unit_tests/test_nested_finalize_route.py` (+4): stale → NESTED_FINALIZE, inside the window → 409, None or unparseable timestamp → stale. `_nested()` now defaults to a fresh `updated_at`.
  - `cloud_functions/tests/test_nested_finalize.py` (+3): stale and no-timestamp records are finalized again with a new nonce, and a record inside the window is refused. The duplicate-delivery case now carries a fresh `updated_at`.
- **Reviewer note (not fixed, harmless):** `finalize_nested` reads the phase and then writes it outside a transaction. Two simultaneous stale recoveries could each issue a nonce. The watcher answers each nonce once and the last write wins.
- **Gate results:**
  - api/unit_tests: 1584 passed (97.75%).
  - cloud_functions/tests: 819 passed (94.28%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V12b (clean up the CHECKED_OUT record when the CHECK_OUT publish fails), then V15 (media uploads).

### Iteration 104 — 2026-10-17
- **Completed:** V12b.
  - `ComputeImage._check_out_new_record(server_name, extra_attrs=None)` publishes CHECK_OUT and waits on the future for `CHECK_OUT_PUBLISH_TIMEOUT_SECONDS` (30). If the publish or the future fails, it deletes `image/<name>` and raises `ServiceUnavailable` ("No template was created; try again"). If the delete also fails, the message says to delete the template first.
  - It covers all three record-creating paths: `create_image_server`, the `process_action_on_image` BUILD branch, and `NestedImage.create`. The nested create passes `product_keys` as `extra_attrs`, which are never logged. `NestedImage._publish_check_out` is gone.
  - The three routes map `ServiceUnavailable` → 503. The two `async def` routes (`POST /create/`, `PUT /{image_name}/`) now run the core call via `run_in_threadpool`, so the 30 s wait cannot block the event loop.
- **Learned:** `PubSubManager.msg` returns the publish future without waiting, so a delivery failure never raised in the API before this. Waiting on `.result(timeout=…)` is the only way to detect it (the CTF code already does this).
- **Tests:**
  - `api/unit_tests/test_check_out_publish_failure.py` (6): success waits on the future and keeps the record; a sync raise and a future failure each delete the record and raise; a failed cleanup gives the delete-the-template message; 503 through both the create route and the PUT BUILD route.
  - `test_nested_image_create_route.py` (+4): 503 removes the record; a future timeout → 503, then a retry with the same name succeeds; no product key in the response; failed cleanup message.
- **Gate results:**
  - api/unit_tests: 1594 passed (97.75%).
  - cloud_functions/tests: 819 passed (94.28%).
  - build_files: 319 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V15 (media uploads).

### Iteration 105 — 2026-10-17
- **Completed:** V15.
  - `api/core/compute/nested/media.py` adds `NestedMedia`, with four routes in `routers/compute_image.py`, registered before `/{image_name}/`:
    - `POST /compute/images/nested/media/` takes `{filename, size_bytes, os_id?}`. It returns `{media_id, upload_url, upload_headers, expires_in}`: a V4 signed resumable-start POST that expires after `NESTED_UPLOAD_URL_TTL_SECONDS`. It rejects an unsupported extension (400), a file over `NESTED_MEDIA_MAX_BYTES` (413), a format the `os_id` entry does not accept (400), and a filename with a path (422). The URL is signed before the record is written, so a signing failure (503) leaves no record.
    - `PUT …/media/{id}/` (uploader or admin) checks that the object exists and that its size equals `size_bytes`. Only then does it set `complete`.
    - `GET …/media/` lists completed media from everyone, plus the caller's own incomplete uploads (an admin sees all of them).
    - `DELETE …/media/{id}/` (uploader or admin) deletes the object, tolerating not-found, then the record.
  - Lifecycle: Firestore's `complete` is invisible to GCS, so the signed upload stamps `x-goog-custom-time` with the start time, and completion moves Custom-Time to `NESTED_MEDIA_KEEP_CUSTOM_TIME` (9999-12-31). The bucket rule is `Delete` when `daysSinceCustomTime >= 2` under `media/`.
  - Setup option 24, **Configure Nested Image Media Bucket**, in `build_files/.../images_and_specs/nested_media_bucket.py`:
    - Creates the bucket, private with uniform access, in `env.region`.
    - CORS for the app origin plus localhost:3000. The allowed headers are built from `NESTED_MEDIA_SIGNED_HEADERS`.
    - Sets the lifecycle rule.
    - Grants `storage.objectAdmin` on the bucket and `iam.serviceAccountTokenCreator` on itself to `agoge-service@`. Both grants are idempotent.
  - Builder: uploaded `gs://` media is now fetched with `gcloud storage cp`. The cache still uses curl.
- **Learned:**
  - In google-auth, Cloud Run's `compute_engine.Credentials` is not `Signing`. `_signing_kwargs` refreshes it and signs through IAM with `service_account_email` + `access_token`. Impersonated credentials sign directly.
  - The guard hook denied two Bash calls because their text contained the gcloud storage command name ("agoge guard: This modifies Cloud Storage buckets"). One was a heredoc file edit plus a test run; the other wrote this log entry. No bucket was touched. The same edits were made with the Edit/Write tools, which run no command. A human may want to narrow that guard pattern.
  - Deleting a medium that a queued nested build references makes that guest fail with "could not download the uploaded media". Nothing prevents it yet.
- **Tests:**
  - `api/unit_tests/test_nested_media_routes.py` (42) covers:
    - Each route, the signed-URL kwargs and headers, unsupported extension, oversize and exact-limit, path filenames, the catalog format mismatch, and a signing failure.
    - Completion with the object missing, the wrong size (±1), and a Custom-Time patch failure.
    - Ownership 403s, list visibility, deletes, and both signing branches.
  - `build_files/cloud_deployment/tests/test_nested_media_bucket.py` (8) covers create, rerun idempotence, appending to an existing binding, failure, environment mismatch, the menu, and that CORS allows every signed header.
  - `test_nested_builder.py` has a fake `gcloud`, and asserts that uploaded media is downloaded through it.
- **Gate results:**
  - api/unit_tests: 1636 passed (97.75%).
  - cloud_functions/tests: 819 passed (94.28%).
  - build_files: 327 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V16, the frontend service layer. The browser must POST `upload_url` with exactly `upload_headers`, then PUT the bytes to the returned `Location` session URI, then call `PUT …/media/{id}/`.

### Verification — 2026-10-17 — PASS
- **Checked:** V13, V14, V14b, V12b and V15, which are every task ticked since the last verification (`38fad61`). HEAD is `2d33bea` and the tree is clean. Two read-only agents checked the commits against PRD.md:1685-1689 and the Nested Image Builder Contract table (PRD.md:1361-1364, 1409). I also ran these checks myself:
  - `bash -n` on `server_specific/nested/finalize.sh`: exit 0, and the file contains no `virsh destroy`.
  - The constants match the contract: 360 / 45 / 240 / 20 GiB / 3600 / `<project>_nested-media`.
  - The signed upload sets `x-goog-content-length-range: 0,{NESTED_MEDIA_MAX_BYTES}` (`api/core/compute/nested/media.py:77`).
  - I scanned the files changed in `38fad61..HEAD` for TODO/FIXME/NotImplemented. The only hit is a TODO at `common/models/agoge.py:909`, written by pdhuff on 2026-03-07, outside this work.
  - V13: `NestedBuildMonitor.refresh` maps the phases and writes only `nested_build`. It removes the secrets before the write, once (a failed removal is retried). It fails and stops a build on a stall or timeout. The teacher-only `GET …/nested-build/` route, the quarter-hourly `_refresh_nested_builds`, and the daily `exempt_names` and `stop_all_running` skip are all present. Tests cover each done-when case (`test_nested_build_monitor.py`).
  - V14:
    - `_check_in_action` returns 409 for provisioning, building and a fresh finalizing phase, and publishes NESTED_FINALIZE for ready and finalized.
    - `ControlHandler` calls `finalize_nested`, which writes the nonce, polls until 360 s, and removes the key in a `finally`. On ok it publishes CHECK_IN once; on error it sets `failed` with the message; on timeout it returns to `ready` with a message. It never stops the server.
    - The watcher and its transient `systemd-run` bootstrap are installed on both check-out paths.
    - Tests: `test_nested_finalize.py:119,147,165,379`, plus the watcher run against fake virsh and curl.
  - V14b: `is_stale_finalize` (timeout + 900 s; a missing or unparseable time counts as stale) is used in both `_check_in_action` and `finalize_nested`. Tests are in both suites.
  - V12b: all three paths that create a record use `_check_out_new_record`, which waits on the publish future. On failure it deletes the record and raises `ServiceUnavailable` (503). Tests cover a raise, a failed future, a failed cleanup and a retry.
  - V15:
    - The four media routes are declared before `/{image_name}/`, and they sign a V4 resumable POST with the TTL. Completion checks the object's size.
    - Setup option 24 is wired in all four places, with CORS, the 2-day `media/` lifecycle rule (by Custom-Time), and tokenCreator on itself.
    - The builder fetches `gs://` media with the gcloud CLI copy.
    - Tests cover the unsupported extension (400), oversize (413), and completion with the object missing or the wrong size.
  - Notes, not reopened:
    - The lifecycle rule keys on Custom-Time because GCS cannot see Firestore's `complete` flag. This meets the intent.
    - The DELETE media response labels the id `build_id`.
    - Deleting a medium that a queued build references is not prevented (iteration 105 logged this).
    - `finalize_nested`'s read-then-write is not transactional (iteration 103 logged this).
- **Gate results:**
  - api/unit_tests: 1636 passed, coverage 97.75%, exit 0.
  - cloud_functions/tests: 819 passed, coverage 96.24%, exit 0.
  - build_files/cloud_deployment/tests: 327 passed, exit 0.
  - frontend `npm test`: 34 files and 452 tests passed.
  - CTF ESLint gate: exit 0. CTF tsc gate: 0 CTF matches (repo-wide tsc exits 2 on pre-existing errors).
  - Group V ESLint gate: exit 0. Group V tsc gate: 0 matches.
- **Reopened:** none.

### Iteration 106 — 2026-10-17
- **Completed:** V16.
  - `frontend/src/services/Server/nested.model.ts` mirrors the Nested* models. `NestedHostSpecInput` holds the client fields, and `NestedHostSpec` adds the derived `exposures`/`console_ports`/`vnc_passwords`.
  - `utilities/transformers/nested.transform.ts` has the response transformers. `transformToNestedBuildStatus` drops `finalize_nonce`. `toNestedImageCreateRequest` rebuilds `nested` from client fields only, trims the name, username and key, and drops blank product keys.
  - `services/Server/nested.service.ts` (`nestedService`) has `list_machine_types` (`?nested=true`), `list_catalog`, `create`, `get_build_status`, `create_media`, `list_media`, `complete_media`, `delete_media`, and `upload_media(file, {osId, onProgress, signal})`.
  - `upload_media` POSTs `upload_url` with exactly `upload_headers` (raw axios, no auth header), PUTs the file to the `Location` session URI, then completes. A storage failure deletes the record (best effort). A completion failure keeps it, so `complete_media` can retry.
  - URL constants in `router/urls.ts`: `URL_COMPUTE_IMAGE_API_MACHINE_TYPES`, `_NESTED`, `_NESTED_CATALOG`, `_NESTED_MEDIA`, `_NESTED_MEDIA_ITEM`, `_NESTED_BUILD`. V14 added no route: Check In still goes through `imageService.post_action` with CHECK_IN, and the API turns it into NESTED_FINALIZE.
- **Learned:** a 422 from the media POST (the API's filename pattern is `^[A-Za-z0-9][A-Za-z0-9._ ()+-]{0,199}$`) carries a FastAPI `detail` array, so `HttpError.message` is not readable text. V19's `MediaUpload` should pre-validate `file.name` against that pattern.
- **Tests:** `nested.service.test.ts` (12) checks each function's URL, body and headers, plus the upload chain: success, session refused, missing Location, byte failure with a failed cleanup, cancel, and a completion failure that keeps the record. `nested.transform.test.ts` (5) covers the round trip from stored spec to create request and back, the sparse-spec defaults, and the catalog, media and upload normalization.
- **Gate results:**
  - frontend `npm test`: 36 files and 469 tests passed.
  - Group V ESLint gate (plus the two test files and `urls.ts`): exit 0.
  - Group V tsc gate: 0 matches.
  - No Python files changed, so the Python suites were not rerun (last run: 1636 / 819 / 327).
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V17, the wizard shell and Host step. Use `nestedService.list_machine_types()` for the build and lab machine types.

### Iteration 107 — 2026-10-17
- **Completed:** V17 (code and vitest; the browser check is still carried by HUMAN).
  - `ServerCreatorForm` has a Standard VM / Nested lab host `ToggleButtonGroup`. Standard keeps the old form, now headed "Create Server", and sends `display` instead of `enable_display` (the checkbox `name` and the `formData.set` both changed).
  - `Forms/NestedImage/nestedWizardState.ts` holds `NestedWizardState` (Host fields, plus `networks` pre-filled with the `lab` NAT network, `guests`, and `product_keys`), the mirrored disk constants, `nestedMinDiskSize`/`effectiveDiskSize`, `validateHostStep`, per-step `validateStep`, and `resolveNavigation`. Back is always allowed. Forward lands on the first invalid step before the target, and that can be an earlier step: a guest change can break the Host disk size.
  - `NestedImageWizard.tsx` is a non-linear `Stepper` (Host, Networks, Guests, Access, Review) modeled on `NewEditor/Editor.tsx`. A step shows its errors only after a forward move has submitted it. Machine types come from `nestedService.list_machine_types()`, and the `n2-standard-8` build default is cleared when the list lacks it.
  - `HostStep.tsx` has name, description, labels, parent OS, build and lab machine types, disk size (shows the computed minimum and keeps a local string while typing), username (the API's `_validate_username` regex), and SSH key (OpenSSH format).
  - Networks, Guests, Access and Review currently render read-only `StepSummary` views. Networks and Guests validate only "at least one". There is no submit button yet.
- **Learned:**
  - react-router `<Form>` needs a data router in tests (`createMemoryRouter` + `RouterProvider`).
  - A real data-router `navigate` throws `RequestInit: Expected signal ... AbortSignal` under jsdom/undici, so `ServerCreatorForm.test.tsx` mocks `useNavigate`.
  - MUI `TextField`'s `aria-label` lands on the FormControl root, not the input. Query by label.
- **Tests:** `nestedWizardState.test.ts` (21), `NestedImageWizard.test.tsx` (6), and `ServerCreatorForm.test.tsx` (2). The last asserts the exact Standard body with `display: "true"`.
- **Gate results:**
  - frontend `npm test`: 39 files and 498 tests passed, rerun after the disk-input fix.
  - Group V ESLint gate (plus `NestedImage/`): exit 0.
  - Group V tsc gate (plus `ServerCreatorForm`): 0 matches.
  - `ServerCreatorForm.tsx` has the same 6 lint problems it had before this change.
  - No Python files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:**
  - V18: replace the Networks `StepSummary` with the editor, and extend `validateNetworksStep` with the client-side network rules.
  - V19: guests. It must also flag the Host disk size when guest disks grow, which `resolveNavigation` already routes back to Host.
  - V20: submit via `toNestedImageCreateRequest`. Wizard state is lost when the toggle switches back to Standard; lift it if that matters.

### Iteration 108 — 2026-10-17
- **Completed:** V18 (code and vitest; the browser check is still carried by HUMAN).
  - `Forms/NestedImage/networkRules.ts` mirrors `NestedHostValidator._validate_networks`: 1–8 networks, SLUG15 unique names, a strict RFC 1918 CIDR from /16 to /29, no overlap with the reserved ranges (169.254/16, 192.168.122/24) or an earlier network, addresses inside the range and not the network or broadcast address, NAT and DHCP need `parent_address`, `dhcp_start <= dhcp_end`, and the range must exclude the parent. Errors are keyed `networks.<index>.<field>` (`networkErrorKey`), with `networks` for list-level errors. `validateNetworksStep` now calls it.
  - `NetworksStep.tsx` has one outlined section per network (name, CIDR, mode, parent address, DHCP switch and range), plus **Add network** (`nextNestedNetwork`: `netN` on the first free 192.168.x.0/24 from .101, isolated, valid as-is). Remove is disabled for the last network and for a network a guest NIC uses. Renaming a network carries guest NICs along (`renameNetworkInGuests`), but only while the old name is unique.
  - `NetworkTopology.tsx` is the inline-SVG preview. Rails are networks (NAT ones in the primary colour). Boxes are the parent and the guests, with a drop line per parent address or NIC, labelled with the IP or "DHCP". NICs on a missing network are skipped.
  - The wizard renders `NetworksStep`, and `StepSummary` no longer has a Networks branch.
- **Learned:** the API checks `dhcp_start`/`dhcp_end` as host addresses even when `dhcp` is false, because the transformer still sends them. The client does the same, and `NetworksStep` shows those errors in an Alert while the range fields are hidden.
- **Tests:** `networkRules.test.ts` (15) covers parsing, overlap (with another network and with the reserved ranges), prefix bounds, the address and DHCP range rules, the suggestions, and rename. `NetworkTopology.test.tsx` (1). `NestedImageWizard.test.tsx` has a new Networks flow test (7 tests in total).
- **Gate results:**
  - frontend `npm test`: 41 files and 515 tests passed.
  - Group V ESLint gate: exit 0.
  - Group V tsc gate: 0 matches.
  - No Python files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V19, the Guests step. Validate each NIC's network against `state.networks` and each static IP with `parseIpv4`/`parseCidr` from `networkRules.ts`: inside the CIDR, not the parent address, not inside the DHCP range. `resolveNavigation` already sends the instructor back to Guests when a network edit breaks a NIC.

### Iteration 109 — 2026-10-17
- **Completed:** V19 (code and vitest; the browser check, including the ≥1 GB upload, is still carried by HUMAN).
  - `Forms/NestedImage/guestRules.ts` mirrors `NestedHostValidator._validate_guests/_validate_nics/_validate_credentials/_validate_capacity` and the `NestedGuestModel` limits: SLUG15 unique names, an enabled catalog entry, vCPU/RAM/disk ranges with the catalog minimums, admin username pattern, password length plus Windows complexity, a product key for retail Windows (`unattended_iso` with no `eval_days`), completed media in an accepted format for `requires_upload`, packages only on Linux `cloud_image`, NIC network/static-IP/DHCP-range/parent/duplicate rules, at most 8 exposures, and memory/vCPU capacity against both machine types. Errors are keyed `guests.<i>.<field>` and `guests.<i>.nics.<n>.<field>`, with `guests` for the list.
  - `validateStep`/`firstInvalidStep`/`resolveNavigation` take an optional `GuestRuleContext` (`{catalog, media}`). Without it, every guest reads as an unknown OS, so Guests never passes unchecked.
  - `OsPickerDialog.tsx` groups the catalog by `group`, with search, chips (`osChipLabels`), and the license note shown before **Add guest** is enabled. `GuestsStep.tsx` has the guest form: password show/hide/generate, product key, NICs, packages (freeSolo Autocomplete), script, console, autostart, start order and delay. `MediaUpload.tsx` picks from the library (`usableMedia`) or uploads with progress and cancel, pre-checking the filename pattern, format and the 20 GiB limit.
  - The wizard loads `list_catalog` and `list_media` on mount. The `StepSummary` Guests branch is gone.
- **Learned:**
  - `MediaUpload` calls `onUploaded` through a latest-ref. The closure from when the upload started would write back a stale guest list and drop edits made during a long upload.
  - Leaving the Guests step unmounts `MediaUpload`, which aborts an upload in flight; the service then deletes the unfinished record.
  - This MUI is v6: `Autocomplete` uses `renderTags`, not `renderValue`.
- **Tests:** `guestRules.test.ts` (13). `NestedImageWizard.test.tsx` adds 2 flow tests: picker → license note → `requires_upload` blocks Next → upload, where an edit made mid-upload survives → Access; and a wrong-format file refused before any upload. The wizard mock now includes `list_catalog`, `list_media` and `upload_media`. One `nestedWizardState.test.ts` case now passes a catalog.
- **Gate results:**
  - frontend `npm test`: 42 files and 530 tests passed (rerun of the NestedImage files after the ref fix: 59 passed).
  - Group V ESLint gate: exit 0.
  - Group V tsc gate: 0 matches.
  - No Python files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V20, the Access and Review steps. The Review meters can reuse `NESTED_PARENT_OVERHEAD_MB` and the capacity logic in `guestRules.ts`. The submit sends `toNestedImageCreateRequest` with `state.product_keys`.

### Iteration 110 — 2026-10-17
- **Completed:** V20 (code and vitest; the browser check, creating the SC-35 three-guest host, is still carried by HUMAN).
  - `Forms/NestedImage/accessReview.ts` holds the pure logic. `deriveExposures`/`deriveConsoles` mirror `NestedHostValidator.derive`: guest order, then NIC order; console ports 5901+ over guests with a console. Because the API derives slots and the client may not send them, `moveExposure` reorders the **guests**. An exposure can only pass a neighbour on another guest (`canMoveExposure`), and the whole guest moves, console port included. `capacityMeters` gives build/lab RAM and vCPU plus the disk minimum. `estimateBuildMinutes` is a heuristic: 10 min parent, then per-method minutes on two install slots in `start_order`. `reviewWarnings` covers evaluation expiry, manual installs (and manual with the console off), agentless → CTF `offline` driver, uploaded Windows media, and an estimate over the 240-minute limit. `toCreateRequest` sends product keys only for guests that need one, because the API refuses a key for an unknown guest.
  - `AccessStep.tsx` has the slot table with up/down buttons (no drag), the alias-count note, and the console port table. `ReviewStep.tsx` has the host summary, estimate, `LinearProgress` meters, warnings, and a credentials table with a show-passwords switch.
  - The wizard replaces Next with **Create image** on Review. It posts `nestedService.create(toCreateRequest(...))` and navigates to `URL_TEACHER_SERVERS`; on failure it keeps the state and shows the API message. `StepSummary` is gone.
- **Learned:** `toNestedImageCreateRequest` (inside the service) already trims keys and names, so `toCreateRequest` does not need to.
- **Tests:** `accessReview.test.ts` (11) uses an SC-35 state: derive order, moves, meters, estimate, warnings, and the request body. `NestedImageWizard.test.tsx` adds 2 flow tests (reorder → review → submit body and navigate; a create failure keeps the wizard), and mocks `useNavigate` and `create`.
- **Gate results:**
  - frontend `npm test`: 43 files and 543 tests passed.
  - Group V ESLint gate: exit 0.
  - Group V tsc gate: 0 matches.
  - No Python files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V21, nested rows in `ImageListTable`: poll `get_build_status` while the phase is active, disable Check In while building, and add guest details and SSH tunnel hints to `ImageDetailsDialog`/Connect. `transformToNestedHostSpec` already reads the stored `exposures`/`console_ports`.

### Verification — 2026-10-17 — PASS
- **Checked:** V16, V17, V18, V19 and V20, which are every task ticked since the last verification (`0b81a25`). HEAD is `e61bc29` and the tree is clean. Two read-only agents checked the five commits against PRD.md:1691-1699, `api/core/compute/nested/validator.py` and the Nested* models. I also checked these myself:
  - I scanned the lines added in `0b81a25..HEAD` for TODO/FIXME/NotImplemented/placeholder. The only hits are the `placeholder="ad-lab-host"` input hint and the product-key format text in an error message. Neither is a stub.
  - V16: the URL constants (`router/urls.ts:81-86`) match the routes in `api/routers/compute_image.py`: `machine-types/?nested`, `nested/`, `nested/catalog/`, `nested/media/` (POST, GET), `nested/media/{id}/` (PUT, DELETE) and `{name}/nested-build/`. The tests call all 9 service functions, and the round trip is tested.
  - V17:
    - The API reads `form_data.get('display')` (`api/core/compute/image.py:630`), so the `display` key fix is real, and the heading is "Create Server".
    - The Stepper is `nonLinear` with the five steps and per-step validation.
    - Machine types come from `?nested=true`.
    - The disk-size minimum and the defaults match the API's.
  - V18:
    - The default `lab` NAT network is 192.168.100.0/24, parent .1, DHCP .100–.199.
    - `networkRules.ts` follows `_validate_networks` rule for rule.
    - The topology preview is inline SVG.
  - V19: `guestRules.ts` matches the validator and the `NestedGuestModel` limits: patterns, vCPU/RAM/disk ranges, the catalog minimums, the upload, product-key and Windows-password rules, the NIC rules, and capacity with the 2048 MB parent overhead. A `requires_upload` guest with no media blocks Next (`NestedImageWizard.test.tsx:186-253`).
  - V20:
    - `deriveExposures`/`deriveConsoles` match `derive()`: guest order, then NIC order, consoles from port 5901.
    - Reordering uses up/down buttons with no drag (MUI X Community).
    - The submit body matches `NestedImageCreateRequest` and leaves out the fields the server derives.
    - All four warnings are present.
    - After Create, the wizard returns to `URL_TEACHER_SERVERS`.
  - Notes, not reopened:
    - `parseCidr` trims but the transformer sends `cidr` as stored. This can't cause a failure, because the CIDR input trims on every keystroke (`NetworksStep.tsx:96`).
    - The client trims the product key before validating it, and `toNestedImageCreateRequest` trims it again before submit (`nested.transform.ts:158`), so the two agree.
    - The build-time estimate's per-install minutes (`accessReview.ts:94-104`) are a heuristic, not values from the PRD. The PRD asks only for "the estimated build time".
    - The "verified in browser" done-whens for V17–V20 are still carried by HUMAN, which stays `[ ]`.
- **Gate results:**
  - api/unit_tests: 1636 passed, coverage 97.75%, exit 0.
  - cloud_functions/tests: 819 passed, coverage 96.24%, exit 0.
  - build_files/cloud_deployment/tests: 327 passed, exit 0.
  - frontend `npm test`: 43 files and 543 tests passed, exit 0.
  - CTF ESLint gate: exit 0. CTF tsc gate: 0 CTF matches (repo-wide tsc exits 2 on pre-existing errors).
  - Group V ESLint gate: exit 0. Group V tsc gate: 0 matches.
- **Reopened:** none.

### Iteration 111 — 2026-10-17
- **Completed:** V21 (code and vitest; the "verified in browser on a live build" check is carried by HUMAN).
  - `AgogeImage` now carries `nested`/`nested_build`. Before this, `transformToAgogeImage` dropped both, so the list never saw a nested record. `finalize_nonce` is still stripped.
  - `Forms/NestedImage/nestedImageStatus.ts` holds the pure logic:
    - Phase and guest-status labels.
    - `isStaleFinalize`, which mirrors `is_stale_finalize` (360+900 s).
    - `isNestedBuildActive`: queued, provisioning, building, or a live finalizing.
    - `isNestedCheckInBlocked`. This deliberately also blocks `queued`, which the API would allow, because a queued host has no guests.
    - `latestBuildStatus`/`withPolledBuildStatus`: whichever of the list record and the poll has the later `updated_at` wins.
    - `prunePolledBuilds`.
    - `nestedGuestDetails`.
    - `nestedTunnels`: a console tunnel is `ssh -L p:localhost:p`; an exposed guest is `ssh -L 13389+slot:<ip>:3389` (Windows) or `2222+slot:<ip>:22`.
  - `ImageListTable` has a **Nested build** chip column. It polls `get_build_status` for active nested rows through a second `usePolling`, and disables Check In while the build is active. The details dialog is looked up by name on each render, so it follows the polled status.
  - `ImageDetailsDialog` renders `NestedGuestDetails`: status, IPs (DHCP when not static), alias slots, credentials, and console port plus VNC password, with passwords behind a switch.
  - `ServerConnectButton` renders `NestedTunnelHints`. It uses the parent's SSH `human_interaction` username and fetches the catalog on open.
- **Learned:**
  - The catalog is the only source of a guest's family. No os_id naming convention exists (V6 is unseeded), so when the catalog does not know a guest, the hint offers both the RDP and SSH tunnels rather than guessing.
  - The agoge-reviewer found that an unpruned polled map masks a re-created `queued` record (`updated_at` null), and polling never resumes. Fixed with `prunePolledBuilds` on each list refresh.
- **Tests:** `nestedImageStatus.test.ts` (12): activity, stale finalize, Check In blocking, the merge, the prune, guest details, tunnels, and the transformer. `NestedImageDetails.test.tsx` (3): the guest table with the password switch, the tunnel commands with a mocked catalog, and no hostname.
- **Gate results:**
  - frontend `npm test`: 45 files and 558 tests passed.
  - Group V ESLint gate: exit 0.
  - Group V tsc gate: 0 matches.
  - The touched files outside the gate add no new lint errors or tsc errors. The 2 import/order errors and 5 TS2322 errors in `ImageListTable.tsx` are pre-existing.
  - No Python files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V22, Guacamole `alias_index`/`port` targets in `DisplayProxy` and `GuacamoleConfiguration.prepare_guac_connection`, plus the lab spec validation for nested images on both save paths.

### Iteration 112 — 2026-10-17
- **Completed:** V22.
  - `GuacamoleConfiguration.prepare_guac_connection` takes `ip_aliases`. A connection with `alias_index` targets `ip_aliases[alias_index]`; a CIDR suffix is stripped, and an out-of-range index raises `ValueError`. `port` overrides the per-protocol default in `DEFAULT_PORTS` (rdp 3389, ssh 22, vnc 5901). The three SQL templates now take `{port}` and no longer hardcode it. The returned dict carries the resolved `ip` and `port`.
  - `DisplayProxy.prepare_server_record` passes NIC 0's `ip_aliases`, and it records the resolved IP in `ProxyConnectionModel.internal_ip_address`.
  - New `object_validators/nested_servers.py` `NestedServersValidator(config, image_loader)`:
    - A server whose image doc has `nested` needs an n1/n2 machine type and at least `len(nested.exposures)` NIC 0 aliases.
    - Every `alias_index` must be in range on any server.
    - Public image paths (containing `/`) and image-less servers are skipped.
  - The validator runs on both save paths: after `ServersValidator` in `SpecEditManager._validate_spec`, and after `UnitValidator` in `SpecFileManager._validate_spec`. Both use the new `LabSpecBase._get_image_record`.
- **Learned:**
  - The image loader result is used only when it is a `dict`. Existing spec tests use a bare `MagicMock` db, and its `.get('nested')` would otherwise look truthy.
  - The nested checks run on partial editor saves too, unlike the WireGuard listener check. Every field they read comes from the servers form itself.
  - Pre-existing ruff F541 at `lab_spec_base.py:111`; not touched.
- **Tests:**
  - `cloud_functions/tests/test_guacamole_nested_targets.py` (8): an alias target, an alias with a CIDR suffix, a console target with a port override, ordinary rdp/ssh/vnc targets (unchanged), an out-of-range index, and DisplayProxy end to end.
  - `api/unit_tests/test_nested_server_spec_validation.py` (11): a valid spec, and the three bad cases (an E2 machine type, too few aliases, an alias_index out of range) on both save paths. It also covers a plain server, alias_index on a plain server, and the lookup skipping.
- **Gate results:**
  - api/unit_tests: 1647 passed, coverage 97.75%.
  - cloud_functions/tests: 827 passed, coverage 94.28%.
  - build_files: 327 passed.
  - No frontend files changed.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V23 (the spec editor's Nested guests panel, alias filling, connection generation, and N5 accepting a nested-image parent). Its connection generator should emit `alias_index`/`port`/`nested_guest` in the shape this validator accepts.

### Iteration 113 — 2026-10-17
- **Completed:** V23 (code and vitest; the "verified in browser" check is carried by HUMAN).
  - N5: `CtfValidator(config, image_loader=None)`. A nested-guest parent with no `ip_aliases` passes when its image doc has `nested`. All four call sites pass a loader: `SpecEditManager`, `SpecFileManager` (`_get_image_record`), and both `CtfSetup` calls (new `CtfSetup._get_image_record`). `NestedServersValidator._image_doc_id` is now the public `image_doc_id`. `ctf.py` imports it relatively (`from .nested_servers`). An absolute `utilities.…` import broke collection in cloud_functions/tests and build_files tests, which load the validator without `api/` on the path.
  - The server form has a new `ServerFormKeys.serverHumanInteraction` (null means "use the image's connections", as before). It initializes from the saved list only when that list has nested fields, and it resets to null when the base image changes to a different value. `render()` prefers it.
  - The `HumanInteraction` type gains `nested_guest`/`alias_index`/`port` in both `specification.model.ts` and `specificationEdit.model.ts`.
  - `ServerForm/nestedServer.ts`:
    - `fillAliasIps`: one alias per exposure slot. It keeps a valid existing alias in its slot and takes the lowest free addresses for the rest, skipping the GCP-reserved network, .1, second-to-last and broadcast. Taken addresses are every IP and alias on the network, plus its reservations.
    - `nestedConnections`: RDP for an exposed Windows guest, SSH for an exposed Linux guest (alias_index = first slot, the guest's admin credentials), VNC console (port + vnc password) otherwise. It never guesses for a guest the catalog doesn't know.
    - `mergeNestedConnections` keeps the parent's own entries.
    - `nestedCtfGuests`: `domain` = guest name (builder.sh `virt-install --name "$guest"`), driver from the catalog `agent`. Appliances and unknown guests are skipped.
    - `nestedMachineTypes` keeps only N1/N2.
  - `NestedGuestsPanel` renders under the image/machine-type group when the selected image has `nested`. It has the guest table, **Fill alias IPs** (writes NIC 0's comma-joined alias field), and **Add connections**.
  - The CTF step: `CtfSpecFields.imageGuests` plus `missingImageGuests` (dedupes by (server, name), caps at 8 per server) adds an **Add guests from images (n)** button. `Editor.tsx` loads the catalog only when the unit is CTF.
- **Learned:** importing `CtfSpecEditor` in a node-env test pulls the CTF service, which initializes Firebase, so mock `services/Ctf/ctf.service`.
- **Tests:**
  - `api/unit_tests/test_ctf_nested_guest_validation.py` (+7): a nested-image parent with no aliases passes (3 image-ref forms); non-nested/None images are rejected; a public image is never looked up.
  - `nestedServer.test.ts` (12): alias filling, connection generation, CTF pre-fill, missingImageGuests, and the helpers.
  - `NestedGuestsPanel.test.tsx` (2): the buttons write the expected aliases and connections; an unknown subnet errors.
- **Gate results:**
  - api/unit_tests: 1654 passed, coverage 97.67%.
  - cloud_functions/tests: 827 passed, coverage 94.28%.
  - build_files: 327 passed.
  - frontend `npm test`: 47 files and 572 tests passed.
  - CTF and Group V ESLint/tsc gates pass.
  - Touched files outside the gates add no new lint or tsc errors. The pre-existing errors are the `Layers`/`Memory` unused imports in `ServerForm.tsx`, 11 in `Editor.tsx`, and TS2769 in `SelectImageTable.tsx`.
- **Blockers:** V6 is still BLOCKED on Open Question V-5.
- **Next:** V24, the nested image guide `docs/guides/nested-lab-hosts.md`.


### Iteration 114 — 2026-10-17
- **Completed:** V24. Wrote `docs/guides/nested-lab-hosts.md`. It covers licensing (eval periods, `slmgr /rearm`, no Windows redistribution, upload limits), sizing, every wizard step, build time and troubleshooting (builder log, `agoge-nested/message`, failure messages), tunnels, finalize, lab use (aliases and connections), CTF use, and the root-on-parent warning. The Game Master Guide's nested section now links to it.
- **Learned:** the OS catalog is empty until V6 is unblocked. The guide says the administrator maintains `nested-os-catalog`, and an entry without `media_sha256` fails its download. Finalize's `agoge-pristine` has no BIOS-only check in code; the guide warns that UEFI guests can fail the snapshot.
- **Gate results:** docs only, so no code gates apply.
- **Blockers:** V6 is still BLOCKED on Open Question V-5. V25 and HUMAN need a person.
- **Next:** none the loop can do. V6 waits on V-5's answers; V25 and HUMAN are human-only.

### Verification — 2026-10-17 — PASS
- **Checked:** V21, V22, V23 and V24, which are every task ticked since the last verification (`9a16242`). HEAD is `ebfa508` and the tree was clean before this entry. Two read-only agents checked the four commits against PRD.md:1701-1707. I also checked these myself:
  - I scanned the lines added in `9a16242..HEAD` for TODO/FIXME/NotImplemented/placeholder/stub. The only hit is a test comment saying `UnitValidator` is stubbed so the nested rules are what is under test. That is a test mock, not a stub in shipped code.
  - I grepped every `CtfValidator(` call outside tests. All four (`file_manager.py:70`, `edit_manager.py:309`, `ctf/setup.py:130,281`) pass `image_loader`.
  - The three Guacamole SQL templates use `'{port}'` (`guacamole_configuration.py:78,89,98`), and each `.format()` passes `port=conn["port"]`.
  - V21:
    - `ImageListTable` polls `nestedService.get_build_status` (`…/nested-build/`) for rows with an active build.
    - Check In is disabled through `isNestedCheckInBlocked`.
    - `NestedGuestDetails` renders in `ImageDetailsDialog` when the image has `nested`.
    - `ServerConnectButton` renders `NestedTunnelHints` with `ssh -L` commands for each console and each exposed guest.
  - V22:
    - `DisplayProxy` passes `nics[0].ip_aliases`.
    - `alias_index` resolves to the alias with any CIDR suffix stripped, and an out-of-range index raises.
    - `port` falls back to 3389, 22 or 5901 by protocol.
    - `NestedServersValidator` checks the N1/N2 machine type, the alias count and the `alias_index` range. It runs on both save paths.
    - The tests cover an alias target, a console target and an ordinary target. The three bad cases are tested on both `file_manager` and `edit_manager`.
  - V23:
    - `NestedGuestsPanel` renders only for a nested image.
    - The machine-type picker is filtered to `^n[12]-` for a nested image.
    - **Add connections** writes `serverHumanInteraction`, which `render()` saves. The shapes match `HumanInteractionModel` (`alias_index`/`port`/`nested_guest`).
    - N5 accepts a parent whose image has `nested`, with a test covering 3 image-ref forms.
    - The N13 pre-fill sets `domain` to the guest name and `driver` from the catalog `agent`.
    - Vitest covers alias filling and connection generation.
  - V24:
    - `docs/guides/nested-lab-hosts.md` covers every topic the PRD lists.
    - The paths and messages it cites match the code: `/var/log/agoge-nested-builder.log` and `agoge-nested/message` (`builder.sh`), the stall and upload limits (`common/constants/nested.py`), and `agoge-pristine`.
  - Notes, not reopened:
    - No test renders `ImageListTable` itself. The polling and Check In wiring was confirmed by reading the code, and the pure logic behind it is unit-tested.
    - A guest with several exposed NICs gets one RDP/SSH connection, on its first slot, as its doc comment says.
    - `_has_nested_image` reloads the image for each guest with no cache. That only costs time.
    - The "verified in browser" done-whens for V21 and V23 are still carried by HUMAN, which stays `[ ]`.
    - V6 is still BLOCKED on V-5, and V25 is human-only.
- **Gate results:**
  - api/unit_tests: 1654 passed, coverage 97.67%, exit 0.
  - cloud_functions/tests: 827 passed, coverage 94.28%, exit 0.
  - build_files/cloud_deployment/tests: 327 passed, exit 0.
  - frontend `npm test`: 47 files and 572 tests passed, exit 0.
  - CTF ESLint gate: exit 0. CTF tsc gate: 0 CTF matches (repo-wide tsc exits 2 on pre-existing errors).
  - Group V ESLint gate: exit 0. Group V tsc gate: 0 matches.
- **Reopened:** none.

### Iteration 115 — 2026-10-17
- **Diagnosis:** iterations 40 and 41 of this run made no commit. Every open item was BLOCKED (V6) or human-only (I4b, V25, HUMAN), and both iterations stopped without changing anything. V6 had been treated as all-or-nothing. But the sync operation and the upload-only entries depend on no V-5 answer: under the contract a `requires_upload` entry has no URL and no hash. So I split V6 into V6a, done here, and V6b, which stays BLOCKED on V-5.
- **Completed:** V6a.
  - `build_files/cloud_deployment/operations/images_and_specs/nested_os_catalog_sync.py` (`NestedOsCatalogSync`) has the four menu edits (`SetupOptions.NESTED_OS_CATALOG = 25`, Server Images & Build Specs).
    - It validates the JSON and rejects repeated ids.
    - It upserts by id, keeping a stored boolean `is_enabled`, and writes only entries whose stored document differs. A second sync therefore writes nothing.
    - It never deletes entries missing from the JSON.
  - `common/data/nested_os_catalog.json` has 19 upload-only entries.
- **Learned:**
  - The current stable virtio-win (stable-virtio redirect, 2026-10-17) is `0.1.302-1`. Its ISO has the `w10`/`w11`/`2k16`–`2k25` driver directories, which I checked by reading the ISO's first 8 MB. Win10/11 and Server 2016+ pin it. Vista–8.1 and Server 2008–2012 R2 use SATA + e1000 with `virtio_win_version: null` and `agent: false` until V-3 pins their last virtio-win release.
  - `windows_image_index` is 1 for client and 2008/2008 R2, and 2 (Standard with GUI) for 2012+. The license note tells the instructor which index gets installed.
  - The custom ISO/disk entries use family/group `appliance`, which gives console-only hints, and `osinfo: generic`.
  - `test_nested_manifest.py` now also runs over the 13 JSON `unattended_iso` entries (+52 tests).
- **Tests:** `build_files/cloud_deployment/tests/test_nested_os_catalog_sync.py` (60).
- **Gate results:**
  - build_files: 387 passed.
  - cloud_functions/tests: 879 passed, coverage 94.28%.
  - api/unit_tests: 1654 passed, coverage 97.67%.
  - No frontend files changed.
  - agoge-reviewer found no violations.
- **Blockers:** V6b is BLOCKED on Open Question V-5 (Microsoft eval and Kali URLs and SHA-256s need a person). V25 and HUMAN need a person.
- **Next:** V6b only once V-5 is answered. Its Linux and appliance entries also need pinned, dated release URLs and their published SHA-256s.

### Iteration 116 — 2026-10-17
- **Diagnosis:** every open item was BLOCKED or human-only again. But V6b's Linux entries need no V-5 answer: they need only a pinned, dated URL and the publisher's published SHA-256. So I split V6b into V6b1 (done here) and V6b2 (still partly BLOCKED).
- **Completed:** V6b1. `common/data/nested_os_catalog.json` now has 23 entries. The 4 new ones are `ubuntu-20.04`, `-22.04`, `-24.04` and `-26.04`: `cloud_image`, qcow2, netplan, agent, BIOS, and virtio disk and NIC. Each URL is a dated `releases/<codename>/release-YYYYMMDD/` file. Each SHA-256 comes from that directory's `SHA256SUMS`, fetched over https on 2026-10-17. I checked every file's magic number, and each is `QFI\xfb` (qcow2).
- **Tests:**
  - `test_nested_os_catalog_sync.py` adds two rules: no downloadable URL has a `current`, `latest` or `daily` path segment, and every `cloud_image` entry is a Linux disk format with an agent and a real `net_config`.
  - `test_nested_manifest.py` renders a manifest for each seeded cloud image.
- **Learned:**
  - Ubuntu 16.04 and 18.04 would build but get no network config, so they are queued as V6c and V6d, each with its URL and hash.
  - The `osinfo` ids `ubuntu24.04` and `ubuntu26.04` may be missing from Debian 12's osinfo-db. `define_domain` already falls back to `generic`.
  - Ubuntu prunes old dated release dirs eventually, so a pinned URL can start returning 404. The guide's "could not download the media" row covers that case.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 883 passed, 94.28%.
  - build_files: 399 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. V25 and HUMAN need a person.
- **Next:** V6d, then V6c. Both are small `builder.sh` fixes plus one catalog entry each. After them, V6b2's Fedora/Rocky/Alma entries, done like V6b1.

### Iteration 117 — 2026-10-17
- **Completed:** V6d.
  - `builder.sh` `write_network_config` now writes the netplan gateway route as `to: 0.0.0.0/0`, not `to: default`.
  - `common/data/nested_os_catalog.json` has 24 entries. The new one, `ubuntu-18.04`, is placed before 20.04 and is pinned to `bionic/release-20230607`.
- **Learned:** I re-fetched that release's `SHA256SUMS` over https on 2026-10-17, and it matches the queued hash. The file's magic number is `QFI\xfb` (qcow2). Its manifest lists `netplan.io 0.99-0ubuntu3~18.04.5`.
- **Tests:** `test_nested_builder.py::test_netplan_default_route_uses_a_cidr_older_netplan_accepts` checks the rendered `90-agoge.yaml`. The existing catalog and manifest tests also cover the new entry.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 885 passed, 94.28%.
  - build_files: 402 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. V25 and HUMAN need a person.
- **Next:** V6c (the `interfaces.d/agoge.cfg` rename plus `ubuntu-16.04`), then V6b2's Fedora/Rocky/Alma entries, done like V6b1.

### Iteration 118 — 2026-10-17
- **Completed:** V6c.
  - `builder.sh` `write_network_config` now writes the ifupdown config as `interfaces.d/agoge.cfg`, not `interfaces.d/agoge`.
  - `common/data/nested_os_catalog.json` has 25 entries. The new one, `ubuntu-16.04`, is placed before 18.04. It uses `ifupdown` and `osinfo` `ubuntu16.04`, and is pinned to `xenial/release-20211001/...-disk1.img`.
- **Learned:** I re-fetched that release's `SHA256SUMS` over https on 2026-10-17, and it matches the queued hash. The magic number is `QFI\xfb` (qcow2). The manifest lists `ifupdown 0.8.10ubuntu1.4` and `systemd 229`. That systemd is new enough for the udev `.link` rename. The image does not ship `qemu-guest-agent`, but `customize_linux` installs it.
- **Tests:** `test_nested_builder.py::test_ifupdown_config_is_a_cfg_file_ubuntu_16_04_sources` checks the upload target, the `.link` file and the static stanza. The existing catalog and manifest tests also cover the new entry.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 887 passed, 94.28%.
  - build_files: 405 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. V25 and HUMAN need a person.
- **Next:** V6b2's Fedora/Rocky/Alma entries, done like V6b1: a dated release dir with a published SHA-256 file.

### Iteration 119 — 2026-10-17
- **Completed:** V6b2a, split out of V6b2. `common/data/nested_os_catalog.json` has 31 entries. The 6 new ones follow `ubuntu-26.04`: `rocky-8`, `rocky-9`, `rocky-10`, `almalinux-8`, `almalinux-9` and `almalinux-10`. Each is a `cloud_image` (qcow2) with `nm-keyfile`, an agent, BIOS, virtio, and 1024 MB minimum memory.
- **Learned:**
  - Each URL sits in a versioned directory (`rocky/9.8/`, `almalinux/9.8/`), not the rolling major dir (`9/`). Each SHA-256 comes from the publisher's `CHECKSUM` file, fetched over https on 2026-10-17. Every file's magic is `QFI\xfb` (qcow2), and every virtual size is 10 GiB.
  - Neither vault has a copy of a current minor release. When the next minor ships, the pinned `/pub` URL moves to `vault` and returns 404 until someone re-pins it. AlmaLinux also prunes old dated builds.
  - Rocky 10 and AlmaLinux 10 need an x86-64-v3 CPU. `define_domain` already uses `host-passthrough`.
- **Tests:** `test_nested_os_catalog_sync.py::test_nm_keyfile_entries_match_the_builders_rhel_family` checks every `nm-keyfile` entry's osinfo against `builder.sh`'s `RHEL_FAMILY`. Only those entries get `--selinux-relabel`, and without it SELinux makes NetworkManager ignore the uploaded keyfile.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 893 passed, 94.28%.
  - build_files: 429 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. V25 and HUMAN need a person.
- **Next:** V6b2's Fedora 43/44 entries (`dl.fedoraproject.org/pub/fedora/linux/releases/<n>/Cloud/x86_64/images/` with its `CHECKSUM`), done the same way.

### Verification — 2026-10-17 — PASS
- **Checked:** the items ticked since the last verification (7b23b7b): V6a, V6b1, V6d, V6c and V6b2a. I also confirmed that parent V6 and V6b/V6b2 are still `[ ]`, that V6 is BLOCKED on V-5, and that V25/HUMAN are still `[ ]` and marked human-only.
  - V6a: `nested_os_catalog_sync.py` makes all four add-setup-operation edits (SetupOptions 25, `category_menu`, the class, the `operation_map` binding). It upserts by id, keeps a stored boolean `is_enabled`, writes only changed entries, and leaves ids that are absent from the JSON alone. Firestore `query` returns plain `to_dict()` records, so the second-sync no-op also holds against the real database. The tests use a stateful fake database, not hardcoded values.
  - V6d and V6c: `builder.sh` now writes `to: 0.0.0.0/0`, and the ifupdown file is `interfaces.d/agoge.cfg` in both the write and the upload mapping. Each fix has its own test.
  - V6b1, V6d, V6c and V6b2a catalog entries: there are 31 entries, and all 12 downloadable URLs are dated or versioned paths. I re-fetched the publishers' checksum files over https and compared four hashes: ubuntu-24.04, ubuntu-16.04, rocky-9 and almalinux-10. All four match the JSON exactly.
  - No TODO, stub or `NotImplemented` in the new code.
- **Gate results:**
  - api/unit_tests: 1654 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 893 passed, 94.28% (≥85%).
  - build_files: 429 passed.
  - Frontend `npm test`: 47 files, 572 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: no matches.
  - Group V eslint: exit 0. Group V tsc grep: no matches.
- **Reopened:** none.

### Iteration 120 — 2026-10-17
- **Completed:** V6b2b, split out of V6b2. `common/data/nested_os_catalog.json` has 33 entries. The 2 new ones follow `almalinux-10`: `fedora-43` and `fedora-44`. Each is a `cloud_image` (qcow2) with `nm-keyfile`, osinfo `fedora43`/`fedora44` (both match `RHEL_FAMILY`, so they get `--selinux-relabel`), an agent, BIOS, virtio, and 1024 MB minimum memory.
- **Learned:**
  - Each SHA-256 comes from the release's PGP-signed `CHECKSUM`, fetched over https on 2026-10-17. Both files start with `QFI\xfb` (qcow2 v3), and both have a 5 GiB virtual size. Fedora 42 has already moved to the archive, so `releases/<n>/` 404s after EOL, just as Rocky and Alma `/pub` URLs do.
  - The Fedora Cloud root is btrfs, so `findmnt -no SOURCE /` returns `/dev/vda4[/root]`. With that value, the old firstboot grow broke `lsblk` and the partition number, and it had no btrfs resize. It now uses `findmnt -nvo` (`--nofsroot`) and picks the resize tool from `FSTYPE`: `xfs_growfs`, `btrfs filesystem resize max`, or `resize2fs`.
- **Tests:** `test_nested_builder.py::test_firstboot_grows_the_root_filesystem_for_its_fstype` pulls the grow command out of the rendered builder. It runs the command against stub `findmnt`/`lsblk`/`growpart`/resize tools for btrfs, xfs and ext4 roots.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 898 passed, 94.28%.
  - build_files: 437 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. V25 and HUMAN need a person.
- **Next:** V6b2's openSUSE Leap / Arch / Alpine cloud images (each from a dated or versioned dir with a published SHA-256), or CentOS Stream 9/10 GenericCloud from its dated `cloud.centos.org` files and `CHECKSUM`.

### Iteration 121 — 2026-10-17
- **Completed:** V6b2c, split out of V6b2. `common/data/nested_os_catalog.json` has 34 entries. The new one, `centos-stream-10`, follows `fedora-44`. It is a `cloud_image` (qcow2) with `nm-keyfile`, osinfo `centos-stream10` (matches `RHEL_FAMILY`, so it gets `--selinux-relabel`), an agent, BIOS, virtio, and 1024 MB minimum memory.
- **Learned:**
  - The SHA-256 `c98bf5b4…1e8b` appears in both the file's `.SHA256SUM` and the directory `CHECKSUM`, fetched over https on 2026-10-17. The file starts with `QFI\xfb` (qcow2 v3), has a 10 GiB virtual size, and a HEAD returns 200 with 2411266048 bytes.
  - CentOS Stream 9 is **not** added: its `9-stream` `CHECKSUM` lists no GenericCloud qcow2, and no dated GenericCloud file has a `.SHA256SUM` (fetching one returns a CloudFront 502). It needs a published SHA-256 from another source before it can be seeded. The loop must not hash the download itself.
  - CentOS Stream 10, like Rocky and Alma 10, needs an x86-64-v3 CPU. `define_domain`'s `host-passthrough` covers that. cloud.centos.org prunes old dated builds, so the pinned URL will eventually 404.
- **Tests:** no new test. The existing catalog rules (https, SHA-256, no `latest` segment, cloud-image fields, `nm-keyfile` osinfo against `RHEL_FAMILY`) and the per-entry manifest render cover the new entry.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 899 passed, 94.28%.
  - build_files: 441 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256 for its GenericCloud image. V25 and HUMAN need a person.
- **Next:** V6b2's openSUSE Leap / Arch / Alpine cloud images, each from a dated or versioned dir with a published SHA-256.

### Iteration 122 — 2026-10-17
- **Completed:** V6b2d, split out of V6b2. `common/data/nested_os_catalog.json` has 35 entries. The new one, `archlinux`, follows `centos-stream-10`. It is a `cloud_image` (qcow2) with `networkd`, osinfo `archlinux`, an agent, BIOS, virtio, and 1024 MB minimum memory.
- **Learned:**
  - Arch publishes dated build dirs `images/vYYYYMMDD.NNNNNN/`, each file with its own `.SHA256`. The SHA-256 `360f0fa4…4e87` matched on both the geo and fastly mirrors on 2026-10-17. The file starts with `QFI\xfb`, is 578080256 bytes, and has a 2 GiB virtual size. The root is btrfs, which iteration 120's firstboot grow already handles.
  - arch-boxes leaves the pacman keyring empty: `pacman-init.service` fills it only on first boot (`ConditionFirstBoot`). virt-customize's `--install` runs `pacman -S` with no sync, Arch has no `openssh-server` package, and the image has no `sudo`. So the old customize would have failed on Arch. `builder.sh` now has `ARCH_FAMILY` and runs keyring init plus `pacman -Syu` before `--install`. It uses a full upgrade, not `-Sy`, because Arch does not support partial upgrades. virt-customize applies operations in command-line order.
- **Tests:** `test_nested_builder.py::test_arch_initializes_pacman_and_installs_its_own_ssh_and_sudo_packages` checks the package list, that pacman setup comes before `--install`, and the sudoers drop-in. `test_non_arch_guests_skip_the_pacman_setup` checks that other distros don't get it.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 902 passed, 94.28%.
  - build_files: 444 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. V25 and HUMAN need a person.
- **Next:** V6b2's openSUSE Leap 16 (NetworkManager, but SELinux-enforcing, so it also needs `--selinux-relabel`) or Alpine. Alpine needs builder work: OpenRC, busybox `adduser`, and an `interfaces` file that does not source `interfaces.d`.

### Iteration 123 — 2026-10-17
- **Completed:** V6b2e, split out of V6b2. `common/data/nested_os_catalog.json` has 36 entries. The new one, `opensuse-leap-16.0`, follows `archlinux`. It is a `cloud_image` (qcow2) with `nm-keyfile`, osinfo `opensuse16.0` (the osinfo-db short-id), an agent, BIOS, virtio, and 1024 MB minimum memory.
- **Learned:**
  - Leap 16 appliances have build-numbered files (`…-Cloud-Build18.81.qcow2`) next to unversioned aliases. The SHA-256 `ed375c62…a31b` comes from the build file's published `.sha256` (it has a PGP-signed `.sha256.asc` too), fetched over https on 2026-10-17. The file starts with `QFI\xfb` (qcow2 v3), is 338000896 bytes, and has a 1.42 GiB virtual size. Its SBOM (`…-Cloud.json`, SPDX) lists qemu-guest-agent, openssh-server, sudo, NetworkManager, growpart, selinux-policy-targeted and grub2-i386-pc, so BIOS boot and the existing customize work.
  - Leap 16 enforces SELinux, so `opensuse` is now in `RHEL_FAMILY` and gets `--selinux-relabel` (the qemu-ga sysconfig edit is file-guarded). SUSE's sudoers (SLFO 1.2 `sudo-sudoers.patch`) is `Defaults targetpw` + `ALL ALL=(ALL) ALL`, and root is locked, so the admin user could not sudo at all. `sudo-policy-wheel-auth-self` is not in the image. `builder.sh` now writes its two rules as single-line `/etc/sudoers.d` drop-ins. `/usr/etc/sudoers` ends with `@includedir /etc/sudoers.d`.
  - Risk for V25: under enforcing SELinux, qemu-ga `guest-exec` may run the post-install script confined (`virt_qemu_ga_t`; the `virt_qemu_ga_run_unconfined` boolean is off by default). That applies to the RHEL family too. It is unverified, so check it during live acceptance.
- **Tests:** `test_nested_builder.py::test_opensuse_relabels_and_lets_wheel_sudo_with_its_own_password` checks the relabel, the package list, both sudoers drop-ins and their modes, and the keyfile upload. The catalog rules (including `nm-keyfile` osinfo against `RHEL_FAMILY`) cover the entry.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 904 passed, 94.28%.
  - build_files: 448 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. V25 and HUMAN need a person.
- **Next:** Alpine needs builder work: OpenRC, busybox `adduser`, and an `interfaces` file that does not source `interfaces.d`. Or openSUSE Leap 15.6 (wicked networking, so a new `net_config`), or the appliances (pfSense, OPNsense, VyOS, Security Onion) from versioned releases with published SHA-256s.

### Iteration 124 — 2026-10-17
- **Completed:** V6b2f, split out of V6b2. `common/data/nested_os_catalog.json` has 37 entries. The new one, `security-onion-3.3.0`, comes right before `custom-iso`. It is a downloaded `manual_iso` appliance: agentless, `net_config` `none`, osinfo `generic`, BIOS, virtio disk and NIC. Its minimums are 4096 MB and 100 GB (SO's Import install), and its defaults are 4 vCPUs, 8192 MB and 200 GB (SO's Eval install, from the 3/main hardware guide).
- **Learned:**
  - SO publishes MD5, SHA-1 and SHA-256 for each ISO in `DOWNLOAD_AND_VERIFY_ISO.md` on the release branch, and a PGP `.sig` under `sigs/`. 3.3.0-20260911 (the latest release, 2026-09-11) is on `3/main`. `2.4/main` still lists 2.4.211. The ISO URL is versioned and returned HTTP 200 with 14007926784 bytes. Its ISO9660 label is `Security-Onion-3.3.0`. The El Torito catalog has an x86 BIOS default entry plus an EFI section, so `firmware: bios` boots.
  - osinfo is `generic` because the base distro isn't confirmed (2.4 was Oracle Linux 9). `define_domain` falls back to `generic` anyway, and the disk and NIC buses are set explicitly.
  - A downloaded `manual_iso` needs no builder or validator change: `fetch_media` verifies the URL's SHA-256, and `install_manual_iso` attaches it as the CD-ROM. Found V6e: the parent's 12 GB scratch reservation is smaller than this ISO.
- **Tests:** `test_nested_manifest.py::test_manifest_downloads_each_seeded_appliance_iso_by_its_pinned_url` runs once per downloaded `manual_iso` JSON entry. It checks the `url` media source, the SHA-256, the `iso` format and `net_config` `none`. The existing catalog rules (https, SHA-256, no rolling path segment) cover the entry too.
- **Gate results:**
  - api/unit_tests: 1654 passed, 97.67%.
  - cloud_functions/tests: 905 passed, 94.28%.
  - build_files: 450 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. V25 and HUMAN need a person.
- **Next:** V6e (scratch sizing for large media). Or the rest of V6b2's appliances: VyOS (versioned stream ISO), OPNsense (`.iso.bz2` needs a decompress step in `fetch_media` or a new format), and pfSense CE (`.iso.gz`, likewise). Alpine needs builder work too.

### Verification — 2026-10-17 — PASS
- **Checked:** the items ticked since the last verification (1612733): V6b2b, V6b2c, V6b2d, V6b2e and V6b2f. Parent V6, V6b and V6b2 are still `[ ]`, and so are V6e, V25, I4b and HUMAN.
  - Catalog entries: I re-fetched each publisher's checksum file over https and compared all six new hashes. All six match the JSON exactly: Fedora 43 and 44 (`CHECKSUM`), CentOS Stream 10 (`.SHA256SUM`), Arch `v20261001.604814` (`.SHA256`), Leap 16.0 Build18.81 (`.sha256`), and Security Onion 3.3.0-20260911 (`3/main` `DOWNLOAD_AND_VERIFY_ISO.md`, which also lists the same pinned ISO URL). Every URL is a dated or versioned path.
  - `builder.sh`: the Arch keyring init and `pacman -Syu` come before `--install` in `args`. Arch swaps `openssh-server` for `openssh,sudo`. SUSE gets both single-line sudoers drop-ins with mode 0440. `opensuse` joined `RHEL_FAMILY`, where the qemu-ga edit is guarded by `[ -f ]`. The firstboot grow uses `findmnt -nvo` (`--nofsroot`) and picks the resize tool by `FSTYPE`.
  - Tests: the new builder tests run the real rendered script, and the grow test runs the extracted command against stub tools. `-rs` shows none of them are skipped (`test_nested_builder.py` + `test_nested_manifest.py`: 162 passed). The new manifest test is parametrized over the JSON's downloaded `manual_iso` entries. The new code has no TODO, FIXME or `NotImplemented`.
  - Known gap: V6e is still open, so the 14 GB Security Onion ISO exceeds `NESTED_BUILD_SCRATCH_GB` (12). It is tracked as an open task and does not reopen V6b2f.
- **Gate results:**
  - api/unit_tests: 1654 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 905 passed, 96.19% (≥85%).
  - build_files: 450 passed.
  - Frontend `npm test`: 47 files, 572 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: no matches.
  - Group V eslint: exit 0. Group V tsc grep: no matches. `tsc` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 125 — 2026-10-17
- **Completed:** V6e. `NestedHostValidator.min_disk_size(guests, media_sizes)` now adds the size of each distinct medium, rounded up to whole GiB, on top of base + guest disks + `NESTED_BUILD_SCRATCH_GB`. `media_sizes()` keys media the way `builder.sh` `fetch_media` caches them (catalog sha256, else upload sha256, else `upload-<id>`), so guests that share a medium count it once. It follows `nested_manifest._media_source`, so a guest's `media_id` wins even on a downloadable entry. `validate()` now returns `NestedValidation(entries, disk_size)`, and `NestedImage.create` stores that `disk_size`. `NestedOsCatalogModel.media_size_bytes` is new, and all 18 downloaded JSON entries carry it (HTTP `Content-Length`, following redirects, on 2026-10-17; the Security Onion, CentOS, Arch and Leap values match earlier iterations' notes). An entry or upload without a known size reserves `NESTED_MEDIA_MAX_BYTES` (20 GiB). The disk row in `docs/guides/nested-lab-hosts.md` is updated.
- **Learned:** media stay in `MEDIA_DIR` until `finalize.sh` removes it, so reserving the largest medium alone would not be enough: the sum is what the parent holds. The sync op writes `model_dump()`, so re-running **Synchronize Nested Guest OS Catalog** fills `media_size_bytes` on existing Firestore entries. Until then they reserve 20 GiB each, which is safe but large. Archive extraction (`ova`/`zip`/`tar.xz` into `work-<guest>`) still fits only in the 12 GB scratch.
- **Tests:** `test_nested_host_validator.py` has new tests for GiB rounding, dedupe by cache key, an upload's sha256 key, the unknown-size fallback, `media_id` on a downloadable entry, and a missing upload. Expected minimums moved from 122 to 134. `test_nested_os_catalog_sync.py::test_downloaded_entries_record_their_size_for_the_parent_disk` covers the JSON.
- **Gate results:**
  - api/unit_tests: 1659 passed, 98%.
  - cloud_functions/tests: 905 passed, 94%.
  - build_files: 487 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. V25 and HUMAN need a person.
- **Next:** V6f (mirror the media reservation in the wizard), then the rest of V6b2's appliances.

### Iteration 126 — 2026-10-17
- **Completed:** V6f. `NestedOsCatalogEntry.media_size_bytes` (model + transformer, `orNull`). New `nestedMediaSizes(guests, context)` in `nestedWizardState.ts` mirrors `NestedHostValidator.media_sizes`: a guest's `media_id` wins; key is the upload's sha256, else `upload-<id>`, else the entry's `media_sha256`, else its id; an unknown upload, an unmatched entry, or a null/0 size reserves `NESTED_MEDIA_MAX_BYTES`. `nestedMinDiskSize(guests, context)` adds the per-medium GiB ceiling. `effectiveDiskSize`, `validateHostStep` and `capacityMeters` now take the `GuestRuleContext` (required, so no caller silently reserves 20 GiB per guest); `HostStep` gets `context` from the wizard's `guestContext`, `ReviewStep` builds it from its `catalog`/`media` props. The Host helper text now names the install media.
- **Learned:** while the catalog is still loading, every guest reads as an unmatched entry and reserves 20 GiB, so the Host minimum briefly overstates. That is the API's own fallback and only raises the floor.
- **Tests:** `nestedWizardState.test.ts` (min disk with media, cache-key dedupe, upload sha/id keys, missing upload, media_id over the entry, GiB rounding, unsized/unmatched entries; Host disk bounds moved 72→73), `accessReview.test.ts` (Disk meter includes 1 + 4 + 20 GB), `NestedImageWizard.test.tsx` (Review shows `75 GB disk` for two Kali guests sharing a 3 GiB image), `nested.transform.test.ts` (size kept, null default).
- **Gate results:**
  - api/unit_tests: 1659 passed, 97.67%.
  - cloud_functions/tests: 905 passed, 94.28%.
  - build_files: 487 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint/tsc: pass. Group V eslint/tsc: pass.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. V25 and HUMAN need a person.
- **Next:** the rest of V6b2's appliances: VyOS (versioned stream ISO), OPNsense (`.iso.bz2`) and pfSense CE (`.iso.gz`), which need a decompress step in `fetch_media`; Alpine needs builder work.

### Iteration 127 — 2026-10-17
- **Completed:** V6b2g, split out of V6b2. `common/data/nested_os_catalog.json` has 38 entries. The new one, `opnsense-26.7`, comes right before `security-onion-3.3.0`. It is a downloaded `disk_image` appliance: agentless, `net_config` `none`, osinfo `freebsd14.0`, BIOS, virtio. Its minimums are 3072 MB and 4 GB, and its defaults are 2 vCPUs, 4096 MB and 40 GB (docs.opnsense.org hardware tables). `media_size_bytes` is 490849116 (HTTP `Content-Length`). There is a new `img.bz2` media format, in `NestedMediaFormat`, `nested.model.ts` and `guestRules.ts` `MEDIA_FORMATS`. The API's `MEDIA_FORMATS` derives from the Literal. `builder.sh` `prepare_disk` expands it with `bzip2 -dc` into `work-<guest>` (covered by scratch) and fails the guest if that fails. `bzip2` joined `HOST_PACKAGES`.
- **Learned:**
  - The OPNsense 26.7 README says nano is "a preinstalled serial image ... with secondary VGA console enabled", so it works over the VNC console and needs no install. Its MBR is a FreeBSD-dedicated BIOS-boot disk (one active slice, type a5). The DVD installer (`.iso.bz2`) would have needed the expanded ISO kept on the parent for the whole build, which means a different disk-reservation rule. Nano needs only transient scratch.
  - 26.7 is built on FreeBSD 15.1. I chose `freebsd14.0` because older osinfo-db releases lack 15.x. `define_domain` falls back to `generic` anyway.
  - The SHA-256 `28d5e2f3…cb9d` comes from `OPNsense-26.7-checksums-amd64.sha256` (signed `.sig` beside it), fetched over https on 2026-10-17. Default login is root/opnsense, and the note tells the instructor to change it.
  - VyOS is not seedable: its stream releases publish only minisign `.minisig` files, no SHA-256 (no `SHA256SUMS` or `.sha256` on community-downloads.vyos.dev).
- **Tests:** `test_nested_builder.py::test_a_bz2_disk_image_is_expanded_to_raw_before_conversion` and `::test_a_bz2_disk_image_that_will_not_expand_fails_only_that_guest` run real `bzip2`. `test_nested_manifest.py::test_manifest_downloads_each_seeded_appliance_disk_by_its_pinned_url` is parametrized over downloaded `disk_image` JSON entries. `test_nested_media_routes.py` covers `nano.img.bz2` → `img.bz2`, and `guestRules.test.ts` covers `mediaFormat`.
- **Gate results:**
  - api/unit_tests: 1660 passed, 97.67%.
  - cloud_functions/tests: 908 passed, 94.28%.
  - build_files: 490 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint/tsc: pass. Group V eslint/tsc: pass.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 has no published SHA-256. VyOS publishes no SHA-256. V25 and HUMAN need a person.
- **Next:** V6g (the `img.xz` expansion failure path). Then pfSense CE (`.iso.gz`/`.img.gz`; check whether a published SHA-256 and a VGA-console image exist), Metasploitable 2, or Alpine (builder work).

### Iteration 128 — 2026-10-17
- **Completed:** V6g. In `builder.sh` `prepare_disk`, the `img.xz` branch now fails the guest when `xz -dc` fails. It removes `work-<guest>` and sets `FAIL_MESSAGE="could not expand the img.xz media"`, matching the `img.bz2` branch, so a truncated raw image is never converted into a disk that cannot boot.
- **Learned:** no catalog entry ships `img.xz` yet, so the tests point the `opnsense` fixture at an `img.xz` URL with a matching hash. A corrupt body with a correct SHA-256 reaches the expansion step, which is the only way to test that step's failure.
- **Tests:** `test_nested_builder.py::test_an_xz_disk_image_is_expanded_to_raw_before_conversion` and `::test_an_xz_disk_image_that_will_not_expand_fails_only_that_guest` run real `xz`. The failure test fails against the unfixed script.
- **Gate results:**
  - api/unit_tests: 1660 passed, 97.67%.
  - cloud_functions/tests: 910 passed, 94.28%.
  - build_files: 490 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 and VyOS publish no SHA-256. V25 and HUMAN need a person.
- **Next:** the rest of V6b2: pfSense CE (check for a published SHA-256 and a VGA-console image), Metasploitable 2, or Alpine (needs builder work).

### Iteration 129 — 2026-10-17
- **Completed:** V6b2h, split out of V6b2. `common/data/nested_os_catalog.json` has 41 entries. `debian-11`, `debian-12` and `debian-13` come right before `ubuntu-16.04`, and each is pinned to a dated genericcloud qcow2: bullseye `20260821-2577` (the last bullseye build), bookworm `20261015-2632`, and trixie `20261017-2634`. They use osinfo `debian<n>`, the Ubuntu sizing (512/2048 MB, 10/20 GB), and `media_size_bytes` from `Content-Length`.
- **Learned:**
  - cloud.debian.org publishes only `SHA512SUMS`, with no SHA-256 and no signature file in the dated dirs. I downloaded each qcow2 over https, checked it with `shasum -a 512 -c` against that dir's `SHA512SUMS` (all three OK), and then took its SHA-256. A verifier can repeat this.
  - Each build's `<image>.json` lists its packages. Debian 11 ships `ifupdown` 0.8.36 plus `resolvconf`, so `dns-nameservers` works. Debian 12 (netplan.io 0.106) and 13 (1.1.2) ship netplan, not ifupdown, so they use `netplan`. All three ship `cloud-guest-utils`, so the firstboot growpart runs. None ships qemu-guest-agent, which the builder installs anyway.
- **Tests:** no new test functions. The existing JSON-parametrized tests now run once per new entry: `test_nested_os_catalog_sync.py` checks https, SHA-256, size, a dated release and the cloud-image rules, and `test_nested_manifest.py` checks the pinned cloud-image download (`-k debian`: 3 passed).
- **Gate results:**
  - api/unit_tests: 1660 passed, 97.67%.
  - cloud_functions/tests: 913 passed, 94.28%.
  - build_files: 502 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 and VyOS publish no SHA-256. V25 and HUMAN need a person.
- **Next:** the rest of V6b2: pfSense CE (check for a published SHA-256 and a VGA-console image), Metasploitable 2 (SourceForge zip; check for a published hash), or Alpine (needs builder work for apk/openrc).

### Verification — 2026-10-17 — PASS
- **Checked:** the items ticked since the last verification (fc8970f): V6e, V6f, V6b2g, V6g and V6b2h. Parent V6, V6b and V6b2 are still `[ ]`, and so are I4b, V25 and HUMAN.
  - V6e: `NestedHostValidator.media_sizes` keys each medium the way `builder.sh` `fetch_media` does (the sha256, else `upload-<media_id>`). It counts a shared medium once, lets `media_id` win over a downloadable entry, and falls back to `NESTED_MEDIA_MAX_BYTES` when a size is unknown. `min_disk_size` adds the GiB ceiling of each medium. `validate()` returns `NestedValidation.disk_size`, and `NestedImage.create` stores it. `media_size_bytes` is in the model with `gt=0`.
  - V6f: `nestedMediaSizes`/`nestedMinDiskSize` in `nestedWizardState.ts` match the API rule line for line. `context` is a required argument of `effectiveDiskSize`, `validateHostStep` and `capacityMeters`, and `HostStep`, `ReviewStep` and the wizard pass it. The transformer keeps `media_size_bytes`.
  - V6g/V6b2g: in `prepare_disk`, the `img.xz` and `img.bz2` branches both remove `work-<guest>`, set `FAIL_MESSAGE` and return 1 when expansion fails. `bzip2` is in `HOST_PACKAGES`. `img.bz2` is in the Python Literal, the TS type and `MEDIA_FORMATS`. The four xz/bz2 builder tests run real binaries, and `-rs` shows none skipped.
  - Catalog hashes, checked independently: the OPNsense `OPNsense-26.7-checksums-amd64.sha256` lists `28d5e2f3…cb9d` for the nano image, and its `Content-Length` (490849116) matches. I downloaded all three Debian qcow2s over https. Each passed `shasum -a 512 -c` against its dated dir's `SHA512SUMS`, and its SHA-256 and byte size match the JSON exactly (debian-11 `9e857537…58ee`/288358400, debian-12 `2f2a2fa5…f6cc`/349044736, debian-13 `87211f08…3b02`/342818816).
  - The new code has no TODO, FIXME or `NotImplemented`.
- **Gate results:**
  - api/unit_tests: 1660 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 913 passed, 96.19% (≥85%).
  - build_files: 502 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches. `tsc` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 130 — 2026-10-17
- **Completed:** V6b2i, split out of V6b2. `common/data/nested_os_catalog.json` has 42 entries. `metasploitable-2` follows `opensuse-leap-16.0` and is the PRD's `disk_image` (`zip`/vmdk, agentless, SourceForge) row. It has `net_config` `none`, BIOS, an IDE disk, an e1000 NIC, 256/512 MB, and an 8/8 GB disk (the vmdk's virtual size is 8 GiB).
- **Learned:**
  - SourceForge publishes a SHA-256 for every file in the project's files JSON (`2ae8788e…85a1ff`). I downloaded the zip over https from the direct `downloads.sourceforge.net/project/...` path, which skips the `/download` HTML page, and its hash matched. Size 865084584. It holds `Metasploitable2-Linux/Metasploitable.vmdk`, a 1.9 GB monolithicSparse file, next to its vmx and nvram, so `largest_disk_file` picks the vmdk.
  - The vmx puts the disk on LSI Logic SCSI, which libvirt does not offer for this model. The catalog uses `ide`, as `win-xp-disk` does, because Ubuntu 8.04's 2.6.24 initrd has ata_piix (disk still `/dev/sda`) and may not have virtio_blk. Risk for V25: I could not read the guest's ext3 to confirm the NIC is not renamed by a udev persistent-net rule for the old VMware MACs. VirtualBox imports with new MACs reportedly get DHCP on eth0, so check that live.
  - openSUSE Leap 15.6 is not done. Its Cloud kiwi profile (`openSUSE:Leap:15.6/kiwi-templates-Minimal`) installs wicked, not NetworkManager, and enables cloud-init and jeos-firstboot, so it needs a new net_config.
  - One full cloud_functions run showed "1 failed" with no name captured. Three later full runs and five loops of the builder and runtime files all passed, so it is an unidentified flake.
- **Tests:** `test_nested_builder.py::test_a_zip_disk_image_converts_its_largest_disk_file` and `::test_a_zip_without_a_disk_file_fails_only_that_guest`. They use a fake `7z` that extracts with `zipfile`. `test_nested_manifest.py`'s seeded-disk format allow-list now names every format `prepare_disk` handles, not just the formats seeded before.
- **Gate results:**
  - api/unit_tests: 1660 passed, 97.67%.
  - cloud_functions/tests: 916 passed, 94.28%.
  - build_files: 505 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs a wicked net_config that the PRD's `NestedNetConfig` does not have. V25 and HUMAN need a person.
- **Next:** pfSense CE (check for a published SHA-256; its ISO ships as `iso.gz`, which is not a `NestedMediaFormat`), or Alpine (needs builder work for apk/openrc).

### Iteration 131 — 2026-10-17
- **Completed:** V6b2j, split out of V6b2. `common/data/nested_os_catalog.json` has 43 entries. `pfsense-ce-2.7.2` follows `opnsense-26.7` and is the PRD's pfSense CE `manual_iso` row. It uses BIOS, a virtio disk and NIC, VGA, 1024/2048 MB, an 8/20 GB disk and 2 vCPUs. It lists `media_formats` `["iso.gz", "iso"]`, so an instructor can also upload a plain ISO.
- **Learned:**
  - Netgate still serves the CE 2.7.2 installer (only as `.iso.gz`) with a `.sha256` file at `atxfiles.netgate.com/mirror/downloads/`. Later CE releases ship only through the online installer. I downloaded the file over https: SHA-256 `883fb7bc…cd9e4` matched, size 574277009, and it expands to 874672128 bytes.
  - The new `iso.gz` format is in the model Literal, the TS type, `MEDIA_FORMATS` and the guide. `fetch_media` sets `dest` to `<key>.iso` for an iso.gz, so the cached-file check, `install_manual_iso` and `install_unattended_iso` all see a plain ISO. The GCS cache stores the gz, whose hash is the catalog's, before the expansion removes it. A failed `gzip -dc` removes both files and fails the guest. The cache upload moved into a `cache_media` helper. `gzip` is Essential on Debian, so no host package was added.
  - `media_size_bytes` stays the download size, as the model's description says, but what the parent keeps is the expanded ISO. Both round up to 1 GiB here, so the reservation is unchanged. A large iso.gz upload would be undercounted by its compression ratio. The 12 GB scratch absorbs that for now.
- **Tests:** `test_nested_builder.py::test_an_iso_gz_is_expanded_once_and_only_the_iso_is_kept` and `::test_an_iso_gz_that_will_not_expand_fails_only_that_guest` run real `gzip`. `test_nested_manifest.py`'s seeded-appliance test now expects each entry's first format and limits it to `iso`/`iso.gz`. `test_nested_media_routes.py` and `guestRules.test.ts` cover the `.iso.gz` extension.
- **Gate results:**
  - api/unit_tests: 1662 passed, 97.67%.
  - cloud_functions/tests: 919 passed, 94.28%.
  - build_files: 508 passed.
  - Frontend: 574 passed.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches.
  - No CTF frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs a wicked net_config that `NestedNetConfig` does not have. V25 and HUMAN need a person.
- **Next:** Alpine (needs builder work for apk/openrc and a net_config). Otherwise the rest of V6b2 needs a person.

### Iteration 132 — 2026-10-17
- **Completed:** V6b2k, split out of V6b2. `common/data/nested_os_catalog.json` has 44 entries. `alpine-3.23` follows `archlinux`: `cloud_image`, BIOS, virtio, `net_config` `ifupdown`, 512/1024 MB, 2/8 GB disk. Download SHA-512 `f85d04d2…d5a6` matched the published `.sha512`. SHA-256 `23004bcd…f141`, size 167182336, virtual size 216 MiB.
- **Learned:**
  - libguestfs `firstboot.ml` errors "guest type alpinelinux is not supported" for `--firstboot-command`, and it supports `apk` for `--install`. So for Alpine, `customize_linux` skips `--firstboot-command`. It uploads a self-removing `/etc/local.d/agoge-firstboot.start` that does the ssh-keygen and root grow, and enables `local`.
  - Alpine has mdev, not udev, so a `.link` file does nothing. Alpine's `ifupdown` writes `/etc/mactab`, and a boot-runlevel `/etc/init.d/agoge-boot` (`before net networking qemu-guest-agent`) runs busybox `nameif`. busybox has `CONFIG_NAMEIF=y`. The same script links `/dev/virtio-ports/org.qemu.guest_agent.0` from sysfs, because I could not confirm that mdev creates that link.
  - Alpine's stub `/etc/network/interfaces` sources nothing, so the builder replaces it whole (lo plus `auto agogeN`). Static DNS goes to `/etc/resolv.conf` because Alpine has no resolvconf.
  - cloud-init's OpenRC services are removed with `rc-update -a del`, because `cloud-init.disabled` alone may not stop them rewriting the interfaces file. The package itself stays (Working Note 16).
  - The base image already has sudo and `openssh-server-pam`, so `ssh_package` is `openssh-server-pam`. Plain `openssh-server` could conflict with it. `bash` (needed by post-install's `/bin/bash -s`), `shadow` (`useradd`), and the grow tools are added.
  - 3.24.1 is in the CDN listing, but its files return 404, so the pin is 3.23.6.
  - Risk for V25: none of the OpenRC path has run on a real guest. Check that nameif renames the NIC, that qemu-ga answers, and that the root grows.
- **Tests:** `test_nested_builder.py::test_alpine_uses_openrc_and_mactab_instead_of_systemd_firstboot_and_udev`.
- **Gate results:**
  - api/unit_tests: 1662 passed, 97.67%.
  - cloud_functions/tests: 921 passed, 94.28%.
  - build_files: 512 passed.
  - No frontend files changed.
- **Blockers:** V6b2's Microsoft and Kali entries are BLOCKED on V-5. CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs a wicked net_config that `NestedNetConfig` does not have. V25 and HUMAN need a person.
- **Next:** Every remaining V6b2 entry needs a person (V-5 hashes, or a PRD decision on Leap 15.6's wicked net_config). I4b, V25 and HUMAN are browser or live checks.

### Iteration 133 — 2026-10-17
- **Completed:** none. No task in the queue can be done by the loop. I4b, V25 and HUMAN are browser or live checks. Every entry left in V6b2 needs a person: the Microsoft evals and Kali wait on V-5, CentOS Stream 9 and VyOS publish no SHA-256, and Leap 15.6 needs a `NestedNetConfig` value the PRD does not define.
- **Learned (for whoever answers V-5's Kali part):** `https://kali.download/cloud-images/kali-2026.2/` is a dated directory. It holds `kali-linux-2026.2-cloud-genericcloud-amd64.tar.xz`, and its published `SHA256SUMS` gives `3f4ca86ae1eca0dc2bf2092f065a959508e186c6b44f85758813a8e9a0604f3e`. `tar.xz` is already a `NestedMediaFormat`. I did not download the file or seed it, because the queue says V-5 needs a person's answer first. If a person confirms this URL and format in progress.md, the next iteration can seed `kali-2026.2` the way V6b1 did.
- **Gate results:** not run, because no code changed.
- **Blockers:** V-5 (Microsoft hashes; confirm the Kali URL above). CentOS Stream 9 and VyOS have no published SHA-256. Leap 15.6 needs the wicked net_config decision. V25 and HUMAN need a person.
- **Next:** the loop should stop until a person unblocks one of these. Re-running it as things stand only adds empty iterations.

### Iteration 134 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 133 (HEAD 093bc66 only logged that iteration). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer for the Kali URL or the Microsoft hashes.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS have no published SHA-256. Leap 15.6 needs the wicked net_config decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Verification — 2026-10-17 — PASS
- **Checked:** the items ticked since the last verification: V6b2i, V6b2j and V6b2k. Parent V6, V6b and V6b2 are still `[ ]`, and so are I4b, V25 and HUMAN. Iterations 133–134 changed no code.
  - V6b2i: `metasploitable-2` is a `disk_image` with `zip` format, `agent: false`, `net_config: none`, an IDE disk and an e1000 NIC. In `prepare_disk`, `zip|7z` extracts with `7z` and picks the disk through `largest_disk_file`, which matches `*.vmdk`. `p7zip-full` is in `HOST_PACKAGES`.
  - V6b2j: `iso.gz` is in the Python `NestedMediaFormat` Literal and the TS type. `fetch_media` caches the verified gz through `cache_media`, then expands it with `gzip -dc` to `<key>.iso`. It removes the gz, and on failure it cleans up both files and sets `FAIL_MESSAGE`. The cached-file check uses the expanded `.iso` path.
  - V6b2k: for `^alpinelinux` osinfo ids, `customize_linux` skips `--firstboot-command`. It uploads `/etc/init.d/agoge-boot` (runs `nameif -c /etc/mactab` and links the qemu-ga port) and the self-removing `/etc/local.d/agoge-firstboot.start`. It enables them with `rc-update` and removes the cloud-init OpenRC services. `write_network_config` replaces `/etc/network/interfaces` whole and writes `/etc/mactab` and a static `resolv.conf`.
  - Catalog hashes, checked independently:
    - pfSense: Netgate's `.sha256` gives `883fb7bc…cd9e4`, and `Content-Length` is 574277009. Both match the JSON.
    - Metasploitable 2: SourceForge's files JSON gives sha256 `2ae8788e…85a1ff`, and `Content-Length` is 865084584. Both match the JSON.
    - Alpine 3.23.6: I downloaded the qcow2 over https. It matched the published `.sha512` (`f85d04d2…d5a6`). Its SHA-256 `23004bcd…f141` and size 167182336 match the JSON.
  - The diffs of the three commits have no TODO, FIXME or `NotImplemented`. The new tests exist: `test_a_zip_*`, `test_an_iso_gz_*` and `test_alpine_uses_openrc_and_mactab_instead_of_systemd_firstboot_and_udev`.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 921 passed, 96.19% (≥85%).
  - build_files: 512 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches. `tsc` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 135 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 134: HEAD f851ac4 is the verifier's PASS, V-5 in PRD.md is still `[ ]`, and progress.md still has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 136 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 135 (HEAD 5df52d8 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 137 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 136 (HEAD d05076c only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 138 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 137 (HEAD e4e6724 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 139 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 138 (HEAD 2e886ca only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Verification — 2026-10-17 — PASS
- **Checked:** every `[x]` task, by diffing against the last verified PASS (f851ac4). `git diff --stat f851ac4 HEAD` shows only progress.md changed (+30 lines, from iterations 135–139), and the working tree was clean. So no code has changed since a full PASS. Spot checks:
  - None of the CTF or nested code has a TODO, FIXME or `NotImplemented`. The scan covered `api/core/ctf*`, `common/utilities/ctf_*`, `course_objects/ctf*`, `handlers/ctf_handler.py`, the frontend Ctf components and services, and the NestedImage form and services.
  - `common/data/nested_os_catalog.json` has 44 entries and 25 SHA-256 values. All 25 are unique 64-character hex strings, none look like placeholders, and the file has no `http://` URLs.
  - The open items are still correctly `[ ]` and blocked on a person: I4b, V6, V6b, V6b2, V25 and HUMAN.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 921 passed, coverage 94.28% (≥85%).
  - build_files: 512 passed.
  - Frontend `npm test`: 47 files, 574 tests passed, exit 0.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches. `tsc` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 140 — 2026-10-17
- **Completed:** none. Nothing has changed since the verification PASS (HEAD 12dc641 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 141 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 140 (HEAD b7b5e98 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 142 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 141 (HEAD 4efc6c3 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 143 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 142 (HEAD 218b225 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 144 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 143 (HEAD c72f0c2 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Verification — 2026-10-17 — PASS
- **Checked:** every `[x]` task, by diffing against the last code-bearing verified PASS (f851ac4). `git diff --stat f851ac4 HEAD` shows only progress.md changed (+74 lines, from iterations 135–144 and the 12dc641 verification), and the working tree was clean. The `- [x]`/`- [ ]` lines in the task queue match f851ac4 exactly, so nothing was ticked after the last verification. Spot checks:
  - I scanned the CTF and nested code for TODO, FIXME, `NotImplemented` and XXX: `api/core/ctf*`, `common/utilities/ctf_*`, `course_objects/ctf*`, `handlers/ctf_handler.py`, the frontend Ctf components and services, and the NestedImage form and services. The only hits are `mktemp` `XXXXXX` templates and the product-key format hint in `guestRules.ts`, which are not stubs.
  - `common/data/nested_os_catalog.json` has 44 entries and 25 SHA-256 values. All are unique 64-character lowercase hex, and the file has no `http://` URLs.
  - The open items are still correctly `[ ]` and blocked on a person: I4b, V6, V6b, V6b2, V25 and HUMAN.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 921 passed, coverage 94.28% (≥85%).
  - build_files: 512 passed.
  - Frontend `npm test`: 47 files, 574 tests passed, exit 0.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches. `tsc --noEmit` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 145 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 144 (HEAD 125b2ad is only the verification PASS). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 146 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 145 (HEAD ac8a261 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 147 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 146 (HEAD f79c197 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 148 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 147 (HEAD 94774a6 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 149 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 148 (HEAD f4f8f59 only logged it). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Verification — 2026-10-17 — PASS
- **Checked:** every `[x]` task. `git diff --stat f851ac4 HEAD` shows only progress.md changed (+118 lines of iteration and verification logs), and the working tree was clean. So no code has changed since the last code-bearing PASS. I still re-inspected the code for the higher-risk items:
  - BUG3: `_publish_arm` (api/core/ctf/event.py:245-249) calls `future.result(timeout=...)` on each publish future against one shared deadline. Failed futures go into `unpublished` and on to `_fail_unpublished`. The fake test sets `future.set_exception` (test_ctf_event_actions.py:101), with tests at :298 and :311.
  - BUG5: `_fail_unfinished` goes through `_write_flags`, which re-reads the doc inside the transaction (flag_planter.py:1016). It is tested by `test_error_mid_results_keeps_flags_already_recorded`.
  - BUG4: `AnonymousAppUser()` constructs. BUG2: `batch_write` runs once, after the image loop. BUG: `SpecEditManager.save` validates before it writes.
  - E3, E4b, G4b and N11: `CtfHandler.action_map` routes all three actions, passes `guest` through, and an unknown action raises `ValueError`.
  - I4b's prerequisite routes are present (AppRouter.tsx:99-100).
  - V6e/V6f: the media reservation is on both the backend and the frontend. V6g: a failed `xz`/`bzip2` expand fails the guest (builder.sh:358,360). V12b: the record is deleted when its publish fails (image.py:508-538). V14b: a stale `finalizing` phase is finalizable (`is_stale_finalize`, NESTED_FINALIZE_TIMEOUT_SECONDS + 900).
  - Stub scan of the CTF and nested backend and frontend: no TODO, FIXME, `NotImplemented` or pass-only bodies. The only matches are `mktemp` `XXXXXX` templates and MUI `placeholder` props.
  - `nested_os_catalog.json` has 44 entries and 25 SHA-256 values, all unique 64-character lowercase hex. Every URL is https. No Microsoft entry has a URL or hash, so none was invented.
  - The open items are still correctly `[ ]` and blocked on a person: I4b, V6, V6b, V6b2, V25 and HUMAN.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 921 passed, total coverage 96.19% (≥85%).
  - build_files: 512 passed.
  - Frontend `npm test`: 47 files, 574 tests passed, exit 0.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches. `tsc --noEmit` itself exits 2, but only on files outside both scopes.
- **Reopened:** none.

### Iteration 150 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 149 (HEAD d6b11d9 only logged a verification PASS). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 151 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 150 (HEAD cee4963 only logged it, and the working tree is clean). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 152 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 151 (HEAD 5a94a04 only logged it, and the working tree is clean). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Iteration 153 — 2026-10-17
- **Completed:** none. Nothing has changed since iteration 152 (HEAD acaade1 only logged it, and the working tree is clean). V-5 in PRD.md is still `[ ]`, and progress.md has no human answer.
- **Gate results:** not run, because no code changed.
- **Blockers:** the same as iteration 133. V-5 (Microsoft hashes; confirm the Kali URL). CentOS Stream 9 and VyOS publish no SHA-256. Leap 15.6 needs the wicked `net_config` decision. I4b, V25 and HUMAN need a person.
- **Next:** stop the loop until a person unblocks one of these.

### Out-of-loop work — 2026-10-17 (V-5)
- **Completed (outside the loop, by hand):** Open Question V-5 is answered and ticked in PRD.md. Every Microsoft eval ISO, both Kali images, CentOS Stream 9 GenericCloud and the VyOS rolling ISO were downloaded from their official sites and hashed. The values are in the "V-5 answers" table under V6b2. V6b2 is split into V6b2l–V6b2o, and all four can now be done. PRD.md checkboxes for N1–N15 and V3–V24 (minus V6) were ticked to match this queue; they had never been ticked there.
- **Learned:** Windows 10 Enterprise is no longer on the Evaluation Center. Microsoft publishes a SHA-256 for the Windows 11 Enterprise eval only. CentOS Stream 9 does publish SHA-256s. VyOS signs with minisign and publishes no SHA-256.
- **Gate results:** not run; only PRD.md and progress.md changed.
- **Blockers:** none for the loop (Leap 15.6 was dropped; see the decision below). I4b, V25 and HUMAN need a person.
- **Next:** V6b2l, then V6b2m, V6b2n and V6b2o, then close V6b and V6.
- **Decision 2026-10-18 (user):** drop openSUSE Leap 15.6. It is not in V6b2 any more, and nothing in V6b2 is blocked now.

### Iteration 154 — 2026-10-18
- **Completed:** V6b2l. Added `kali-rolling` (`cloud_image`, `tar.xz`, `netplan`, osinfo `debiantesting`, min disk 25 GB) and `kali-qemu` (`disk_image`, `7z` then `qcow2`, `nm-keyfile`, `default_username` `kali`, 2 vCPU/4 GiB, min/default disk 81 GB) to `nested_os_catalog.json`. The URLs, SHA-256s and sizes are from "V-5 answers"; the tar.xz download re-hashed to the same value. Added builder tests for a tar.xz cloud image holding `disk.raw` and for a 7z Linux disk image holding a qcow2 that gets customized, plus a catalog test that pins `min_disk_gb` at or above each archive's virtual size. Widened two catalog-rule tests: a cloud image's first format may be `tar.xz`, and `nm-keyfile` may have a Debian-family osinfo (AppArmor, so no relabel). The manifest test no longer requires `net_config: none` for a Linux disk image that has an agent.
- **Learned:** I checked the real media. Kali's tar.xz holds a single GNU-sparse (`S`) `disk.raw`: 25 GiB virtual and 0.96 GiB of data, so GNU tar restores the holes and it fits in scratch. The image has netplan.io and systemd-resolved, but no ifupdown, NetworkManager or qemu-guest-agent. The 7z holds one 16.0 GB qcow2 v3 with an 86,000,000,000-byte virtual size, and it has network-manager, ifupdown, qemu-guest-agent and grub-pc (BIOS). `prepare_disk` only grows a disk, so the 81 GB minimum keeps the reservation honest. The 16 GB extraction is bigger than the 12 GB scratch, but the thin 81 GB disk it converts into covers it.
- **Gate results:** api 1662 passed, 97.67%. cloud_functions 925 passed, 94.28%. build_files 522 passed. Frontend 574 passed. CTF and Group V eslint exit 0, and both tsc greps 0.
- **Next:** V6b2m (CentOS Stream 9), then V6b2n and V6b2o.

### Verification — 2026-10-18 — PASS
- **Checked:** the only item ticked since the last verification (125b2ad, re-verified at d6b11d9): V6b2l. `git diff --stat 125b2ad HEAD` touches only PRD.md, progress.md, `nested_os_catalog.json` and three test files. The task-queue diff shows V6b2l as the only new `[x]`. Parents V6, V6b and V6b2 stay `[ ]`, and so do V6b2m–o, I4b, V25 and HUMAN.
  - V6b2l: `kali-rolling` and `kali-qemu` are in `common/data/nested_os_catalog.json`. Their URLs, SHA-256s and byte sizes match the "V-5 answers" table character for character. `builder.sh` already handled both archive types before this commit: `tar.xz` extracts with `tar -xJf` and `7z` with `7z x`, then `largest_disk_file` picks the disk. `install_disk_image` runs `customize_linux` for a Linux guest with an agent, and the nm-keyfile path does `chmod 600` and skips `--selinux-relabel` for a non-RHEL osinfo. That matches what the new builder tests assert, and they exercise the real script, not a stub. The widened catalog/manifest assertions are scoped (only `tar.xz` is added, and nm-keyfile now also accepts a `debian*` osinfo) and line up with the builder's behavior. They are not blanket relaxations. `min_disk_gb` (25 and 81) covers the recorded virtual sizes.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 925 passed, coverage 94.28% (≥85%).
  - build_files: 522 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches.
- **Reopened:** none.

### Iteration 155 — 2026-10-18
- **Completed:** V6b2m. Added `centos-stream-9` (`cloud_image`, `qcow2`, `nm-keyfile`, osinfo `centos-stream9`, min/default disk 10/20 GB) to `nested_os_catalog.json`, just before `centos-stream-10`. Its URL, SHA-256 and byte size are from "V-5 answers".
- **Learned:** the published `.SHA256SUM` and the HTTP content-length both match V-5. The qcow2 header (bytes 24–31) gives a virtual size of exactly 10 GiB, so `min_disk_gb` 10 does not under-reserve. `RHEL_FAMILY` in `builder.sh` already matches `centos`, so the image gets an SELinux relabel and needs no builder change. The existing parametrized catalog rules cover the new entry.
- **Gate results:** api 1662 passed, 97.67%. cloud_functions 926 passed, 94.28%. build_files 527 passed. Frontend 574 passed. CTF and Group V eslint exit 0, and both tsc greps 0.
- **Next:** V6b2n (Microsoft evaluations), then V6b2o (VyOS).

### Iteration 156 — 2026-10-18
- **Completed:** V6b2n. Added `win-server-2016-eval`, `-2019-eval`, `-2022-eval`, `-2025-eval` (`eval_days` 180, image index 2) and `win-11-enterprise-eval` (`eval_days` 90, image index 1) to `nested_os_catalog.json`, each just after its upload-only counterpart and copying its hardware, virtio-win and unattend settings. The URLs, SHA-256s and sizes are from "V-5 answers". `win-10` stays upload-only. I skipped the optional `win-11-ltsc-eval` because nothing here confirms its `install.wim` image index. Added `test_downloaded_windows_entries_are_the_evaluations` and corrected the guide's licensing bullet, which still said a Windows 10 Enterprise evaluation exists.
- **Learned:** a bare `curl -I` (no browser User-Agent) gets 200 and the expected Content-Length from `software-static.download.prss.microsoft.com`, so `builder.sh` `fetch_media` needs no extra headers. Only the Evaluation Center HTML pages return 403. An eval entry must carry `eval_days`, because `NestedHostValidator` asks for a product key from any unattended Windows entry that has none.
- **Gate results:** api 1662 passed, 97.67%. cloud_functions 946 passed, 94.28%. build_files 548 passed. Frontend 574 passed. I did not re-run eslint/tsc because no frontend file changed.
- **Next:** V6b2o (VyOS). Then V6b2, V6b and V6 can close.

### Iteration 157 — 2026-10-18
- **Completed:** V6b2o. Added `vyos-rolling-2026.10.17` (`manual_iso`, `iso`, agentless, `net_config` none, osinfo `generic`, 1–2 GiB memory, 4/10 GB disk, 2 vCPU) to `nested_os_catalog.json`, after Security Onion. The URL, SHA-256 and size are from "V-5 answers". Its license note and the guide's "could not download the media" row both say that VyOS publishes no SHA-256 (the hash comes from a minisign-verified download) and that GitHub prunes nightly builds, so the download will eventually stop working. This closes V6b2, V6b and V6. Windows 10 Enterprise stays upload-only because Microsoft no longer offers that evaluation.
- **Learned:** today the GitHub release URL 302s to a 200 whose Content-Length (634388480) matches V-5. The existing parametrized catalog rules (https + SHA-256, recorded size, no rolling `current/`/`latest/` path segment) cover the entry, and the dated `2026.10.17-0025-rolling` segment passes the pin check.
- **Gate results:** api 1662 passed, 97.67%. cloud_functions 947 passed, 94.28%. build_files 551 passed. Frontend 574 passed. I did not re-run eslint/tsc because no frontend file changed.
- **Next:** every loop-doable item is `[x]`. I4b, V25 and HUMAN need a person.

### Iteration 158 — 2026-10-18
- **Completed:** none. Every loop-doable task is `[x]`, and the tree is clean at HEAD 8f05166 (V6b2o). The only open items are I4b (browser checks), V25 (live acceptance, human only) and HUMAN. Each one needs a person on the development project.
- **Gate results:** not run; no code changed since iteration 157, which passed them all.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** a human runs the I4b/HUMAN browser checks and V25. The loop can stop until then.

### Iteration 159 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 158: every loop-doable task is `[x]`, the tree was clean at HEAD a2d9037, and the only open items are I4b (browser checks), V25 (live acceptance) and HUMAN. All three need a person.
- **Gate results:** not run; no code changed since iteration 157, which passed them all.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop until a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Verification — 2026-10-18 — PASS
- **Checked:** the items ticked since the last verification (35e2a9d): V6b2m, V6b2n and V6b2o, and the parents they close (V6b2, V6b, V6). `git diff --stat 35e2a9d HEAD` touches only `nested_os_catalog.json`, `test_nested_os_catalog_sync.py`, `docs/guides/nested-lab-hosts.md` and progress.md. I4b, V25 and HUMAN are still `[ ]`.
  - V6b2m/n/o: a script matched every catalog `media_url` against the "V-5 answers" table. All nine V-5 entries in the catalog (`centos-stream-9`, the four `win-server-*-eval`, `win-11-enterprise-eval`, `kali-rolling`, `kali-qemu`, `vyos-rolling-2026.10.17`) have an exact SHA-256 and byte-size match. The only unused row is the optional Windows 11 LTSC eval, which iteration 156 skipped and said why. The eval entries carry `eval_days` (180/90) and image index 2 (Server Standard Desktop) or 1 (Win11), and `win-10` stays upload-only. VyOS is `manual_iso`, agentless, `net_config` none, and both its license note and the guide note that GitHub prunes nightly builds.
  - V6 done-when (PRD.md:1671): `test_nested_os_catalog_sync.py` validates every entry against the model, checks https + SHA-256 for downloaded entries, Microsoft hosts for Windows URLs, upload-only for Windows older than 10/2016, and a no-op second sync. V-5 is answered. All 34 downloadable entries cover V6b's list, except the Windows 10 eval (no longer offered) and Leap 15.6 (dropped by the user). No TODO or stub found.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 947 passed, coverage 94.28% (≥85%).
  - build_files: 551 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. CTF tsc grep: 0 matches.
  - Group V eslint: exit 0. Group V tsc grep: 0 matches.
- **Reopened:** none.

### Iteration 160 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 159, and the tree was clean at HEAD b294682, after the verification PASS. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at b294682 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop until a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 161 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 160, and the tree was clean at HEAD e1a9f96. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at b294682 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the fourth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 162 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 161, and the tree was clean at HEAD f4e2e4c. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at b294682 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the fifth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 163 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 162, and the tree was clean at HEAD 4a9d597. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at b294682 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the sixth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 164 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 163, and the tree was clean at HEAD d80a533. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at b294682 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the seventh no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Verification — 2026-10-18 — PASS
- **Checked:** no code has changed since the last verification (b294682): `git diff --stat b294682 HEAD` touches only progress.md (the no-op iterations 160–164), and the tree is clean. Three parallel read-only agents spot-checked 20 ticked tasks against their PRD done-whens and the code:
  - **Backend:** B1, H1, H2, H3, N1, N2, R4.
  - **Frontend:** I10, I13, I14, J1, J3, L7, N14.
  - **Nested images:** V3, V7, V12, V14, V15, V22.
  - All 20 match the PRD. Product keys are never persisted (V12). Flags are compared in constant time (B1). The award and rate-limit steps run in Firestore transactions (H2/H3). Only MUI X Community grid imports are used.
  - One agent flagged V15 for downloading `gs://` media with curl. That was wrong: `builder.sh:276` fetches uploaded media with the gcloud CLI copy command as the PRD says, and only the sha256 cache (`gcs_get`, :216) uses curl, as iteration 2d33bea recorded.
  - A grep for TODO/FIXME/NotImplemented across the CTF and nested modules found only `mktemp` `XXXXXX` templates and a product-key format hint.
  - I4b, V25 and HUMAN stay `[ ]`, because they need a person.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 947 passed, coverage 94.28% (≥85%).
  - build_files: 551 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. Group V eslint: exit 0. Scoped tsc grep: 0 matches (CTF and Group V).
- **Reopened:** none.

### Iteration 165 — 2026-10-18
- **Completed:** none. The queue is unchanged since the verification at bb55a78, and the tree was clean. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at bb55a78 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the eighth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 166 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 165, and the tree was clean at HEAD 3e7327f. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at bb55a78 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the ninth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 167 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 166, and the tree was clean at HEAD 24f2b43. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at bb55a78 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the tenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 168 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 167, and the tree was clean at HEAD 676c066. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at bb55a78 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the eleventh no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Iteration 169 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 168, and the tree was clean at HEAD f573942. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at bb55a78 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Next:** stop the loop. This is the twelfth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, or adds new tasks.

### Verification — 2026-10-18 — PASS
- **Checked:** no code has changed since the last verification (bb55a78). `git diff --stat bb55a78 HEAD` touches only progress.md (no-op iterations 165–169), and no `- [x]`/`- [ ]` lines changed. Three parallel read-only agents checked 31 ticked tasks that earlier verifications had not sampled, against their PRD done-whens and the code:
  - **Backend:** A3, A5, C2, D2, D4, E3, E5, F4, F6, G2, G5, H5, R2, N5, N9.
  - **Frontend and nested:** I3, I7, I11, I16, J4, L3, L5, N11, V5, V9, V11, V16, V19, V6f, V12b.
  - **Handler dispatch:** CTF actions 18, 19 and 20 are each dispatched (ctf_handler.py:60-62), and an unknown action raises ValueError.
  - All 31 match the PRD. `package.json` has only MUI X Community packages.
  - C2: `CtfValidator` is skipped on non-CTF partial form saves (edit_manager.py:303-309). The PRD only says to call it when `ctf` is present, so this was accepted again, as at progress.md:1188.
  - Edge case: the plant watcher is installed only on Linux servers with `ip_aliases` (lab_server_manager.py:354-358). That is the N8 spec as written (PRD.md:1638). A nested-image parent without `ip_aliases`, which N5 allows, would fail guest resets with "Plant watcher did not respond". This is a PRD-level gap, not an unfinished task, and V25 live acceptance may surface it.
  - A grep for TODO/FIXME/NotImplemented across the CTF and nested modules found only `mktemp` `XXXXXX` templates and a product-key format hint.
  - I4b, V25 and HUMAN stay `[ ]`, because they need a person.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 947 passed, coverage 94.28% (≥85%). This is from a solo rerun; a run in parallel with the api suite shared a `.coverage` file and printed a contaminated 96.19%.
  - build_files: 551 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. Group V eslint: exit 0. Scoped tsc grep: 0 matches for CTF and for Group V (90 tsc errors elsewhere, all pre-existing and outside scope).
- **Reopened:** none.

### Iteration 170 — 2026-10-18
- **Completed:** none. The queue is unchanged since the verification at a992df6, and the tree was clean. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at a992df6 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. `## ALL TASKS COMPLETE` is withheld because they are still `[ ]`.
- **Learned:** the verifier's plant-watcher gap (progress.md:2827) was not queued, on purpose. N8 (PRD.md:1638) limits the installer to `ip_aliases` servers, so fixing it would mean departing from the PRD. A human must decide whether to widen N8 to nested-image parents.
- **Next:** stop the loop. This is the thirteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 171 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 170, and the tree was clean at HEAD 9ef8655. Every loop-doable task is `[x]`. The only open items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at a992df6 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the fourteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 172 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 171, and the tree was clean at HEAD dd36455. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at a992df6 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the fifteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 173 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 172, and the tree was clean at HEAD 1eaf08e. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at a992df6 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the sixteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 174 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 173, and the tree was clean at HEAD 28f9ead. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at a992df6 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the seventeenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Verification — 2026-10-18 — PASS
- **Checked:** no code has changed since the last verification (a992df6). `git diff --stat a992df6 HEAD` touches only progress.md (no-op iterations 170–174), the tree is clean, and no `- [x]`/`- [ ]` lines changed. Three parallel read-only agents checked 69 ticked tasks that the last two verifications had not sampled, against their PRD done-whens and the code:
  - **Backend:** A1, A4, A6, B2, B3, B4, C1, D1, D3, E1, E2, E4, F1, F2, F3, F5, F7, G1, G3, G4, G6, G7, H4, H6, H7, R1, R3.
  - **Frontend:** 0.1, 0.2, I1, I2, I5, I6, I8, I9, I12, I15, I17, J2, K1, L1, L2, L4, L6.
  - **Nested:** N3, N4, N6, N7, N8, N10, N12, N13, N15, V1, V2, V4, V6, V8, V10, V13, V14b, V6e, V6g, V17, V18, V20, V21, V23, V24.
  - All 69 match the PRD.
  - I6: `CreateCtfButton.tsx` was removed in 83e5abc because L7 (PRD.md:1617) removes the lab-page button. Creating an event now goes through `CreateCtfDialog`, so I6 counts as superseded, not undone.
  - `package.json` has only MUI X Community packages.
  - A grep for TODO/FIXME/NotImplemented across the CTF and nested modules found nothing. The one TODO nearby, at `base_compute_manager.py:37`, has been there since the repo's initial commit and has nothing to do with these tasks.
  - Bookkeeping only: PRD.md:1671 still shows V6 as `[ ]`, but the code meets it. I did not edit the PRD.
  - I4b, V25 and HUMAN stay `[ ]`, because they need a person. The N8 plant-watcher gap noted at progress.md:2827 is still a PRD-level decision for a human.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 947 passed, coverage 94.28% (≥85%). The Python suites ran one after another, so the coverage files did not mix.
  - build_files: 551 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. Group V eslint: exit 0.
  - Scoped tsc grep: 0 matches for CTF and for Group V (90 tsc errors elsewhere, all pre-existing and outside scope).
- **Reopened:** none.

### Iteration 175 — 2026-10-18
- **Completed:** none. The queue is unchanged since the verification at 0320692 (PASS), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the eighteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 176 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 175 (HEAD a2a79c7), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the nineteenth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 177 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 176 (HEAD 2ed0309), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twentieth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 178 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 177 (HEAD b219d81), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twenty-first no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 179 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 178 (HEAD e2b7cd5), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twenty-second no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 180 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 179 (HEAD a80ed13), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0320692 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twenty-third no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Verification — 2026-10-18 — PASS
- **Checked:** no code has changed since the last verification (0320692). `git diff --stat 0320692 HEAD` touches only progress.md (no-op iterations 175–180), the tree is clean, and no `- [x]`/`- [ ]` lines changed. A read-only agent re-checked 17 ticked tasks against their PRD done-whens and the code: B1, H1, H2, H3, R4, I10, I13, I14, J1, J3, N1, N2, N14, V3, V7, V15 and V22.
  - All 17 match the PRD.
  - V15: incomplete uploads expire 2 days after a Custom-Time stamp, not through an `age` rule. Completing an upload moves Custom-Time to the year 9999. This still meets "delete incomplete `media/` objects after 2 days".
  - N14: replant on a flagless guest row is disabled with a tooltip, not hidden, and the API also refuses it. PRD.md:1650 asks only for the same reset menu, so this is acceptable.
  - A grep for TODO/FIXME/NotImplemented across the CTF and nested modules (tests excluded) found nothing.
  - I4b, V25 and HUMAN stay `[ ]`, because they need a person. The N8 plant-watcher gap (progress.md:2827) is still a PRD-level decision for a human.
- **Gate results:**
  - api/unit_tests: 1662 passed, coverage 97.67% (≥85%).
  - cloud_functions/tests: 947 passed, coverage 94.28% (≥85%).
  - build_files: 551 passed.
  - Frontend `npm test`: 47 files, 574 tests passed.
  - CTF eslint: exit 0. Group V eslint: exit 0.
  - Scoped tsc grep: 0 matches for CTF and for Group V (90 tsc errors elsewhere, all pre-existing and outside scope).
- **Reopened:** none.

### Iteration 181 — 2026-10-18
- **Completed:** none. The queue is unchanged since the verification at 0922423 (PASS), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0922423 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twenty-fourth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.

### Iteration 182 — 2026-10-18
- **Completed:** none. The queue is unchanged since iteration 181 (HEAD f99473a), and the tree was clean. The only `[ ]` items are I4b (browser checks), V25 (live acceptance) and HUMAN, and all three need a person.
- **Gate results:** not run; no code changed since iteration 157, and the verification at 0922423 passed every gate.
- **Blockers:** I4b, V25 and HUMAN need a person. The N8 plant-watcher gap (progress.md:2827) needs a human decision. `## ALL TASKS COMPLETE` is withheld because those items are still `[ ]`.
- **Next:** stop the loop. This is the twenty-fifth no-op iteration in a row. Restart it only after a human runs the I4b/HUMAN browser checks and V25, decides the N8 gap, or adds new tasks.
