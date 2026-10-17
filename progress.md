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
- [ ] **BUG5** `FlagPlanter.plant`'s `except` calls `_fail_unfinished(board, targets)` with the board as it was before `_await_acks`/`_await_results` were called. Those helpers rebind `board` locally, so if one raises mid-loop (e.g. a Firestore error in `_record`), flags they already recorded `planted`/`failed` still read `planting` on the stale model and get overwritten with `MSG_ABORTED`. This predates N9 for `_await_results`. Fix by re-reading stored flag statuses in `_fail_unfinished` (inside the transaction), with a test that raises on the second `_record`.
- [ ] **N10** Guest host reset publish — spec + done-when at PRD.md:1642
- [ ] **N11** Guest host reset modes — spec + done-when at PRD.md:1644
- [ ] **N12** Offline driver — spec + done-when at PRD.md:1646
- [ ] **N13** Nested guests in the spec editor — spec + done-when at PRD.md:1648 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **N14** Guest rows on the Hosts panel — spec + done-when at PRD.md:1650 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **N15** Nested host guide — spec + done-when at PRD.md:1652

### Group V — Nested image builder
See `### Nested Image Builder Contract` and Working Notes 14–23. Independent of the CTF groups except V23. Frontend items use the Group V eslint/tsc gate lines in PRD.md `## Quality Gates`.
- [x] **V1** Nested virtualization for template and lab servers — spec + done-when at PRD.md:1661
- [x] **V2** Nested machine types — spec + done-when at PRD.md:1663
- [ ] **V3** License on check-in — spec + done-when at PRD.md:1665
- [ ] **V4** Template startup-script merge — spec + done-when at PRD.md:1667
- [ ] **V5** Models and constants — spec + done-when at PRD.md:1669 (`common/constants/nested.py` already exists from V2 with `NESTED_MACHINE_FAMILIES`, `NESTED_MAX_MACHINE_MEMORY_MB`, `STANDARD_MAX_MACHINE_MEMORY_MB`; extend it)
- [ ] **V6** OS catalog and seeding — spec + done-when at PRD.md:1671
- [ ] **V7** Nested host validator — spec + done-when at PRD.md:1673
- [ ] **V8** Manifest and unattend rendering — spec + done-when at PRD.md:1675
- [ ] **V9** Builder script — spec + done-when at PRD.md:1677
- [ ] **V10** Runtime service — spec + done-when at PRD.md:1679
- [ ] **V11** Nested template server provisioning — spec + done-when at PRD.md:1681
- [ ] **V12** Create route — spec + done-when at PRD.md:1683
- [ ] **V13** Build monitor — spec + done-when at PRD.md:1685
- [ ] **V14** Finalize handshake — spec + done-when at PRD.md:1687
- [ ] **V15** Media uploads — spec + done-when at PRD.md:1689
- [ ] **V16** Frontend service layer — spec + done-when at PRD.md:1691
- [ ] **V17** Wizard shell and Host step — spec + done-when at PRD.md:1693 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **V18** Networks step — spec + done-when at PRD.md:1695 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **V19** Guests step — spec + done-when at PRD.md:1697 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **V20** Access and Review steps — spec + done-when at PRD.md:1699 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **V21** Image list and details for nested images — spec + done-when at PRD.md:1701 (code and vitest here; the browser check is carried by HUMAN)
- [ ] **V22** Guacamole targets for guests — spec + done-when at PRD.md:1703
- [ ] **V23** Spec editor and CTF integration — spec + done-when at PRD.md:1705 (needs N3, N5, N13; the browser check is carried by HUMAN)
- [ ] **V24** Nested image guide — spec + done-when at PRD.md:1707
- [ ] **V25** Live acceptance — spec + done-when at PRD.md:1708 — **HUMAN ONLY.** Builds real VMs on the development project; the loop must not attempt it. Carried by HUMAN.

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
