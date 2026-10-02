# Agoge CTF — Game Master Control Plane for Capture-the-Flag Exercises

> **Created:** 2026-10-02
> **Author:** liquidswrds
> **Status:** Draft
> **Target branch:** `main` (commit `7d0a5a8` or later)

---

## Overview

### Problem Statement

Agoge provisions per-student lab environments but has no way to run a timed,
scored, competitive exercise across them. An instructor who wants to run a CTF
today must build a unit, hand out the workout links, and then track flags,
scores, host breakage, and the clock by hand — in a spreadsheet, outside the
product. There is no supported way to plant a flag, re-plant one after a
student destroys the host it lives on, generate background network activity so
detection work is a real exercise, reset one team's host without disturbing
another's, or start and stop the whole exercise on a schedule. The vestigial
`EscapeRoomModel` in `common/models/agoge.py` is the only trace of a previous
attempt and has no live implementation.

### Solution

Add a **CTF control plane** that layers on top of an existing Agoge unit. A CTF
event is a Firestore document that references a built unit; every workout in
that unit becomes a team board. Instructors and game masters get a dashboard at
`/teacher/ctf/{ctf_id}` with five panels — Event Control, Flags, NPCs, Hosts,
Scoreboard — plus an event log. Students keep the workout page they already
have, gaining three cards: a CTF status banner, a challenge list, and a flag
submission box.

The control plane reuses Agoge's existing machinery rather than introducing a
parallel one: flags are planted through GCE instance metadata startup scripts
(the same channel `AssessmentManager` already uses), NPCs are driven by a
per-event Pub/Sub topic (the same pattern `agent_configuration.py` already
uses), host resets go through the existing `ComputeManagerFactory` and
`SnapshotManager`, and every long-running action is published to the `agoge`
topic for the Cloud Function to execute.

### Target Users

- **Primary — Game master / instructor:** needs one page that answers "is the
  exercise running, are the flags where I put them, are the NPCs alive, which
  host is broken, who is winning", and lets them act on each answer without a
  shell.
- **Secondary — Student / team:** needs their existing workout page, plus the
  challenges they can attempt, the flags they have captured, and their standing.
- **Secondary — Agoge administrator:** needs CTF activity visible in the same
  structured logs and budget controls as every other Agoge build.

---

## Goals

- **Plant flags.** Every flag declared in a lab specification lands on every
  team's servers at build time, verified by a per-flag SHA-256 digest recorded
  in Firestore.
- **Reset hosts.** A game master puts one team's one server back in four modes,
  the fastest of which finishes in under 180 seconds without deleting the
  instance and without touching any other team.
- **Control NPCs.** A game master queues a timeline deploy or a stop to any
  NPC-bearing server from the dashboard, with each row showing that NPC's last
  heartbeat age.
- **Start and stop the exercise.** Arm, start, pause, resume, and end each have
  one control, fanning out across every team board in the unit.
- **Detect flag sharing.** Every flag value is derived per workout, so a value
  captured in workout A and submitted in workout B is recorded as
  `cross_submission` on the game master's dashboard within the same request.
- **Preserve the student experience.** The student workout page keeps its
  existing layout, route, and auth model, gaining exactly three cards.

## Non-Goals

These are explicitly out of scope. Do not build them, do not scaffold them, and
do not add configuration hooks for them.

- **No CTFd, and no second scoring service.** Scoring lives in the Agoge API and
  Firestore. Do not add a Cloud Run service, a MySQL instance, an SSO bridge, or
  a plugin host.
- **No attack/defense format.** No service-availability (SLA) checks, no round
  ticks, no flag rotation on a timer, no stealing flags from another team's
  hosts, no per-round scoring.
- **No new `BuildConstants.BuildType` member and no new build pipeline.** A CTF
  rides on an existing `UnitModel`. Do not modify `BuildHandler`, `SoloWorkout`,
  `CommunityWorkout`, `UnitStates`, or `WorkoutStates`.
- **No per-challenge containers.** Challenges live on the VMs the unit already
  builds. No Docker, no Kubernetes, no Cloud Run challenge instances.
- **No public or unauthenticated-internet scoreboard.** The scoreboard is served
  by the same API behind the same path routing as the rest of the app.
- **No writeup submission, no report grading, no rubric generation for CTF.**
  `RubricModel` and the LLM rubric generator are untouched.
- **No team self-registration, no new identity provider, and no change to
  `verify_token` or `ProtectedRoute`.** Teams are the workouts the unit already
  created; membership is the existing join code.
- **No WebSocket or server-sent-event push in Phase 1.** The dashboard polls, as
  `TeacherUnit` and `StudentWorkout` already do. `api/utilities/connection_manager.py`
  stays unused.
- **No cost or budget UI.** `BudgetManager` and `budget_exceeded` already own
  spend control. The CTF dashboard links to admin project settings; it does not
  reimplement them.
- **No offensive NPCs.** NPCs generate benign background activity only. They do
  not exploit, scan, or attack. No red-team bot, no `CyberArenaAgent` revival.
- **No MUI X Pro components.** Community DataGrid only, per existing convention.
- **No in-app NPC timeline editor.** Timelines are JSON files synchronized to
  the spec bucket by `setup.py`, like startup scripts already are.
- **No modification of `api/tests/`** (the live, billable integration suite).

---

## Success Criteria

| ID | Criterion | Measurement | Target |
|----|-----------|-------------|--------|
| SC-1 | Creates a CTF event from a unit id | `POST /ctf/` with a valid `unit_id` returns 200 and an `AgogeResponse[AgogeIDResponse]` whose `build_id` matches `^[a-z]{10}$` | 100% of valid requests |
| SC-2 | Rejects a CTF event on a unit with no `ctf` spec block | `POST /ctf/` with a unit built from a spec lacking `ctf` returns 400 with `{"detail": "..."}` | 100% of such requests |
| SC-3 | Derives a distinct flag value per workout | For two workout ids in one event, `derive_flag_value(seed, wid, fid)` returns different strings for every flag id | 0 collisions across 1000 generated pairs in the unit suite |
| SC-4 | Never stores a flag value in Firestore | Grep of every `CtfFlagStateModel` written by the planter contains `digest` and no field whose value matches the flag regex | 0 occurrences |
| SC-5 | Plants every flag at build time | After a unit build completes, every `CtfFlagStateModel` for every board has `planted_at` set and `plant_status == "planted"` | 100% of flags on a successful build |
| SC-6 | Re-plants one server without deleting the instance | `PUT /ctf/{id}/boards/{wid}/hosts/{server}/reset/` with `mode: "replant"` leaves `instances.get` returning the same `id` before and after | 100% of replant calls |
| SC-7 | Completes a single-server replant inside the deadline | Wall-clock from the Pub/Sub publish to `plant_status == "planted"` | ≤ 180 seconds |
| SC-8 | Leaves other boards untouched during a single-host reset | `state_timestamp` on every other board's servers is unchanged after the reset | 0 other boards modified |
| SC-9 | Detects cross-team flag submission | Submitting workout B's derived flag to workout A's `submit` endpoint returns 200 with `correct: false` and writes a `CtfSubmissionModel` with `verdict == "cross_submission"` | 100% of cross submissions |
| SC-10 | Rate-limits flag submissions | The 11th submission to one flag on one board inside 60 seconds returns 429 with `{"detail": "..."}` | 100% over the threshold |
| SC-11 | Reports NPC heartbeat age on every row | `GET /ctf/{id}/npc/` returns one entry per NPC-bearing server with an integer `heartbeat_age_seconds` or `null` | 100% of NPC servers |
| SC-12 | Degrades the NPC panel to read-only when the control plane is stale | With every heartbeat older than `npc_heartbeat_stale_seconds`, `GET /ctf/{id}/npc/` returns 200 with `backend: "UNAVAILABLE"` while `PUT /ctf/{id}/npc/{server}/` returns 503 | 100% of stale-state calls |
| SC-13 | Fans a start out to every board | `PUT /ctf/{id}/action/` with `action: "start"` publishes exactly one Pub/Sub message per board in the unit | message count == board count |
| SC-14 | Honors the scoreboard freeze | After `scoreboard_frozen_at` is set, `GET /ctf/{id}/public-scoreboard/` returns ranks computed from solves with `solved_at <= scoreboard_frozen_at` only | 100% of reads while frozen |
| SC-15 | Never leaks a flag path or host name to a student | `GET /ctf/{id}/board/{wid}/` response contains no `path`, no `server`, and no `location_type` field | 0 occurrences |
| SC-16 | Rejects a specification whose NPC timeline writes a flag path | Saving a spec whose timeline write root contains any flag `path` returns 400 naming the flag id | 100% of such specs |
| SC-17 | Writes one audit row per game-master action | Every `PUT`/`POST` on a `/ctf/` control route appends exactly one `CtfLogModel` document | 1 row per action |
| SC-18 | Leaves the student workout route unchanged | `frontend/src/router/urls.ts` `URL_STUDENT_WORKOUT` and the `StudentWorkout` route definition are byte-identical to `main` | 0 diff |
| SC-19 | Passes every quality gate | The commands in **Quality Gates** all exit 0 | 0 failures |
| SC-20 | Covers new Python modules with tests | `pytest --cov` over `api/core/ctf*.py`, `common/utilities/ctf_flags.py`, and `cloud_functions/cloud_fn_utilities/course_objects/ctf/` | ≥ 85% line coverage |

