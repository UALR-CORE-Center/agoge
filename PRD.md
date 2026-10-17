# Agoge CTF — Game Master Control Plane for Capture-the-Flag Exercises

> **Created:** 2026-10-02
> **Revised:** 2026-10-16 — audit fixes: metadata-safe planting, arm aggregation, NPCs and rotation moved to Phase 2, gates re-verified
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
  write followed by a boot; every answer from a VM is a guest attribute.
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
  the key is removed. Failure to install it is not a plant failure.
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
| PUT | `/ctf/{ctf_id}/boards/{workout_id}/hosts/{server}/reset/` | `CtfHostResetRequest`; one `CTF_HOST_RESET` | `teacher_required` | instructor |
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

---

## Features

### MVP (Phase 1)

Ordered by dependency. Each item is one iteration and includes its own tests.

**Group 0 — Green baseline**

- [ ] **0.1 Frontend test script** — Change `frontend/package.json` `"test"` to `vitest run --exclude "tests/**"` so vitest stops collecting the `node:test` files in `frontend/tests/`.
  - Done when: `(cd frontend && npm test)` exits 0 with 23 tests passing; the two `.mjs` files are untouched.
- [ ] **0.2 Rubric opt-in tests** — Make the four failing tests in `api/unit_tests/test_rubric_opt_in.py` pass.
  - Done when: `api/unit_tests` reports 49 passed, 0 failed; no test is deleted or skipped; `test_storing_openai_key_does_not_enable_rubrics` no longer reaches a real `input()` call.

**Group A — Contracts and constants**

- [ ] **A1 CTF constants** — Add `CtfStates`, six `DbCollections` members, `Handlers.CTF`, three `Actions`, three `EventAttributes`.
  - Done when: a unit test asserts no new `Actions` value collides with an existing one.
- [ ] **A2 CTF specification models** — Add `CtfFlagSpecModel`, `CtfScoringSpecModel`, `CtfSpecModel` and the `Literal` aliases.
  - Done when: tests reject a bad flag id, an unknown `location_type`, and a malformed `file_mode`.
- [ ] **A3 CTF stored models** — Add `CtfEventModel`, `CtfFlagStateModel`, `CtfBoardModel`, `CtfDigestModel`, `CtfRateLimitModel`, `CtfSubmissionModel`, `CtfLogModel`.
- [ ] **A4 CTF request models** — Add the seven request models.
- [ ] **A5 CTF response models** — Add the response models to `common/models/response.py`.
- [ ] **A6 Spec block wiring** — Add `ctf: Optional[CtfSpecModel]` to `CatalogModel`, `CatalogEditModel`, `UnitModel`.
  - Done when: a test builds `CatalogEditModel → CatalogModel → UnitModel` and the `ctf` block survives each step, matching `test_opt_in_survives_specification_models_and_lab_build`.

**Group B — Flag derivation and state**

- [ ] **B1 Derivation module** — Write `common/utilities/ctf_flags.py` with the five contract functions.
  - Done when: tests cover determinism, per-workout uniqueness (SC-3), `seed_version` sensitivity, case/whitespace normalization, `parse_flag_id` hits and misses, and that `flags_match` calls `hmac.compare_digest`.
- [ ] **B2 Seed property** — Add the lazy `ctf_flag_seed` property to `CloudEnv`, matching `openai_api_key`.
- [ ] **B3 Seed provisioning** — In `environment_variables.py`, add `ctf_enabled`; when set to true, create `ctf_flag_seed` with `secrets.token_hex(32)` if absent.
  - Done when: a build_files test with mocked Secret Manager shows the secret is created once and not overwritten on a second enable.
- [ ] **B4 CTF state manager** — Write `common/utilities/ctf_state_manager.py`.
  - Done when: tests accept every allowed transition, raise `Conflict` for `(RUNNING, ARMING)` and `(ENDED, RUNNING)`, and stamp `state_timestamp`.

**Group C — Specification validation**

