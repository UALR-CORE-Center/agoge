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
- [x] **0.1** Frontend test script — spec + done-when at PRD.md:943
- [x] **0.2** Rubric opt-in tests — spec + done-when at PRD.md:945

### Group A — Contracts and constants
- [x] **A1** CTF constants — spec + done-when at PRD.md:950
- [x] **A2** CTF specification models — spec + done-when at PRD.md:952
- [x] **A3** CTF stored models — spec + done-when at PRD.md:954
- [x] **A4** CTF request models — spec + done-when at PRD.md:955
- [x] **A5** CTF response models — spec + done-when at PRD.md:956
- [ ] **A6** Spec block wiring — spec + done-when at PRD.md:957

### Group B — Flag derivation and state
- [ ] **B1** Derivation module — spec + done-when at PRD.md:962
- [ ] **B2** Seed property — spec + done-when at PRD.md:964
- [ ] **B3** Seed provisioning — spec + done-when at PRD.md:965
- [ ] **B4** CTF state manager — spec + done-when at PRD.md:967

### Group C — Specification validation
- [ ] **C1** Flag validator — spec + done-when at PRD.md:972
- [ ] **C2** Validator wiring — spec + done-when at PRD.md:974

### Group D — Compute primitives and the loader
- [ ] **D1** `set_metadata` — spec + done-when at PRD.md:979
- [ ] **D2** `get_guest_attributes` — spec + done-when at PRD.md:981
- [ ] **D3** Plant contract module — spec + done-when at PRD.md:982
- [ ] **D4** Loader at build — spec + done-when at PRD.md:983

### Group E — Planting
- [ ] **E1** Payload builder — spec + done-when at PRD.md:988
- [ ] **E2** Plant procedure — spec + done-when at PRD.md:990
- [ ] **E3** CTF handler — spec + done-when at PRD.md:992
- [ ] **E4** Arm worker — spec + done-when at PRD.md:994
- [ ] **E5** Overnight exemption — spec + done-when at PRD.md:996

### Group F — Event core
- [ ] **F1** Config and feature flag — spec + done-when at PRD.md:1001
- [ ] **F2** Error helper — spec + done-when at PRD.md:1003
- [ ] **F3** Audit helper — spec + done-when at PRD.md:1004
- [ ] **F4** Event create — spec + done-when at PRD.md:1006
- [ ] **F5** Event read, update, delete — spec + done-when at PRD.md:1008
- [ ] **F6** Event actions — spec + done-when at PRD.md:1009
- [ ] **F7** Event reads for panels — spec + done-when at PRD.md:1011

### Group G — Hosts
- [ ] **G1** Replant publish — spec + done-when at PRD.md:1015
- [ ] **G2** Host rows — spec + done-when at PRD.md:1016
- [ ] **G3** Reset publish — spec + done-when at PRD.md:1017
- [ ] **G4** Reset dispatcher — spec + done-when at PRD.md:1018
- [ ] **G5** Reset `replant` — spec + done-when at PRD.md:1020
- [ ] **G6** Reset `restart` — spec + done-when at PRD.md:1021
- [ ] **G7** Reset `rebuild` — spec + done-when at PRD.md:1022

### Group H — Scoring
- [ ] **H1** Submission resolve — spec + done-when at PRD.md:1026
- [ ] **H2** Solve award — spec + done-when at PRD.md:1028
- [ ] **H3** Rate limiting — spec + done-when at PRD.md:1030
- [ ] **H4** Hints — spec + done-when at PRD.md:1032
- [ ] **H5** Student board read — spec + done-when at PRD.md:1033
- [ ] **H6** Scoreboards — spec + done-when at PRD.md:1035
- [ ] **H7** Score adjustment — spec + done-when at PRD.md:1037

### Group R — Routers
- [ ] **R1** Instructor router — spec + done-when at PRD.md:1041
- [ ] **R2** Student router — spec + done-when at PRD.md:1042
- [ ] **R3** Router registration — spec + done-when at PRD.md:1043
- [ ] **R4** Router auth tests — spec + done-when at PRD.md:1044

### Group I — Game master UI
- [ ] **I1** CTF TypeScript models — spec + done-when at PRD.md:1049
- [ ] **I2** CTF transformer and service — spec + done-when at PRD.md:1050
- [ ] **I3** Feature flag hook — spec + done-when at PRD.md:1052
- [ ] **I4** Routes and menu — spec + done-when at PRD.md:1053
- [ ] **I5** Events list page — spec + done-when at PRD.md:1055
- [ ] **I6** Create from unit — spec + done-when at PRD.md:1057
- [ ] **I7** Action confirm dialog — spec + done-when at PRD.md:1059
- [ ] **I8** CTF state chip — spec + done-when at PRD.md:1060
- [ ] **I9** Dashboard shell — spec + done-when at PRD.md:1061
- [ ] **I10** Event Control panel — spec + done-when at PRD.md:1063
- [ ] **I11** Scoreboard settings — spec + done-when at PRD.md:1065
- [ ] **I12** Flags panel — spec + done-when at PRD.md:1066
- [ ] **I13** Flags bulk replant — spec + done-when at PRD.md:1067
- [ ] **I14** Hosts panel — spec + done-when at PRD.md:1068
- [ ] **I15** Scoreboard panel — spec + done-when at PRD.md:1069
- [ ] **I16** Event log panel — spec + done-when at PRD.md:1070
- [ ] **I17** Submission log panel — spec + done-when at PRD.md:1071

### Group J — Student UI
- [ ] **J1** Student CTF polling — spec + done-when at PRD.md:1075
- [ ] **J2** CTF banner — spec + done-when at PRD.md:1076
- [ ] **J3** Flag submission card — spec + done-when at PRD.md:1078
- [ ] **J4** Challenge list — spec + done-when at PRD.md:1080

### Group K — Documentation
- [ ] **K1** Game master guide — spec + done-when at PRD.md:1085

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
