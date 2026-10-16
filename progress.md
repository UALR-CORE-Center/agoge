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
- [x] **A6** Spec block wiring — spec + done-when at PRD.md:957

### Group B — Flag derivation and state
- [x] **B1** Derivation module — spec + done-when at PRD.md:962
- [x] **B2** Seed property — spec + done-when at PRD.md:964
- [x] **B3** Seed provisioning — spec + done-when at PRD.md:965
- [x] **B4** CTF state manager — spec + done-when at PRD.md:967

### Group C — Specification validation
- [x] **C1** Flag validator — spec + done-when at PRD.md:972
- [x] **C2** Validator wiring — spec + done-when at PRD.md:974

- [ ] **BUG** `SpecEditManager.save` writes the spec to Firestore (catalog on publish, edits otherwise) *before* calling `is_valid()`, so an invalid spec is persisted and then the call raises. Callers in `lab_spec_edit.py` check `is_valid()` first, which masks it. Not CTF-specific.

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