- [ ] **C1 Flag validator** — Write `object_validators/ctf.py`: every `server` names a server in the spec; flag ids unique; `(server, slot)` unique; every flag on one server has the same `operating_system`; `path` matches its row in Flag Location Formats; `registry`/`ads` require `windows`; non-decoy `points > 0`; every `unlocks_after` id exists and the graph has no cycle.
  - Done when: one test per rule rejects a bad spec with a message naming the flag id.
- [ ] **C2 Validator wiring** — Call the validator from both `edit_manager._validate_spec` and `file_manager._validate_spec` when `ctf` is present.
  - Done when: a test per save path shows an invalid `ctf` block is rejected.

**Group D — Compute primitives and the loader**

- [ ] **D1 `set_metadata`** — Add `ComputeInstanceAPI.set_metadata(resource_name, items: dict, remove: list = None, wait=True)`: re-reads the instance for its current `fingerprint`, merges `items` into the existing metadata, drops keys in `remove`, and leaves every other key unchanged.
  - Done when: tests show the merge keeps unrelated keys and that a 412 (stale fingerprint) triggers one re-read and retry.
- [ ] **D2 `get_guest_attributes`** — Add `ComputeInstanceAPI.get_guest_attributes(resource_name, query_path)` returning a `{key: value}` dict, empty when none exist.
- [ ] **D3 Plant contract module** — Write `common/utilities/ctf_plant_contract.py` with the names and both loader stubs.
- [ ] **D4 Loader at build** — In `LabServerManager._add_metadata`, add the Linux loader through `_merge_metadata_item` and the Windows loader as `windows-startup-script-ps1`; extend `_merge_metadata_item` to concatenate `windows-startup-script-ps1`.
  - Done when: tests show an existing `startup-script` and assessment script are kept with the loader appended, and two Windows ps1 scripts are concatenated, not overwritten.

**Group E — Planting**

- [ ] **E1 Payload builder** — Write `FlagPlanter.build_payload(board, server, nonce, seed)` for Linux (bash) and Windows (PowerShell), covering every row of Flag Location Formats.
  - Done when: tests show the payload contains only that server's flags, contains the nonce, and has no command that prints a value (`echo $FLAG`-style).
- [ ] **E2 Plant procedure** — Write `FlagPlanter.plant(board, servers)` per the Plant procedure.
  - Done when: SC-5, SC-6, and SC-7 tests pass against a mocked `ComputeInstanceAPI`.
- [ ] **E3 CTF handler** — Write `cloud_functions/handlers/ctf_handler.py` routing the three CTF actions, and add the `Handlers.CTF` branch to `cloud_functions/main.py`.
  - Done when: a test shows each action reaches its class and an unknown action raises `ValueError`.
- [ ] **E4 Arm worker** — Write `ArmWorker.run(ctf_id, workout_id)`: workout not `WorkoutStates.RUNNING` → board `failed` with `"Workout is not running"`; else plant every flag-bearing server; then aggregate.
  - Done when: SC-15 tests pass for all-armed, mixed, and zero-armed outcomes.
- [ ] **E5 Overnight exemption** — Make `DailyMaintenance._stop_all` skip workouts with an active board in an event in `ARMING`, `ARMED`, `RUNNING`, or `PAUSED`.
  - Done when: SC-20 test passes and non-CTF workouts are still stopped.

**Group F — Event core**

- [ ] **F1 Config and feature flag** — Write `api/core/ctf/config.py` `is_ctf_enabled()` reading `admin-info/project` with a 60-second in-process cache, plus the `ctf_enabled_required` dependency.
  - Done when: a test shows a changed flag is seen after the cache expires.
- [ ] **F2 Error helper** — Write `api/utilities/http_errors.py` `to_http_exception(e)` using the Error Handling table.
- [ ] **F3 Audit helper** — Write `api/core/ctf/audit.py` `CtfAudit.action(...)` context manager writing one `CtfLogModel` with `OK`, `DENIED`, or `ERROR`.
  - Done when: tests cover all three results and show `detail` rejects a value matching `^agoge\{`.
