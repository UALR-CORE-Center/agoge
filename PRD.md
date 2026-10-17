# Agoge CTF — Game Master Control Plane for Capture-the-Flag Exercises

> **Created:** 2026-10-02
> **Revised:** 2026-10-16 — audit fixes: metadata-safe planting, arm aggregation, NPCs and rotation moved to Phase 2, gates re-verified
> **Revised:** 2026-10-17 — Group V: nested image builder (create nested lab hosts from the Create Image page)
> **Author:** liquidswrds
> **Status:** Draft
> **Target branch:** `release/2027-spring` (the quality gates below were run there; it does not contain `main`'s `7d0a5a8`)

---

## Overview

### Problem Statement

Agoge provisions per-student lab environments but has no way to run a timed,
scored, competitive exercise across them. An instructor who wants to run a CTF
today must build a unit, hand out the workout links, and then track flags,
scores, host breakage, and the clock by hand — in a spreadsheet, outside the
product. There is no supported way to plant a flag, re-plant one after a
student destroys the host it lives on, reset one team's host without disturbing
another's, or start and stop the whole exercise. The vestigial
`EscapeRoomModel` in `common/models/agoge.py` is the only trace of a previous
attempt and has no live implementation.

### Solution

Add a **CTF control plane** that layers on top of an existing Agoge unit. A CTF
event is a Firestore document that references a built unit; every workout in
that unit becomes a team board. Instructors get an events list at
`/teacher/ctf` and a dashboard at `/teacher/ctf/{ctf_id}` with panels for Event
Control, Flags, Hosts, Scoreboard, Event Log, and Submissions. Students keep the
workout page they already have, gaining three sections: a CTF status banner, a
challenge list, and a flag submission box.

The control plane reuses Agoge's existing machinery: flags reach hosts through
GCE instance metadata and are confirmed through GCE guest attributes (no network
path into the workout VPC is needed), host resets go through the existing
`ComputeManagerFactory`, and long-running work is published to the `agoge`
topic for the Cloud Function to execute.

### Target Users

- **Primary — Game master / instructor:** needs one page that answers "is the
  exercise running, are the flags where I put them, which host is broken, who is
  winning", and lets them act on each answer without a shell.
- **Secondary — Student / team:** needs their existing workout page, plus the
  challenges they can attempt, the flags they have captured, and their standing.
- **Secondary — Agoge administrator:** needs CTF activity visible in the same
  structured logs and budget controls as every other Agoge build.

---

## Goals

- **Plant flags.** Arming an event plants every flag declared in the event's
  spec on every team's servers, each plant confirmed by the host itself, with a
  per-flag SHA-256 digest recorded in Firestore.
- **Keep flags off the metadata server.** No flag value remains readable from
  instance metadata once a plant attempt finishes, whether it succeeded or failed.
- **Reset hosts.** A game master puts one team's one server back in three modes
  (`replant`, `restart`, `rebuild`), the fastest of which finishes in under 180
  seconds without deleting the instance and without touching any other team.
- **Start and stop the exercise.** Arm, start, pause, resume, end, and archive
  each have one control on the dashboard.
- **Detect flag sharing.** Every flag value is derived per workout, so a value
  captured in workout A and submitted in workout B is recorded as
  `cross_submission` on the game master's dashboard within the same request.
- **Preserve the student experience.** The student workout page keeps its
  existing layout, route, and auth model, gaining exactly three sections.
- **Build nested lab hosts** (Group V). An instructor creates, from the Create
  Image page, one image holding a libvirt parent and up to eight guests (Kali,
  Linux, Windows XP through Windows 11 / Server 2025, appliances) on networks they
  define, and selects it as a server in any lab or CTF template.

## Non-Goals

These are explicitly out of scope. Do not build them, do not scaffold them, and
do not add configuration hooks for them.

- **No NPCs in Phase 1.** No NPC models, NPC routes, NPC panel, NPC agent,
  timeline files, or Pub/Sub topics for NPCs. Workout VMs have no egress and no
  Pub/Sub scope; the Phase 2 entry records the intended metadata-based design.
- **No seed rotation in Phase 1.** `seed_version` exists in the model and in the
  derivation input, and is always `1`. No rotate route, action, or UI.
- **No snapshot reset mode in Phase 1.** `SnapshotManager.restore_from_snapshot`
  does not restart lab servers today (see Working Notes); fixing it is Phase 2.
- **No `db` flag location in Phase 1.** Planting a database row needs a client
  and a locator format that does not exist yet.
- **No CTFd, and no second scoring service.** Scoring lives in the Agoge API and
  Firestore. Do not add a Cloud Run service, a MySQL instance, an SSO bridge, or
  a plugin host.
- **No attack/defense format.** No SLA checks, no round ticks, no flag rotation
  on a timer, no stealing flags from another team's hosts, no per-round scoring.
- **No new `BuildConstants.BuildType` member and no new build pipeline.** A CTF
  rides on an existing solo `UnitModel`, which the event creates from a catalog
  template (Group L). Do not modify `BuildHandler`, `SoloWorkout`,
  `CommunityWorkout`, `UnitStates`, `WorkoutStates`, or `ServerStates`.
- **No per-challenge containers.** Challenges live on the VMs the unit already
  builds. No Docker, no Kubernetes, no Cloud Run challenge instances.
- **No public or unauthenticated-internet scoreboard.** The student scoreboard is
  served by the same API behind the same path routing as the rest of the app.
- **No writeup submission, no report grading, no rubric generation for CTF.**
  `RubricModel` and the LLM rubric generator are untouched.
- **No team self-registration, no new identity provider, and no change to
  `verify_token` or `ProtectedRoute`.** The game master defines teams and their
  member emails before the event (Group L); a participant joins with the existing
  join code plus a rostered email, and teammates share one workout.
- **No WebSocket or server-sent-event push in Phase 1.** Every panel polls
  through the existing `usePolling` hook.
- **No cost or budget UI.** `BudgetManager` and `budget_exceeded` already own
  spend control. The dashboard shows a banner when `budget_exceeded` is true; it
  does not reimplement budget settings.
- **No offensive automation.** No red-team bot, no scanner, no `CyberArenaAgent` revival.
- **No MUI X Pro components.** Community DataGrid only, per existing convention.
- **No refactor of existing routers' error handling.** The shared error helper
  is used by the CTF routers only.
- **No modification of `api/tests/`** (the live, billable integration suite).
- **No network delivery to nested guests.** No SSH, WinRM, or HTTP endpoint on
  the parent that guests pull from. Guest networks are instructor-defined and
  student-modifiable; only the hypervisor channel is relied on.
- **No nested hypervisor other than libvirt/QEMU-KVM on a Linux parent** (Group N).
  Hyper-V, VirtualBox, VMware, GNS3, and EVE-NG are Phase 2.
- **No automatic guest snapshots in the relay.** The relay never creates
  `agoge-pristine`; it is made during image prep, by the instructor or by Group V's
  finalize step.
- **No Windows media redistribution** (Group V). Agoge downloads Windows only
  from Microsoft-hosted evaluation URLs; everything else is uploaded by the
  instructor, who supplies the license. No bundled ISOs, no key generation, no
  activation bypass beyond Microsoft's documented `slmgr /rearm`.
- **No unattended install of Windows XP, Server 2003, or older** (Group V). They
  build as `manual_iso` or from an uploaded disk image; `winnt.sif` automation is Phase 2.
- **No guests spanning several parents.** One nested host is one VM; multi-VM
  labs keep using ordinary spec servers and networks.
- **No Guacamole for image servers.** Instructors reach guests during the build
  through SSH tunnels shown in the Connect dialog; Guacamole stays a lab feature.
- **No automatic rebuild from a saved nested spec.** Editing a finalized host is
  check-out, customize, check-in; regenerating from the spec is Phase 2.

---

## Success Criteria

| ID | Criterion | Measurement | Target |
|----|-----------|-------------|--------|
| SC-1 | Creates a CTF event from a catalog template | `POST /ctf/` with a valid `spec_id` and future `expires` returns 200 and an `AgogeResponse[AgogeIDResponse]` whose `build_id` matches `^[a-z]{10}$`; the event is DRAFT with no boards and its own solo unit | 100% of valid requests |
| SC-2 | Rejects a CTF event from a template with no `ctf` spec block | `POST /ctf/` on a template whose `ctf` is null returns 400 with `{"detail": "..."}` | 100% of such requests |
| SC-3 | Derives a distinct flag value per workout | For two workout ids in one event, `derive_flag_value(seed, wid, fid, 1)` returns different strings for every flag id | 0 collisions across 1000 generated pairs in the unit suite |
| SC-4 | Never stores a flag value in Firestore | Unit tests capture every document written by `CtfSetup` (create, add_team, update_spec), `FlagPlanter`, and `CtfScoring`; none contains a string matching `^agoge\{` | 0 occurrences |
| SC-5 | Plants every flag on arm | After the arm worker finishes a board whose hosts confirm, every `CtfFlagStateModel` on that board has `plant_status == "planted"` and `planted_at` set (mocked compute API in `test_flag_planter.py`) | 100% of flags on confirming hosts |
| SC-6 | Clears the plant payload after every attempt | `FlagPlanter` calls `set_metadata` removing `agoge-ctf-plant` after success, after an error result, and after a confirmation timeout (three unit tests) | 3 of 3 paths |
| SC-7 | Re-plants one server without deleting the instance | `CTF_PLANT` for one server calls `set_metadata` and `reset`, and never calls `delete` or `nuke` (mocked) | 100% of replant calls |
| SC-8 | Completes a single-server replant inside the deadline | Manual: wall-clock from the reset button to `plant_status == "planted"` on a live Linux lab server | ≤ 180 seconds |
| SC-9 | Leaves other boards untouched during a single-host reset | A host reset scoped to board A issues no compute call and no Firestore write naming any other board (mocked) | 0 other boards modified |
| SC-10 | Detects cross-team flag submission | Submitting board B's derived flag to board A returns 200 with `correct: false`, `verdict: "incorrect"`, and writes a `CtfSubmissionModel` with `verdict == "cross_submission"` and `matched_workout_id == B` | 100% of cross submissions |
| SC-11 | Rate-limits flag submissions | The 11th submission naming one flag id on one board inside 60 seconds returns 429 with `{"detail": "..."}` | 100% over the threshold |
| SC-12 | Awards a solve exactly once under concurrency | Two concurrent correct submissions of one flag on one board produce one `correct` and one `duplicate`, and the board score rises by the flag's points once | 100% |
| SC-13 | Fans an arm out per board | `PUT /ctf/{id}/action/` with `action: "arm"` publishes exactly one `CTF_ARM_BOARD` message per board and no other message | message count == board count |
| SC-14 | Starts, pauses, resumes, ends, and archives without Pub/Sub | Those five actions change the event state in the request and publish 0 messages | 0 messages |
| SC-15 | Aggregates arm results | When the last board worker finishes, the event moves to `ARMED` if at least one board armed and to `BROKEN` if none did | 100% of arms |
| SC-16 | Honors the scoreboard freeze | After `scoreboard_frozen_at` is set, `GET /ctf-board/{wid}/scoreboard/` ranks using only solves with `solved_at <= scoreboard_frozen_at` | 100% of reads while frozen |
| SC-17 | Never leaks a flag location to a student | No `/ctf-board/` response contains a `path`, `server`, `location_type`, `digest`, or `access_level` key | 0 occurrences |
| SC-18 | Writes one audit row per game-master action | Every `PUT`/`POST`/`DELETE` on `/ctf/` that reaches core appends exactly one `CtfLogModel`, with `result` `OK`, `DENIED` (core raised `Unauthorized`/`Forbidden`/`Conflict`/`BadRequest`), or `ERROR` | 1 row per action |
| SC-19 | Hides the feature when disabled | With `ctf_enabled` false, every `/ctf/` route except `GET /ctf/config/` returns 404, `GET /ctf-board/{wid}/` returns `enrolled: false`, and the Teachers menu has no CTF entry | 100% |
| SC-20 | Keeps CTF boards running overnight | `DailyMaintenance._stop_all` publishes no STOP for a workout with an active board in an event in `ARMING`, `ARMED`, `RUNNING`, or `PAUSED` | 0 such stops |
| SC-21 | Leaves the student workout route unchanged | The `URL_STUDENT_WORKOUT` line in `frontend/src/router/urls.ts` and the `StudentWorkout` `<Route>` in `AppRouter.tsx` are unchanged by the CTF work | 0 diff on those lines |
| SC-22 | Passes every quality gate | The commands in **Quality Gates** all exit 0 | 0 failures |
| SC-23 | Covers new Python modules with tests | The coverage commands in **Quality Gates** | ≥ 85% line coverage |
| SC-24 | Blocks nested guests from the parent's metadata server | Every Linux payload and `LINUX_LOADER` contain the FORWARD reject for `169.254.169.254` (unit tests); manual: from a NAT'd guest on a live nested host, `curl -m 5 -H 'Metadata-Flavor: Google' http://169.254.169.254/` fails after the parent boots | 100% of payloads; 0 successful guest requests |
| SC-25 | Never puts a guest flag value in a process argument list | Unit tests: in every nested payload, no `virsh` invocation has arguments and no command line outside a heredoc or `printf` builtin contains a derived value | 0 occurrences |
| SC-26 | Replants one guest without resetting the parent | A guest-scoped plant or host reset calls compute `reset`, `stop`, `start`, and `nuke` 0 times (mocked), whether or not the watcher acks | 0 calls |
| SC-27 | Reports guest results per guest | With mocked guest attributes where `plant-result-a` is `ok` and `plant-result-b` is `error`, guest a's flags end `planted` and guest b's `failed` with b's message | 100% |
| SC-28 | Completes a guest replant inside the deadline | Manual: wall-clock from the Hosts-panel guest replant to `planted` on a live nested host with a running Linux guest | ≤ 90 seconds |
| SC-29 | Creates a nested image server from the wizard | `POST /compute/images/nested/` with a valid body returns 200; `image/<name>` holds `nested` with derived `exposures`/`console_ports`, `nested_build.phase == "queued"`, no product key; exactly one CONTROL / CHECK_OUT / TEMPLATE_SERVER message is published (mocked) | 100% of valid requests |
| SC-30 | Rejects invalid nested specs | One test per row of the Nested Image Builder validation table returns 400 naming the network, guest, or field | 100% of rows |
| SC-31 | Gives nested template and lab servers nested virtualization | Mocked `InstanceResource.new` receives `enable_nested_virtualization` and an Intel `min_cpu_platform` for nested template servers, nested-image lab servers, and `ip_aliases` lab servers | 100% |
| SC-32 | Licenses every nested image for VMX | Mocked `ImagesClient.insert` carries `ENABLE_VMX_LICENSE` on every nested check-in | 100% of nested check-ins |
| SC-33 | Keeps guest secrets out of the manifest, the disk, and argument lists | Unit tests: no admin password, VNC password, or product key in `agoge-nested-manifest` or in any rendered command line; secrets are read only from `/run/agoge-nested/secrets.json` | 0 occurrences |
| SC-34 | Removes the secrets item once a build ends | `NestedBuildMonitor` removes `agoge-nested-secrets` exactly once when the phase becomes `ready` or `failed` (mocked) | 100% of terminal builds |
| SC-35 | Builds a three-guest host unattended | Manual: Kali (cloud image) + Ubuntu 24.04 + Windows Server 2022 Evaluation on two networks, `build_machine_type` `n2-standard-8`, from Submit to `ready` with no console interaction | ≤ 60 minutes |
| SC-36 | Finalizes inside the function budget | Manual: Check In on a ready host reaches `finalized` and CHECKED_IN with `agoge-pristine` on every guest; the `NESTED_FINALIZE` invocation ends before 540 s | ≤ 360 s finalize |
| SC-37 | Reaches every guest from a lab | Manual: a lab built from the finalized image opens a Guacamole session to each exposed guest (RDP/SSH) and to one console (VNC) | 100% of guests |
| SC-38 | Isolates guests from the parent | Manual, from a guest on a NAT network of a lab server: the SC-24 metadata `curl` fails, and TCP 22 and 5901 on the parent's bridge address are refused or time out | 0 successful connections |
| SC-39 | Keeps overnight maintenance from killing builds | `DailyMaintenance` publishes no STOP for a template server whose `nested_build.phase` is `provisioning` or `building` (mocked) | 0 such stops |
| SC-40 | Never fetches Windows media from a non-Microsoft host | Catalog test: every Windows entry with a `media_url` has a Microsoft host; every Windows entry older than Windows 10 / Server 2016 has `requires_upload` | 100% of entries |

---

## Architecture

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Instructor API | FastAPI router `api/routers/ctf.py` | Matches every other Agoge surface; inherits `get_cloud_env`, `teacher_required`, `build_id_path` |
| Student API | FastAPI router `api/routers/ctf_board.py` (prefix `/ctf-board`) | Keeps the unauthenticated routes in a separate, visibly different file |
| Core logic | Package `api/core/ctf/` (`event.py`, `hosts.py`, `scoring.py`, `audit.py`, `config.py`) | One class per responsibility; core raises `common.exceptions`, routers translate |
| Error translation | `api/utilities/http_errors.py` | One mapping for the CTF routers instead of per-route `try/except` variants |
| Event state machine | `common/utilities/ctf_state_manager.py` | Both the API (start/pause/…) and the Cloud Function (arm aggregation) transition event state |
| Async work | Pub/Sub topic `agoge`, new handler `Handlers.CTF` → `CtfHandler` | The API never performs a long operation; one CTF entry point instead of `elif`s across `ControlHandler` |
| State | Firestore database `agoge-v1`, six new collections | Same database, same `DocumentDatabaseFactory`, same `DbCollections` enum |
| Flag derivation | `hmac` + `hashlib` from the stdlib | No new dependency; deterministic and reproducible offline in tests |
| Flag seed | Secret Manager secret `ctf_flag_seed`, created by `setup.py`, read lazily by `CloudEnv` | Matches `openai_api_key`, `api_key`, Guacamole passwords; `CloudEnv` stays read-only |
| Flag delivery | Dedicated metadata key `agoge-ctf-plant`, run by a fixed loader stub added at build | Does not overwrite the shared `startup-script` key; `FlagPlanter` owns only its own key |
| Plant confirmation | GCE guest attributes, namespace `agoge-ctf/` | Written from inside the VM through the metadata server; needs no egress and no credential |
| UI | React 18 + Vite 6 + MUI v6, MUI X **Community** 7 DataGrid | Existing frontend stack; Pro features are banned by convention |
| UI data | `apiService` in `src/services/api-request.service.ts`, `usePolling` hook, `utilities/transformers/ctf.transform.ts` | Same unwrap contract and transformer pattern as rubric, unit, and workout |

### System Architecture

```
                    ┌──────────────────────────────────────────────┐
  Game master ─────▶│  frontend  /teacher/ctf  (events list)       │
  (instructor)      │            /teacher/ctf/{ctf_id} (dashboard) │
                    │  Control │ Flags │ Hosts │ Score │ Log │ Subs│
                    └────────────────────┬─────────────────────────┘
                                         │  HTTPS (Firebase ID token)
  Student  ────────▶ /student/workout/{build_id}   (unchanged route,
      │                 + CTF banner / challenges / submit box)
      │  no auth (build id is the capability)    │
      ▼                                          ▼
  ┌───────────────────────────────────────────────────────────────┐
  │  agoge-api  (Cloud Run)                                       │
  │    routers/ctf_board.py ─▶ core/ctf/scoring.py                │
  │    routers/ctf.py ───────▶ core/ctf/event.py  (CRUD, actions) │
  │                       ───▶ core/ctf/hosts.py  (replant/reset) │
  │                       ───▶ core/ctf/audit.py  (every action)  │
  │    start/pause/resume/end/archive: synchronous Firestore      │
  │    arm, replant, reset: publish to topic agoge                │
  └──────────┬──────────────────────────────┬─────────────────────┘
             │ reads/writes                 │ publish (handler=CTF)
             ▼                              ▼
  ┌──────────────────────┐      ┌───────────────────────────────┐
  │ Firestore agoge-v1   │      │ agoge_cloud_function          │
  │  agoge-ctf           │◀─────│   BudgetManager check         │
  │  agoge-ctf-board     │      │   CtfHandler.route()          │
  │  agoge-ctf-digest    │      │     CTF_ARM_BOARD → ArmWorker │
  │  agoge-ctf-rate-limit│      │     CTF_PLANT     → Planter   │
  │  agoge-ctf-submission│      │     CTF_HOST_RESET→ HostReset │
  │  agoge-ctf-log       │      └───────┬───────────────────────┘
  └──────────────────────┘              │ compute API: setMetadata,
                                        │ reset, getGuestAttributes
                           ┌────────────▼─────────────────────────┐
                           │ Per-team workout VPC (already built) │
                           │  boot → loader stub reads metadata   │
                           │  key agoge-ctf-plant, plants files,  │
                           │  writes guest attribute              │
                           │  agoge-ctf/plant-result = ok:<nonce> │
                           └──────────────────────────────────────┘
```

Three properties of this shape are contracts, not style:

- **Nothing in Cloud Run or the Cloud Function opens a session to a range host,
  and no range host calls the API.** There is no SSH key, no WinRM password, no
  exec service, and no credential on the VM. Every write to a VM is a metadata
  write followed by a boot (or, on a nested host, picked up by the plant
  watcher); every answer from a VM is a guest attribute. A nested guest is
  reached only by its parent, over the hypervisor (Nested Guest Contract).
- **Every flag value is derived per workout and never stored.** Firestore holds
  the SHA-256 digest; the value is re-derived from the Secret Manager seed at
  plant time and by the admin reveal route only.
- **A flag value lives in instance metadata only for the duration of one plant
  attempt.** `FlagPlanter` removes `agoge-ctf-plant` in a `finally` block.

### Project Structure

```
common/
  constants/
    states.py                  (+ CtfStates)
    database.py                (+ CTF, CTF_BOARD, CTF_DIGEST, CTF_RATE_LIMIT,
                                  CTF_SUBMISSION, CTF_LOG)
    pub_sub.py                 (+ Handlers.CTF,
                                + Actions.CTF_ARM_BOARD/CTF_PLANT/CTF_HOST_RESET,
                                + EventAttributes.CTF_ID/WORKOUT_ID/RESET_MODE)
  models/
    agoge.py                   (+ CTF spec, runtime, request models, listed below;
                                + optional `ctf` on CatalogModel, CatalogEditModel, UnitModel)
    response.py                (+ CTF response models, listed below)
  utilities/
    ctf_flags.py               NEW — derivation, digest, normalize, compare, parse
    ctf_plant_contract.py      NEW — metadata key, guest-attribute path, loader stubs
    ctf_state_manager.py       NEW — CtfStateManager
    gcp/
      cloud_env.py             (+ ctf_flag_seed lazy secret property)
      compute/compute_instance.py  (+ set_metadata, + get_guest_attributes)

api/
  core/ctf/
    __init__.py                NEW
    config.py                  NEW — is_ctf_enabled() with 60 s cache
    audit.py                   NEW — CtfAudit context manager
    event.py                   NEW — CtfEvent: CRUD, boards, actions, reads
    hosts.py                   NEW — CtfHosts: replant / reset publish, host rows
    scoring.py                 NEW — CtfScoring: submit, hint, scoreboards
  routers/
    ctf.py                     NEW — instructor router, prefix /ctf
    ctf_board.py               NEW — student router, prefix /ctf-board
  utilities/
    http_errors.py             NEW — to_http_exception()
    infrastructure_as_code/object_validators/
      ctf.py                   NEW — spec-time flag validation
  core/specifications/utilities/
    edit_manager.py            (+ CTF validator call)
    file_manager.py            (+ CTF validator call)
  main.py                      (+ include ctf_router, ctf_board_router)
  unit_tests/
    test_ctf_flag_derivation.py        NEW
    test_ctf_state_manager.py          NEW
    test_ctf_spec_validation.py        NEW
    test_ctf_event.py                  NEW
    test_ctf_hosts.py                  NEW
    test_ctf_scoring.py                NEW
    test_ctf_router_auth.py            NEW
    test_ctf_config.py                 NEW

cloud_functions/
  main.py                      (+ Handlers.CTF branch)
  handlers/
    ctf_handler.py             NEW — CtfHandler
  cloud_fn_utilities/
    course_objects/ctf/
      __init__.py              NEW
      flag_planter.py          NEW — payload builder + plant procedure
      arm_worker.py            NEW — one board's arm + aggregation
      host_reset.py            NEW — replant / restart / rebuild
    course_objects/compute/lab_server_manager.py
                               (+ loader stub in _add_metadata,
                                + _merge_metadata_item concatenates windows-startup-script-ps1)
    periodic_maintenance/daily_maintenance.py
                               (+ skip workouts on active CTF boards)
  tests/
    test_ctf_handler.py                NEW
    test_flag_planter.py               NEW
    test_ctf_arm_worker.py             NEW
    test_ctf_host_reset.py             NEW
    test_ctf_loader_stub.py            NEW
    test_ctf_daily_maintenance.py      NEW

build_files/cloud_deployment/operations/env_and_quotas/
  environment_variables.py     (+ ctf_enabled; creates ctf_flag_seed when enabled)

frontend/src/
  components/Teacher/Ctf/
    CtfEventList.tsx           NEW — events list page
    CreateCtfButton.tsx        NEW — shown on TeacherUnit for CTF-capable units
    CtfDashboard.tsx           NEW — 25/75 shell + tabs
    EventControlPanel.tsx      NEW
    ScoreboardSettings.tsx     NEW
    FlagsPanel.tsx             NEW
    HostsPanel.tsx             NEW
    ScoreboardPanel.tsx        NEW
    EventLogPanel.tsx          NEW
    SubmissionLogPanel.tsx     NEW
  components/Student/Ctf/
    CtfBanner.tsx              NEW
    ChallengeList.tsx          NEW
    FlagSubmitCard.tsx         NEW
  components/Common/Dialogs/ActionConfirmDialog/
    ActionConfirmDialog.tsx    NEW — plain confirm/cancel
  components/Common/Status/StateMapping.tsx   (+ CTF state mapping with icon)
  hooks/useCtfEnabled.tsx      NEW
  services/Ctf/
    ctf.model.ts               NEW
    ctf.service.ts             NEW
    ctf.service.test.ts        NEW
  utilities/transformers/ctf.transform.ts     NEW
  router/
    urls.ts                    (+ CTF route and API-path constants)
    AppRouter.tsx              (+ 2 protected routes)
  components/Common/NavigationBar/AgogeAppBar.tsx   (+ 1 item in the Teachers menu)
  components/Teacher/Unit/TeacherUnit.tsx           (+ CreateCtfButton in the left column)
  components/Student/Workout.tsx                    (+ 3 sections, no route change)

docs/guides/
  game-master-guide.md         NEW
  nested-lab-hosts.md          NEW (V24)

# Group V — nested image builder
common/
  constants/nested.py          NEW — contract constants
  data/nested_os_catalog.json  NEW — seeded guest OS catalog
  models/agoge.py              (+ Nested* models; AgogeImageModel.nested/nested_build; HumanInteractionModel targets)
  utilities/nested_manifest.py NEW — manifest, secrets, autounattend rendering
  utilities/nested_build_monitor.py  NEW — NestedBuildMonitor (used by the API and the Cloud Function, so it lives in common/)
  utilities/gcp/compute/compute_image.py         (+ licenses)
  utilities/gcp/compute/compute_machine_type.py  (+ nested machine types)

api/
  core/compute/nested/
    validator.py               NEW — NestedHostValidator
    nested_image.py            NEW — create, catalog, media
  routers/compute_image.py     (+ /nested/, /nested/catalog/, /nested/media/, /{name}/nested-build/)

cloud_functions/
  cloud_fn_utilities/server_specific/nested/
    builder.sh                 NEW
    runtime.sh                 NEW
    finalize_watcher.sh        NEW
    autounattend.xml.tmpl      NEW
  cloud_fn_utilities/course_objects/compute/
    base_compute_manager.py    (nested virtualization, min CPU fix)
    image_template_manager.py  (nested provisioning, finalize_nested, license, metadata merge)
  handlers/control_handler.py  (+ NESTED_FINALIZE branch)
  cloud_fn_utilities/periodic_maintenance/   (build monitor task; daily-stop exemption)

build_files/cloud_deployment/operations/images_and_specs/
  nested_os_catalog_sync.py    NEW — setup operation
  nested_media_bucket.py       NEW — setup operation

frontend/src/
  components/Teacher/ServerManagement/Forms/NestedImage/
    NestedImageWizard.tsx      NEW — stepper shell
    HostStep.tsx, NetworksStep.tsx, GuestsStep.tsx, AccessStep.tsx, ReviewStep.tsx   NEW
    OsPickerDialog.tsx, MediaUpload.tsx, TopologyPreview.tsx                         NEW
  components/Teacher/ServerManagement/Forms/ServerCreator/ServerCreatorForm.tsx      (+ type toggle; display fix)
  components/Teacher/ServerManagement/ImageListTable.tsx, ImageDetailsDialog         (+ build phase, guests)
  components/Teacher/Specifications/NewEditor/ServerForm/NestedGuestsPanel.tsx       NEW
  services/Server/nested.service.ts, nested.model.ts                                 NEW
  utilities/transformers/nested.transform.ts                                         NEW
```

### Data Models

All Pydantic models go in `common/models/agoge.py` (request and stored models)
or `common/models/response.py` (response models). Stored data is loaded through
`ModelValidator`, never `Model(**data)`. Models follow the file's existing
`class Config: from_attributes = True` style where they are stored documents.

```python
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator

LocationType = Literal['file', 'registry', 'env', 'ads']
OperatingSystem = Literal['linux', 'windows']
PlantStatus = Literal['pending', 'planting', 'planted', 'failed', 'stale']
ArmStatus = Literal['pending', 'arming', 'armed', 'failed']
Verdict = Literal['correct', 'incorrect', 'duplicate', 'decoy',
                  'cross_submission', 'rate_limited', 'closed']
CtfAction = Literal['arm', 'start', 'pause', 'resume', 'end', 'archive']
ResetMode = Literal['replant', 'restart', 'rebuild']
LogAction = Literal['CTF_CREATE', 'CTF_UPDATE', 'CTF_ARM', 'CTF_START', 'CTF_PAUSE',
                    'CTF_RESUME', 'CTF_END', 'CTF_ARCHIVE', 'CTF_DELETE',
                    'FLAG_REPLANT', 'FLAG_REVEAL', 'HOST_RESET', 'SCORE_ADJUST']
LogResult = Literal['OK', 'DENIED', 'ERROR']

# ---------------------------------------------------------------------------
# Specification-side: authored in the lab spec JSON under the key `ctf`,
# copied into the unit on build, and into the event on event creation.
# ---------------------------------------------------------------------------

class CtfFlagSpecModel(BaseModel):
    id: str = Field(..., pattern=r'^[a-z0-9][a-z0-9-]{1,31}$', description="Stable slug, unique within the spec; appears inside the flag value")
    server: str = Field(..., description="ServerModel.name this flag is planted on")
    slot: int = Field(..., ge=1, le=9, description="Difficulty tier within the host; slot 1 is reachable by the initial foothold")
    category: Optional[str] = Field(default=None, max_length=32, description="Board grouping, e.g. 'Web', 'Windows', 'Forensics'")
    location_type: LocationType = Field(..., description="Where the planter writes the value; see Flag Location Formats")
    path: str = Field(..., description="Locator in the format its location_type requires")
    operating_system: OperatingSystem = Field(...)
    access_level: Literal['user', 'root', 'admin'] = Field(default='user', description="Documentation only; the planter always writes as the boot account")
    points: int = Field(..., description="Awarded on a correct submission. Must be > 0 unless decoy is true; a decoy may be negative.")
    decoy: bool = Field(default=False, description="Deliberately out-of-scope flag; never listed to students; submitting it is recorded as a scope observation")
    hint: Optional[str] = Field(default=None, max_length=1000)
    hint_cost: int = Field(default=0, ge=0)
    unlocks_after: Optional[List[str]] = Field(default=None, description="Flag ids that must be solved before this one is listed to the team")
    file_mode: Optional[str] = Field(default=None, pattern=r'^0[0-7]{3}$', description="Linux file placements only")
    file_owner: Optional[str] = Field(default=None, pattern=r'^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$', description="Linux file placements only")
    guest: Optional[str] = Field(default=None, pattern=r'^[a-z0-9][a-z0-9-]{1,31}$', description="CtfNestedGuestSpecModel.name on `server`; None = the server itself (Group N)")


NestedGuestDriver = Literal['qemu-agent', 'offline']


class CtfNestedGuestSpecModel(BaseModel):
    """A VM running inside a lab server under libvirt/QEMU-KVM (Group N, Nested Guest Contract)."""
    name: str = Field(..., pattern=r'^[a-z0-9][a-z0-9-]{1,31}$', description="Stable slug, unique per server; used by flags and in result keys")
    server: str = Field(..., description="ServerModel.name of the Linux parent that runs this guest")
    domain: str = Field(..., pattern=r'^[A-Za-z0-9_.-]{1,64}$', description="libvirt domain name on the parent")
    operating_system: OperatingSystem = Field(...)
    driver: NestedGuestDriver = Field(default='qemu-agent', description="How the parent writes into the guest")


class CtfScoringSpecModel(BaseModel):
    flag_prefix: str = Field(default="agoge", pattern=r'^[a-z][a-z0-9]{1,15}$', description="Literal prefix of every flag value")
    submission_rate_limit: int = Field(default=10, ge=1, le=100, description="Maximum submissions per flag id, per board, per 60 seconds")
    reveal_decoy_penalty: bool = Field(default=False, description="Whether a decoy verdict shows its negative value to the student")


class CtfSpecModel(BaseModel):
    """The `ctf` block of a lab specification. Its presence makes a unit CTF-capable."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    rules_url: Optional[str] = Field(default=None, description="Link to rules of engagement shown on the student banner")
    flags: List[CtfFlagSpecModel] = Field(..., min_length=1, max_length=200)
    scoring: CtfScoringSpecModel = Field(default_factory=CtfScoringSpecModel)
    nested_guests: List[CtfNestedGuestSpecModel] = Field(default_factory=list, max_length=32, description="Group N; empty for labs without nested VMs")

# CatalogModel, CatalogEditModel, UnitModel each gain:
#     ctf: Optional[CtfSpecModel] = Field(default=None)


# ---------------------------------------------------------------------------
# Collection `agoge-ctf`, doc id = ctf_id (IdGenerator.build_id)
# ---------------------------------------------------------------------------

class CtfEventModel(BaseModel):
    id: str = Field(...)
    unit_id: str = Field(...)
    instructor_id: List[str] = Field(..., description="Copied from the unit (normalized to a list) at creation")
    spec: CtfSpecModel = Field(..., description="Copied from the unit at creation; later unit edits do not change it")
    seed_version: int = Field(default=1, description="Always 1 in Phase 1; part of the derivation input")
    creation_timestamp: float = Field(...)
    starts_at: Optional[float] = Field(default=None, description="Set by start")
    ends_at: Optional[float] = Field(default=None, description="Null means open-ended; resume extends it by the paused duration")
    paused_at: Optional[float] = Field(default=None)
    accumulated_pause_seconds: float = Field(default=0.0)
    scoreboard_frozen_at: Optional[float] = Field(default=None, description="Public scoreboard ignores solves after this")
    public_scoreboard_enabled: bool = Field(default=False)
    board_ids: List[str] = Field(default_factory=list, description="Workout ids of the team boards")
    boards_pending: int = Field(default=0, description="Arm workers not yet finished; decremented in a transaction")
    state: int = Field(..., description="CtfStates value")
    state_timestamp: str = Field(..., description="ISO 8601 UTC")

    class Config:
        from_attributes = True


class CtfFlagStateModel(BaseModel):
    """Per-board, per-flag state. Embedded in CtfBoardModel."""
    flag_id: str = Field(...)
    digest: str = Field(..., description="SHA-256 hex of the normalized derived value")
    plant_status: PlantStatus = Field(default='pending')
    planted_at: Optional[float] = Field(default=None)
    plant_error: Optional[str] = Field(default=None, description="Never contains a flag value")
    solved: bool = Field(default=False)
    solved_at: Optional[float] = Field(default=None)
    hint_taken: bool = Field(default=False)
    hint_taken_at: Optional[float] = Field(default=None)
    attempts: int = Field(default=0, description="Submissions whose parsed flag id is this flag")


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-board`, doc id = f"{ctf_id}-{workout_id}"
# ---------------------------------------------------------------------------

class CtfBoardModel(BaseModel):
    id: str = Field(...)
    workout_id: str = Field(...)
    ctf_id: str = Field(...)
    active: bool = Field(default=True, description="False once the event is archived or deleted; a workout has at most one active board")
    team_name: str = Field(..., description="WorkoutModel.team_name, else student_email, else workout_id")
    flags: List[CtfFlagStateModel] = Field(default_factory=list)
    score: int = Field(default=0, description="Solved points + decoy points − hint costs + manual adjustments")
    solve_count: int = Field(default=0)
    decoy_count: int = Field(default=0)
    decoy_points: int = Field(default=0, description="Sum of decoy points in `score`; student views subtract it unless reveal_decoy_penalty")
    last_solve_at: Optional[float] = Field(default=None, description="Ranking tiebreaker")
    arm_status: ArmStatus = Field(default='pending')
    arm_error: Optional[str] = Field(default=None)

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-digest`, doc id = digest. Written at event creation.
# One document read resolves any submitted value to its board and flag.
# ---------------------------------------------------------------------------

class CtfDigestModel(BaseModel):
    digest: str = Field(...)
    ctf_id: str = Field(...)
    workout_id: str = Field(...)
    flag_id: str = Field(...)


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-rate-limit`, doc id = f"{ctf_id}-{workout_id}-{bucket}"
# bucket = parsed flag id, or "unparsed". Updated in a transaction.
# ---------------------------------------------------------------------------

class CtfRateLimitModel(BaseModel):
    id: str = Field(...)
    window_start: float = Field(..., description="Start of the current 60 s window")
    count: int = Field(default=0)


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-submission`, doc id = IdGenerator.uuid(). Append-only.
# ---------------------------------------------------------------------------

class CtfSubmissionModel(BaseModel):
    id: str = Field(...)
    ctf_id: str = Field(...)
    workout_id: str = Field(...)
    flag_id: Optional[str] = Field(default=None, description="Resolved flag id, else the parsed flag id, else null")
    submitted_digest: str = Field(..., description="The submission itself is never stored")
    verdict: Verdict = Field(...)
    matched_workout_id: Optional[str] = Field(default=None, description="Set on cross_submission")
    points_awarded: int = Field(default=0)
    submitted_at: float = Field(...)
    origin_ip: Optional[str] = Field(default=None, description="request.client.host")


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-log`, doc id = IdGenerator.uuid(). Append-only.
# ---------------------------------------------------------------------------

class CtfLogModel(BaseModel):
    id: str = Field(...)
    ctf_id: str = Field(...)
    action: LogAction = Field(...)
    actor: str = Field(..., description="AgogeUser.email, or 'system'")
    target: Optional[str] = Field(default=None, description="workout_id, server name, or flag id")
    result: LogResult = Field(...)
    detail: Optional[Dict[str, Union[str, int, bool]]] = Field(default=None, description="Scalar context only. Never a flag value, never a seed.")
    created_at: float = Field(...)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CtfCreateRequest(BaseModel):
    spec_id: str = Field(..., min_length=1, max_length=200)
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    expires: float = Field(..., gt=0)

class CtfUpdateRequest(BaseModel):
    """Only fields present in the body are applied (model_fields_set);
    sending scoreboard_frozen_at: null unfreezes."""
    ends_at: Optional[float] = None
    scoreboard_frozen_at: Optional[float] = None
    public_scoreboard_enabled: Optional[bool] = None

class CtfActionRequest(BaseModel):
    action: CtfAction

class CtfReplantRequest(BaseModel):
    workout_ids: Optional[List[str]] = Field(default=None, description="Null = every board")
    servers: Optional[List[str]] = Field(default=None, description="Null = every flag-bearing server")

class CtfHostResetRequest(BaseModel):
    mode: ResetMode

class CtfScoreAdjustRequest(BaseModel):
    delta: int = Field(..., ge=-10000, le=10000)
    reason: str = Field(..., min_length=1, max_length=500)

class CtfSubmitRequest(BaseModel):
    flag: str = Field(..., min_length=1, max_length=200)
```

Response models in `common/models/response.py`:

```python
class CtfConfigResponse(BaseModel):
    ctf_enabled: bool

class CtfEventSummary(BaseModel):          # GET /ctf/ items
    id: str
    name: str
    unit_id: str
    state: int
    state_name: str
    board_count: int
    creation_timestamp: float
    starts_at: Optional[float]
    ends_at: Optional[float]

class CtfBoardStatus(BaseModel):
    workout_id: str
    team_name: str
    arm_status: ArmStatus
    arm_error: Optional[str]
    plant_failed_count: int
    plant_stale_count: int

class CtfStateResponse(BaseModel):         # GET /ctf/{id}/state/
    id: str
    state: int
    state_name: str
    state_timestamp: str
    starts_at: Optional[float]
    ends_at: Optional[float]
    paused_at: Optional[float]
    accumulated_pause_seconds: float
    scoreboard_frozen_at: Optional[float]
    public_scoreboard_enabled: bool
    budget_exceeded: bool
    boards: List[CtfBoardStatus]

class CtfFlagBoardStatus(BaseModel):
    workout_id: str
    team_name: str
    plant_status: PlantStatus
    planted_at: Optional[float]
    plant_error: Optional[str]
    solved: bool

class CtfFlagRow(BaseModel):               # GET /ctf/{id}/flags/ items
    flag_id: str
    server: str
    slot: int
    category: Optional[str]
    location_type: LocationType
    points: int
    decoy: bool
    boards: List[CtfFlagBoardStatus]

class CtfFlagRevealResponse(BaseModel):
    flag_id: str
    workout_id: str
    value: str

class CtfHostRow(BaseModel):               # GET /ctf/{id}/hosts/ items
    workout_id: str
    team_name: str
    server: str
    server_state: Optional[int]
    server_state_name: Optional[str]
    flag_count: int
    rebuild_allowed: bool                  # False when the server has a wireguard_endpoint_id

class CtfScoreboardRow(BaseModel):         # instructor
    rank: int
    workout_id: str
    team_name: str
    score: int
    solve_count: int
    decoy_count: int
    last_solve_at: Optional[float]

class CtfPublicScoreboardRow(BaseModel):   # student
    rank: int
    team_label: str                        # "Team <n>", n by board order
    score: int
    solve_count: int
    is_you: bool

class CtfChallenge(BaseModel):
    flag_id: str
    category: Optional[str]
    points: int
    solved: bool
    solved_at: Optional[float]
    hint_available: bool
    hint_cost: int
    hint: Optional[str]                    # only once taken

class CtfStudentBoardResponse(BaseModel):  # GET /ctf-board/{wid}/
    enrolled: bool
    ctf_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    rules_url: Optional[str] = None
    state_name: Optional[str] = None
    remaining_seconds: Optional[int] = None
    flag_format: Optional[str] = None      # e.g. "agoge{<challenge>_<20 hex characters>}"
    score: Optional[int] = None
    challenges: List[CtfChallenge] = []
    public_scoreboard_enabled: bool = False

class CtfSubmitResponse(BaseModel):
    verdict: Literal['correct', 'incorrect', 'duplicate', 'decoy']
    correct: bool
    points_awarded: int                    # 0 for a decoy unless reveal_decoy_penalty
    message: str

class CtfHintResponse(BaseModel):
    flag_id: str
    hint: str
    hint_cost: int
    score: int
```

A `cross_submission` is stored as such but answered to the student as
`incorrect`. `rate_limited` and `closed` are answered as 429 and 409.

Additions to `common/constants/states.py`:

```python
class CtfStates(Enum):
    DRAFT = 0        # created, digests derived, nothing planted
    ARMING = 1       # arm workers planting across boards
    ARMED = 2        # at least one board armed, clock not started
    RUNNING = 3      # clock running, submissions accepted
    PAUSED = 4       # clock held, submissions refused
    ENDED = 5        # clock stopped, scoreboard final, submissions refused
    ARCHIVED = 6     # read-only; boards inactive
    BROKEN = 7       # an arm finished with zero boards armed
```

`CtfStateManager` (`common/utilities/ctf_state_manager.py`) is standalone — it
does not subclass `cloud_functions`' `BaseStateManager`, because the API needs it
and because `BaseStateManager.state_transition()` never calls
`_is_valid_transition`. `transition(ctf_id, new_state, **fields)` runs in a
Firestore transaction: it reads the event, raises `Conflict` if
`(current, new)` is not in the allow-list, writes `state`, `state_timestamp`,
and any extra fields through a field mask, and revalidates against
`CtfEventModel`.

```python
VALID_TRANSITIONS = {
    (DRAFT, ARMING), (DRAFT, ARCHIVED),
    (ARMING, ARMED), (ARMING, BROKEN),
    (ARMED, ARMING), (ARMED, RUNNING), (ARMED, ARCHIVED),
    (RUNNING, PAUSED), (RUNNING, ENDED),
    (PAUSED, RUNNING), (PAUSED, ENDED),
    (ENDED, ARCHIVED),
    (BROKEN, ARMING), (BROKEN, ARCHIVED),
}
```

Action → transition map (`CtfEvent.process_action`):

| Action | From | To | Side effects | Pub/Sub |
|--------|------|----|--------------|---------|
| `arm` | DRAFT, ARMED, BROKEN | ARMING | `boards_pending = len(board_ids)`; every board `arm_status = "pending"` | one `CTF_ARM_BOARD` per board |
| `start` | ARMED | RUNNING | `starts_at = now` | none |
| `pause` | RUNNING | PAUSED | `paused_at = now` | none |
| `resume` | PAUSED | RUNNING | `accumulated_pause_seconds += now − paused_at`; `ends_at += same` if set; `paused_at = null` | none |
| `end` | RUNNING, PAUSED | ENDED | `ends_at = now` | none |
| `archive` | DRAFT, ARMED, ENDED, BROKEN | ARCHIVED | every board `active = false` | none |

Arm aggregation (`ArmWorker`): after planting its board, each worker runs one
transaction that sets its board's `arm_status`, decrements `boards_pending`, and,
if the result is 0, transitions `ARMING → ARMED` when any board is `armed`, else
`ARMING → BROKEN`.

Additions to `common/constants/database.py`:

```python
CTF = 'agoge-ctf'
CTF_BOARD = 'agoge-ctf-board'
CTF_DIGEST = 'agoge-ctf-digest'
CTF_RATE_LIMIT = 'agoge-ctf-rate-limit'
CTF_SUBMISSION = 'agoge-ctf-submission'
CTF_LOG = 'agoge-ctf-log'
```

Additions to `common/constants/pub_sub.py` (values 18–20 are unused; `RESET`
is avoided because `RESET_EXPIRATION = 12` already exists):

```python
class Handlers(str, Enum):
    CTF = "CTF"

class Actions(Enum):
    CTF_ARM_BOARD = 18   # plant every flag on one board, then aggregate
    CTF_PLANT = 19       # plant one board's flags on one server (or all its servers)
    CTF_HOST_RESET = 20  # reset one server of one board in a ResetMode

class EventAttributes:
    CTF_ID = 'ctf_id'
    WORKOUT_ID = 'workout_id'
    RESET_MODE = 'reset_mode'
    # existing SERVER_NAME = 'server_name' is reused for the target server
```

### Flag Derivation Contract

`common/utilities/ctf_flags.py` is the single definition. The planter, the
event creator, the reveal route, and the submission checker import it; none
reimplements it.

```python
def derive_flag_value(seed: str, workout_id: str, flag_id: str,
                      seed_version: int, prefix: str = "agoge") -> str:
    """
    Returns '<prefix>{<flag_id>_<digest>}' where digest is the first 20 hex
    characters of HMAC-SHA256(seed, f"{seed_version}:{workout_id}:{flag_id}").
    """

def normalize_flag(submitted: str) -> str:
    """Strip surrounding whitespace, then lowercase. Nothing else."""

def flag_digest(value: str) -> str:
    """SHA-256 hex of normalize_flag(value). The only form ever persisted."""

def flags_match(submitted: str, expected_digest: str) -> bool:
    """hmac.compare_digest(flag_digest(submitted), expected_digest)."""

def parse_flag_id(submitted: str, prefix: str) -> Optional[str]:
    """Returns <flag_id> if normalize_flag(submitted) matches
    ^<prefix>\{([a-z0-9-]+)_[0-9a-f]{20}\}$, else None. Used for rate-limit
    bucketing and attempt counting only — never as proof of correctness."""
```

The flag format shown to students, verbatim on the submission card:

```
agoge{<challenge>_<20 hex characters>}
```

Comparison trims surrounding whitespace and is case-insensitive. Nothing else
is normalized — no punctuation stripping, no fuzzy matching.

### Plant Contract

`common/utilities/ctf_plant_contract.py` holds every name both sides of the
metadata channel depend on:

| Name | Value |
|------|-------|
| Plant metadata key | `agoge-ctf-plant` |
| Guest-attribute enable key | `enable-guest-attributes` = `TRUE` (written with every plant) |
| Guest-attribute path | `agoge-ctf/plant-result` |
| Result values | `ok:<nonce>` or `error:<nonce>:<message ≤ 200 chars, no flag value>` |
| Linux loader | appended to `startup-script` at build via `_merge_metadata_item` |
| Windows loader | added as `windows-startup-script-ps1` at build; `_merge_metadata_item` is extended to concatenate this key the way it does `startup-script` |

**Loader stub** (fixed text, added to every lab server at build): fetch
`agoge-ctf-plant` from the metadata server; if absent, do nothing. If present,
write it to a file readable only by the boot account, execute it, delete the
file. The loader never prints the payload.

**Payload** (built per board, per server by `FlagPlanter.build_payload`):

- Writes only that server's flags for that one board.
- Is idempotent: re-running it overwrites, never duplicates.
- Never echoes a flag value to stdout or stderr (startup-script output reaches
  the serial console and Cloud Logging).
- On Linux, first installs (best effort, idempotent) an iptables rule rejecting
  traffic to `169.254.169.254` from non-root UIDs, to close the window before
  the key is removed, and (N1) a FORWARD rule rejecting forwarded traffic to it,
  so a nested guest NAT'd through the host cannot read the host's metadata.
  Failure to install either is not a plant failure.
- Finishes by writing `ok:<nonce>` or `error:<nonce>:<message>` to the guest
  attribute.

**Plant procedure** (`FlagPlanter.plant(board, servers)`), per server:

1. `nonce = IdGenerator.uuid()`.
2. Set every affected flag's `plant_status = "planting"`.
3. `ComputeInstanceAPI.set_metadata(name, {"agoge-ctf-plant": payload, "enable-guest-attributes": "TRUE"})`.
4. `ComputeInstanceAPI.reset(name)`.

Steps 3–4 run for every server of the board before any polling. Then, per server:

5. Poll `get_guest_attributes(name, query_path="agoge-ctf/")` every 10 s for up
   to 240 s until `plant-result` carries this `nonce`.
6. `ok` → `planted`, `planted_at = now`, `plant_error = null`. `error` →
   `failed` with the message. Timeout → `failed`, `"No plant confirmation within 240 s"`.
7. In a `finally`: `set_metadata(name, remove=["agoge-ctf-plant"])`.

A server whose instance is not running is not reset; its flags go to `failed`
with `"Server is not running"`. The plant does not start stopped servers.

### Flag Location Formats

The validator enforces these patterns; the payload builder relies on them, so no
spec-authored string reaches a script unescaped.

| `location_type` | OS | `path` pattern | Planter writes |
|-----------------|----|----------------|----------------|
| `file` | linux | `^/[A-Za-z0-9_./-]+$` | File content = value; applies `file_mode`/`file_owner` |
| `file` | windows | `^[A-Za-z]:\\[A-Za-z0-9_.\\ -]+$` | File content = value |
| `registry` | windows | `^HKLM\\[A-Za-z0-9_\\ ]+:[A-Za-z0-9_]+$` (key `:` value name) | String value |
| `env` | linux, windows | `^[A-Z_][A-Z0-9_]{0,63}$` | Linux: replaces or appends the line in `/etc/environment`; Windows: machine-scope variable |
| `ads` | windows | `^[A-Za-z]:\\[A-Za-z0-9_.\\ -]+:[A-Za-z0-9_]+$` (file `:` stream) | Alternate data stream content |

### API Endpoints

Instructor routes are under `/ctf`; every one depends on `teacher_required`
and, except `GET /ctf/config/`, on `ctf_enabled_required` (404 when disabled).
Event-scoped routes also require the caller's email in the event's
`instructor_id` (else `Unauthorized`), except for admins.

| Method | Endpoint | Description | Auth | Role |
|--------|----------|-------------|------|------|
| GET | `/ctf/config/` | `CtfConfigResponse` | `teacher_required` | instructor |
| GET | `/ctf/` | `{'items': [CtfEventSummary]}` the caller may operate | `teacher_required` | instructor |
| POST | `/ctf/` | `CtfCreateRequest` → `AgogeIDResponse` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/` | `CtfEventModel` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/` | `CtfUpdateRequest` | `teacher_required` | instructor |
| DELETE | `/ctf/{ctf_id}/` | `DRAFT` or `ARCHIVED` only; deletes event, boards, digest and rate-limit docs; keeps submissions and log | `admin_required` | admin |
| GET | `/ctf/{ctf_id}/state/` | `CtfStateResponse` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/action/` | `CtfActionRequest` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/flags/` | `{'items': [CtfFlagRow]}` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/flags/` | `CtfReplantRequest`; one `CTF_PLANT` per affected board+server; allowed in `ARMED`, `RUNNING`, `PAUSED`, `BROKEN` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/flags/{flag_id}/reveal/?workout_id=` | `CtfFlagRevealResponse`; writes `FLAG_REVEAL` | `admin_required` | admin |
| GET | `/ctf/{ctf_id}/boards/` | `{'items': [CtfBoardStatus]}` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/hosts/` | `{'items': [CtfHostRow]}` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/boards/{workout_id}/hosts/{server}/reset/` | `CtfHostResetRequest` (optional `guest`, Group N); one `CTF_HOST_RESET` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/boards/{workout_id}/score/` | `CtfScoreAdjustRequest`; writes `SCORE_ADJUST` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/scoreboard/` | `{'items': [CtfScoreboardRow]}`, ignores the freeze | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/submissions/?verdict=` | `{'items': [CtfSubmissionModel]}`, newest first, max 500 | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/log/?action=` | `{'items': [CtfLogModel]}`, newest first, max 500 | `teacher_required` | instructor |

Student routes are under `/ctf-board` and resolve the workout's single active
board (`workout_id == X and active == True`).

| Method | Endpoint | Description | Auth | Role |
|--------|----------|-------------|------|------|
| GET | `/ctf-board/{workout_id}/` | `CtfStudentBoardResponse`; `enrolled: false` when no active board or `ctf_enabled` is false | none | student |
| POST | `/ctf-board/{workout_id}/submit/` | `CtfSubmitRequest` → `CtfSubmitResponse` | none | student |
| POST | `/ctf-board/{workout_id}/hint/{flag_id}/` | `CtfHintResponse`; deducts `hint_cost` once | none | student |
| GET | `/ctf-board/{workout_id}/scoreboard/` | `{'items': [CtfPublicScoreboardRow]}`; 404 unless `public_scoreboard_enabled`; honors the freeze | none | student |

**On the unauthenticated student routes.** `GET /workouts/{build_id}/` and
`PUT /workouts/{build_id}/question/{question_key}/` already carry no auth
dependency; knowledge of the ten-letter build id *is* the capability. The CTF
student routes match that model deliberately. Anyone holding a board's workout
id can submit against it; `submission_rate_limit`, the append-only submission
log with `origin_ip`, and `unit.workspace_settings.registration_required`
bound it. Do not add auth to these routes in Phase 1.

All collection responses use `AgogeResponse[T]` with `data = {'items': [...]}`;
single objects use `data = <object>`.

### Submission Algorithm

`CtfScoring.submit(workout_id, flag, origin_ip)`:

1. Resolve the active board and event. Event not `RUNNING` → record `closed`, raise `Conflict("Submissions are closed.")`.
2. `bucket = parse_flag_id(flag, prefix) or "unparsed"`. In a transaction on
   `agoge-ctf-rate-limit/{ctf_id}-{workout_id}-{bucket}`: reset the window if
   older than 60 s, else increment; over `submission_rate_limit` → record
   `rate_limited`, raise `RateLimitExceeded`.
3. `digest = flag_digest(flag)`; get `agoge-ctf-digest/{digest}`.
4. No document, or a different `ctf_id` → `incorrect`.
5. Different `workout_id` in this event → `cross_submission` with `matched_workout_id`.
6. Same board → in one transaction on the board: already solved → `duplicate`;
   decoy → add its points to `score` and `decoy_points`, `decoy_count += 1`, `decoy`; else set `solved`,
   `solved_at`, add points, `solve_count += 1`, `last_solve_at`, `correct`.
   Also increment `attempts` on the parsed flag, if it exists.
7. Append one `CtfSubmissionModel`.

### Host Reset Modes

| Mode | What it does | Instance deleted | Flags afterwards | Typical duration |
|------|--------------|------------------|------------------|------------------|
| `replant` | Plant procedure for that one server | No | Re-planted, same values, confirmed | ≤ 180 s |
| `restart` | `ComputeManagerFactory` → `stop()` then `start()` | No | Unchanged on disk (the plant key is already cleared, so the loader does nothing) | ≤ 240 s |
| `rebuild` | `ComputeManagerFactory` → `nuke()`; then that server's flags → `stale` | Yes | Absent until a replant; the Flags panel shows a one-click Replant | ≤ 900 s |

`rebuild` is refused with 400 for a server with a `wireguard_endpoint_id`,
because `LabServerManager.nuke()` leaves those servers deleted.

### Nested Guest Contract

Instructors build some lab servers as hypervisors: a Linux parent with nested
virtualization (enabled today by `ip_aliases`, see `base_compute_manager.py`)
running child VMs under libvirt/QEMU-KVM. Children may be Linux or Windows and
may sit on subnets and routes the parent has no address on. A child is not a GCE
instance: it has no metadata server, no guest attributes, and no
`{workout_id}-{server}` instance name. Group N delivers its flags by **relaying
through the parent over the hypervisor**, never over the network.

**Spec shape.** A guest is declared once in `ctf.nested_guests` and referenced by
a flag's `guest`. The flag's `server` stays the parent, so instance naming,
`mark_stale` on a parent rebuild, and board isolation (SC-9) are unchanged. A
flag's `operating_system` is the guest's, not the parent's.

```json
"nested_guests": [
  {"name": "win-dc", "server": "hv-host", "domain": "win2019-dc", "operating_system": "windows", "driver": "qemu-agent"},
  {"name": "web", "server": "hv-host", "domain": "ubuntu-web", "operating_system": "linux", "driver": "offline"}
],
"flags": [
  {"id": "dc-admin", "server": "hv-host", "guest": "win-dc", "slot": 3, "location_type": "registry",
   "path": "HKLM\\SOFTWARE\\Corp:Secret", "operating_system": "windows", "points": 300}
]
```

**Validation** (in `object_validators/ctf.py`, both save paths):

| Rule | Rejection message names |
|------|-------------------------|
| `nested_guests[].server` names a spec server whose `os` is Linux and that has at least one NIC with `ip_aliases` | the guest name |
| `(server, name)` is unique; at most 8 guests per server | the guest name |
| `flag.guest` names a guest declared on `flag.server` | the flag id |
| `flag.operating_system` equals the guest's `operating_system` | the flag id |
| The same-OS rule and the `(server, slot)` uniqueness rule apply per `(server, guest)`, with `guest = None` for the parent itself | the flag id |
| `driver: offline` with `windows`: only `file`, `registry`, `env`; `windows_access` and `hidden` must be unset; a registry path must start `HKLM\SOFTWARE\` or `HKLM\SYSTEM\` | the flag id |

**Contract names** (added to `common/utilities/ctf_plant_contract.py`):

| Name | Value |
|------|-------|
| Per-guest result key | `agoge-ctf/plant-result-<guest name>`; same `ok:<nonce>` / `error:<nonce>:<message>` grammar |
| Ack key | `agoge-ctf/plant-ack` = `<nonce>`, written by every payload as its first action |
| Watcher unit | `agoge-ctf-watcher.service`, script `/usr/local/sbin/agoge-ctf-watcher` |
| Run lock / dedupe | `/run/agoge-ctf/plant.lock` (`flock`), `/run/agoge-ctf/last` = SHA-256 of the last payload run; directory mode `0700` |
| Pristine snapshot | libvirt snapshot named `agoge-pristine` on each guest domain (made by the instructor) |
| Timeouts | `WATCHER_ACK_SECONDS = 30`, `NESTED_CONFIRM_TIMEOUT_SECONDS = 420`, relay budget `RELAY_BUDGET_SECONDS = 360` |

The Cloud Function timeout is 540 s (`agoge_app.py`), so
`WATCHER_ACK_SECONDS + NESTED_CONFIRM_TIMEOUT_SECONDS` plus API overhead must stay
below it. These constants are chosen to satisfy that; do not raise them alone.

**Plant watcher.** Installed at build on every Linux lab server with
`ip_aliases`, by an installer `LabServerManager` merges into `startup-script`
(idempotent at every boot). It long-polls
`.../instance/attributes/agoge-ctf-plant?wait_for_change=true` using the response
`ETag`, and on a non-empty value whose SHA-256 differs from `/run/agoge-ctf/last`
runs it under the run lock, exactly as the loader would. The loader stub takes the
same lock and writes the same `last` file, so a payload is never run twice on one
boot. With the watcher, a nested host is planted **without a reset**, so its
guests keep running.

**Parent payload** for a nested host is the existing Linux payload plus one
relay section per targeted guest:

1. The prologue writes the ack key, then installs the metadata blocks (see N1).
2. The parent's own flags are planted as today.
3. Guest sections run **in parallel** (background jobs + `wait`), each bounded by
   `RELAY_BUDGET_SECONDS`. Each writes its own per-guest result key.
4. The epilogue writes `plant-result` last. It reports only the parent's own
   flags, and its presence means every guest section has finished.

**Driver `qemu-agent`** (guest needs `qemu-guest-agent` with `guest-exec` and
`guest-exec-status` permitted, and the `org.qemu.guest_agent.0` channel):

1. Domain not running (`virsh domstate`) → `error:<nonce>:<guest>: guest is not running`. The relay never starts a guest.
2. `guest-ping` every 5 s until it answers or the budget ends → `<guest>: guest agent did not respond`.
3. `guest-exec` with `capture-output: true` and the guest payload as base64
   `input-data` (stdin). Linux: `/bin/bash -s`. Windows: `powershell.exe` with a
   fixed bootstrap that reads stdin to the end, writes it to
   `%ProgramData%\agoge-ctf\plant-<guid>.ps1` under the SYSTEM-only ACL the
   Windows loader already uses, runs it with `-File`, and deletes it.
4. Poll `guest-exec-status` until `exited`. The decoded `out-data` is the result line.

**Driver `offline`** (parent needs `libguestfs-tools`):

1. `virsh shutdown`, wait up to 120 s for `shut off` → `<guest>: guest did not shut down`. The relay never `virsh destroy`s a guest.
2. Write each placement with libguestfs opened by domain name. Linux: `virt-customize --upload`, `--chmod`, and `--run-command 'chown …'`. Windows: file upload via `guestfish` with case-insensitive path resolution, and registry and env through `virt-win-reg --merge`, with `HKLM\SYSTEM\CurrentControlSet` mapped to the hive's current `ControlSet00N`.
3. Read every value back and compare SHA-256; a mismatch is `<flag id>: verification failed`.
4. `virsh start` in a `trap`, whatever the outcome.

**Guest payload** (`FlagPlanter.build_guest_payload`) is the existing bash or
PowerShell body for that guest's flags. Its epilogue does not touch guest
attributes. It prints exactly one line, the result, to the stdout it saved before
the prologue's redirect, and nothing else.

**No flag value in any process argument list, on the parent or the guest.**
`virsh` is run in shell mode with its commands on stdin (`printf … | virsh`),
never with the agent JSON as an argument. Guest payloads travel as `guest-exec`
`input-data`. Offline values go through root-only temp files under
`/run/agoge-ctf/`, removed in a `trap`.

**Nested plant procedure.** These changes apply to `FlagPlanter.plant` for any
server that has `nested_guests`. Servers without them are unchanged.

| Scope | After `set_metadata` | No ack within `WATCHER_ACK_SECONDS` |
|-------|----------------------|-------------------------------------|
| Whole server (arm, Flags-panel replant) | Wait for `plant-ack` = nonce; no reset | `reset()` the parent, as today |
| One guest (host reset on a guest) | Wait for `plant-ack` = nonce; no reset | Every targeted flag → `failed`, `"Plant watcher did not respond"`; **never** reset |

Each flag then takes its status from its own key: `plant-result-<guest>` for a
guest flag and `plant-result` for a parent flag. The server's confirmation window
is `NESTED_CONFIRM_TIMEOUT_SECONDS`. A payload longer than 256 KB (the metadata
value limit) → `BadRequest`, `"Plant payload exceeds the metadata size limit"`.

**Host reset modes on a guest** (`CtfHostResetRequest.guest` set). Each runs as a
one-guest payload through the watcher and touches no GCE instance:

| Mode | Guest action | Flags afterwards |
|------|--------------|------------------|
| `replant` | Plant that guest's flags only | Re-planted, same values, confirmed |
| `restart` | `virsh reboot <domain>` | Unchanged |
| `rebuild` | `virsh snapshot-revert <domain> agoge-pristine --running`, then plant that guest's flags in the same payload | Re-planted; missing snapshot → `failed`, `"<guest>: no agoge-pristine snapshot"` |

A `rebuild` of the **parent** recreates every guest's disk from the image, so the
existing `mark_stale` already covers guest flags.

### Nested Image Builder Contract

Group V lets an instructor build a **nested lab host** from the Create Image
page: one Debian parent VM running libvirt/QEMU-KVM, with up to eight guest VMs
(Kali, Linux distributions, Windows XP through Windows 11 / Server 2025, network
appliances) on networks the instructor defines inside the parent. The result
is an ordinary Agoge image (`image-<name>` plus an `image/<name>` document), so
it appears in the server picker of the lab spec editor and of CTF templates. One
VM then carries a whole lab.

A reference host built by hand on 2026-10-17 exists in the development project:
`image-nested-hv-debian12` (Debian 12 parent, `linux-guest` Debian 12 at
192.168.122.10, `windows-guest` Windows Server 2022 Evaluation at
192.168.122.20, both with qemu-guest-agent and an `agoge-pristine` snapshot,
`enable-vmx` license). Group V automates what was done to build it; see Working
Notes 14–23 for what that build taught.

**Lifecycle.** It reuses the existing image-server check-out/check-in cycle
and adds one build phase and one finalize handshake:

| Step | Who | What happens |
|------|-----|--------------|
| Create | Instructor, wizard | `POST /compute/images/nested/` validates the spec, writes `image/<name>` CHECKED_OUT with `nested` and `nested_build.phase = "queued"`, publishes the existing CONTROL / CHECK_OUT / TEMPLATE_SERVER message |
| Provision | Cloud Function | `ImageTemplateManager.check_out` builds the template server from the Debian family image on `build_machine_type`, with nested virtualization, `enable-guest-attributes`, the builder `startup-script`, `agoge-nested-manifest`, and `agoge-nested-secrets` |
| Build | Builder on the parent | Installs libvirt, creates networks, downloads and verifies media, installs every guest, runs post-install scripts, reports progress in guest attributes, then reports `ready` (or `failed`). Leaves guests running |
| Monitor | API on poll, `MaintenanceHandler` every 15 min | `NestedBuildMonitor` copies guest attributes into `nested_build`, removes `agoge-nested-secrets` once the phase is `ready` or `failed`, and fails a stalled or overlong build |
| Customize | Instructor | Works in the guests through the consoles (SSH tunnel from the Connect dialog) to install lab software |
| Finalize | Check In button | The API publishes `NESTED_FINALIZE` instead of CHECK_IN. The function writes `agoge-nested-finalize` = nonce. The parent's finalize watcher shuts the guests down, (re)creates `agoge-pristine`, cleans up, and answers `finalize-result`. The function then publishes the existing CHECK_IN |
| Image | Cloud Function | The existing check-in stops, snapshots, and images the disk, adding the `enable-vmx` license; the record returns to CHECKED_IN with `nested_build.phase = "finalized"` |
| Re-check-out | Instructor | The existing check-out of a finalized image. The startup-script installs only the finalize watcher (no manifest, nothing is rebuilt); Check In finalizes again |
| Lab use | Unit build | A lab server built from the image gets nested virtualization from the license (and explicitly, V1). `agoge-nested-runtime.service` maps the server's alias IPs to exposed guests and isolates the guests from the parent |

**Data models** (added to `common/models/agoge.py`):

```python
NestedOsFamily = Literal['linux', 'windows', 'appliance']
NestedOsGroup = Literal['kali', 'linux', 'windows_client', 'windows_server', 'appliance']
NestedInstallMethod = Literal['cloud_image', 'unattended_iso', 'disk_image', 'manual_iso']
NestedMediaFormat = Literal['qcow2', 'raw', 'img.xz', 'tar.xz', 'iso', 'vmdk', 'vhd', 'vhdx', 'ova', 'zip', '7z']
NestedNetConfig = Literal['networkd', 'netplan', 'nm-keyfile', 'ifupdown', 'windows', 'none']
NestedGuestStatus = Literal['pending', 'downloading', 'installing', 'post_install', 'manual', 'ready', 'failed']
NestedBuildPhase = Literal['queued', 'provisioning', 'building', 'ready', 'finalizing', 'finalized', 'failed']
SLUG15 = r'^[a-z][a-z0-9-]{0,13}[a-z0-9]$'   # libvirt domain, hostname, NetBIOS (15 chars)

# Collection `nested-os-catalog`, doc id = id. Seeded from common/data/nested_os_catalog.json (V5).
class NestedOsCatalogModel(BaseModel):
    id: str = Field(..., pattern=r'^[a-z0-9][a-z0-9.-]{1,47}$')    # e.g. "win-server-2022-eval"
    display_name: str
    family: NestedOsFamily
    group: NestedOsGroup
    version: str
    install_method: NestedInstallMethod
    media_url: Optional[str] = None            # https only; None => requires_upload
    media_sha256: Optional[str] = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    media_formats: List[NestedMediaFormat]     # accepted formats (first = the media_url's format)
    requires_upload: bool = False
    license_note: str                          # shown in the wizard; never empty for windows
    eval_days: Optional[int] = None
    osinfo: str                                # virt-install --osinfo value, e.g. "win2k22"
    firmware: Literal['bios', 'uefi'] = 'bios'
    disk_bus: Literal['virtio', 'sata', 'ide'] = 'virtio'
    nic_model: Literal['virtio', 'e1000e', 'e1000', 'rtl8139'] = 'virtio'
    video: Literal['virtio', 'qxl', 'vga', 'cirrus'] = 'vga'
    virtio_win_version: Optional[str] = None   # pinned virtio-win ISO release; None = no virtio media
    agent: bool                                # qemu-guest-agent available => CTF driver qemu-agent, else offline
    net_config: NestedNetConfig
    unattend_template: Optional[Literal['autounattend']] = None   # Vista and later only
    windows_image_index: Optional[int] = None
    default_username: Optional[str] = None     # disk_image/manual entries with fixed credentials, e.g. kali
    min_memory_mb: int
    default_memory_mb: int
    min_disk_gb: int
    default_disk_gb: int
    default_vcpus: int = 1
    is_enabled: bool = True

# Collection `nested-media`, doc id = IdGenerator.uuid(). Instructor uploads (V13).
class NestedMediaModel(BaseModel):
    id: str
    filename: str
    format: NestedMediaFormat
    size_bytes: int
    gcs_path: str                              # gs://<project>_nested-media/media/<id>/<filename>
    sha256: Optional[str] = None               # filled by the builder on first use
    os_id: Optional[str] = None                # catalog entry it was uploaded for
    uploaded_by: str
    uploaded_at: str
    complete: bool = False

class NestedNetworkModel(BaseModel):
    name: str = Field(..., pattern=SLUG15)
    cidr: str                                  # RFC 1918, /16 to /29
    mode: Literal['nat', 'isolated']           # nat: internet through the parent
    parent_address: Optional[str] = None       # the parent's address on this network; None = pure L2 segment
    dhcp: bool = True
    dhcp_start: Optional[str] = None
    dhcp_end: Optional[str] = None

class NestedGuestNicModel(BaseModel):
    network: str
    ip: Optional[str] = None                   # static; None = DHCP or unconfigured
    expose: bool = False                       # 1:1 NAT to the next alias slot on the lab server

class NestedGuestModel(BaseModel):
    name: str = Field(..., pattern=SLUG15)
    os_id: str
    media_id: Optional[str] = None             # required when the catalog entry requires_upload
    vcpus: int = Field(default=1, ge=1, le=8)
    memory_mb: int = Field(default=2048, ge=256, le=32768)
    disk_gb: int = Field(default=20, ge=2, le=500)
    nics: List[NestedGuestNicModel] = Field(..., min_length=1, max_length=4)
    admin_username: str = Field(..., pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]{0,19}$')
    admin_password: str                        # stored; teachers see it (like human_interaction)
    packages: List[str] = Field(default_factory=list, max_length=50)   # cloud_image Linux only
    post_install_script: Optional[str] = Field(default=None, max_length=65536)  # bash or PowerShell
    console: bool = True                       # VNC console on the parent
    autostart: bool = True
    start_order: int = Field(default=0, ge=0, le=99)
    start_delay_seconds: int = Field(default=0, ge=0, le=600)

class NestedHostSpecModel(BaseModel):
    parent_os: Literal['debian-12', 'debian-13'] = 'debian-12'
    build_machine_type: str = 'n2-standard-8'
    networks: List[NestedNetworkModel] = Field(..., min_length=1, max_length=8)
    guests: List[NestedGuestModel] = Field(..., min_length=1, max_length=8)
    # Derived by the API on create, never sent by the client:
    exposures: List[Tuple[str, int]] = Field(default_factory=list)   # (guest, nic index); list index = alias slot
    console_ports: Dict[str, int] = Field(default_factory=dict)      # guest -> 5901..5908
    vnc_passwords: Dict[str, str] = Field(default_factory=dict)      # guest -> 8 chars (VNC limit)

class NestedBuildStatusModel(BaseModel):
    phase: NestedBuildPhase = 'queued'
    guests: Dict[str, NestedGuestStatus] = Field(default_factory=dict)
    message: Optional[str] = Field(default=None, max_length=200)
    heartbeat_at: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    finalize_nonce: Optional[str] = None

# AgogeImageModel gains:
#     nested: Optional[NestedHostSpecModel] = None
#     nested_build: Optional[NestedBuildStatusModel] = None
# and `base_family: Optional[str] = None` loses its trailing comma (Working Note 19).
#
# HumanInteractionModel gains (V22):
#     nested_guest: Optional[str] = None   # label only
#     alias_index: Optional[int] = None    # connect to server.nics[0].ip_aliases[alias_index]
#     port: Optional[int] = None           # Guacamole port override (VNC console 5901..5908)

# Request body, POST /compute/images/nested/
class NestedImageCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    server_name: str
    description: str = Field(..., max_length=200)
    labels: List[str] = Field(default_factory=list)
    machine_type: str                          # what lab servers default to
    disk_size: Optional[int] = None            # None = computed minimum
    username: str
    ssh_key: str                               # parent access, as for standard Linux images
    nested: NestedHostSpecModel                # exposures/console_ports/vnc_passwords must be empty
    product_keys: Dict[str, str] = Field(default_factory=dict)   # guest -> key; never persisted
```

**Validation** (`api/core/compute/nested/validator.py` `NestedHostValidator`,
raising `BadRequest` with a message naming the network, guest, or field):

| Rule | Names |
|------|-------|
| `server_name` passes `_validate_new_name` and is not `nested` (reserved for the route prefix) | the name |
| Network names unique; each `cidr` is RFC 1918, /16–/29, and overlaps no other network, `169.254.0.0/16`, or libvirt's `192.168.122.0/24` | the network |
| `parent_address`, `dhcp_start`, `dhcp_end` lie inside the CIDR and are not its network or broadcast address; `mode: nat` and `dhcp: true` both require `parent_address`; the DHCP range excludes `parent_address` and every static guest IP | the network |
| Guest names unique; `os_id` names an enabled catalog entry; `requires_upload` ⇒ `media_id` names a `complete` medium whose `format` is in the entry's `media_formats` | the guest |
| `memory_mb ≥ min_memory_mb`, `disk_gb ≥ min_disk_gb` | the guest |
| Σ guest `memory_mb` + `NESTED_PARENT_OVERHEAD_MB` ≤ memory of `machine_type` and of `build_machine_type`; Σ `vcpus` ≤ 2 × the machine's vCPUs | `machine_type` |
| `machine_type` and `build_machine_type` are N1 or N2 (nested-capable); E2 is rejected | the machine type |
| `disk_size` (or the computed minimum) ≥ `NESTED_PARENT_BASE_DISK_GB` + Σ `disk_gb` + `NESTED_BUILD_SCRATCH_GB`, ≤ `NESTED_MAX_DISK_GB` | `disk_size` |
| Every NIC's `network` exists; a static `ip` is inside the CIDR, unique across guests, not `parent_address`, and outside the DHCP range | the guest |
| `expose: true` requires a static `ip`; at most `NESTED_MAX_EXPOSURES` exposed NICs | the guest |
| An `unattended_iso` Windows entry without `eval_days` requires `product_keys[guest]` matching `^([A-Z0-9]{5}-){4}[A-Z0-9]{5}$` | the guest |
| `packages` only for `cloud_image` Linux entries, each matching `^[a-z0-9][a-z0-9+.-]{0,63}$` | the guest |
| `admin_password` meets Windows complexity for Windows guests (≥ 8 chars, 3 of 4 classes) and ≥ 8 chars otherwise | the guest |

**Constants** (`common/constants/nested.py`):

| Name | Value |
|------|-------|
| `ENABLE_VMX_LICENSE` | `https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx` |
| `NESTED_PARENT_OVERHEAD_MB` | `2048` |
| `NESTED_PARENT_BASE_DISK_GB` / `NESTED_BUILD_SCRATCH_GB` / `NESTED_MAX_DISK_GB` | `20` / `12` / `1000` |
| `NESTED_MAX_EXPOSURES` | `8` |
| `NESTED_CONSOLE_BASE_PORT` | `5901` |
| `NESTED_MAX_MACHINE_MEMORY_MB` | `65536` (the machine-type list for nested images; standard images keep 17000) |
| `NESTED_FINALIZE_TIMEOUT_SECONDS` | `360` (must stay below the 540 s function timeout with overhead) |
| `NESTED_BUILD_STALL_MINUTES` / `NESTED_BUILD_MAX_MINUTES` | `45` / `240` |
| `NESTED_MEDIA_MAX_BYTES` / `NESTED_UPLOAD_URL_TTL_SECONDS` | `21474836480` (20 GiB) / `3600` |
| `NESTED_MEDIA_BUCKET_SUFFIX` | `nested-media` → `<project>_nested-media` |

**Metadata and guest attributes:**

| Name | Kind | Value |
|------|------|-------|
| `agoge-nested-manifest` | metadata, build only | JSON: the spec without secrets, plus each guest's resolved catalog entry and media source (`https` URL + sha256, or `gs://` path) |
| `agoge-nested-secrets` | metadata, removed after build | JSON `{guest: {admin_password, vnc_password, product_key?}}`. The builder copies it to `/run/agoge-nested/secrets.json` (tmpfs, 0600) and never writes it to the persistent disk |
| `agoge-nested-finalize` | metadata | nonce, written by `NESTED_FINALIZE`, removed after the answer |
| `enable-guest-attributes` | metadata | `TRUE` |
| `agoge-nested/phase` | guest attribute | `building`, `ready`, `failed` |
| `agoge-nested/guest-<name>` | guest attribute | a `NestedGuestStatus`, optionally `failed:<message>` |
| `agoge-nested/message` | guest attribute | the latest human-readable step, ≤ 200 chars |
| `agoge-nested/heartbeat` | guest attribute | epoch seconds, written every 60 s while building |
| `agoge-nested/finalize-result` | guest attribute | `ok:<nonce>` or `error:<nonce>:<message>` |

**Parent filesystem layout:**

| Path | Contents |
|------|----------|
| `/usr/local/sbin/agoge-nested-builder` | the builder (rendered from `cloud_functions/cloud_fn_utilities/server_specific/nested/builder.sh`); per-step markers in `/var/lib/agoge-nested/state/` so a reboot resumes rather than restarts |
| `/var/lib/libvirt/boot/agoge-nested/` | downloaded media and unattend ISOs. Not under `/root`: `libvirt-qemu` cannot read it (Working Note 15). Deleted at finalize |
| `/var/lib/libvirt/images/<guest>.qcow2` | guest disks |
| `/etc/agoge-nested/host.json` | non-secret host description (networks, guests, IPs, exposures, console ports) read by the runtime |
| `/usr/local/sbin/agoge-nested-runtime` + `agoge-nested-runtime.service` | runs at every boot of every server built from the image |
| `/usr/local/sbin/agoge-nested-finalize` + `agoge-nested-finalize.service` | long-polls `agoge-nested-finalize`; installed only on template servers by the startup-script |

**Builder.** On a template server whose manifest is present and whose state is not done, the builder:

1. Writes `phase=building` and installs `qemu-system-x86 qemu-utils libvirt-daemon-system virtinst libguestfs-tools genisoimage p7zip-full ovmf swtpm`.
2. Destroys and undefines libvirt's `default` network, then defines one persistent, autostarted network per `NestedNetworkModel` with bridge `agb<index>`. NAT networks use libvirt `<forward mode='nat'/>`; isolated networks have no `<forward>`. A network with `parent_address: None` has no `<ip>` (pure L2). DHCP reservations come from static IPs.
3. Installs the runtime (below) and starts it, so the metadata block is in force before any guest boots.
4. Installs guests in `start_order`, at most two installs at a time. For each guest it obtains the media (cache `gs://<project>_nested-media/cache/<sha256>` first, else the `https` URL), verifies the SHA-256, and fails the guest on a mismatch. It then runs the install method:

| Method | Steps | Done when |
|--------|-------|-----------|
| `cloud_image` | Convert to qcow2 and resize. `virt-customize`: hostname; admin user with the password read from a root-only file (`--password user:file:…`, never on the command line); `qemu-guest-agent`, `openssh-server`, and `packages`; network config per `net_config`; disable cloud-init with `/etc/cloud/cloud-init.disabled` (do **not** purge it, Working Note 16); regenerate SSH host keys at first boot; `--selinux-relabel` for RHEL-family; on RHEL-family remove the `guest-exec` block from `/etc/sysconfig/qemu-ga`. `virt-install --import` | the agent answers `guest-ping` |
| `unattended_iso` | Render `autounattend.xml` (V8) with hostname, admin password, product key or none, the image index, virtio driver paths, and for Windows 11 the `LabConfig` TPM/Secure Boot/RAM bypass keys. Build a small ISO. `virt-install` with the OS ISO, the pinned virtio-win ISO (when set), and the unattend ISO, `--boot hd,cdrom`. FirstLogonCommands install virtio guest tools (when set), enable RDP and ICMP, configure static IPs by MAC, delete `C:\Windows\Panther\unattend*.xml` (it holds the password), then power off. The builder waits for `shut off` (never relying on `virt-install --wait`, Working Note 17), detaches all media, and starts the guest | the agent answers, or for agentless entries the guest has been running 120 s |
| `disk_image` | Unpack `ova`/`zip`/`7z`/`xz`, `qemu-img convert` to qcow2, grow to `disk_gb` when larger. For Linux entries with `agent: true`, the same `virt-customize` user, password, and agent steps as `cloud_image` | as above |
| `manual_iso` | Blank qcow2 of `disk_gb`, boot the ISO with the console enabled, set guest status `manual` | the instructor finishes in the console; finalize accepts `manual` guests |

5. Runs `post_install_script` through `guest-exec` with the script as `input-data` (bash `-s` / `powershell.exe -Command -`), for guests whose entry has `agent: true`. A non-zero exit fails that guest with the first 150 chars of stderr.
6. Every domain gets `--cpu host-passthrough`, the `org.qemu.guest_agent.0` channel, a VNC console on `0.0.0.0:<console_port>` with the guest's `vnc_password` (when `console: true`), and `virsh autostart` per `autostart`.
7. Writes `phase=ready`. One failed guest does not stop the others; the phase is `failed` only when no guest reached `ready` or `manual`. `message` says which guests failed.

**Finalize watcher** (answers one nonce; the function times out after `NESTED_FINALIZE_TIMEOUT_SECONDS`):
1. ACPI-shutdown every running guest in parallel and wait up to 240 s. A guest still running → `error:<nonce>:<guest>: guest did not shut down`. The watcher never runs `virsh destroy`.
2. `managedsave-remove`, delete any existing `agoge-pristine`, then `snapshot-create-as <guest> agoge-pristine --atomic` (internal; BIOS guests only, see Open Questions).
3. Remove `/var/lib/libvirt/boot/agoge-nested/`, `/run/agoge-nested/`, the builder state, and the apt cache; `fstrim -av`.
4. Leave guests shut off; the runtime starts them in `start_order` with `start_delay_seconds` at the next boot. Write `ok:<nonce>`.

**Runtime** (`agoge-nested-runtime`, every boot, idempotent):
1. `iptables -I FORWARD -d 169.254.169.254 -j REJECT` (the same rule as N1; SC-24 applies to every nested image).
2. `INPUT` from any `agb*` bridge accepts only DHCP (udp 67) and DNS (udp/tcp 53) to the parent; everything else is dropped, so guests cannot reach the parent's SSH, VNC, or metadata-holding processes.
3. Reads `instance/network-interfaces/0/ip-aliases/` from the metadata server. For exposure slot *i* with alias *a* and guest IP *g*: `PREROUTING -d a -j DNAT --to g`, `POSTROUTING -s g -j SNAT --to a` on the primary NIC, and `FORWARD` accept between them. Extra aliases are ignored. Missing aliases leave that guest unexposed, which is logged, not an error.
4. Starts autostart guests in `start_order` with their delays (libvirt's own autostart is disabled so the order holds).
5. Configures `libvirt-guests` with `ON_SHUTDOWN=shutdown`, `PARALLEL_SHUTDOWN=8`, and `SHUTDOWN_TIMEOUT=80` so a workout stop shuts guests down instead of cutting their power.

**Lab and CTF use.** A spec server whose image has `nested`:
- needs an N1/N2 machine type;
- needs `len(nested.exposures)` alias IPs on NIC 0 (alias slot *i* is exposure *i*);
- gets editor help to add Guacamole connections per guest. An exposed guest uses `alias_index` and its protocol (RDP for Windows, SSH for Linux). A console uses protocol `vnc`, `port` = the console port, and the VNC password.

N5's rule "the parent has at least one NIC with `ip_aliases`" also accepts a parent whose image has `nested` (V23). The CTF editor pre-fills `nested_guests` from the image: `domain` = guest name, and `driver` = `qemu-agent` when the catalog entry has `agent`, else `offline`.

**Guest OS catalog.** Seeded entries (V5). Agoge downloads only media its
publisher hosts publicly. Windows media is never redistributed, and every Windows
entry before Windows 10 / Server 2016 requires an upload. The license note is
shown before selection.

| Group | Entries | Method | Media |
|-------|---------|--------|-------|
| Kali | Kali rolling (current release) | `cloud_image` (generic cloud image) | kali.org |
| Kali | Kali QEMU VM (default `kali`/`kali`) | `disk_image` (`7z`) | kali.org |
| Linux | Debian 11, 12, 13 | `cloud_image` | cloud.debian.org |
| Linux | Ubuntu 16.04, 18.04, 20.04, 22.04, 24.04, 26.04 | `cloud_image` | cloud-images.ubuntu.com |
| Linux | Fedora (current), Rocky 8/9/10, AlmaLinux 8/9/10, CentOS Stream 9/10, CentOS 7 (vault) | `cloud_image` | publisher mirrors |
| Linux | openSUSE Leap (current), Arch Linux, Alpine (cloud) | `cloud_image` | publisher mirrors |
| Linux | Metasploitable 2 | `disk_image` (`zip`/vmdk), agentless | SourceForge |
| Windows server | Server 2016, 2019, 2022, 2025 Evaluation (180 days) | `unattended_iso`, agent via virtio-win | Microsoft Evaluation Center |
| Windows client | Windows 10 Enterprise, Windows 11 Enterprise Evaluation (90 days), where Microsoft still publishes them | `unattended_iso` | Microsoft Evaluation Center |
| Windows client | Windows Vista, 7, 8.1, 10, 11 (retail/volume, with product key) | `unattended_iso`, upload required | instructor |
| Windows server | Server 2008, 2008 R2, 2012, 2012 R2, 2016–2025 (licensed) | `unattended_iso`, upload required | instructor |
| Windows legacy | Windows XP, Server 2003 (2000 optional) | `manual_iso` or `disk_image`, upload required, IDE disk, `rtl8139`/`e1000`, agentless | instructor |
| Appliance | pfSense CE, OPNsense, VyOS, Security Onion | `manual_iso` (OPNsense also `disk_image`) | publisher or upload |
| Any | Custom ISO / custom disk image | `manual_iso` / `disk_image`, upload required | instructor |

Profiles: XP/2003 use IDE + `rtl8139` or `e1000`, `cirrus`/`vga`. Vista–8.1 and 2008–2012 R2 use SATA + `e1000`, with the agent from the pinned virtio-win release that last supports them (Open Questions). Windows 10+/Server 2016+ use virtio + current virtio-win. Windows 11 and Server 2025 use BIOS with LabConfig bypass keys, not UEFI (Design Decisions).

---

## Features

### MVP (Phase 1)

Ordered by dependency. Each item is one iteration and includes its own tests.

**Group 0 — Green baseline**

- [x] **0.1 Frontend test script** — Change `frontend/package.json` `"test"` to `vitest run --exclude "tests/**"` so vitest stops collecting the `node:test` files in `frontend/tests/`.
  - Done when: `(cd frontend && npm test)` exits 0 with 23 tests passing; the two `.mjs` files are untouched.
- [x] **0.2 Rubric opt-in tests** — Make the four failing tests in `api/unit_tests/test_rubric_opt_in.py` pass.
  - Done when: `api/unit_tests` reports 49 passed, 0 failed; no test is deleted or skipped; `test_storing_openai_key_does_not_enable_rubrics` no longer reaches a real `input()` call.

**Group A — Contracts and constants**

- [x] **A1 CTF constants** — Add `CtfStates`, six `DbCollections` members, `Handlers.CTF`, three `Actions`, three `EventAttributes`.
  - Done when: a unit test asserts no new `Actions` value collides with an existing one.
- [x] **A2 CTF specification models** — Add `CtfFlagSpecModel`, `CtfScoringSpecModel`, `CtfSpecModel` and the `Literal` aliases.
  - Done when: tests reject a bad flag id, an unknown `location_type`, and a malformed `file_mode`.
- [x] **A3 CTF stored models** — Add `CtfEventModel`, `CtfFlagStateModel`, `CtfBoardModel`, `CtfDigestModel`, `CtfRateLimitModel`, `CtfSubmissionModel`, `CtfLogModel`.
- [x] **A4 CTF request models** — Add the seven request models.
- [x] **A5 CTF response models** — Add the response models to `common/models/response.py`.
- [x] **A6 Spec block wiring** — Add `ctf: Optional[CtfSpecModel]` to `CatalogModel`, `CatalogEditModel`, `UnitModel`.
  - Done when: a test builds `CatalogEditModel → CatalogModel → UnitModel` and the `ctf` block survives each step, matching `test_opt_in_survives_specification_models_and_lab_build`.

**Group B — Flag derivation and state**

- [x] **B1 Derivation module** — Write `common/utilities/ctf_flags.py` with the five contract functions.
  - Done when: tests cover determinism, per-workout uniqueness (SC-3), `seed_version` sensitivity, case/whitespace normalization, `parse_flag_id` hits and misses, and that `flags_match` calls `hmac.compare_digest`.
- [x] **B2 Seed property** — Add the lazy `ctf_flag_seed` property to `CloudEnv`, matching `openai_api_key`.
- [x] **B3 Seed provisioning** — In `environment_variables.py`, add `ctf_enabled`; when set to true, create `ctf_flag_seed` with `secrets.token_hex(32)` if absent.
  - Done when: a build_files test with mocked Secret Manager shows the secret is created once and not overwritten on a second enable.
- [x] **B4 CTF state manager** — Write `common/utilities/ctf_state_manager.py`.
  - Done when: tests accept every allowed transition, raise `Conflict` for `(RUNNING, ARMING)` and `(ENDED, RUNNING)`, and stamp `state_timestamp`.

**Group C — Specification validation**

- [x] **C1 Flag validator** — Write `object_validators/ctf.py`: every `server` names a server in the spec; flag ids unique; `(server, slot)` unique; every flag on one server has the same `operating_system`; `path` matches its row in Flag Location Formats; `registry`/`ads` require `windows`; non-decoy `points > 0`; every `unlocks_after` id exists and the graph has no cycle.
  - Done when: one test per rule rejects a bad spec with a message naming the flag id.
- [x] **C2 Validator wiring** — Call the validator from both `edit_manager._validate_spec` and `file_manager._validate_spec` when `ctf` is present.
  - Done when: a test per save path shows an invalid `ctf` block is rejected.

**Group D — Compute primitives and the loader**

- [x] **D1 `set_metadata`** — Add `ComputeInstanceAPI.set_metadata(resource_name, items: dict, remove: list = None, wait=True)`: re-reads the instance for its current `fingerprint`, merges `items` into the existing metadata, drops keys in `remove`, and leaves every other key unchanged.
  - Done when: tests show the merge keeps unrelated keys and that a 412 (stale fingerprint) triggers one re-read and retry.
- [x] **D2 `get_guest_attributes`** — Add `ComputeInstanceAPI.get_guest_attributes(resource_name, query_path)` returning a `{key: value}` dict, empty when none exist.
- [x] **D3 Plant contract module** — Write `common/utilities/ctf_plant_contract.py` with the names and both loader stubs.
- [x] **D4 Loader at build** — In `LabServerManager._add_metadata`, add the Linux loader through `_merge_metadata_item` and the Windows loader as `windows-startup-script-ps1`; extend `_merge_metadata_item` to concatenate `windows-startup-script-ps1`.
  - Done when: tests show an existing `startup-script` and assessment script are kept with the loader appended, and two Windows ps1 scripts are concatenated, not overwritten.

**Group E — Planting**

- [x] **E1 Payload builder** — Write `FlagPlanter.build_payload(board, server, nonce, seed)` for Linux (bash) and Windows (PowerShell), covering every row of Flag Location Formats.
  - Done when: tests show the payload contains only that server's flags, contains the nonce, and has no command that prints a value (`echo $FLAG`-style).
- [x] **E2 Plant procedure** — Write `FlagPlanter.plant(board, servers)` per the Plant procedure.
  - Done when: SC-5, SC-6, and SC-7 tests pass against a mocked `ComputeInstanceAPI`.
- [x] **E3 CTF handler** — Write `cloud_functions/handlers/ctf_handler.py` routing the three CTF actions, and add the `Handlers.CTF` branch to `cloud_functions/main.py`.
  - Done when: a test shows each action reaches its class and an unknown action raises `ValueError`.
- [x] **E4 Arm worker** — Write `ArmWorker.run(ctf_id, workout_id)`: workout not `WorkoutStates.RUNNING` → board `failed` with `"Workout is not running"`; else plant every flag-bearing server; then aggregate.
  - Done when: SC-15 tests pass for all-armed, mixed, and zero-armed outcomes.
- [x] **E5 Overnight exemption** — Make `DailyMaintenance._stop_all` skip workouts with an active board in an event in `ARMING`, `ARMED`, `RUNNING`, or `PAUSED`.
  - Done when: SC-20 test passes and non-CTF workouts are still stopped.

**Group F — Event core**

- [x] **F1 Config and feature flag** — Write `api/core/ctf/config.py` `is_ctf_enabled()` reading `admin-info/project` with a 60-second in-process cache, plus the `ctf_enabled_required` dependency.
  - Done when: a test shows a changed flag is seen after the cache expires.
- [x] **F2 Error helper** — Write `api/utilities/http_errors.py` `to_http_exception(e)` using the Error Handling table.
- [x] **F3 Audit helper** — Write `api/core/ctf/audit.py` `CtfAudit.action(...)` context manager writing one `CtfLogModel` with `OK`, `DENIED`, or `ERROR`.
  - Done when: tests cover all three results and show `detail` rejects a value matching `^agoge\{`.
- [x] **F4 Event create** — *Superseded by L2.* Originally `CtfEvent.create(unit_id, user)` built one board per existing workout; creation now starts from a catalog template with no teams, and boards are added per team in DRAFT.
  - Done when: SC-1, SC-2, and the SC-4 check on created documents pass.
- [x] **F5 Event read, update, delete** — Add `get`, `list`, `update` (applies only fields in `model_fields_set`), `delete` (per the endpoint table).
- [x] **F6 Event actions** — Add `process_action` per the action map.
  - Done when: SC-13 and SC-14 tests pass and an illegal action raises `Conflict` naming the state.
- [x] **F7 Event reads for panels** — Add `state()`, `boards()`, `flags()`, `log()`, `submissions()` returning the response models; `state()` reads the event and one board query.

**Group G — Hosts**

- [x] **G1 Replant publish** — Write `CtfHosts.replant(ctf_id, workout_ids, servers, user)` publishing one `CTF_PLANT` per board+server.
- [x] **G2 Host rows** — Add `CtfHosts.hosts(ctf_id)` joining boards to their workouts' server documents.
- [x] **G3 Reset publish** — Add `CtfHosts.reset(ctf_id, workout_id, server, mode, user)`; `rebuild` on a WireGuard server → `BadRequest`.
- [x] **G4 Reset dispatcher** — Write `host_reset.py` with a mode → method map called by `CtfHandler`.
  - Done when: SC-9 test passes and an unknown mode raises `ValueError`.
- [x] **G5 Reset `replant`** — Delegate to `FlagPlanter.plant(board, [server])`.
- [x] **G6 Reset `restart`** — Delegate to `ComputeManagerFactory` `stop()` then `start()`.
- [x] **G7 Reset `rebuild`** — Delegate to `ComputeManagerFactory` `nuke()`, then mark that server's flags `stale`.

**Group H — Scoring**

- [x] **H1 Submission resolve** — Write `CtfScoring.submit` steps 1, 3, 4, 5, 7 (closed, lookup, incorrect, cross-submission, record).
  - Done when: SC-10 test passes.
- [x] **H2 Solve award** — Add step 6 in a board transaction.
  - Done when: SC-12 concurrency test passes and decoy points apply with `decoy_count`.
- [x] **H3 Rate limiting** — Add step 2.
  - Done when: SC-11 test passes and a new window resets the count.
- [x] **H4 Hints** — Add `CtfScoring.hint`: deducts `hint_cost` once; a second call returns the hint without deducting.
- [x] **H5 Student board read** — Add `CtfScoring.board(workout_id)` returning `CtfStudentBoardResponse`, hiding decoys and flags whose `unlocks_after` are unsolved.
  - Done when: SC-17 test passes on the response.
- [x] **H6 Scoreboards** — Add instructor ranking (score desc, then earliest `last_solve_at`) and public ranking (anonymized, `is_you`, freeze-aware).
  - Done when: SC-16 test passes.
- [x] **H7 Score adjustment** — Add `CtfScoring.adjust(ctf_id, workout_id, delta, reason, user)` writing `SCORE_ADJUST`.

**Group R — Routers**

- [x] **R1 Instructor router** — Write `api/routers/ctf.py` with every `/ctf` route, using `to_http_exception` and `CtfAudit`.
- [x] **R2 Student router** — Write `api/routers/ctf_board.py` with every `/ctf-board` route.
- [x] **R3 Router registration** — Include both routers in `api/main.py`.
- [x] **R4 Router auth tests** — Write `test_ctf_router_auth.py`.
  - Done when: a non-instructor gets 403 on every `/ctf` route, a non-admin gets 403 on DELETE, reveal returns 403 for an instructor, and SC-19's 404 behavior holds.

**Group I — Game master UI**

- [x] **I1 CTF TypeScript models** — Write `services/Ctf/ctf.model.ts` as `export interface`s with snake_case keys mirroring every response and request model.
- [x] **I2 CTF transformer and service** — Write `utilities/transformers/ctf.transform.ts` and `services/Ctf/ctf.service.ts` calling each endpoint through `apiService`.
  - Done when: `ctf.service.test.ts`, using the mock setup in `rubric.service.test.ts`, covers one GET, one PUT, and one error path.
- [x] **I3 Feature flag hook** — Write `hooks/useCtfEnabled.tsx` reading `GET /ctf/config/` once per session for instructors.
- [x] **I4 Routes and menu** — Add `URL_TEACHER_CTF_BASE` (`${URL_TEACHER_BASE}/ctf`) and the dashboard URL, two `ProtectedRoute level="instructor"` routes, and one item in the **Teachers** `AppBarMenu` that is filtered out when `useCtfEnabled` is false.
  - Done when: verified in browser that the item appears only when enabled.
- [x] **I5 Events list page** — Write `CtfEventList.tsx`: `StyledDataGrid` with Active / Archived `Tabs` (same `sx` as `ActiveExpiredUnitTable`), rows link to the dashboard.
  - Done when: verified in browser.
- [x] **I6 Create from unit** — Write `CreateCtfButton.tsx` and render it in `TeacherUnit`'s left column only when the unit has a `ctf` block, as `UnitRubricEditor` is gated; on success navigate to the dashboard.
  - Done when: verified in browser that the button is absent on a non-CTF unit.
- [x] **I7 Action confirm dialog** — Write `Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog.tsx` with props `{open, title, message, confirmLabel, onConfirm, onClose, loading}` and a `LoadingButton`, modelled on `ConfirmCancelDialog`.
- [x] **I8 CTF state chip** — Add a CTF mapping to `Common/Status/StateMapping.tsx` returning `{text, color, icon}` using theme palette keys, rendered through `StatusBadge` with `icon` and announced through `StateInfo`'s `aria-live`.
- [x] **I9 Dashboard shell** — Write `CtfDashboard.tsx` copying `TeacherUnit`'s 25/75 `Box` split: left column holds the state chip, remaining time, and Event Control panel in `Paper elevation={2}`; right column holds MUI `Tabs` for Flags, Hosts, Scoreboard, Event Log, Submissions. Polls `state` with `usePolling` every 10 s. Shows an `Alert` banner when `budget_exceeded`.
  - Done when: verified in browser.
- [x] **I10 Event Control panel** — Render Arm, Start, Pause, Resume, End, Archive, each enabled only in its legal states. Arm/Start/Pause/Resume use `ActionConfirmDialog`; End and Archive use the existing type-to-confirm `ConfirmationDialog`, extended with a `confirmLabel` prop so its button no longer reads "Delete".
  - Done when: verified in browser that illegal actions are disabled.
- [x] **I11 Scoreboard settings** — Write `ScoreboardSettings.tsx`: freeze toggle, public-scoreboard toggle, `ends_at` picker, each sending `PUT /ctf/{id}/`.
- [x] **I12 Flags panel** — Render a Community DataGrid of flag id, server, slot, points, decoy, and per-board plant status, with a Replant action per row; `stale` and `failed` rows show a warning icon and text.
- [x] **I13 Flags bulk replant** — Add Community `checkboxSelection` driving one scoped `PUT /ctf/{id}/flags/`.
- [x] **I14 Hosts panel** — Render one row per board per server with server state and a reset menu offering `replant`, `restart`, `rebuild` with no default; `rebuild` is disabled with a tooltip when `rebuild_allowed` is false and confirmed with the type-to-confirm dialog.
- [x] **I15 Scoreboard panel** — Render ranked boards, polled every 30 s, with a visible banner while frozen.
- [x] **I16 Event log panel** — Render the action log, filterable by action, newest first.
- [x] **I17 Submission log panel** — Render the submission log, filterable by verdict, newest first, with `cross_submission` rows showing the matched team.

**Group J — Student UI**

- [x] **J1 Student CTF polling** — In `Workout.tsx`, fetch `GET /ctf-board/{workout_id}/` once on mount; if `enrolled`, poll it with `usePolling` every 15 s (independent of the page's existing 3.5 s workout poll); if not, make no further CTF request.
- [x] **J2 CTF banner** — Write `CtfBanner.tsx` at the top of the left `aside`, above `TimerBox`: a `Paper` with `component="section"` and `aria-labelledby` (as in `ConfigureAccess.tsx`), showing event name, state, remaining time, and a rules link.
  - Done when: verified in browser; absent when not enrolled.
- [x] **J3 Flag submission card** — Write `FlagSubmitCard.tsx` in the aside below `ConfigureAccess`: one text field, the flag format shown verbatim, verdicts shown with `showModal(SimpleSnackbar, {severity})`; a 429 shows the server's message.
  - Done when: verified in browser.
- [x] **J4 Challenge list** — Write `ChallengeList.tsx` in the main column below `WorkoutTable`: category, points, solved state, and a hint button confirmed with `ActionConfirmDialog` stating the cost; no host, no path. When `public_scoreboard_enabled`, add a standings table with the caller's row highlighted.
  - Done when: verified in browser.

**Group K — Documentation**

- [x] **K1 Game master guide** — Write `docs/guides/game-master-guide.md` covering spec authoring (with a complete `ctf` block example), create-to-archive, the three reset modes, what `stale` and `failed` mean, and the overnight-stop exemption.

**Group L — Setup & rosters**

Replaces create-from-unit. The game master creates an event from **Teachers → CTF Events**, then prepares it in DRAFT before any participant can join.

- [x] **L1 Shared workout record** — Move `BaseUnit._create_workout_record` into `common/utilities/workout_record.py` `build_workout_record(unit_model, workout_id, …)` so the API can write a NOT_BUILT workout without a Pub/Sub round trip; `BaseUnit` delegates to it.
- [x] **L2 Create from template** — `CtfSetup.create`: `POST /ctf/` body `{spec_id, name?, expires}`. Solo templates with a `ctf` block only (community → 400). Writes a solo unit (`Unit.new_unit_model`, `ctf_event_id`, `registration_required`, `count` 0) and a DRAFT event with no boards and the unit's `join_code`; publishes nothing. `GET /ctf/templates/` lists eligible templates.
- [x] **L3 Teams** — `GET|POST /ctf/{id}/teams/`, `PUT|DELETE /ctf/{id}/teams/{workout_id}/`. A team is a board with `members` plus a NOT_BUILT workout (`team_name`, `student_email` = first member). Add/remove only in DRAFT (board id list changed in a transaction that re-checks DRAFT); remove only while NOT_BUILT; names unique per event; an email on at most one active board; `ctf_max_boards` caps teams. Members editable until ENDED.
- [x] **L4 Per-event flags** — `PUT /ctf/{id}/spec/` in DRAFT only: `CtfSpecModel` + `CtfValidator` against the unit's servers, then every board's flag states and digests are rebuilt and stale digests deleted.
- [x] **L5 Servers** — `PUT /ctf/{id}/servers/` `{action: build|start|stop}` publishes the existing workout BUILD/START/STOP messages per team (build only NOT_BUILT; stop never while RUNNING). Arm with no boards → 400 "Add at least one team before arming".
- [x] **L6 Roster-only join** — `Workout._find_existing_workout`: on a unit with `ctf_event_id`, the email resolves through the active board whose `members` contains it (single `array_contains` filter; no composite index) to the team's workout; anyone else → `NotOnRoster` → 403 with a roster message. Non-CTF units unchanged.
- [x] **L7 Setup UI** — **New CTF** dialog on the events list; a **Setup** tab (default in DRAFT) with Teams (add, CSV import, members, remove, join code), Flags (editor), and Servers (build/start/stop all) sections; Arm disabled until there is a team. The lab-page **Create CTF Event** button is removed.
  - Done when: verified in browser on the development project.

**Group N — Nested lab hosts**

Plants and replants flags on VMs nested inside a lab server. See the Nested Guest Contract. N1 is a standalone security fix: ship it first.

- [ ] **N1 Metadata forward block** — Add an idempotent, best-effort `iptables -C FORWARD -d 169.254.169.254 -j REJECT || iptables -I FORWARD -d 169.254.169.254 -j REJECT` to the Linux payload prologue in `flag_planter.py`.
  - Done when: a test shows every Linux payload contains the `-C`/`-I FORWARD` pair before the first placement, and that the payload still reports `ok` when `iptables` is absent.
- [ ] **N2 Loader forward block** — Add the same FORWARD rule to `LINUX_LOADER` in `ctf_plant_contract.py`, before the metadata fetch.
  - Done when: a test shows the rule precedes the `curl` line, and the D4 merge tests still pass.
- [ ] **N3 Nested guest models** — Add `NestedGuestDriver`, `CtfNestedGuestSpecModel`, `CtfFlagSpecModel.guest`, `CtfSpecModel.nested_guests` per Data Models, plus `guest: Optional[str]` (same slug pattern) on `CtfHostResetRequest` and `CtfHostRow`.
  - Done when: tests reject a bad guest slug, a bad `domain`, and an unknown `driver`, and a spec without `nested_guests` still loads.
- [ ] **N4 Nested contract constants** — Add the Nested Guest Contract names and timeouts to `ctf_plant_contract.py`, and `PubSub.EventAttributes.GUEST = 'guest'`.
  - Done when: a test asserts `WATCHER_ACK_SECONDS + NESTED_CONFIRM_TIMEOUT_SECONDS < 540` and that `GUEST` collides with no existing attribute value.
- [ ] **N5 Nested guest validator** — Enforce the Nested Guest Contract validation table in `object_validators/ctf.py`.
  - Done when: one test per table row rejects a bad spec with a message naming the guest or flag id, and an existing non-nested spec still validates.
- [ ] **N6 Guest payload builder** — Write `FlagPlanter.build_guest_payload(board, server, guest, nonce, seed)` returning the per-OS body whose epilogue prints exactly one result line to the saved stdout.
  - Done when: tests show it holds only that guest's flags, writes no guest attribute, and has no command that prints a value; `bash -n` accepts the Linux output.
- [ ] **N7 qemu-agent relay section** — Extend `build_payload` for a server with `nested_guests`: ack first, parent flags, one parallel relay section per targeted `qemu-agent` guest, `plant-result` last; reject payloads over 256 KB.
  - Done when: tests show `virsh` is only ever fed on stdin (no argument contains `input-data`), each section writes `plant-result-<guest>`, `plant-result` is the last write, and `bash -n` passes.
- [ ] **N8 Plant watcher installer** — In `LabServerManager._add_metadata`, merge the watcher installer into `startup-script` for Linux servers with `ip_aliases`; make the loader stub take the run lock and write `/run/agoge-ctf/last`.
  - Done when: tests show the installer is merged only for `ip_aliases` servers, existing `startup-script` content is kept, and the loader and watcher scripts reference the same lock and dedupe file.
- [ ] **N9 Nested plant procedure** — Implement the Nested plant procedure table in `FlagPlanter.plant`, with an optional `guest` scope and per-key status mapping.
  - Done when: mocked tests show an acked plant calls `reset` 0 times, an un-acked whole-server plant calls it once, an un-acked guest plant calls it 0 times and fails its flags with `"Plant watcher did not respond"`, and guest and parent flags take status from their own keys.
- [ ] **N10 Guest host reset publish** — `CtfHosts.reset` accepts `guest`, rejects an undeclared guest with `NotFound`, and publishes `GUEST` on `CTF_HOST_RESET`; `CtfHosts.hosts` adds one row per board per guest with `rebuild_allowed: true`.
  - Done when: router tests show the guest reaches the message, the audit row's detail names the guest, and an unknown guest returns 404.
- [ ] **N11 Guest host reset modes** — `HostReset` with a guest runs the three guest modes from the Nested Guest Contract through `FlagPlanter`.
  - Done when: SC-9 holds for guest resets, and mocked tests show a guest reset of any mode calls no compute `reset`, `stop`, `start`, or `nuke`.
- [ ] **N12 Offline driver** — Add the `offline` relay section to `build_payload` per the Nested Guest Contract.
  - Done when: tests show values reach libguestfs only through `/run/agoge-ctf/` temp files, `virsh start` sits in a `trap`, `virsh destroy` never appears, and `bash -n` passes.
- [ ] **N13 Nested guests in the spec editor** — Add a nested-guests section to the CTF part of the spec editor and a guest select on each flag, filtered to guests on the flag's server.
  - Done when: verified in browser; vitest covers the transformer round trip.
- [ ] **N14 Guest rows on the Hosts panel** — Render guest rows indented under their parent with the same reset menu.
  - Done when: verified in browser.
- [ ] **N15 Nested host guide** — Add a "Nested lab hosts" section to `docs/guides/game-master-guide.md`: guest image prep (qemu-guest-agent with `guest-exec` allowed, which RHEL-family `/etc/sysconfig/qemu-ga` blocks by default; the agent channel; domain autostart; the `agoge-pristine` snapshot; `libguestfs-tools` for `offline`), a spec example, and the warning that root on the parent exposes every guest flag.

**Group V — Nested image builder**

Builds nested lab hosts from the Create Image page. See the Nested Image
Builder Contract. Independent of the CTF groups except V23, which needs N3, N5,
and N13. V1–V4 fix defects the rest depends on (Working Notes 18, 20, 21); ship them
first.

- [x] **V1 Nested virtualization for template and lab servers** — In `BaseComputeManager._build_server`, enable nested virtualization when `self.ip_aliases` **or** the server's image record has `nested`. `ImageTemplateManager._load_template_server` and `LabServerManager` set a `self.nested_host` flag from the image document. Fix the stale local `min_cpu_platform` (Working Note 18) so the N1/N2 platform reaches the insert. Raise `BadRequest` for an E2 machine type on a nested server.
  - Done when: mocked tests show `InstanceResource.new` receives `advanced_machine_features={"enable_nested_virtualization": True}` and the platform for a nested template server, a nested lab server, and an `ip_aliases` lab server (unchanged); E2 is rejected; a standard template server gets neither.
- [x] **V2 Nested machine types** — Make `ComputeMachineType.get` resolve any N1/N2 type up to `NESTED_MAX_MACHINE_MEMORY_MB` (keeping the 17000 MB cap for `list()` unless `nested=True`), and make `_lookup_machine_type` handle `None` instead of raising `AttributeError` (Working Note 20). `GET /compute/images/machine-types/?nested=true` returns N1/N2 types up to the nested cap.
  - Done when: tests show `n2-standard-8` resolves for a nested server, an unknown type falls back to SMALL with a warning, the default list is unchanged, and the nested list holds no E2 type.
- [ ] **V3 License on check-in** — Add `licenses: Optional[List[str]]` to `ComputeImageAPI.create` (passed into `Image(...)`), and have `ImageTemplateManager._create_image_from_snapshot` pass `[ENABLE_VMX_LICENSE]` when the record has `nested`.
  - Done when: mocked `ImagesClient.insert` receives the license for a nested record and no `licenses` for a standard one.
- [ ] **V4 Template startup-script merge** — `ImageTemplateManager._add_metadata` concatenates the image's `startup_script` with the user-creation script under one `startup-script` key (reuse `LabServerManager._merge_metadata_item`), fixing the duplicate key (Working Note 21).
  - Done when: a test shows exactly one `startup-script` item containing both scripts, and Windows images are unchanged.
- [ ] **V5 Models and constants** — Add the contract's models, `common/constants/nested.py`, `DbCollections.NESTED_OS_CATALOG = 'nested-os-catalog'` and `NESTED_MEDIA = 'nested-media'`, `PubSub.Actions.NESTED_FINALIZE`, `AgogeImageModel.nested`/`nested_build`, the three `HumanInteractionModel` fields, and fix the `base_family` default.
  - Done when: tests reject a bad guest slug, an http `media_url`, and an unknown install method; an existing image document without `nested` still validates; `base_family` defaults to `None`; `NESTED_FINALIZE` collides with no existing action value.
- [ ] **V6 OS catalog and seeding** — Write `common/data/nested_os_catalog.json` per the contract's catalog table and a setup operation **Synchronize Nested Guest OS Catalog** (the four `add-setup-operation` edits) that upserts entries by id while keeping an admin's `is_enabled` choice.
  - Done when: a test validates every JSON entry against `NestedOsCatalogModel`; every entry without `requires_upload` has an `https` URL and a SHA-256; every Windows entry with a URL points at a Microsoft host; every Windows entry older than Windows 10 / Server 2016 has `requires_upload`; a second sync changes nothing; Open Question V-5 is answered first.
- [ ] **V7 Nested host validator** — Write `NestedHostValidator` enforcing the contract's validation table, plus `derive(spec)` filling `exposures`, `console_ports`, and generated `vnc_passwords`.
  - Done when: one test per table row rejects a bad spec with a message naming the network, guest, or field; a valid three-guest, two-network spec passes; `derive` is deterministic for a given spec except for the passwords.
- [ ] **V8 Manifest and unattend rendering** — Write `common/utilities/nested_manifest.py`: `render_manifest(spec, catalog, media)` and `render_secrets(spec, product_keys)`, and `render_autounattend(guest, entry, secrets)` from `.../server_specific/nested/autounattend.xml.tmpl`.
  - Done when: tests show the manifest contains no admin password, VNC password, or product key; both stay under 256 KB for eight guests; the XML parses for every `unattended_iso` catalog entry, carries the virtio driver paths only when `virtio_win_version` is set, carries LabConfig only for Windows 11 / Server 2025, and its FirstLogonCommands delete `Panther\unattend*.xml` and end with a shutdown.
- [ ] **V9 Builder script** — Write `builder.sh` per the contract's Builder section: resumable step markers, network definitions, cache-then-URL media fetch with SHA-256 check, the four install methods, post-install over `guest-exec`, progress attributes, heartbeat, and phase rules.
  - Done when: the rendered script passes `bash -n`; tests show no secret is interpolated into a command line (secrets read from `/run/agoge-nested/secrets.json` only); media lives under `/var/lib/libvirt/boot/agoge-nested/`; `virsh destroy` never appears; the script installs and starts the runtime before the first `virt-install`.
- [ ] **V10 Runtime service** — Write `agoge-nested-runtime` per the contract's Runtime section and its systemd unit; the builder installs both.
  - Done when: tests on the rendered script show the FORWARD metadata reject, the bridge INPUT policy, DNAT/SNAT pairs generated from a sample `ip-aliases` response in slot order, ordered guest start, and the `libvirt-guests` settings; `bash -n` passes.
- [ ] **V11 Nested template server provisioning** — `ImageTemplateManager.check_out` for a record with `nested`: on the first build (phase `queued`), boot from the Debian family image of `parent_os` on `build_machine_type`, size the disk to `add_disk`, and add the four metadata items plus the builder bootstrap, then set phase `provisioning`. On re-check-out of a finalized image, boot from `image-<name>` with only the finalize-watcher bootstrap.
  - Done when: mocked tests show both paths' metadata keys and machine type, the secrets item is present only on the first build, and a standard image's check-out is unchanged.
- [ ] **V12 Create route** — `POST /compute/images/nested/` (teacher) taking `NestedImageCreateRequest`: validate, derive, write the record (`_create_record`, status CHECKED_OUT, Debian base, `human_interaction` for the parent from `username`/`ssh_key`), then publish the existing check-out. `GET /compute/images/nested/catalog/` (teacher) lists enabled entries.
  - Done when: router tests cover 200, 400 (validator), 409 (name exists), and 403 (student); the stored record has no product key; a router test shows `/compute/images/nested/catalog/` is not captured by `/{image_name}/`.
- [ ] **V13 Build monitor** — Write `common/utilities/nested_build_monitor.py` `NestedBuildMonitor.refresh(image)` (in `common/` because both deployables call it): read the `agoge-nested/*` guest attributes, update `nested_build` through a field mask, remove `agoge-nested-secrets` once the phase is `ready` or `failed`, and fail the build (stopping the server) when the heartbeat is older than `NESTED_BUILD_STALL_MINUTES` or the build exceeds `NESTED_BUILD_MAX_MINUTES`. Add `GET /compute/images/{name}/nested-build/` (teacher, refreshes then returns `NestedBuildStatusModel`) and a quarter-hourly maintenance task over active builds. `DailyMaintenance` skips template servers whose phase is `provisioning` or `building`.
  - Done when: mocked tests cover each phase mapping, secrets removal exactly once, stall and timeout failure, and the daily-stop exemption.
- [ ] **V14 Finalize handshake** — `process_action_on_list` publishes `NESTED_FINALIZE` instead of `CHECK_IN` for a nested record in phase `ready` or `finalized` (CHECK_IN is refused with 409 while phase is `provisioning`, `building`, or `finalizing`). The `ControlHandler` branch calls `ImageTemplateManager.finalize_nested()`, which writes the nonce, sets phase `finalizing`, waits up to `NESTED_FINALIZE_TIMEOUT_SECONDS` for `finalize-result`, removes the key, then publishes CHECK_IN on `ok` or records `failed` with the message (leaving the server checked out and running). Write the finalize watcher per the contract and its bootstrap.
  - Done when: mocked tests show ok → CHECK_IN published once, error → no CHECK_IN and the message stored, timeout → no CHECK_IN and phase back to `ready` with a message; the watcher script never contains `virsh destroy`, and `bash -n` passes.
- [ ] **V15 Media uploads** — A setup operation creates `<project>_nested-media` with CORS for the app origins, a lifecycle rule deleting incomplete `media/` objects after 2 days, and `roles/iam.serviceAccountTokenCreator` for the API service account on itself (needed to sign URLs on Cloud Run). Routes: `POST /compute/images/nested/media/` `{filename, size_bytes, os_id?}` returns `{media_id, upload_url}` (V4 signed resumable upload, `x-goog-content-length-range` capped at `NESTED_MEDIA_MAX_BYTES`, expiry `NESTED_UPLOAD_URL_TTL_SECONDS`); `PUT …/media/{id}/` marks it complete after checking the object's size; `GET …/media/` lists them; `DELETE …/media/{id}/` (uploader or admin). The builder fetches `gs://` media with `gcloud storage cp`.
  - Done when: tests with mocked storage cover each route, reject an unsupported extension and an oversize request, and show completion fails when the object is missing or the wrong size.
- [ ] **V16 Frontend service layer** — `services/Server/nested.service.ts`, `nested.model.ts`, `utilities/transformers/nested.transform.ts`, and URL constants for every V2/V12–V15 route.
  - Done when: vitest covers each service function's URL and body (pattern of `rubric.service.test.ts`) and the transformer round trip.
- [ ] **V17 Wizard shell and Host step** — Add an image-type toggle (Standard VM / Nested lab host) to `ServerCreatorForm`; Standard keeps today's form, with the `enable_display` → `display` key and the "Edit Server" heading fixed (Working Note 22). Nested renders `Forms/NestedImage/NestedImageWizard.tsx`: a non-linear MUI `Stepper` following `NewEditor/Editor.tsx` (Host, Networks, Guests, Access, Review) with per-step validation. The Host step has name, description, labels, parent OS, build and lab machine types (from `?nested=true`), disk size (computed minimum, editable upward), username, and SSH key.
  - Done when: verified in browser on the development project; vitest covers step validation and that the Standard path still submits the same body plus the corrected `display` key.
- [ ] **V18 Networks step** — Editable network list (name, CIDR, NAT/isolated, parent address, DHCP and range), pre-filled with one NAT network `lab` `192.168.100.0/24` (parent `.1`, DHCP `.100–.199`), with client-side versions of the network rules and a read-only topology preview (networks as rails, guests as boxes, inline SVG).
  - Done when: verified in browser; vitest covers overlap and range validation.
- [ ] **V19 Guests step** — An OS picker dialog grouped by catalog `group`, with search and chips for Auto install / Upload required / Manual install / Eval *n* days / No agent, and the license note before confirming. Then a guest form: name, vCPU/RAM/disk (catalog defaults and minimums), admin username and password (generate, show/hide), product key when required, media (upload with progress through the signed URL, or pick from the media library), NICs (network, static IP or DHCP, expose), packages (Linux `cloud_image`), post-install script, console, autostart, start order and delay.
  - Done when: verified in browser with an upload of at least 1 GB; vitest covers the per-guest rules and that `requires_upload` blocks Next without media.
- [ ] **V20 Access and Review steps** — Access lists exposures in alias-slot order (move up/down buttons, no drag; MUI X Community) and consoles with their ports. Review shows RAM, vCPU, and disk meters against the chosen machine types, warnings (evaluation expiry, manual installs needing console work, agentless guests using the CTF `offline` driver, legacy Windows needing an upload), the estimated build time, and a credentials summary. Submit posts the request and returns to the server list.
  - Done when: verified in browser by creating the three-guest host of SC-35; vitest covers the request body built from wizard state.
- [ ] **V21 Image list and details for nested images** — In `ImageListTable`, a nested row shows the build phase (polled through `GET …/nested-build/` while active) and disables Check In while building. `ImageDetailsDialog` lists guests with status, IPs, credentials, and console ports. The Connect dialog shows the `ssh -L <port>:localhost:<port>` tunnel per console and per exposed guest (RDP 3389 / SSH 22 through the tunnel to the guest IP).
  - Done when: verified in browser on a live build.
- [ ] **V22 Guacamole targets for guests** — `DisplayProxy` and `GuacamoleConfiguration.prepare_guac_connection` honor `alias_index` (target `server.nics[0].ip_aliases[alias_index]`) and `port`. Lab spec validation requires a server using a nested image to have an N1/N2 machine type and at least `len(nested.exposures)` aliases on NIC 0, and every `alias_index` to be in range.
  - Done when: mocked tests show the connection IP and port for an alias target, a console target, and an ordinary target (unchanged); the spec validator rejects the three bad cases on both save paths.
- [ ] **V23 Spec editor and CTF integration** — In the lab spec server form, selecting a nested image shows a Nested guests panel: guest list, a **Fill alias IPs** button choosing free addresses in NIC 0's subnet in slot order, and **Add connections** creating `HumanInteractionModel` entries (RDP for exposed Windows, SSH for exposed Linux, VNC console otherwise). The machine-type picker hides E2. The N5 rule accepts a parent whose image has `nested`, and the N13 nested-guests section pre-fills from the image (`domain` = guest name, `driver` from catalog `agent`).
  - Done when: verified in browser; vitest covers alias filling and connection generation; a C/N validator test shows a nested-image parent without `ip_aliases` passes N5.
- [ ] **V24 Nested image guide** — Write `docs/guides/nested-lab-hosts.md`: licensing (evaluation periods, `slmgr /rearm`, no Windows redistribution, upload requirements), sizing, the wizard, build time and troubleshooting (where the builder logs, `agoge-nested/message`), customizing through tunnels, finalize, using the image in a lab (aliases and connections), CTF use, and the warning that root on the parent exposes every guest.
- [ ] **V25 Live acceptance** — On the development project, build the SC-35 host, customize one guest, finalize, build a lab from it, connect through Guacamole to every guest, and run the SC-38 isolation checks. Record the results and timings in Open Questions.
  - Done when: SC-35 through SC-38 are met and recorded.

### Phase 2 (Post-MVP)

- [ ] **NPC background activity** — Benign traffic generators controlled through a `agoge-ctf-npc` metadata key (the agent long-polls the metadata server with `?wait_for_change=true`) with heartbeats in guest attributes, keeping the no-network-path contract.
- [ ] **Seed rotation** — Per-board `seed_version` so a rotation can fail on one board without desynchronizing others.
- [ ] **Snapshot reset mode** — First fix `SnapshotManager.restore_from_snapshot` publishing START without a build id for lab servers.
- [ ] **`db` flag location** — Database row placement with a defined locator format.
- [ ] **First-blood bonus** — Extra points for the first board to solve each flag.
- [ ] **Dynamic decay scoring** — Reduce a flag's value as its solve count rises, with a floor.
- [ ] **LMS grade export** — Push final board scores through the existing `LMSIntegrationModel`.
- [ ] **Live scoreboard push** — Replace polling with WebSocket.
- [ ] **Scheduled arming** — `MaintenanceHandler` arms and starts an event at a future `starts_at`.
- [ ] **Scope-violation report** — Per-board decoy report for a rules-of-engagement grade.
- [ ] **Attack/defense mode** — Round ticks, SLA checks, per-round flag rotation.
- [ ] **Authenticated team boards** — Require a Firebase identity on the student routes.
- [ ] **Event retention** — Automatic deletion of archived events after a configured age.
- [ ] **Watcher on every lab server** — Install the plant watcher on all Linux servers, not only nested hosts, so every replant avoids a reset.
- [ ] **Other nested hypervisors** — Windows Hyper-V parents (`Copy-VMFile` + PowerShell Direct), VirtualBox, VMware Workstation, GNS3, and EVE-NG nodes.
- [ ] **Asynchronous plant confirmation** — Settle long plants from `MaintenanceHandler` instead of polling inside one invocation, lifting the 540 s ceiling on nested plants.
- [ ] **Unattended legacy Windows** — `winnt.sif` automation for Windows XP and Server 2003.
- [ ] **Role recipes for nested guests** — One-click post-install recipes: AD DS domain controller with domain join of sibling guests, IIS, DVWA/Juice Shop, Kali metapackages, appliance config injection (pfSense `config.xml`).
- [ ] **Rebuild and duplicate nested hosts** — Regenerate an image from its saved `nested` spec, or start a new wizard pre-filled from an existing host.
- [ ] **Guacamole consoles for image servers** — Browser consoles to guests during the build instead of SSH tunnels.
- [ ] **UEFI and Secure Boot guests** — swtpm + OVMF for guests that need them, once Open Question V-4 allows pristine snapshots.

---

## Quality Gates

Every command below must exit 0 before each commit. Run each line from the
repository root in its own shell, with no credentials, no network, and no
interactive input. They were run on `release/2027-spring` on 2026-10-16; the
comments give what they produced there, and what they must produce once
Group 0 is done.

```bash
# Python suites. PYTHONPATH is mandatory. ./venv/bin/python is Python 3.12 with the dependencies.
PYTHONPATH=.:api ./venv/bin/python -m pytest api/unit_tests -q                                          # today 45 passed / 4 failed; after 0.2: 49 passed
PYTHONPATH=.:cloud_functions ./venv/bin/python -m pytest cloud_functions/tests -q                       # 280 passed
PYTHONPATH=.:build_files:cloud_functions ./venv/bin/python -m pytest build_files/cloud_deployment/tests -q  # 293 passed

# Frontend unit tests.
(cd frontend && npm test)                                                                               # today exits 1 (2 node:test files); after 0.1: 23 passed

# Lint, scoped to the new code (repo-wide eslint has hundreds of pre-existing errors). Config is frontend/.eslintrc.json.
(cd frontend && npx eslint src/components/Teacher/Ctf src/components/Student/Ctf src/services/Ctf src/hooks/useCtfEnabled.tsx src/utilities/transformers/ctf.transform.ts src/components/Common/Dialogs/ActionConfirmDialog --max-warnings 0)

# Type check, scoped to the new code: passes when no tsc error names a CTF file.
(cd frontend && ! npx tsc --noEmit 2>&1 | grep -E '^src/(components/(Teacher|Student)/Ctf|services/Ctf|hooks/useCtfEnabled|utilities/transformers/ctf|components/Common/Dialogs/ActionConfirmDialog)')

# Group V: the same two checks, scoped to the nested image builder code.
(cd frontend && npx eslint src/components/Teacher/ServerManagement/Forms/NestedImage src/services/Server/nested.service.ts src/services/Server/nested.model.ts src/utilities/transformers/nested.transform.ts --max-warnings 0)
(cd frontend && ! npx tsc --noEmit 2>&1 | grep -E '^src/(components/Teacher/ServerManagement/Forms/NestedImage|services/Server/nested|utilities/transformers/nested)')
```

Coverage gate for SC-23. `pytest-cov` is **not** installed; the first
iteration that needs it adds `pytest-cov>=6,<8` to the root `requirements.txt`
only:

```bash
PYTHONPATH=.:api ./venv/bin/python -m pytest api/unit_tests -q --cov=core.ctf --cov=common.utilities.ctf_flags --cov=common.utilities.ctf_state_manager --cov-fail-under=85
PYTHONPATH=.:cloud_functions ./venv/bin/python -m pytest cloud_functions/tests -q --cov=cloud_fn_utilities.course_objects.ctf --cov=handlers.ctf_handler --cov-fail-under=85
```

**Do not run `api/tests/`.** It is a live integration suite that builds real VMs,
costs money, takes many minutes, and asserts the active project is in
`ValidTestProjects`.

---

## Constraints

### Performance

- A single-server replant completes within **180 seconds** from Pub/Sub publish
  to `plant_status == "planted"` on a Linux lab server (manual check, SC-8).
- One board's arm finishes within **300 seconds** (all its servers reset in
  parallel, 240 s confirmation cap), inside the Cloud Function's 540 s timeout.
- `GET /ctf/{ctf_id}/state/` returns within **800 ms** at p95 for 40 boards:
  one event read plus one board query, never one read per board.
- `POST /ctf-board/{workout_id}/submit/` returns within **500 ms** at p95: one
  board query, one rate-limit transaction, one digest read, at most one board
  transaction, one insert.
- The dashboard polls `state` every **10 s** and the scoreboard every **30 s**;
  the student CTF poll is **15 s**. No CTF poll is faster than 10 s.
- Arming publishes exactly **one Pub/Sub message per board**.

### Security

- A flag value is never written to Firestore, a log line, a `CtfLogModel.detail`,
  a `plant_error`, or any response except the admin reveal route.
- A flag value is present in instance metadata only between steps 3 and 7 of
  the plant procedure; step 7 runs in a `finally`.
- The plant payload never prints a flag value; the loader never prints the payload.
- `ctf_flag_seed` is created only by `setup.py`, read only through `CloudEnv`,
  and never written to Firestore, a log, an audit row, or a response.
- Flag comparison uses `hmac.compare_digest`, never `==`.
- A payload carries only one server's flags for one board.
- No spec-authored string reaches a script unless it matched its Flag Location
  Formats pattern at spec-save time; the payload builder re-checks the pattern
  and raises `BadRequest` on a mismatch.
- No credential of any kind is placed on a workout VM by this feature.
- No guest flag value appears in a process argument list on the parent or the
  guest (SC-25); `virsh` takes agent commands on stdin, guest payloads travel as
  `guest-exec` `input-data`, offline values go through root-only temp files.
- Linux lab servers reject forwarded traffic to `169.254.169.254` from boot
  (loader) and during every plant (payload), so a nested guest cannot read its
  parent's plant payload, startup scripts, SSH keys, or service-account token.
- Root on a nested host is root on its guests: a game master who gives students
  root on a parent exposes every guest flag on it. The guide says so (N15).
- Student responses contain no `path`, `server`, `location_type`, `digest`, or
  `access_level`, and never list a decoy.
- A decoy verdict's response names neither the host nor the penalty unless
  `reveal_decoy_penalty` is true. Without it, every score a student can read
  (board, hint response, public scoreboard score and rank) excludes `decoy_points`.
- Every game-master control route that reaches core writes exactly one
  `CtfLogModel`, including when core denies it. Rejections by `teacher_required`
  or `admin_required` happen before core and are not logged.

### Compatibility

- Python 3.12 for `api/` and `cloud_functions/`; `./venv` is the reference interpreter.
- Pydantic v2; stored data loads through `ModelValidator`, never `Model(**data)`.
- React 18, Vite 6, MUI v6, MUI X **Community** 7 only.
- Firestore `agoge-v1` through `DbCollections` and `DATABASE_NAME`; no string
  literal collection names.
- Imports inside `api/` and `cloud_functions/` are top-level
  (`from core.ctf.event import CtfEvent`), never package-qualified.
- `ctf_id` is ten lowercase letters from `IdGenerator.build_id`, enforced on
  routes by `build_id_path`; `workout_id` path params are enforced the same way.
- ESLint `import/order` with alphabetized imports.
- No runtime dependency is added: `api/requirements.txt`,
  `cloud_functions/requirements.txt`, and `frontend/package.json` dependencies
  are unchanged. The only permitted additions are `pytest-cov` in the root
  `requirements.txt` and the `test` script change in 0.1.
- CTF events can only be created on units built after D4 ships, because only
  those servers carry the loader. Any unit with a `ctf` block satisfies this,
  since the `ctf` field ships in the same release.
- The N2 loader change and the N8 watcher reach only servers built after they
  ship; a unit built earlier must be rebuilt. Until then its nested hosts fall
  back to reset on whole-server plants, and guest-scoped resets fail with
  `"Plant watcher did not respond"`.
- Guest-side software (`qemu-guest-agent`, `libguestfs-tools` on the parent) is
  instructor image preparation, not an Agoge dependency; no requirements file
  changes for Group N.

### Deployment

- Ships through `PYTHONPATH=.:build_files:cloud_functions python setup.py`. No new
  deploy script; `api/deploy.sh` and `frontend/deploy.sh` are unchanged.
- The Cloud Function keeps its entry point and topic; `Handlers.CTF` is a new
  branch in `cloud_functions/main.py`.
- With `ctf_enabled` absent or false the deployment behaves as today: no menu
  item, every `/ctf/` route except `/ctf/config/` answers 404, and student pages
  make one CTF request that returns `enrolled: false`.

---

## Error Handling Strategy

Core classes raise the exceptions in `common/exceptions/agoge.py`. Only routers
translate them, and the CTF routers do it through `to_http_exception` in
`api/utilities/http_errors.py`. FastAPI types never appear in `api/core/`.

The wire shape is FastAPI's default, `{"detail": "<message>"}`, because
`handleError` in `frontend/src/services/api-request.service.ts` reads
`e.response?.data?.detail`.

| Error Type | Raised as | HTTP | Response body |
|------------|-----------|------|---------------|
| Malformed body, unknown action or mode, invalid spec | `BadRequest` | 400 | `{"detail": "<what was wrong>"}` |
| Caller not an instructor on this event or unit | `Unauthorized` | 403 | `{"detail": "Requesting user is not authorized to make this request"}` |
| Caller lacks the permission level | `Forbidden` | 403 | `{"detail": "Insufficient permissions"}` |
| Unknown `ctf_id`, `workout_id`, `server`, `flag_id`; CTF disabled | `NotFound` | 404 | `{"detail": "<object> not found"}` |
| Action illegal in the current state; workout already on an active board | `Conflict` | 409 | `{"detail": "Cannot <action> an event in state <STATE>"}` |
| Student submit when the event is not `RUNNING` | `Conflict` | 409 | `{"detail": "Submissions are closed."}` |
| Submission rate limit exceeded | `RateLimitExceeded` | 429 | `{"detail": "Too many submissions for this challenge. Try again in <n> seconds."}` |
| Seed secret missing | `ServiceUnavailable` | 503 | `{"detail": "CTF is not provisioned on this deployment. Ask an administrator to enable it in setup."}` |
| Unhandled | — | 500 | `{"detail": "Something went wrong"}`, real cause logged |

(401 stays reserved for a missing or invalid Firebase token, which `verify_token` already returns.)

Asynchronous failures never become HTTP errors, because the request has
already returned. They become Firestore state the dashboard renders:

- **A failed plant changes no flag value.** The flag goes to `failed` with
  `plant_error`; every other flag and board is untouched.
- **A partial arm is not an error.** The event goes to `ARMED` with each board's
  `arm_status` visible; `BROKEN` only when zero boards armed.
- **Budget halts are silent in the Cloud Function**, so the dashboard shows
  `budget_exceeded` from `CtfStateResponse` as a banner.

All logging uses `Logger(LoggerNames.API | LoggerNames.CLOUD_FN, class_name=...)`
with messages prefixed `f"{self.class_name}:{ctf_id} - …"` and context passed as
keyword arguments.

---

## Environment Variables

Agoge reads configuration from the Firestore document `admin-info/project` in
`agoge-v1` and from Secret Manager, not from process environment. This feature
adds **no** process environment variable. `api/.env` and
`frontend/.env.production` are generated during deploy; do not add keys to them.

| Variable | Location | Required | Default | Description |
|----------|----------|----------|---------|-------------|
| `ctf_flag_seed` | Secret Manager | Yes when enabled | none | Root secret for flag derivation. Created by `setup.py` when `ctf_enabled` is set true; never created by the API. |
| `ctf_enabled` | `admin-info/project` | No | `false` | Set through `setup.py`. Read by the API with a 60 s cache, not from the lifespan `env_dict`. |
| `ctf_max_boards` | `admin-info/project` | No | `100` | Event creation refuses a unit with more workouts than this. |
| `budget_exceeded` | `admin-info/project` | — | existing | When true, every CTF async action silently does nothing; the dashboard shows a banner. |

---

## Open Questions

Group N only. Resolve each on a live nested host in the development project
before N7 and N9 run in the loop; record the answer here.

- [ ] Does a guest on libvirt's default NAT network reach `169.254.169.254` through the parent today, and does the N1 FORWARD rule stop it? (Bridged setups only hit iptables with `br_netfilter` loaded.)
- [ ] Does a dual-stack instance also need an `ip6tables` FORWARD rule for the IPv6 metadata address?
- [ ] Does the metadata server accept a guest-attribute key of the form `plant-result-<slug>` (hyphens, up to 32 characters)?
- [ ] Does `virsh` in shell mode accept a `qemu-agent-command` line as long as a 256 KB payload's base64 needs, or must the relay chunk with `guest-file-write`?
- [ ] Do guest attributes from a previous boot survive a parent `reset()`? (Affects whether a stale `plant-ack` could be read; the nonce check should make it harmless.)

Group V. Resolve on the development project before the item named; record the answer here.

- [ ] **V-1** (V10) Does 1:1 NAT on an alias IP work with the Google guest agent's local alias routes, and without `canIpForward`? Is the metadata `ip-aliases/` list returned in the order the spec lists the aliases?
- [ ] **V-2** (V10) Does `libvirt-guests` shut a Windows guest down within the time GCE allows during a workout stop, or does the instance need GCE graceful shutdown configured?
- [ ] **V-3** (V9) Which virtio-win release is the last with drivers and qemu-ga for Windows 7 / 2008 R2, and for 8.1 / 2012 R2? Pin them in the catalog.
- [ ] **V-4** (V14) Can Debian 12's libvirt (9.0) take internal snapshots of a UEFI guest? Can Debian 13's? If either can, UEFI becomes an option for Windows 11.
- [ ] **V-5** (V6) What are the current Microsoft Evaluation Center URLs and SHA-256 values for Server 2016/2019/2025 and Windows 10/11 Enterprise (if still offered)? (Server 2022: `https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US` worked on 2026-10-17.) Also the Kali cloud image URL and format.
- [ ] **V-6** (V15) Can the Cloud Run API service account sign V4 URLs once it has `serviceAccountTokenCreator` on itself, and does a browser resumable PUT to the bucket succeed with the CORS rule?
- [ ] **V-7** (V13) What are the size limits on a guest attribute value, and how many keys can one namespace hold?

---

## Design Decisions

Each row is a decision taken deliberately, with the alternative that was
rejected and why. A future iteration that wants to change one of these should
change this table first.

| Decision | Alternative rejected | Why |
|----------|---------------------|-----|
| A CTF event references an existing unit | A new `BuildType.CTF` pipeline | Touching `BuildHandler`, the unit and workout state machines, and the solo/community factories is the largest risk in the repository and buys nothing a reference does not. |
| First planting happens on arm | Planting at unit build | The event, its boards, and its seed do not exist when the unit builds. |
| Flags delivered through a dedicated metadata key run by a loader | Writing `startup-script` directly | `startup-script` already holds Guacamole, assessment, and custom scripts concatenated; overwriting it breaks them, and appending duplicates on every replant. A separate key also means `FlagPlanter` never depends on `LabServerManager` internals. |
| The plant key is removed after every attempt | Leaving the plant script in metadata | Any local user can read instance metadata; a lingering payload hands a slot-1 foothold every root-tier flag on the host. |
| Plants confirmed through guest attributes | Assuming success when `reset()` returns, or a callback to the API | `reset()` returns before the script runs; workout VMs have no egress and no credential to call the API. Guest attributes need neither. |
| Start/pause/resume/end/archive are synchronous | Fanning every action out per board | They change only Firestore; a fan-out adds 40 invocations and an aggregation problem for no work. |
| `CtfStateManager` lives in `common/` | Subclassing `BaseStateManager` in `cloud_functions/` | The API transitions state too, and `BaseStateManager.state_transition()` does not enforce allow-lists. |
| Dedicated `CtfHandler` | CTF branches in each `ControlHandler` method | Keeps CTF dispatch in one file instead of spreading `elif`s across a two-level dispatcher. |
| `api/core/ctf/` package of single-purpose classes | One `api/core/ctf.py` | Event lifecycle, host operations, scoring, and audit change for different reasons; a package also gives the coverage gate a precise target. |
| Separate student router `/ctf-board` | Student routes inside `/ctf/{ctf_id}/…` | The student page knows only its workout id, and the unauthenticated surface stays in one visibly separate file. |
| Digest index collection | Scanning every board on each wrong submission | One document read resolves any value, meeting the 500 ms target. |
| Rate limit keyed by the flag id parsed from the value | Per-flag limit with a challenge selector | The submit box is a single input; the flag format already carries the id. |
| Rate limits in Firestore transactions | In-memory limiter | Cloud Run runs several instances; memory does not span them. |
| Seed created by `setup.py` | API creates it on first use | Keeps `CloudEnv` read-only and avoids relying on the API service account's `roles/owner`. |
| `ctf_enabled` read with a 60 s cache | Reading it from the lifespan `env_dict` | `env_dict` is loaded once per instance; a toggle would not reach running instances. |
| No `RESETTING` server state on replant | Reusing `ServerStates.RESETTING` | The workout nuke flow already writes `RESETTING`; the board's `plant_status` carries replant progress. |
| NPCs deferred to Phase 2 | Per-event Pub/Sub topics | Workout VMs have no egress and no Pub/Sub scope, and the heartbeat had no workable credential. |
| Flag values derived per workout | One shared value per flag | Per-workout derivation makes flag sharing a detected, attributable event. |
| Only the SHA-256 digest is stored | Storing the value for instructor lookup | A Firestore read would leak the answer key. The reveal route re-derives on demand, admin-only, logged. |
| Scoring in the Agoge API and Firestore | Deploying CTFd | A second service, a MySQL instance, an SSO bridge, and a second home for challenge data. |
| Scoreboard freeze is a timestamp | A `FROZEN` state | A frozen scoreboard still accepts submissions. |
| Student routes stay unauthenticated | Requiring a Firebase identity | Matches `GET /workouts/{build_id}/`; changing the trust model is a deliberate Phase 2 decision. |
| Decoy penalties hidden by default; decoy score = spec `points` | Showing the penalty, or a zero-score observation | Showing it tells students which targets to avoid; the spec author already chooses the value. |
| Public scoreboard opt-in per event, off by default | Always on | Classroom evidence on live rankings is mixed; the instructor decides. |
| Team name = `team_name`, else `student_email`, else workout id | Typed by the first student | Uses data the workout already has. |
| No fuzzy flag matching | Reusing `PuzzleControl._similarity` | Fuzzy matching on a 20-hex digest cannot help. |
| Hints cost points and are always available | Time-gated hints | Time gating needs a per-board clock the event does not otherwise need. |
| Archived events are never deleted automatically | Retention in `DailyMaintenance` | Deletion is an explicit admin action. |
| Nested guests reached over the hypervisor (qemu-agent, libguestfs) | SSH/WinRM from the parent, or guests pulling from the parent | Guest subnets and routes vary and the parent may have no address on them; students change passwords and firewalls; a pull endpoint on a shared bridge leaks other guests' flags. |
| Guests declared once in `ctf.nested_guests`, flags keep `server` = parent | Making each guest a `ServerModel` | A guest is not a GCE instance; keeping `server` as the parent leaves instance naming, `mark_stale`, and SC-9 untouched. |
| `qemu-agent` is the default driver | `offline` (libguestfs) as default | qemu-agent keeps the guest running and supports every Windows placement; offline reboots the guest and cannot set ADS, ACLs, or Hidden. |
| A plant watcher on nested hosts | Resetting the parent, as for other servers | A reset hard-kills every guest (disk corruption risk) and a nested reboot does not fit the 540 s function timeout. |
| A guest-scoped plant never resets the parent | Falling back to reset, as whole-server plants do | Resetting the parent to fix one guest disrupts every sibling guest and the teams working on them. |
| One result key per guest | One `plant-result` for the whole server | Guests succeed and fail independently, and the 200-character message would be shared by every guest. |
| Nested lab hosts are ordinary Agoge images built through the existing check-out/check-in cycle | A separate nested-image pipeline and collection | The server picker, sharing, copying, and lab builds already work on `image/<name>`; only the build and the finalize step are new. |
| The build runs on the parent (startup-script builder), with progress in guest attributes | Driving the build from the Cloud Function | A Windows install takes many minutes and the function stops at 540 s; guest attributes already carry CTF plant results without network access. |
| Nested virtualization comes from the `enable-vmx` image license, and is also requested explicitly | Relying on `ip_aliases` to turn it on | Verified 2026-10-17: an instance from a licensed image has VMX without the flag, so a lab server works whether or not the spec author adds aliases. |
| Guests reach the VPC through 1:1 NAT on the lab server's alias IPs | Bridging guests onto the VPC, or port forwards on the primary IP | GCE does not bridge foreign MACs, and alias IPs are already how Agoge marks a nested host; one alias per guest keeps every port of a guest reachable. |
| Guest consoles are VNC on the parent, one port per guest | Requiring network access to each guest | Consoles work for isolated guests, manual installs, and agentless legacy systems, and survive a student breaking a guest's network. |
| Windows 11 and Server 2025 install under BIOS with LabConfig bypass keys | UEFI + Secure Boot + swtpm | Internal `agoge-pristine` snapshots, which N11's rebuild uses, are not available for pflash UEFI guests on Debian 12's libvirt; lab use does not need Secure Boot. |
| Product keys are used at build time and never stored | Saving them on the image document | Firestore image documents are readable by every teacher, and copied when shared. |
| Guest admin passwords are stored on the image document | Write-only secrets | Lab authors need them for Guacamole connections, exactly like `human_interaction` passwords today. |
| Cloud-init is disabled, not purged, in Linux cloud images | Purging it | Purging removed the only network configuration from the Debian cloud image in the 2026-10-17 build. |
| Media is cached in the project bucket by SHA-256 | Downloading on every build | Publisher URLs move and Microsoft links are slow; the cache also makes a rebuild reproducible. |
| One failed guest does not fail the host | All-or-nothing builds | An instructor can fix or replace one guest from the console instead of waiting for a full rebuild. |

---

## Working Notes

Facts about this repository that will otherwise cost an iteration:

1. **Branch.** Work on `release/2027-spring`. It is 25 commits ahead of `main`
   and 6 behind it, and does not contain `main`'s `7d0a5a8`. The gate counts
   above were taken here.
2. **Pre-existing lint and type errors.** `frontend` carries hundreds of
   pre-existing `tsc --noEmit` and ESLint errors. The gates are scoped to new CTF
   paths. Do not fix pre-existing errors as part of a CTF iteration.
3. **Python.** `python` is not on `PATH`; `python3` is 3.14 without the
   dependencies. Use `./venv/bin/python`.
4. **`ServerStates.RESETTING` is used** by the workout nuke flow
   (`base_workout.py`). The CTF feature does not write any server state directly.
5. **State managers.** `ServerStateManager._is_valid_transition` returns `True`
   and `BaseStateManager.state_transition()` never calls `_is_valid_transition`;
   only `WorkoutStatesManager` enforces its allow-list.
6. **`startup-script` is shared.** `LabServerManager._merge_metadata_item`
   concatenates only `startup-script`; any other duplicate key is overwritten.
   D4 extends it for `windows-startup-script-ps1`.
7. **Known broken paths the MVP avoids.** `SnapshotManager.restore_from_snapshot`
   publishes START with `image_name=None` for lab servers, so the server stays
   stopped. `LabServerManager.nuke()` leaves WireGuard gateway servers deleted.
8. **Midnight stop.** `DailyMaintenance._stop_all` stops every running workout;
   E5 exempts CTF boards.
9. **Validation has two save paths.** `edit_manager._validate_spec` and
   `file_manager._validate_spec`; both must call the CTF validator.
10. **Exception mapping elsewhere is inconsistent** (`Unauthorized` is 401 in
    `workout.py` and 403 in `project.py`). The CTF routers use
    `to_http_exception`; leave existing routers alone.
11. **Project settings are admin-only.** `GET /project/` is `admin_required`, so
    the frontend learns `ctf_enabled` only through `GET /ctf/config/`.
12. **UI conventions.** Pages use `Paper`, never `Card`; there is no assessment
    "card" on the student page (assessment is a toggled accordion view).
    `ConfirmationDialog` is type-to-confirm with a hard-coded Delete button.
    Polling uses `hooks/usePolling.tsx`, not `setInterval`. Services pass
    transformer functions into `apiService`.
13. **Tests in `cloud_functions/tests`** use plain pytest without a conftest:
    `object.__new__(Handler)` with attributes set by hand, or `patch.object` on
    `CloudEnv`, `Logger`, `PubSubManager`, and
    `DocumentDatabaseFactory.create_db_object`.
14. **Reference nested host.** `image-nested-hv-debian12` in the development
    project was built by hand on 2026-10-17 and registered as `image/nested-hv-debian12`.
    It carries the `enable-vmx` license. An `n2-standard-4` instance built from it
    **without** `--enable-nested-virtualization` had VMX, and both guests
    autostarted with working agents. Windows Server 2022 went from ISO boot to the
    FirstLogonCommands power-off in under 10 minutes on `n2-standard-8` with
    `--cpu host-passthrough`.
15. **libvirt cannot read `/root`.** qemu runs as `libvirt-qemu`; media under
    `/root` fails with "Permission denied". Keep media under `/var/lib/libvirt/boot/`.
16. **Debian cloud images get their network from cloud-init.** Purging cloud-init
    left the guest with no network configuration; a systemd-networkd `en*` DHCP
    file fixed it. Disable cloud-init instead. `virt-customize --write` does not
    expand `\n`; use `--run-command 'printf …'` or `--upload`.
17. **`virt-install --wait` returns at the first Windows Setup reboot**, not at
    the end of the install. Wait for the domain to reach `shut off` after
    FirstLogonCommands powers it off.
18. **Template servers never get nested virtualization.** `_build_server` checks
    `self.ip_aliases`, which only `LabServerManager._add_nics` sets. In the same
    method, the local `min_cpu_platform` is read before the N1/N2 platform is
    assigned to `server_spec`, so the platform is never sent (V1).
19. **`AgogeImageModel.base_family` defaults to the tuple `(None,)`** because of a
    trailing comma (V5).
20. **Machine types are capped at 17000 MB and N1/N2/E2.** `ComputeMachineType.get`
    returns `None` for anything larger (for example `n2-standard-8`), and
    `_lookup_machine_type` then raises `AttributeError` on `.name`. Today's
    lab and image servers cannot use more than 16 GB (V2).
21. **Template servers can get two `startup-script` items** when the image has a
    custom script and a Linux user-creation script (V4).
22. **Create Image form defects.** It sends `enable_display`, but
    `_generate_human_interaction` reads `display`, so the checkbox does nothing.
    The heading says "Edit Server". No image or server-management component,
    service, or transformer has a vitest test.
23. **Image servers today.** They sit on the `default` network with a public IP
    and a `<name><parent_dns_suffix>` DNS record. The Connect dialog shows SSH/RDP
    to that name; the VPC allows only 22 and 3389 (`default-allow-management`).
    `DailyMaintenance` stops every checked-out template server at midnight.
    Check-in does stop, snapshot, image delete, and image insert in one 540 s
    invocation. `self.server_spec = self.Server` assigns the dataclass itself, so
    attributes persist across calls in a warm function instance; set every field
    the nested path reads. The image routes take raw `request.json()` dicts; the
    nested routes use Pydantic request models.