---

## Architecture

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Control API | FastAPI router `api/routers/ctf.py` | Matches every other Agoge surface; inherits `get_cloud_env`, `teacher_required`, `build_id_path` |
| Core logic | `api/core/ctf.py`, `api/core/ctf_scoring.py` | Convention: core raises `common.exceptions`, routers translate to `HTTPException` |
| Async work | Pub/Sub topic `agoge` → `ControlHandler` | The API never performs a long operation (CLAUDE.md) |
| State | Firestore database `agoge-v1`, four new collections | Same database, same `DocumentDatabaseFactory`, same `DbCollections` enum |
| Flag derivation | `hmac` + `hashlib` from the stdlib | No new dependency; deterministic and reproducible offline in tests |
| Flag seed | Secret Manager secret `ctf_flag_seed`, read lazily by `CloudEnv` | Matches `openai_api_key`, `api_key`, Guacamole passwords |
| Flag planting | GCE instance metadata `startup-script` / `windows-startup-script-bat` | The channel `AssessmentManager` already uses; needs no network path into the workout VPC |
| In-place replant | New `ComputeInstanceAPI.set_metadata()` + existing `reset()` | GCE re-runs the startup script on every boot; `ServerStates.RESETTING` is already declared and unused |
| NPC transport | Per-event Pub/Sub topic + subscription | The pattern `cloud_fn_utilities/server_specific/agent_configuration.py` already establishes |
| NPC timelines | JSON in the spec bucket under `npc_timelines/` | Matches `Buckets.Folders.STARTUP_SCRIPTS`; synchronized by `setup.py` option 11 |
| UI | React 18 + Vite + MUI v6, MUI X **Community** DataGrid | Existing frontend stack; Pro features are banned by convention |
| UI data | `apiService` in `src/services/api-request.service.ts` with polling | Same unwrap contract (`data.items` then `data`) as every other service |

### System Architecture

```
                    ┌──────────────────────────────────────────┐
  Game master ─────▶│  frontend  /teacher/ctf/{ctf_id}         │
  (instructor)      │  ┌────────┬────────┬─────┬───────┬─────┐ │
                    │  │ Event  │ Flags  │ NPC │ Hosts │Score│ │
                    │  │Control │ Panel  │Panel│ Panel │board│ │
                    │  └────────┴────────┴─────┴───────┴─────┘ │
                    └────────────────────┬─────────────────────┘
                                         │  HTTPS (Firebase ID token)
  Student  ────────▶ /student/workout/{build_id}   (unchanged route,
      │                 + CTF banner / challenges / submit card)
      │                                  │
      ▼                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │  agoge-api  (Cloud Run)                                       │
  │    routers/ctf.py ──▶ core/ctf.py          (control)          │
  │                   ──▶ core/ctf_scoring.py  (submit / hints)   │
  │    validates, reads+writes Firestore, publishes Pub/Sub       │
  └──────────┬──────────────────────────────┬─────────────────────┘
             │ writes/reads                 │ publish (topic: agoge)
             ▼                              ▼
  ┌──────────────────────┐      ┌───────────────────────────────┐
  │ Firestore agoge-v1   │      │ agoge_cloud_function          │
  │  agoge-ctf           │◀─────│   BudgetManager.check_budget  │
  │  agoge-ctf-board     │      │   ControlHandler.route()      │
  │  agoge-ctf-submission│      │     CTF_EVENT  → CtfEvent     │
  │  agoge-ctf-log       │      │     CTF_FLAG   → FlagPlanter  │
  │  (existing: unit,    │      │     CTF_NPC    → CtfNpcManager│
  │   workout, server)   │      └───────┬───────────────────────┘
  └──────────────────────┘              │
                                        │ compute API
                           ┌────────────▼─────────────────────────┐
                           │ Per-team workout VPC (already built) │
                           │  ┌────────┐ ┌────────┐ ┌──────────┐  │
                           │  │ target │ │ target │ │ Guacamole│  │
                           │  │ +flags │ │ +flags │ │  proxy   │  │
                           │  │ +NPC   │ │ +NPC   │ └──────────┘  │
                           │  └───┬────┘ └───┬────┘               │
                           └──────┼──────────┼────────────────────┘
                                  │ pull     │ heartbeat (api_key)
                                  ▼          ▼
                      Pub/Sub {ctf_id}-npc   POST /ctf/{id}/npc/heartbeat/
```

Two properties of this shape are contracts, not style:

- **Nothing in Cloud Run or the Cloud Function opens a session to a range host.**
  There is no SSH key, no WinRM password, and no exec service. Every write to a
  VM is a metadata write followed by a boot. This is the single largest
  divergence from the Meridian reference range, and it exists because Agoge's
  workout VPCs have no management subnet and no path from Cloud Run.
- **Every flag value is derived per workout, never stored.** Firestore holds the
  SHA-256 digest; the value is re-derived from the Secret Manager seed whenever
  it is needed, which is at plant time and at submission-check time only.

### Project Structure

```
common/
  constants/
    states.py                  (+ CtfStates, + ServerStates usage of RESETTING)
    database.py                (+ CTF, CTF_BOARD, CTF_SUBMISSION, CTF_LOG)
    pub_sub.py                 (+ Actions.PLANT/ROTATE/RESET,
                                + CourseObjects.CTF_EVENT/CTF_FLAG/CTF_NPC,
                                + EventAttributes.CTF_ID/FLAG_ID/NPC_SERVER/
                                  TIMELINE/RESET_MODE/WORKOUT_ID)
    buckets.py                 (+ Folders.NPC_TIMELINES)
  models/
    agoge.py                   (+ 9 CTF models, listed below)
    response.py                (+ 7 CTF response models)
  utilities/
    ctf_flags.py               NEW — derivation, digest, format, compare
    gcp/
      cloud_env.py             (+ ctf_flag_seed lazy secret property)
      compute/compute_instance.py  (+ set_metadata)

api/
  core/
    ctf.py                     NEW — event CRUD, control publish, flag reads
    ctf_scoring.py             NEW — submit, hints, scoreboard, cross-detect
  routers/
    ctf.py                     NEW — the /ctf router
  main.py                      (+ include_router(ctf_router))
  utilities/infrastructure_as_code/object_validators/
    ctf.py                     NEW — spec-time flag + timeline validation
  unit_tests/
    test_ctf_flag_derivation.py        NEW
    test_ctf_event_lifecycle.py        NEW
    test_ctf_scoring.py                NEW
    test_ctf_spec_validation.py        NEW
    test_ctf_router_auth.py            NEW

cloud_functions/
  cloud_fn_utilities/
    course_objects/ctf/
      __init__.py              NEW
      ctf_event.py             NEW — arm/start/pause/resume/end fan-out
      flag_planter.py          NEW — manifest → per-server plant script
      ctf_npc_manager.py       NEW — topic lifecycle, command publish
      host_reset.py            NEW — replant/restart/snapshot/rebuild
    state_managers/
      ctf_states.py            NEW — CtfStateManager
  handlers/
    control_handler.py         (+ CTF_EVENT / CTF_FLAG / CTF_NPC branches)
  tests/
    test_ctf_event.py                  NEW
    test_flag_planter.py               NEW
    test_ctf_host_reset.py             NEW
    test_ctf_npc_manager.py            NEW
    test_ctf_state_manager.py          NEW

frontend/src/
  components/Ctf/
    CtfDashboard.tsx           NEW — tab shell
    EventControlPanel.tsx      NEW
    FlagsPanel.tsx             NEW
    NpcPanel.tsx               NEW
    HostsPanel.tsx             NEW
    ScoreboardPanel.tsx        NEW
    EventLogPanel.tsx          NEW
    Student/
      CtfBanner.tsx            NEW
      ChallengeList.tsx        NEW
      FlagSubmitCard.tsx       NEW
  services/Ctf/
    ctf.model.ts               NEW
    ctf.service.ts             NEW
    ctf.service.test.ts        NEW
  router/
    urls.ts                    (+ CTF route and API-path constants)
    AppRouter.tsx              (+ 1 protected route)
  components/Common/NavigationBar/AgogeAppBar.tsx   (+ 1 menu entry)
  components/Student/Workout.tsx                    (+ 3 cards, no route change)

docs/guides/
  game-master-guide.md         NEW
```