- [ ] **F4 Event create** — *Superseded by L2.* Originally `CtfEvent.create(unit_id, user)` built one board per existing workout; creation now starts from a catalog template with no teams, and boards are added per team in DRAFT.
  - Done when: SC-1, SC-2, and the SC-4 check on created documents pass.
- [ ] **F5 Event read, update, delete** — Add `get`, `list`, `update` (applies only fields in `model_fields_set`), `delete` (per the endpoint table).
- [ ] **F6 Event actions** — Add `process_action` per the action map.
  - Done when: SC-13 and SC-14 tests pass and an illegal action raises `Conflict` naming the state.
- [ ] **F7 Event reads for panels** — Add `state()`, `boards()`, `flags()`, `log()`, `submissions()` returning the response models; `state()` reads the event and one board query.

**Group G — Hosts**

- [ ] **G1 Replant publish** — Write `CtfHosts.replant(ctf_id, workout_ids, servers, user)` publishing one `CTF_PLANT` per board+server.
- [ ] **G2 Host rows** — Add `CtfHosts.hosts(ctf_id)` joining boards to their workouts' server documents.
- [ ] **G3 Reset publish** — Add `CtfHosts.reset(ctf_id, workout_id, server, mode, user)`; `rebuild` on a WireGuard server → `BadRequest`.
- [ ] **G4 Reset dispatcher** — Write `host_reset.py` with a mode → method map called by `CtfHandler`.
  - Done when: SC-9 test passes and an unknown mode raises `ValueError`.
- [ ] **G5 Reset `replant`** — Delegate to `FlagPlanter.plant(board, [server])`.
- [ ] **G6 Reset `restart`** — Delegate to `ComputeManagerFactory` `stop()` then `start()`.
- [ ] **G7 Reset `rebuild`** — Delegate to `ComputeManagerFactory` `nuke()`, then mark that server's flags `stale`.

**Group H — Scoring**

- [ ] **H1 Submission resolve** — Write `CtfScoring.submit` steps 1, 3, 4, 5, 7 (closed, lookup, incorrect, cross-submission, record).
  - Done when: SC-10 test passes.
- [ ] **H2 Solve award** — Add step 6 in a board transaction.
  - Done when: SC-12 concurrency test passes and decoy points apply with `decoy_count`.
- [ ] **H3 Rate limiting** — Add step 2.
  - Done when: SC-11 test passes and a new window resets the count.
- [ ] **H4 Hints** — Add `CtfScoring.hint`: deducts `hint_cost` once; a second call returns the hint without deducting.
- [ ] **H5 Student board read** — Add `CtfScoring.board(workout_id)` returning `CtfStudentBoardResponse`, hiding decoys and flags whose `unlocks_after` are unsolved.
  - Done when: SC-17 test passes on the response.
- [ ] **H6 Scoreboards** — Add instructor ranking (score desc, then earliest `last_solve_at`) and public ranking (anonymized, `is_you`, freeze-aware).
  - Done when: SC-16 test passes.
- [ ] **H7 Score adjustment** — Add `CtfScoring.adjust(ctf_id, workout_id, delta, reason, user)` writing `SCORE_ADJUST`.

**Group R — Routers**

- [ ] **R1 Instructor router** — Write `api/routers/ctf.py` with every `/ctf` route, using `to_http_exception` and `CtfAudit`.
- [ ] **R2 Student router** — Write `api/routers/ctf_board.py` with every `/ctf-board` route.
- [ ] **R3 Router registration** — Include both routers in `api/main.py`.
- [ ] **R4 Router auth tests** — Write `test_ctf_router_auth.py`.
  - Done when: a non-instructor gets 403 on every `/ctf` route, a non-admin gets 403 on DELETE, reveal returns 403 for an instructor, and SC-19's 404 behavior holds.

**Group I — Game master UI**

