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

- [x] **BUG** `SpecEditManager.save` writes the spec to Firestore (catalog on publish, edits otherwise) *before* calling `is_valid()`, so an invalid spec is persisted and then the call raises. Callers in `lab_spec_edit.py` check `is_valid()` first, which masks it. Not CTF-specific.

### Group D — Compute primitives and the loader
- [x] **D1** `set_metadata` — spec + done-when at PRD.md:979
- [x] **D2** `get_guest_attributes` — spec + done-when at PRD.md:981
- [x] **D3** Plant contract module — spec + done-when at PRD.md:982
- [x] **D4** Loader at build — spec + done-when at PRD.md:983

### Group E — Planting
- [x] **E1** Payload builder — spec + done-when at PRD.md:988
- [x] **E2** Plant procedure — spec + done-when at PRD.md:990
- [x] **E3** CTF handler — spec + done-when at PRD.md:992 (split: this slice is the handler, the `main.py` branch, `CTF_PLANT` routing and unknown action → `ValueError`; the other two routes are E4b and G4b)
- [x] **E4** Arm worker — spec + done-when at PRD.md:994
- [x] **E4b** Route `CTF_ARM_BOARD` → `ArmWorker.run(ctf_id, workout_id)` in `CtfHandler.action_map`, with a test showing it reaches ArmWorker (E3 done-when, PRD.md:992)
- [x] **E5** Overnight exemption — spec + done-when at PRD.md:996
- [x] **BUG2** `ProjectServerManager.stop_everything` calls `self.db.batch_write(operations)` inside the image loop (wrong indentation), so the growing batch is rewritten once per checked-out image. Not CTF-specific.

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
- [ ] **G4b** Route `CTF_HOST_RESET` → the `host_reset` dispatcher (with `SERVER_NAME`, `RESET_MODE`) in `CtfHandler.action_map`, with a test showing it reaches it (E3 done-when, PRD.md:992)
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