### Data Models

All Pydantic models go in `common/models/agoge.py`, loaded through
`ModelValidator`, never `Model(**data)`.

```python
# ---------------------------------------------------------------------------
# Specification-side: authored in the lab spec JSON, copied into the unit on
# build, and from the unit into each workout.
# ---------------------------------------------------------------------------

class CtfFlagSpecModel(BaseModel):
    id: str = Field(..., description="Stable slug for this flag, unique within the spec. Pattern ^[a-z0-9][a-z0-9-]{1,31}$")
    server: str = Field(..., description="ServerModel.name this flag is planted on")
    slot: int = Field(..., ge=1, le=9, description="Difficulty tier within the host; slot 1 is reachable by the initial foothold")
    category: Optional[str] = Field(default=None, description="Board grouping, e.g. 'Web', 'Windows', 'Forensics'")
    location_type: str = Field(..., description="file | registry | env | db | ads")
    path: str = Field(..., description="Absolute path, registry key, or locator expression where the planter writes the value")
    operating_system: str = Field(..., description="linux | windows")
    access_level: str = Field(default="user", description="user | root | admin — documentation only; the planter always writes as the boot account")
    points: int = Field(..., description="Awarded on a correct submission. Negative for a decoy.")
    decoy: Optional[bool] = Field(default=False, description="A deliberately out-of-scope flag; submitting it is recorded as a scope observation")
    hint: Optional[str] = Field(default=None, description="Text revealed when a team takes the hint")
    hint_cost: Optional[int] = Field(default=0, ge=0, description="Points deducted when the hint is taken")
    unlocks_after: Optional[List[str]] = Field(default=None, description="Flag ids that must be solved before this one is listed to the team")
    file_mode: Optional[str] = Field(default=None, description="POSIX mode the planter applies, e.g. '0600'. Linux file placements only.")
    file_owner: Optional[str] = Field(default=None, description="Owner the planter applies, e.g. 'root:root'. Linux file placements only.")

    @field_validator('location_type')
    @classmethod
    def known_location(cls, v: str) -> str:
        if v not in ('file', 'registry', 'env', 'db', 'ads'):
            raise ValueError("location_type must be one of file, registry, env, db, ads")
        return v


class CtfNpcSpecModel(BaseModel):
    server: str = Field(..., description="ServerModel.name that runs this NPC")
    timeline: str = Field(..., description="File stem of a timeline JSON in the spec bucket under npc_timelines/")
    operating_system: str = Field(..., description="linux | windows")
    work_root: str = Field(..., description="The only directory tree this NPC may write to. Validated against every flag path.")
    service_account_name: Optional[str] = Field(default="npcsvc", description="Non-privileged local account the NPC client runs as")
    enabled_at_build: Optional[bool] = Field(default=True, description="Whether the client starts with the host or waits for a deploy command")


class CtfScoringSpecModel(BaseModel):
    flag_prefix: Optional[str] = Field(default="agoge", description="Literal prefix of every flag value; the value is '<prefix>{<token>_<digest>}'")
    first_blood_bonus: Optional[int] = Field(default=0, ge=0, description="Extra points for the first board to solve a flag. 0 disables it.")
    submission_rate_limit: Optional[int] = Field(default=10, ge=1, description="Maximum submissions per flag, per board, per 60 seconds")
    reveal_decoy_penalty: Optional[bool] = Field(default=False, description="Whether the board shows a decoy's negative value. Default hides it.")


class CtfSpecModel(BaseModel):
    """The `ctf` block of a lab specification. Its presence makes a unit CTF-capable."""
    name: str = Field(..., description="Display name of the exercise")
    description: Optional[str] = Field(default=None, description="Shown on the team board")
    rules_url: Optional[str] = Field(default=None, description="Link to rules of engagement shown before the first submission")
    flags: List[CtfFlagSpecModel] = Field(..., min_length=1)
    npcs: Optional[List[CtfNpcSpecModel]] = Field(default=None)
    scoring: Optional[CtfScoringSpecModel] = Field(default_factory=CtfScoringSpecModel)


# ---------------------------------------------------------------------------
# Control-plane: collection `agoge-ctf`, doc id = ctf_id (10 lowercase letters)
# ---------------------------------------------------------------------------

class CtfEventModel(BaseModel):
    id: str = Field(..., description="10 lowercase letters from IdGenerator.build_id")
    unit_id: str = Field(..., description="The built UnitModel this event runs on")
    instructor_id: List[str] = Field(..., description="Emails permitted to operate this event")
    spec: CtfSpecModel = Field(..., description="Copied from the unit at event creation; editing the unit afterwards does not change this")
    seed_version: int = Field(default=1, description="Incremented by every seed rotation; part of the derivation input")
    creation_timestamp: float = Field(..., description="UTC epoch seconds")
    starts_at: Optional[float] = Field(default=None, description="UTC epoch seconds the clock started")
    ends_at: Optional[float] = Field(default=None, description="UTC epoch seconds the clock stops; null means open-ended")
    paused_at: Optional[float] = Field(default=None, description="Set while PAUSED; submissions are refused")
    accumulated_pause_seconds: Optional[float] = Field(default=0.0, description="Total paused time, subtracted from elapsed")
    scoreboard_frozen_at: Optional[float] = Field(default=None, description="Solves after this timestamp are hidden from the public scoreboard")
    npc_heartbeat_stale_seconds: Optional[int] = Field(default=600, ge=60, description="Age past which an NPC row is stale and the panel degrades")
    board_ids: List[str] = Field(default_factory=list, description="Workout ids participating as team boards")
    state: int = Field(..., description="CtfStates value")
    state_timestamp: str = Field(..., description="ISO 8601 UTC")

    class Config:
        from_attributes = True


class CtfFlagStateModel(BaseModel):
    """Per-board, per-flag planting state. Embedded in CtfBoardModel."""
    flag_id: str = Field(..., description="CtfFlagSpecModel.id")
    digest: str = Field(..., description="SHA-256 hex of the derived value. The value itself is never stored.")
    plant_status: str = Field(default="pending", description="pending | planting | planted | failed | stale")
    planted_at: Optional[float] = Field(default=None, description="UTC epoch seconds of the last successful plant")
    plant_error: Optional[str] = Field(default=None, description="Last failure message; cleared on success")
    solved: Optional[bool] = Field(default=False)
    solved_at: Optional[float] = Field(default=None, description="UTC epoch seconds of the first correct submission")
    hint_taken: Optional[bool] = Field(default=False)
    hint_taken_at: Optional[float] = Field(default=None)
    attempts: Optional[int] = Field(default=0, description="Count of submissions against this flag on this board")


class CtfNpcStateModel(BaseModel):
    """Per-board, per-NPC runtime state. Embedded in CtfBoardModel."""
    server: str = Field(..., description="ServerModel.name")
    timeline: str = Field(..., description="Timeline file stem currently assigned")
    command_status: str = Field(default="idle", description="idle | queued | running | stopped | unknown")
    queued_at: Optional[float] = Field(default=None, description="UTC epoch seconds a command was published")
    last_heartbeat: Optional[float] = Field(default=None, description="UTC epoch seconds of the agent's last check-in")


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-board`, doc id = workout_id
# ---------------------------------------------------------------------------

