# Agoge CTF — Game Master Control Plane for Capture-the-Flag Exercises — Ralph Loop

You start every iteration with **fresh context**. Nothing carries over except
what is on disk:

- `@PRD.md` — the requirements. Source of truth. Never modify it.
- `@progress.md` — the task queue and the append-only iteration log.
- `@CLAUDE.md` — project memory: build commands, patterns, gotchas.
- Git history — what previous iterations already shipped, and why.

## Each iteration

1. **Study** `@progress.md`, then `@CLAUDE.md`, then only the part of `@PRD.md`
   this task needs. Loading everything wastes the context you need for the work.
2. **Search before you build.** Delegate greps to subagents. The single most
   common failure of this loop is re-implementing something a previous
   iteration already shipped. Parallel subagents for search and analysis; at
   most **one** subagent for builds and test runs, or they fight over locks.
3. **Pick ONE task** — the highest-priority incomplete item in `@progress.md`.
   One thing per iteration. Not "one thing plus a quick refactor while I'm here."
4. **Think hard** about edge cases, contracts, and interactions with existing
   code before you write anything.
5. **Implement it completely.** No placeholders, no stubs, no `TODO: later`, no
   code shaped to make a test pass. If the task is too big, split it in
   `@progress.md` and take the smallest independently-shippable slice.
6. **Verify** — run the tests for the code you just changed first (fast
   feedback), then the full quality gates:

```bash
# Python suites. PYTHONPATH is mandatory. ./venv/bin/python is Python 3.12 with the dependencies.
# The api and cloud_functions lines also enforce SC-23 (>= 85% line coverage of the CTF modules).
PYTHONPATH=.:api ./venv/bin/python -m pytest api/unit_tests -q --cov=core.ctf --cov=common.utilities.ctf_flags --cov=common.utilities.ctf_state_manager --cov-fail-under=85   # >=1554 passed, 97.75% on 2026-10-17
PYTHONPATH=.:cloud_functions ./venv/bin/python -m pytest cloud_functions/tests -q --cov=cloud_fn_utilities.course_objects.ctf --cov=handlers.ctf_handler --cov-fail-under=85   # >=641 passed, 94.28% on 2026-10-17
PYTHONPATH=.:build_files:cloud_functions ./venv/bin/python -m pytest build_files/cloud_deployment/tests -q  # 293 passed

# Frontend unit tests.
(cd frontend && npm test)                                                                               # today exits 1 (2 node:test files); after 0.1: 23 passed

# Lint, scoped to the new code (repo-wide eslint has hundreds of pre-existing errors). Config is frontend/.eslintrc.json.
(cd frontend && npx eslint src/components/Teacher/Ctf src/components/Student/Ctf src/services/Ctf src/hooks/useCtfEnabled.tsx src/utilities/transformers/ctf.transform.ts src/components/Common/Dialogs/ActionConfirmDialog --max-warnings 0)

# Type check, scoped to the new code: passes when no tsc error names a CTF file.
(cd frontend && ! npx tsc --noEmit 2>&1 | grep -E '^src/(components/(Teacher|Student)/Ctf|services/Ctf|hooks/useCtfEnabled|utilities/transformers/ctf|components/Common/Dialogs/ActionConfirmDialog)')

# Group V: the same two checks, scoped to the nested image builder code.
(cd frontend && npx eslint --no-error-on-unmatched-pattern src/components/Teacher/ServerManagement/Forms/NestedImage src/services/Server/nested.service.ts src/services/Server/nested.model.ts src/utilities/transformers/nested.transform.ts --max-warnings 0)
(cd frontend && ! npx tsc --noEmit 2>&1 | grep -E '^src/(components/Teacher/ServerManagement/Forms/NestedImage|services/Server/nested|utilities/transformers/nested)')
```

7. **Fix real failures.** Never weaken, skip, or disable a check to get green.
8. **Do NOT run `git commit`** — it is denied. Write the commit message to
   `.ralph/commit-msg` instead: a summary line, a blank line, then WHY. The
   loop commits your changes under the user's name when you finish. No
   Co-Authored-By or "Generated with" lines.
9. **Log** to `@progress.md`: mark the task `[x]`, one line on what you learned,
   any BLOCKED item with its exact error text, and what should happen next.
10. **Update `@CLAUDE.md`** only for a build command, pattern, or gotcha a future
    iteration genuinely needs — one sentence each. It loads into every run, so
    bloat there costs tokens forever. Reasoning that belongs next to the code
    goes in a code comment instead.

## Rules

- **The loop scaffolding is not the product.** `PRD.md`, `progress.md`,
  `PROMPT.md`, `CLAUDE.md`, and `.ralph/` are build-process files. Don't ship
  them, document them in the product README, or maintain them as code.
- **Never modify `@PRD.md`.** Append to `@progress.md`; never rewrite its history.
- **3 strikes.** After three failed attempts at one task, mark it BLOCKED with
  the exact error and move on. Do not keep grinding.
- **A denied action is a decision, not an obstacle.** If the permission
  classifier blocks a command, do not retry it or route around it with a
  different command. Mark the task BLOCKED and quote the denial in `@progress.md`
  so a human can decide.
- **Found an unrelated bug?** Add it to the task queue in `@progress.md` as a new
  `[ ]` item. Do not fix it in this iteration.
- **Stop what you start.** Kill dev servers, watchers, and other background
  processes before you finish. A headless run waits for them to exit, so a
  forgotten server stalls the whole loop.
- **Your "done" is a claim, not proof.** A separate verifier session re-checks
  completed tasks against the codebase and reopens anything that only looks
  finished. Claiming done early costs an iteration; it doesn't save one.
- **Check library APIs against current docs**, not memory. Use the Context7 MCP
  server if this project has one configured. Record deprecations in `@CLAUDE.md`.
- **Leave a one-line WHY** beside non-obvious code and tests. The next iteration
  has no memory of your reasoning and will "simplify" what it can't explain.

## Completion

Only when every task in `@progress.md` is `[x]` and the gates pass:

1. Run the gates one final time and confirm they pass.
2. Append `## ALL TASKS COMPLETE` to `@progress.md`.
3. Output `<promise>COMPLETE</promise>`