- [ ] **I1 CTF TypeScript models** — Write `services/Ctf/ctf.model.ts` as `export interface`s with snake_case keys mirroring every response and request model.
- [ ] **I2 CTF transformer and service** — Write `utilities/transformers/ctf.transform.ts` and `services/Ctf/ctf.service.ts` calling each endpoint through `apiService`.
  - Done when: `ctf.service.test.ts`, using the mock setup in `rubric.service.test.ts`, covers one GET, one PUT, and one error path.
- [ ] **I3 Feature flag hook** — Write `hooks/useCtfEnabled.tsx` reading `GET /ctf/config/` once per session for instructors.
- [ ] **I4 Routes and menu** — Add `URL_TEACHER_CTF_BASE` (`${URL_TEACHER_BASE}/ctf`) and the dashboard URL, two `ProtectedRoute level="instructor"` routes, and one item in the **Teachers** `AppBarMenu` that is filtered out when `useCtfEnabled` is false.
  - Done when: verified in browser that the item appears only when enabled.
- [ ] **I5 Events list page** — Write `CtfEventList.tsx`: `StyledDataGrid` with Active / Archived `Tabs` (same `sx` as `ActiveExpiredUnitTable`), rows link to the dashboard.
  - Done when: verified in browser.
- [ ] **I6 Create from unit** — Write `CreateCtfButton.tsx` and render it in `TeacherUnit`'s left column only when the unit has a `ctf` block, as `UnitRubricEditor` is gated; on success navigate to the dashboard.
  - Done when: verified in browser that the button is absent on a non-CTF unit.
- [ ] **I7 Action confirm dialog** — Write `Common/Dialogs/ActionConfirmDialog/ActionConfirmDialog.tsx` with props `{open, title, message, confirmLabel, onConfirm, onClose, loading}` and a `LoadingButton`, modelled on `ConfirmCancelDialog`.
- [ ] **I8 CTF state chip** — Add a CTF mapping to `Common/Status/StateMapping.tsx` returning `{text, color, icon}` using theme palette keys, rendered through `StatusBadge` with `icon` and announced through `StateInfo`'s `aria-live`.
- [ ] **I9 Dashboard shell** — Write `CtfDashboard.tsx` copying `TeacherUnit`'s 25/75 `Box` split: left column holds the state chip, remaining time, and Event Control panel in `Paper elevation={2}`; right column holds MUI `Tabs` for Flags, Hosts, Scoreboard, Event Log, Submissions. Polls `state` with `usePolling` every 10 s. Shows an `Alert` banner when `budget_exceeded`.
  - Done when: verified in browser.
- [ ] **I10 Event Control panel** — Render Arm, Start, Pause, Resume, End, Archive, each enabled only in its legal states. Arm/Start/Pause/Resume use `ActionConfirmDialog`; End and Archive use the existing type-to-confirm `ConfirmationDialog`, extended with a `confirmLabel` prop so its button no longer reads "Delete".
  - Done when: verified in browser that illegal actions are disabled.
- [ ] **I11 Scoreboard settings** — Write `ScoreboardSettings.tsx`: freeze toggle, public-scoreboard toggle, `ends_at` picker, each sending `PUT /ctf/{id}/`.
- [ ] **I12 Flags panel** — Render a Community DataGrid of flag id, server, slot, points, decoy, and per-board plant status, with a Replant action per row; `stale` and `failed` rows show a warning icon and text.
- [ ] **I13 Flags bulk replant** — Add Community `checkboxSelection` driving one scoped `PUT /ctf/{id}/flags/`.
- [ ] **I14 Hosts panel** — Render one row per board per server with server state and a reset menu offering `replant`, `restart`, `rebuild` with no default; `rebuild` is disabled with a tooltip when `rebuild_allowed` is false and confirmed with the type-to-confirm dialog.
- [ ] **I15 Scoreboard panel** — Render ranked boards, polled every 30 s, with a visible banner while frozen.
- [ ] **I16 Event log panel** — Render the action log, filterable by action, newest first.
- [ ] **I17 Submission log panel** — Render the submission log, filterable by verdict, newest first, with `cross_submission` rows showing the matched team.

**Group J — Student UI**