class CtfBoardModel(BaseModel):
    workout_id: str = Field(..., description="Doc id; the workout this board scores")
    ctf_id: str = Field(..., description="Parent CtfEventModel.id")
    team_name: Optional[str] = Field(default=None, description="Display name; falls back to the workout's student_email")
    flags: List[CtfFlagStateModel] = Field(default_factory=list)
    npcs: Optional[List[CtfNpcStateModel]] = Field(default=None)
    score: int = Field(default=0, description="Sum of solved flag points, minus hint costs, plus first-blood bonuses")
    solve_count: int = Field(default=0)
    decoy_count: int = Field(default=0, description="Decoy flags submitted; a scope-violation signal, not a score")
    last_solve_at: Optional[float] = Field(default=None, description="UTC epoch seconds, used as the ranking tiebreaker")
    arm_status: str = Field(default="pending", description="pending | arming | armed | failed")

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-submission`, doc id = IdGenerator.uuid()
# ---------------------------------------------------------------------------

class CtfSubmissionModel(BaseModel):
    id: str = Field(..., description="uuid hex")
    ctf_id: str = Field(...)
    workout_id: str = Field(..., description="The board the submission was made from")
    flag_id: Optional[str] = Field(default=None, description="Resolved flag id; null when the value matched nothing")
    submitted_digest: str = Field(..., description="SHA-256 of the normalized submitted string. The submission itself is never stored.")
    verdict: str = Field(..., description="correct | incorrect | duplicate | decoy | cross_submission | rate_limited | closed")
    matched_workout_id: Optional[str] = Field(default=None, description="Set on cross_submission: the board the value actually belongs to")
    points_awarded: int = Field(default=0)
    submitted_at: float = Field(..., description="UTC epoch seconds")
    origin_ip: Optional[str] = Field(default=None, description="request.client.host")


# ---------------------------------------------------------------------------
# Collection `agoge-ctf-log`, doc id = IdGenerator.uuid()
# ---------------------------------------------------------------------------

class CtfLogModel(BaseModel):
    id: str = Field(..., description="uuid hex")
    ctf_id: str = Field(...)
    action: str = Field(..., description="CTF_CREATE | CTF_ARM | CTF_START | CTF_PAUSE | CTF_RESUME | CTF_END | CTF_DELETE | FLAG_REPLANT | FLAG_ROTATE | FLAG_REVEAL | NPC_DEPLOY | NPC_STOP | HOST_RESET | SCOREBOARD_FREEZE | SCOREBOARD_UNFREEZE | SCORE_ADJUST")
    actor: str = Field(..., description="AgogeUser.email, or 'system' for scheduled work")
    target: Optional[str] = Field(default=None, description="workout_id, server name, or flag id the action applied to")
    result: str = Field(..., description="OK | DENIED | ERROR")
    detail: Optional[Dict[str, Union[str, int, bool]]] = Field(default=None, description="Scalar context only. Never a flag value, never a seed.")
    created_at: float = Field(..., description="UTC epoch seconds")
```

Additions to `common/constants/states.py`:

```python
class CtfStates(Enum):
    DRAFT = 0        # created, flags derived, nothing planted
    ARMING = 1       # planting across every board
    ARMED = 2        # every board planted, clock not started
    RUNNING = 3      # clock running, submissions accepted
    PAUSED = 4       # clock held, submissions refused
    ENDING = 5       # stopping boards
    ENDED = 6        # clock stopped, scoreboard final, submissions refused
    ARCHIVED = 7     # NPC topics deleted, event read-only
    BROKEN = 8       # an arm or end failed; game master must act
```

`CtfStateManager` (`cloud_functions/cloud_fn_utilities/state_managers/ctf_states.py`)
subclasses `BaseStateManager` and enforces this allow-list:

```python
VALID_TRANSITIONS = [
    (DRAFT, ARMING), (ARMING, ARMED), (ARMING, BROKEN),
    (ARMED, RUNNING), (ARMED, ARMING), (ARMED, ARCHIVED),
    (RUNNING, PAUSED), (RUNNING, ENDING), (RUNNING, ARMING),
    (PAUSED, RUNNING), (PAUSED, ENDING),
    (ENDING, ENDED), (ENDING, BROKEN),
    (ENDED, ARCHIVED), (ENDED, ARMING),
    (BROKEN, ARMING), (BROKEN, ENDING), (BROKEN, ARCHIVED),
]
```

Additions to `common/constants/database.py`:

```python
CTF = 'agoge-ctf'
CTF_BOARD = 'agoge-ctf-board'
CTF_SUBMISSION = 'agoge-ctf-submission'
CTF_LOG = 'agoge-ctf-log'
```

Additions to `common/constants/pub_sub.py`:

```python
class Actions(Enum):
    PLANT = 18       # plant or re-plant flags
    ROTATE = 19      # rotate the seed, re-derive, then plant
    RESET = 20       # in-place host reset; distinct from NUKE (delete + rebuild)

class CourseObjects(Enum):
    CTF_EVENT = 15
    CTF_FLAG = 16
    CTF_NPC = 17

class EventAttributes:
    CTF_ID = 'ctf_id'
    FLAG_ID = 'flag_id'
    NPC_SERVER = 'npc_server'
    TIMELINE = 'timeline'
    RESET_MODE = 'reset_mode'
    WORKOUT_ID = 'workout_id'
```

### Flag Derivation Contract

`common/utilities/ctf_flags.py` is the single definition. Both the planter and
the submission checker import it; neither reimplements it.

```python
def derive_flag_value(seed: str, workout_id: str, flag_id: str,
                      seed_version: int, prefix: str = "agoge") -> str:
    """
    Returns '<prefix>{<flag_id>_<digest>}' where digest is the first 20 hex
    characters of HMAC-SHA256(seed, f"{seed_version}:{workout_id}:{flag_id}").
    """

def flag_digest(value: str) -> str:
    """SHA-256 hex of normalize_flag(value). The only form ever persisted."""

def normalize_flag(submitted: str) -> str:
    """Strip surrounding whitespace, then lowercase. Nothing else."""

def flags_match(submitted: str, expected_digest: str) -> bool:
    """hmac.compare_digest(flag_digest(submitted), expected_digest)."""
```

The submitted-flag format shown to students, verbatim on the submission card:

```
agoge{<challenge>_<20 hex characters>}
```

Comparison trims surrounding whitespace and is case-insensitive. Nothing else
is normalized — no punctuation stripping, no fuzzy matching. Ambiguous flag
formats are a documented source of avoidable student frustration, and fuzzy
matching on a 20-hex-character digest buys nothing.

### API Endpoints

Every route is under the `/ctf` prefix. `Auth` names the FastAPI dependency.

