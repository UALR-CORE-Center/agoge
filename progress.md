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
- [ ] **0.1** Frontend test script — spec + done-when at PRD.md:943
- [ ] **0.2** Rubric opt-in tests — spec + done-when at PRD.md:945

### Group A — Contracts and constants
- [ ] **A1** CTF constants — spec + done-when at PRD.md:950
- [ ] **A2** CTF specification models — spec + done-when at PRD.md:952
- [ ] **A3** CTF stored models — spec + done-when at PRD.md:954
- [ ] **A4** CTF request models — spec + done-when at PRD.md:955
- [ ] **A5** CTF response models — spec + done-when at PRD.md:956
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