- [ ] **J1 Student CTF polling** — In `Workout.tsx`, fetch `GET /ctf-board/{workout_id}/` once on mount; if `enrolled`, poll it with `usePolling` every 15 s (independent of the page's existing 3.5 s workout poll); if not, make no further CTF request.
- [ ] **J2 CTF banner** — Write `CtfBanner.tsx` at the top of the left `aside`, above `TimerBox`: a `Paper` with `component="section"` and `aria-labelledby` (as in `ConfigureAccess.tsx`), showing event name, state, remaining time, and a rules link.
  - Done when: verified in browser; absent when not enrolled.
- [ ] **J3 Flag submission card** — Write `FlagSubmitCard.tsx` in the aside below `ConfigureAccess`: one text field, the flag format shown verbatim, verdicts shown with `showModal(SimpleSnackbar, {severity})`; a 429 shows the server's message.
  - Done when: verified in browser.
- [ ] **J4 Challenge list** — Write `ChallengeList.tsx` in the main column below `WorkoutTable`: category, points, solved state, and a hint button confirmed with `ActionConfirmDialog` stating the cost; no host, no path. When `public_scoreboard_enabled`, add a standings table with the caller's row highlighted.
  - Done when: verified in browser.

**Group K — Documentation**

- [ ] **K1 Game master guide** — Write `docs/guides/game-master-guide.md` covering spec authoring (with a complete `ctf` block example), create-to-archive, the three reset modes, what `stale` and `failed` mean, and the overnight-stop exemption.

**Group L — Setup & rosters**

Replaces create-from-unit. The game master creates an event from **Teachers → CTF Events**, then prepares it in DRAFT before any participant can join.

- [ ] **L1 Shared workout record** — Move `BaseUnit._create_workout_record` into `common/utilities/workout_record.py` `build_workout_record(unit_model, workout_id, …)` so the API can write a NOT_BUILT workout without a Pub/Sub round trip; `BaseUnit` delegates to it.
- [ ] **L2 Create from template** — `CtfSetup.create`: `POST /ctf/` body `{spec_id, name?, expires}`. Solo templates with a `ctf` block only (community → 400). Writes a solo unit (`Unit.new_unit_model`, `ctf_event_id`, `registration_required`, `count` 0) and a DRAFT event with no boards and the unit's `join_code`; publishes nothing. `GET /ctf/templates/` lists eligible templates.
- [ ] **L3 Teams** — `GET|POST /ctf/{id}/teams/`, `PUT|DELETE /ctf/{id}/teams/{workout_id}/`. A team is a board with `members` plus a NOT_BUILT workout (`team_name`, `student_email` = first member). Add/remove only in DRAFT (board id list changed in a transaction that re-checks DRAFT); remove only while NOT_BUILT; names unique per event; an email on at most one active board; `ctf_max_boards` caps teams. Members editable until ENDED.
- [ ] **L4 Per-event flags** — `PUT /ctf/{id}/spec/` in DRAFT only: `CtfSpecModel` + `CtfValidator` against the unit's servers, then every board's flag states and digests are rebuilt and stale digests deleted.
- [ ] **L5 Servers** — `PUT /ctf/{id}/servers/` `{action: build|start|stop}` publishes the existing workout BUILD/START/STOP messages per team (build only NOT_BUILT; stop never while RUNNING). Arm with no boards → 400 "Add at least one team before arming".
- [ ] **L6 Roster-only join** — `Workout._find_existing_workout`: on a unit with `ctf_event_id`, the email resolves through the active board whose `members` contains it (single `array_contains` filter; no composite index) to the team's workout; anyone else → `NotOnRoster` → 403 with a roster message. Non-CTF units unchanged.
- [ ] **L7 Setup UI** — **New CTF** dialog on the events list; a **Setup** tab (default in DRAFT) with Teams (add, CSV import, members, remove, join code), Flags (editor), and Servers (build/start/stop all) sections; Arm disabled until there is a team. The lab-page **Create CTF Event** button is removed.
  - Done when: verified in browser on the development project.

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