| Method | Endpoint | Description | Auth | Role |
|--------|----------|-------------|------|------|
| GET | `/ctf/` | Lists CTF events the caller may operate | `teacher_required` | instructor |
| POST | `/ctf/` | Creates an event from `{"unit_id": "..."}` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/` | Returns the event document | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/` | Updates `ends_at`, `npc_heartbeat_stale_seconds`, `scoreboard_frozen_at` | `teacher_required` | instructor |
| DELETE | `/ctf/{ctf_id}/` | Deletes an event in `DRAFT` or `ARCHIVED` only | `admin_required` | admin |
| GET | `/ctf/{ctf_id}/state/` | Returns the event state plus per-board `arm_status` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/action/` | `{"action": "arm"\|"start"\|"pause"\|"resume"\|"end"\|"archive"}` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/flags/` | Flag catalog plus per-board plant status | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/flags/` | Re-plants; body may scope by `workout_ids` and `servers` | `teacher_required` | instructor |
| POST | `/ctf/{ctf_id}/flags/rotate/` | Bumps `seed_version`, re-derives, re-plants every board | `admin_required` | admin |
| GET | `/ctf/{ctf_id}/flags/{flag_id}/reveal/` | Re-derives one board's value; writes `FLAG_REVEAL` | `admin_required` | admin |
| GET | `/ctf/{ctf_id}/npc/` | NPC roster with `heartbeat_age_seconds` and `backend` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/npc/{server}/` | `{"action": "deploy"\|"stop", "timeline": "<stem>", "workout_ids": [...]}` | `teacher_required` | instructor |
| POST | `/ctf/{ctf_id}/npc/heartbeat/` | In-VM agent check-in | `verify_request_origin` + `api_key` header | service |
| GET | `/ctf/{ctf_id}/boards/` | Every board with score and arm status | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/boards/{workout_id}/hosts/{server}/reset/` | `{"mode": "replant"\|"restart"\|"snapshot"\|"rebuild"}` | `teacher_required` | instructor |
| PUT | `/ctf/{ctf_id}/boards/{workout_id}/score/` | Manual adjustment `{"delta": int, "reason": str}` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/scoreboard/` | Full ranking, ignores the freeze | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/submissions/` | Submission log; filterable by `verdict` | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/log/` | Game-master action log, newest first | `teacher_required` | instructor |
| GET | `/ctf/{ctf_id}/board/{workout_id}/` | The team's own challenge list and score | none | student |
| POST | `/ctf/{ctf_id}/board/{workout_id}/submit/` | `{"flag": "<value>"}` | none | student |
| POST | `/ctf/{ctf_id}/board/{workout_id}/hint/{flag_id}/` | Takes a hint, deducts `hint_cost` | none | student |
| GET | `/ctf/{ctf_id}/public-scoreboard/` | Anonymized ranking, honors the freeze | none | student |

**On the unauthenticated student routes.** `GET /workouts/{build_id}/` and
`PUT /workouts/{build_id}/question/{question_key}/` already carry no auth
dependency; knowledge of the ten-letter build id *is* the capability, and
`StudentWorkout` is registered under "Public Endpoints" in `AppRouter.tsx`. The
CTF student routes match that model deliberately, because the brief is that
students see what they see today. The accepted consequence is that anyone
holding a board's workout id can submit against it. Three things bound it:
`submission_rate_limit`, the append-only `agoge-ctf-submission` log with
`origin_ip`, and the fact that on a unit with `registration_required` the
workout link is only ever issued to the claiming student. Do not add auth to
these routes in Phase 1; raising the trust model is a Phase 2 item that changes
the student experience and must be decided deliberately.

All collection responses use `AgogeResponse[T]` with `data = {'items': [...], 'total': n}`;
single objects use `data = <object>`. Returning a bare list breaks
`api-request.service.ts`.

### Host Reset Modes

| Mode | What it does | Instance deleted | Flags change | Typical duration |
|------|--------------|------------------|--------------|------------------|
| `replant` | `set_metadata(startup-script=<plant script>)` then `instances.reset()`; server goes `RESETTING` → `RUNNING` | No | Re-planted, same values | ≤ 180 s |
| `restart` | `ComputeManagerFactory` → `stop()` then `start()` | No | Unchanged | ≤ 240 s |
| `snapshot` | `SnapshotManager.restore_from_snapshot(snapshot_name=...)` | Boot disk swapped | Reverted to the snapshot's; `plant_status` set to `stale` | ≤ 600 s |
| `rebuild` | `ComputeManagerFactory` → `nuke()` (delete then build) | Yes | Re-planted at build, same values | ≤ 900 s |

`snapshot` is the only mode that can leave a host holding flags from an earlier
seed. It therefore always sets every affected `CtfFlagStateModel.plant_status`
to `stale`, which the Flags panel renders as a warning row with a one-click
`replant`.

---

## Features

### MVP (Phase 1)

Ordered by dependency. Each item is one iteration.

**Group A — Contracts and constants**

- [ ] **CTF constants** — Add `CtfStates`, the four `DbCollections` members, the three `PubSub.Actions` members, the three `CourseObjects` members, the six `EventAttributes`, and `Buckets.Folders.NPC_TIMELINES`.
- [ ] **CTF specification models** — Add `CtfFlagSpecModel`, `CtfNpcSpecModel`, `CtfScoringSpecModel`, `CtfSpecModel` to `common/models/agoge.py`.
- [ ] **CTF runtime models** — Add `CtfEventModel`, `CtfFlagStateModel`, `CtfNpcStateModel`, `CtfBoardModel`, `CtfSubmissionModel`, `CtfLogModel`.
- [ ] **CTF response models** — Add the `AgogeResponse` payload shapes to `common/models/response.py`.
- [ ] **Spec block wiring** — Add the optional `ctf` field to `CatalogModel`, `CatalogEditModel`, and `UnitModel` so copy-on-build carries it.

**Group B — Flag derivation**

- [ ] **Derivation module** — Write `common/utilities/ctf_flags.py` with the four functions in the derivation contract.
- [ ] **Seed secret** — Add the lazy `ctf_flag_seed` property to `CloudEnv`.
- [ ] **Derivation tests** — Assert determinism, per-workout uniqueness, seed-version sensitivity, and constant-time comparison.

**Group C — Specification validation**

- [ ] **Flag validator** — Write `api/utilities/infrastructure_as_code/object_validators/ctf.py`: every `CtfFlagSpecModel.server` names a server in the spec, flag ids are unique, slots within a server are unique, `operating_system` matches the server's image family.
- [ ] **NPC timeline validator** — Reject any spec where a `CtfNpcSpecModel.work_root` is a prefix of any flag `path` on the same server, or where a timeline JSON carries an inline credential object.
- [ ] **Validator wiring** — Call the CTF validator from the existing spec-save path so a bad spec is rejected at edit time, not at build time.

**Group D — The planting primitive**

- [ ] **`set_metadata` on the compute API** — Add `ComputeInstanceAPI.set_metadata(resource_name, items, wait=True)` in `common/utilities/gcp/compute/compute_instance.py`, building a `compute_v1.SetMetadataInstanceRequest` whose `metadata_resource` is a `compute_v1.Metadata` carrying the instance's current `fingerprint` plus the merged `Items` list. A stale fingerprint is a 412 from GCE, so the method re-reads the instance immediately before the write.
- [ ] **Plant script builder** — Write `FlagPlanter.build_script(board, server)` producing a Linux shell or Windows batch startup script that writes only that server's flags.
- [ ] **Build-time planting** — Call `FlagPlanter` from `LabServerManager._add_metadata()` alongside `AssessmentManager`, so a unit build plants automatically.
- [ ] **In-place replant** — Write `FlagPlanter.replant(workout_id, server)`: set metadata, transition the server to `RESETTING`, call `instances.reset()`, transition to `RUNNING`, stamp `planted_at`.

**Group E — Event control plane**

- [ ] **Event CRUD core** — Write `api/core/ctf.py` with `create`, `get`, `list`, `update`, `delete`.
- [ ] **Board derivation** — Extend `create` so it copies the unit's `ctf` block into the event, then writes one `CtfBoardModel` per workout with every flag digest pre-derived.
- [ ] **CTF state manager** — Write `CtfStateManager` with the transition allow-list.
- [ ] **Control publish** — Add `process_action` to `api/core/ctf.py` publishing one Pub/Sub message per board for arm/start/pause/resume/end/archive.
- [ ] **CTF event course object** — Write `cloud_functions/.../course_objects/ctf/ctf_event.py` implementing `arm`, `start`, `pause`, `resume`, `end`, `archive`.
- [ ] **Control handler branch — event** — Add the `CourseObjects.CTF_EVENT` branch to `ControlHandler`.
- [ ] **Control handler branch — flags** — Add the `CourseObjects.CTF_FLAG` branch routing `PLANT` and `ROTATE` to `FlagPlanter`.
- [ ] **Host reset dispatcher** — Write `cloud_functions/.../course_objects/ctf/host_reset.py` with a mode-to-method map, routed from `Actions.RESET` in `ControlHandler`. Every mode raises `NotImplementedError` until its own task lands.
- [ ] **Host reset — `replant` mode** — Implement the mode by delegating to `FlagPlanter.replant`.
- [ ] **Host reset — `restart` mode** — Implement the mode by delegating to `ComputeManagerFactory` `stop()` then `start()`.
- [ ] **Host reset — `snapshot` mode** — Implement the mode by delegating to `SnapshotManager.restore_from_snapshot`, marking every affected flag `stale`.
- [ ] **Host reset — `rebuild` mode** — Implement the mode by delegating to `ComputeManagerFactory` `nuke()`.

**Group F — Read API**

- [ ] **Event read routes** — Write `api/routers/ctf.py` with the list, get, state, boards, and log routes.
- [ ] **Flags read route** — Add `GET /ctf/{ctf_id}/flags/` returning the catalog joined to per-board plant status.
- [ ] **Flag reveal route** — Add the admin-only reveal, writing a `FLAG_REVEAL` log row on every call.
- [ ] **Router registration** — Include `ctf_router` in `api/main.py`.

**Group G — NPC control**

- [ ] **NPC topic lifecycle** — Write `CtfNpcManager.create_topics()` / `delete_topics()` for `{ctf_id}-npc` and `{ctf_id}-npc-sub`, called on arm and archive.
- [ ] **NPC command publish** — Add `PUT /ctf/{ctf_id}/npc/{server}/` publishing a deploy or stop command, setting `command_status` to `queued`.
- [ ] **NPC heartbeat endpoint** — Add `POST /ctf/{ctf_id}/npc/heartbeat/` writing `last_heartbeat` on the matching `CtfNpcStateModel`.
- [ ] **NPC status read** — Add `GET /ctf/{ctf_id}/npc/` computing `heartbeat_age_seconds` and returning `backend: "UNAVAILABLE"` when every row is stale.
- [ ] **NPC write refusal** — Make the deploy and stop routes return 503 while the backend is `UNAVAILABLE`.

**Group H — Scoring**

- [ ] **Submission endpoint** — Write `api/core/ctf_scoring.py` `submit()`: normalize, digest, match against this board's flags, record a `CtfSubmissionModel`, award points.
- [ ] **Cross-submission detection** — On a non-match, re-derive the submitted digest against every other board's flags; on a hit, record `verdict: "cross_submission"` with `matched_workout_id`.
- [ ] **Submission rate limiting** — Refuse the `submission_rate_limit + 1`-th attempt on one flag within 60 seconds with 429.
- [ ] **Decoy handling** — Award the negative value, increment `decoy_count`, and return a message that names neither the host nor the penalty.
- [ ] **Hint endpoint** — Deduct `hint_cost`, set `hint_taken`, return the hint text.
- [ ] **Instructor scoreboard endpoint** — Add `GET /ctf/{ctf_id}/scoreboard/`, ranked by score then earliest `last_solve_at`, ignoring the freeze.
- [ ] **Public scoreboard endpoint** — Add `GET /ctf/{ctf_id}/public-scoreboard/`, anonymized, counting only solves at or before `scoreboard_frozen_at` while frozen.
- [ ] **Manual score adjustment** — Add the instructor delta route writing a `SCORE_ADJUST` log row.

**Group I — Game master UI**

- [ ] **CTF TypeScript models** — Write `frontend/src/services/Ctf/ctf.model.ts` mirroring every response shape in the endpoint table.
- [ ] **CTF service functions** — Write `frontend/src/services/Ctf/ctf.service.ts` calling each endpoint through `apiService`.
- [ ] **CTF route registration** — Add the URL constants, the `ProtectedRoute level="instructor"` entry, plus one `AgogeAppBar` menu item.
- [ ] **Dashboard shell** — Render `CtfDashboard.tsx` as a tab shell that polls `GET /ctf/{id}/state/` every 10 seconds, showing a state chip that carries a text label, a distinct glyph, plus a color.
- [ ] **Event Control panel** — Render Arm, Start, Pause, Resume, End, Archive, plus a scoreboard freeze toggle, each behind the existing `ConfirmationDialog`.
- [ ] **Flags panel** — Render a Community DataGrid of flag id, server, slot, points, decoy, per-board plant status, with a Replant control on each row.
- [ ] **Flags panel bulk replant** — Add multi-row selection to the Flags panel driving one scoped `PUT /ctf/{ctf_id}/flags/`.
- [ ] **NPC panel** — Render one row per NPC-bearing server showing timeline, command status, heartbeat age, Deploy, Stop; disable both buttons with an explanatory message when the backend is unavailable.
- [ ] **Hosts panel** — Render one row per board per server showing server state, with a reset control offering the four modes and no default selected.
- [ ] **Scoreboard panel** — Render ranked boards with score, solves, decoy count, last solve time, plus a visible banner while the scoreboard is frozen.
- [ ] **Event log panel** — Render the game-master action log, filterable by action, newest first.
- [ ] **Submission log panel** — Render the submission log, filterable by verdict, newest first.

**Group J — Student UI**

- [ ] **CTF banner** — Add a card to `StudentWorkout` showing event name, state, remaining time, rendered only when the workout has a board.
- [ ] **Challenge list** — Add a card listing each unlocked flag's category, points, solved state, hint control, naming no host, no path.
- [ ] **Flag submission card** — Add a single-input submit card beside the assessment card, showing the expected flag format, reporting the verdict through `SimpleSnackbar`.

**Group K — Documentation**

- [ ] **Game master guide** — Write `docs/guides/game-master-guide.md` covering the arm-to-archive sequence, the four reset modes, what a queued NPC command means, and the reseed procedure.

### Phase 2 (Post-MVP)

- [ ] **Dynamic decay scoring** — Reduce a flag's value as its solve count rises, with a configurable floor.
- [ ] **First-blood bonus** — Award `first_blood_bonus` to the first board to solve each flag.
- [ ] **LMS grade export** — Push final board scores to Canvas or Google Classroom through the existing `LMSIntegrationModel`.
- [ ] **Live scoreboard push** — Replace polling with the existing `ConnectionManager` WebSocket.
- [ ] **Scheduled arming** — Let a game master set a future `starts_at` and have `MaintenanceHandler` arm and start the event.
- [ ] **NPC timeline editor** — Edit and validate timeline JSON in the specification editor.
- [ ] **Scope-violation report** — A per-board report of decoy submissions suitable for a rules-of-engagement grade.
- [ ] **Attack/defense mode** — Round ticks, SLA checks, and per-round flag rotation.
- [ ] **Authenticated team boards** — Require a Firebase identity on the student submit route.

---

## Quality Gates

Every command below must exit 0 before each commit. They run from the
repository root, need no credentials, no network, and no interactive input.
Each one was executed against `main` while this document was written, and the
pass counts in the comments are what it produced.

```bash
# Python suites. PYTHONPATH is mandatory — there is no packaging config, and each
# suite assumes a different sources root. ./venv/bin/python is Python 3.12 with the
# dependencies installed; the system python3 on this machine is 3.14 and lacks them.
PYTHONPATH=.:api                      ./venv/bin/python -m pytest api/unit_tests -q                      # 55 passing on main
PYTHONPATH=.:cloud_functions          ./venv/bin/python -m pytest cloud_functions/tests -q                # 55 passing on main
PYTHONPATH=.:build_files:cloud_functions ./venv/bin/python -m pytest build_files/cloud_deployment/tests -q # 31 passing on main

# Frontend unit tests. Component tests need `// @vitest-environment jsdom` as the
# first line — there is no vitest config file.
cd frontend && npm test                                                                                   # 23 passing on main

# Lint, scoped to the new code. Repo-wide eslint reports 411 pre-existing errors,
# so a repo-wide --max-warnings 0 can never pass.
cd frontend && npx eslint src/components/Ctf src/services/Ctf --max-warnings 0

# Type check, scoped to the new code. tsc has no per-path mode and `main` carries
# 221 pre-existing errors, so the gate asserts that none of them name a CTF file.
# grep finding nothing exits 1, which `!` turns into a pass.
cd frontend && ! npx tsc --noEmit 2>&1 | grep -E '^src/(components|services)/Ctf/'
```

Coverage gate for SC-20. `pytest-cov` is **not** currently installed; the first
iteration that needs this gate adds `pytest-cov>=6,<8` to the root
`requirements.txt` (local dev plus deployment tooling), never to
`api/requirements.txt` or `cloud_functions/requirements.txt`:

```bash
PYTHONPATH=.:api ./venv/bin/python -m pytest api/unit_tests -q \
  --cov=api/core --cov=common/utilities/ctf_flags.py --cov-fail-under=85
PYTHONPATH=.:cloud_functions ./venv/bin/python -m pytest cloud_functions/tests -q \
  --cov=cloud_functions/cloud_fn_utilities/course_objects/ctf --cov-fail-under=85
```

**Do not run `api/tests/`.** It is a live integration suite that builds real VMs,
costs money, takes many minutes, and asserts the active project is in
`ValidTestProjects`. See `api/tests/README.md`.

---

## Constraints

### Performance

- A single-server replant completes within **180 seconds** from Pub/Sub publish
  to `plant_status == "planted"`.
- `GET /ctf/{ctf_id}/state/` returns within **800 ms** at p95 for an event with
  40 boards, achieved by reading the event document plus one collection query —
  never one read per board.
- `POST /ctf/{ctf_id}/board/{workout_id}/submit/` returns within **500 ms** at
  p95, including cross-submission detection across up to 40 boards.
- The game master dashboard polls `state` at **10-second** intervals and the
  scoreboard at **30-second** intervals. No panel polls faster than 10 seconds.
- Arming an event publishes at most **one Pub/Sub message per board**, not one
  per flag.

### Security

- A flag value is never written to Firestore, never written to a log line, never
  placed in a `CtfLogModel.detail`, and never returned by any route except
  `GET /ctf/{ctf_id}/flags/{flag_id}/reveal/`.
- `ctf_flag_seed` is read from Secret Manager at use time and is never written
  to Firestore, a log, an audit row, or a response body.
- Flag comparison uses `hmac.compare_digest`, never `==`.
- The plant script sent to one server carries only that server's flags for that
  one board. A board's manifest is never sent whole to a host.
- A rotation re-plants every board before `seed_version` is incremented. A plant
  failure on any board aborts the rotation, leaves `seed_version` unchanged, and
  returns 500 naming the board that failed.
- An NPC timeline carries no credential. The validator rejects any timeline with
  an inline credential object; credentials come from a file on the host.
- No NPC writes to any path that a flag on the same server occupies. Enforced at
  spec-save time by prefix comparison against every flag `path`.
- Student-facing responses contain no `path`, no `server`, no `location_type`,
  no `digest`, and no `access_level`.
- A decoy submission's response names neither the host nor the penalty value
  unless `reveal_decoy_penalty` is true.
- Every game-master control route writes exactly one `CtfLogModel` row, including
  on denial.

### Compatibility

- Python 3.12 for `api/` and `cloud_functions/`; the repo venv at `./venv` is the
  reference interpreter.
- Pydantic v2; every model loads through `ModelValidator`, never `Model(**data)`.
- Node 20 or later; React 18, Vite 6, MUI v6, MUI X **Community** 7 only.
- Firestore database `agoge-v1` through `DbCollections` and `DATABASE_NAME`; no
  string literal collection names.
- Imports inside `api/` and `cloud_functions/` are top-level
  (`from core.ctf import Ctf`), never package-qualified — the `.staging/` deploy
  copy flattens them.
- Build ids, including `ctf_id`, are ten lowercase letters from
  `IdGenerator.build_id`, enforced on routes by `build_id_path`.
- ESLint enforces alphabetized imports (`import/order`) in the frontend.
- The feature adds no runtime dependency: `api/requirements.txt`,
  `cloud_functions/requirements.txt`, and `frontend/package.json` are
  unchanged. The only permitted addition anywhere is `pytest-cov` in the root
  `requirements.txt`, for the coverage gate.

### Deployment

- The feature ships through the existing interactive menu,
  `PYTHONPATH=.:build_files:cloud_functions python setup.py`. It adds no new
  deploy script and does not change `api/deploy.sh` or `frontend/deploy.sh`.
- NPC timeline JSON synchronizes into the spec bucket under `npc_timelines/`
  through the existing `SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS` operation
  (menu entry 11). No new `SetupOptions` member is required for Phase 1.
- `ctf_flag_seed` is created on first use by the API if the secret is absent,
  with 32 bytes from `secrets.token_hex`. Deployment adds no manual step.
- The Cloud Function deploys unchanged: the CTF branches live inside the
  existing `ControlHandler`, on the existing `agoge` topic, in the existing
  `agoge_cloud_function` entry point.
- A deployment with `ctf_enabled` absent or false behaves exactly as `main`
  does today: no navigation entry, and every `/ctf/` route answers 404.

---

## Error Handling Strategy

Core classes raise the exceptions in `common/exceptions/agoge.py`. Only routers
translate them into `HTTPException`. FastAPI types never appear in `api/core/`.

The wire shape is FastAPI's default, `{"detail": "<message>"}`, because
`handleError` in `frontend/src/services/api-request.service.ts` reads
`e.response?.data?.detail`. Do not invent a different envelope.

| Error Type | Raised as | HTTP | Response body |
|------------|-----------|------|---------------|
| Malformed body, unknown action, unknown reset mode | `BadRequest` | 400 | `{"detail": "<what was wrong>"}` |
| Caller is not an instructor on this event | `Unauthorized` | 401 | `{"detail": "Requesting user is not authorized to make this request"}` |
| Caller lacks the permission level for the route | `Forbidden` | 403 | `{"detail": "Insufficient permissions"}` |
| Unknown `ctf_id`, `workout_id`, `server`, or `flag_id` | `NotFound` | 404 | `{"detail": "<object> not found"}` |
| Action illegal in the current `CtfStates` | `Conflict` | 409 | `{"detail": "Cannot <action> an event in state <STATE>"}` |
| Submission rate limit exceeded | `RateLimitExceeded` | 429 | `{"detail": "Too many submissions for this challenge. Try again in <n> seconds."}` |
| Plant failed on a host | `ServiceUnavailable` | 500 | `{"detail": "Flag plant failed on <server> for board <workout_id>"}` |
| NPC control plane stale | `ServiceUnavailable` | 503 | `{"detail": "The NPC control plane is not answering, so no command can be queued."}` |
| Event not `RUNNING` on a student submit | `Conflict` | 409 | `{"detail": "Submissions are closed."}` |
| Unhandled | — | 500 | `{"detail": "Something went wrong"}`, with the real cause logged |

Three behaviors are contracts rather than defaults:

- **A failed plant never rotates the seed and never changes a flag value.** The
  affected `CtfFlagStateModel` goes to `plant_status: "failed"` with
  `plant_error` set; every other board is untouched.
- **A partial arm answers 200, not 500.** The response names each board's
  `arm_status`. Turning "38 of 40 armed" into a 500 tells the game master
  nothing except to try again. The event goes to `BROKEN` only when zero boards
  armed.
- **An unreachable NPC control plane degrades reads, never writes.**
  `GET /ctf/{ctf_id}/npc/` answers 200 with `backend: "UNAVAILABLE"` and the last
  state Firestore holds; deploy and stop answer 503 and write nothing. A stale
  row tells the game master more than an empty panel, and the rest of the
  dashboard is unaffected.

All logging uses `Logger(LoggerNames.API | LoggerNames.CLOUD_FN, class_name=...)`
with messages prefixed `f"{self.class_name}:{ctf_id} - …"` and context passed as
keyword arguments.

---

## Environment Variables

Agoge reads configuration from the Firestore document `admin-info/project` in
the `agoge-v1` database and from Secret Manager, not from process environment
or `.env` files. This feature adds **no** environment variable to `api/.env`,
`frontend/.env.production`, the Cloud Run service definitions, or the Cloud
Function. The table below is the equivalent configuration surface; the
`Location` column says where each one actually lives.

`api/.env` and `frontend/.env.production` are generated during deploy and
restored afterwards. Do not add a key to either expecting it to persist.

| Variable | Location | Required | Default | Description |
|----------|----------|----------|---------|-------------|
| `ctf_flag_seed` | Secret Manager secret | Yes | none | Root secret for flag derivation. Created by `setup.py` on first CTF use; rotating it invalidates every planted flag until the next replant. |
| `ctf_enabled` | `admin-info/project` field | No | `false` | Hides the CTF navigation entry and makes every `/ctf/` route answer 404 when false. |
| `ctf_default_stale_seconds` | `admin-info/project` field | No | `600` | Default for `CtfEventModel.npc_heartbeat_stale_seconds` on new events. |
| `ctf_max_boards` | `admin-info/project` field | No | `100` | Refuses event creation on a unit with more workouts than this. |
| `api_key` | Secret Manager secret | Yes | existing | Already present. Reused to authenticate the NPC heartbeat route. |
| `spec_bucket` | `admin-info/project` field | Yes | existing | Already present. NPC timelines are synchronized into `npc_timelines/` within it. |
| `budget_exceeded` | `admin-info/project` field | — | existing | Already present. When true, `BudgetManager` halts every Cloud Function invocation, so arming, planting, resetting, and NPC commands all silently do nothing. The dashboard surfaces this as a banner. |

---

## Open Questions

Every item here must be resolved and struck from this list before the build
loop starts. Each one names the default the implementation takes if nobody
answers, so an unanswered question blocks review, not work.

- [ ] **Flag prefix.** Is `agoge{...}` the wanted literal, or should it carry
      the course or institution (`ualr{...}`, `csec{...}`)? It is per-spec via
      `CtfScoringSpecModel.flag_prefix`. *Default if unanswered:* `agoge`.
- [ ] **Team identity on community units.** A `CommunityWorkout` is shared by
      several students. Does the board's `team_name` come from
      `WorkoutModel.team_name`, from the join code, or is it typed by the first
      student to open the board? *Default if unanswered:*
      `WorkoutModel.team_name`, falling back to the workout id.
- [ ] **NPC client software.** The reference range runs GHOSTS clients. Does
      Agoge ship the same binary in its images, write a smaller purpose-built
      agent, or reuse the existing Kali agent image
      (`BuildConstants.MachineImages.AGENT`)? This decides whether
      `timeline.schema.json` is GHOSTS' schema or a new one. *Default if
      unanswered:* a purpose-built agent with an Agoge-defined timeline schema,
      because it has no license question and no pinned upstream version.
- [ ] **Which images carry NPC and flag tooling.** Planting a registry value or
      an NTFS alternate data stream needs PowerShell on the image; planting a
      database row needs a client. Is the plant script allowed to assume those
      exist, or must the validator restrict `location_type` per image family?
      *Default if unanswered:* the validator restricts `registry` and `ads` to
      Windows images and `db` to servers whose `details.labels` include a
      database label.
- [ ] **Scoreboard visibility to students.** Research on classroom CTFs is split
      on whether a live ranked scoreboard helps or discourages. Should
      `GET /ctf/{ctf_id}/public-scoreboard/` be enabled by default, opt-in per
      event, or instructor-only? *Default if unanswered:* opt-in per event
      through a `public_scoreboard_enabled` field, defaulting to false.
- [ ] **Decoy semantics.** The reference range scores a decoy −50 and treats a
      submission from the designated off-limits host as a rules-of-engagement
      finding. Does Agoge want the same negative score, a zero-score
      observation, or only a dashboard signal with no score effect? *Default if
      unanswered:* the spec's `points` value, which may be negative, plus the
      `decoy_count` signal.
- [ ] **Event retention.** How long does an `ARCHIVED` event and its submission
      log survive before `DailyMaintenance` deletes it? *Default if
      unanswered:* never deleted automatically; deletion is an explicit
      admin action.

---

## Design Decisions

Each row is a decision taken deliberately, with the alternative that was
rejected and why. A future iteration that wants to change one of these should
change this table first.

| Decision | Alternative rejected | Why |
|----------|---------------------|-----|
| A CTF event references an existing unit | A new `BuildConstants.BuildType.CTF` with its own build pipeline | Touching `BuildHandler`, the unit and workout state machines, and the solo/community factories is the largest risk in the repository and buys nothing a reference does not. |
| Flags planted through GCE instance metadata | An execution service holding SSH and WinRM credentials, as the Meridian range uses | Agoge's workout VPCs have no management subnet and no path from Cloud Run. Metadata is a channel that already works, already runs on every boot, and needs no new credential. |
| In-place replant is `set_metadata` plus `instances.reset()` | `nuke()` (delete and rebuild) for every replant | A rebuild costs the team its foothold and roughly 15 minutes. `ServerStates.RESETTING` is already declared and unused for exactly this. |
| Flag values derived per workout | One shared value per flag, as the Meridian range uses | Agoge already gives every student an isolated VPC, so per-workout derivation is free — and it converts flag sharing from an accepted loss into a detected, attributable event. This is the single largest capability the Agoge architecture grants over the reference range. |
| Only the SHA-256 digest is stored | Storing the value for easy instructor lookup | A Firestore read then leaks the answer key. The reveal route re-derives on demand, admin-only, and logs every call. |
| Scoring in the Agoge API and Firestore | Deploying CTFd beside the app, as the Meridian range does | CTFd means a second Cloud Run service, a MySQL instance, an SSO bridge, and a second place where challenge data lives. Agoge already has submit-and-check in `AssessmentModel`, a React app, and Firestore. |
| NPCs driven by a per-event Pub/Sub topic | A GHOSTS API server inside the range, as the Meridian range uses | A range-resident API server needs a management subnet, a static address, and a firewall path from Cloud Run — none of which a per-student workout VPC has. `agent_configuration.py` already establishes the topic-plus-subscription pattern in this repository. |
| The NPC panel degrades read-only, writes return 503 | Returning 503 for the whole panel | Carried over from the Meridian range unchanged because it is right: a stale row tells the operator more than an empty panel, and the exercise is not down just because a command cannot be queued. |
| Scoreboard freeze is a timestamp, not a state | A `FROZEN` member of `CtfStates` | A frozen scoreboard still accepts submissions. Making it a state would force every transition to be written twice. |
| Student routes stay unauthenticated | Requiring a Firebase identity on submit | The brief is that students see what they see today, and `GET /workouts/{build_id}/` already carries no auth. Changing the trust model is a deliberate Phase 2 decision, not a side effect. |
| Decoy penalties are hidden by default | Showing the negative value on the card | A card that shows the penalty tells a student which targets to avoid, which is the thing they are supposed to know from their own rules of engagement. |
| No fuzzy flag matching | Reusing `PuzzleControl._similarity` | Ambiguous flag formats are a documented source of avoidable student frustration, and fuzzy matching on a 20-hex-character digest cannot help. Trim and lowercase, nothing else. |
| Hints cost points and are always available | Time-gated hint release | Time gating requires a per-board clock the event does not otherwise need, and a cost already discourages casual use while keeping a stuck team moving. |
| Dynamic decay scoring deferred to Phase 2 | Shipping it in the MVP | Static points are what an instructor can predict and grade against. Decay needs a solve-count read on every scoreboard render and changes a team's score without the team doing anything. |

---

## Working Notes

Four facts about this repository that will otherwise cost an iteration:

1. **Build on `main`, not on the `v2026.09` tag.** The quality gates were
   verified at `main` commit `7d0a5a8`. At `v2026.09` the three Python test
   directories and the three frontend test files do not exist,
   `frontend/package.json` has no `test` script, and vitest is not installed,
   so every command in **Quality Gates** fails or collects nothing. Confirm
   with `git branch --show-current` before the first iteration.

2. **`main` carries 221 pre-existing `tsc --noEmit` errors and 760 ESLint
   problems (411 of them errors).** Repo-wide zero-error gates are unreachable
   and must not be attempted as part of this work. The gates above are scoped to
   the new `Ctf` paths for exactly this reason. Do not "fix" the pre-existing
   errors as part of a CTF iteration; that is a separate change.

3. **`python` is not on `PATH`; `python3` is 3.14 and lacks the dependencies.**
   Use `./venv/bin/python` (3.12) for every Python command, or activate the
   venv first. The `python -m pytest` form printed in `CLAUDE.md` assumes an
   activated venv.

4. **`ServerStates.RESETTING` and `ServerStates.RELOADING` are declared but
   unused** anywhere in the tree today. `RESETTING` is the state the replant
   path takes; claiming it is intended, not an accident to be worked around.
   `ServerStateManager._is_valid_transition` returns `True` unconditionally, so
   no allow-list edit is needed to use it.
