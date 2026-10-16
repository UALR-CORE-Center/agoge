#!/usr/bin/env bash
# ralph.sh — Autonomous Ralph Loop
#
# Based on Geoffrey Huntley's Ralph Wiggum technique (https://ghuntley.com/ralph/):
# a fresh-context agent, one task per iteration, with all state on disk and in git.
#
# What this adds over `while :; do cat PROMPT.md | claude -p; done`:
#   - Cost accounting and hard budget ceilings (per iteration and per run)
#   - Stall detection / circuit breaker (no commit + no progress = strike)
#   - Model escalation when the loop stalls
#   - An INDEPENDENT verification gate — the builder does not grade its own work
#   - Git worktree isolation so a run never touches your working tree
#   - Auto-mode permissions by default: a classifier reviews each action instead
#     of the old --dangerously-skip-permissions, which belongs in a container
#   - Rate-limit awareness: waits for a usage window to reset instead of
#     burning iterations (and stall strikes) against a 429
#   - Resume, graceful stop that really lets the iteration finish, archive, replan
#
# Before reaching for this: Claude Code 2.1+ ships supported equivalents that
# survive version updates. Prefer them for smaller jobs.
#   /goal   — work until a verifiable condition holds (tests pass, lint clean).
#             Also runs headless: claude -p "/goal <condition>"
#   /loop   — repeat a prompt on an interval or self-paced
#   /batch  — one mechanical change fanned across parallel worktree agents
#   /plugin install ralph-loop@claude-plugins-official
# Those all keep ONE session (and its context) alive. This script is for
# multi-context-window builds where every iteration must start fresh, with
# budget control, crash recovery, and independent verification in between.
#
# Usage:
#   ./ralph.sh [max_iterations]        # default: 20
#   ./ralph.sh --init                  # scaffold PROMPT.md / progress.md / CLAUDE.md
#   ./ralph.sh --plan                  # analyze the gap, write no code
#   ./ralph.sh --replan                # rebuild the task queue from the codebase
#   ./ralph.sh --verify                # run the verification gate once
#   ./ralph.sh --status                # show current progress
#   ./ralph.sh --reset                 # archive current run, start fresh
#   ./ralph.sh --stop                  # gracefully stop a running loop
#   ./ralph.sh --help                  # full option list
#
# Requirements:
#   - claude CLI 2.1.259+: npm install -g @anthropic-ai/claude-code
#     (--permission-prompts, used by the default auto mode, landed in 2.1.259)
#   - git repository (run `git init` if needed)
#   - PRD.md in project root
#   - jq (optional but recommended — enables cost tracking and live streaming)
#
# Files:
#   PRD.md      — Product requirements (input, never modified by the loop)
#   specs/      — Optional detailed specs, loaded on demand by the agent
#   progress.md — Task queue + append-only iteration log (state between runs)
#   PROMPT.md   — Instructions fed to each iteration (auto-generated, kept short)
#   CLAUDE.md   — Project memory loaded into every iteration (kept slim)
#   .ralph/     — Logs, archives, run state (safe to gitignore)

set -euo pipefail

# Allow ralph.sh to run from inside a Claude Code terminal session.
# The claude CLI refuses to start if it detects a parent Claude Code process
# via CLAUDECODE. Unsetting it is safe — every iteration intentionally spawns
# an independent, fresh-context claude instance.
unset CLAUDECODE 2>/dev/null || true

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

# ─── Configuration ───────────────────────────────────────────────────────────
# Every setting is overridable by env var or flag; flags win.

MAX_ITERATIONS="${RALPH_MAX_ITERATIONS:-20}"

# Budgets, in USD. RUN_BUDGET_USD=0 means unlimited (the claude CLI still
# enforces ITER_BUDGET_USD per invocation). Cost data requires jq.
RUN_BUDGET_USD="${RALPH_BUDGET_USD:-0}"
ITER_BUDGET_USD="${RALPH_ITER_BUDGET_USD:-5.00}"

# Circuit breaker: consecutive iterations with no commit and no progress.md
# change before the loop gives up. Runaway loops are the top cost failure.
MAX_STALLS="${RALPH_MAX_STALLS:-3}"

# Independent verification. The builder claiming COMPLETE is a claim, not proof —
# a separate fresh-context session re-checks the work before the loop exits.
VERIFY_ENABLED="${RALPH_VERIFY:-1}"
VERIFY_EVERY="${RALPH_VERIFY_EVERY:-5}"

MODEL="${RALPH_MODEL:-}"                    # e.g. sonnet — empty = CLI default
ESCALATE_MODEL="${RALPH_ESCALATE_MODEL:-}"  # e.g. opus — used after a stall
FALLBACK_MODEL="${RALPH_FALLBACK_MODEL:-}"  # used when the primary is overloaded
EFFORT="${RALPH_EFFORT:-}"                  # low|medium|high|xhigh|max
COOLDOWN="${RALPH_COOLDOWN:-5}"             # seconds between iterations

# Permissions. "auto" (default) has Claude Code's classifier review each action
# and, with --permission-prompts none, denies anything that would otherwise
# wait for a human — the run keeps going and the denial shows in the log.
# "bypass" is --dangerously-skip-permissions: everything runs unchecked, which
# Anthropic's docs reserve for containers and VMs.
PERMISSION_MODE="${RALPH_PERMISSION_MODE:-auto}"   # auto | bypass

# OS-level Bash sandbox (macOS, Linux, WSL2): shell commands can only write to
# the project and temp dirs. Strict — no unsandboxed retry, and the run fails
# at startup if the sandbox can't start rather than silently running without it.
SANDBOX="${RALPH_SANDBOX:-0}"

# --bare skips ALL settings hooks (the project's .claude/settings.json hooks
# too, not just ~/.claude), plugins, MCP servers, and auto-memory so every
# iteration runs the same on every machine. Needs ANTHROPIC_API_KEY — bare mode
# never reads a subscription login. The loop names its context files in the
# prompt, so CLAUDE.md is still read.
BARE="${RALPH_BARE:-0}"

# Longest the loop will sleep waiting for a rate-limit window to reset (seconds).
MAX_RATE_WAIT="${RALPH_MAX_RATE_WAIT:-21600}"

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_DIR="${PROJECT_ROOT}/.ralph/logs"
ARCHIVE_DIR="${PROJECT_ROOT}/.ralph/archive"
STATE_FILE="${PROJECT_ROOT}/.ralph/state"
STOP_FILE="${PROJECT_ROOT}/.ralph/stop"
CLAUDE_PID_FILE="${PROJECT_ROOT}/.ralph/claude.pid"
# The agent never commits. It leaves a proposed message here, and the script
# commits as the user's own git identity, with no Claude attribution.
COMMIT_MSG_FILE="${PROJECT_ROOT}/.ralph/commit-msg"
STOP_REQUESTED=0

# Common flags for every claude invocation in the loop:
#   --print                                     non-interactive
#   --no-session-persistence                    don't pollute ~/.claude with
#                                               throwaway loop sessions
#   --exclude-dynamic-system-prompt-sections    improves prompt-cache reuse
#                                               across iterations
# Permission, sandbox, and bare flags are added per call in run_claude.
CLAUDE_FLAGS=(
    --print
    --no-session-persistence
    --exclude-dynamic-system-prompt-sections
)

# Results of the last run_claude call.
RC_EXIT=0
RC_COST=0
RC_SUBTYPE="unknown"
RC_LOG=""
RC_DENIALS=0          # tool calls the permission classifier refused
RC_COMPACTIONS=0      # times the iteration overflowed and auto-compacted
RC_API_ERROR=""       # HTTP status of a failed run, e.g. 429
RC_RATE_STATUS=""     # last rate_limit_event status; anything but allowed* = limited
RC_RATE_RESETS=0      # epoch seconds when that rate-limit window resets

# Cumulative spend for this run. Seeded from .ralph/state on resume so a budget
# spans stop/resume cycles, and kept in a variable so the final summary still
# has it after clear_state wipes the file.
SESSION_COST=0

# Verdict of the most recent verification gate: PASS, FAIL, or "" if none ran.
LAST_VERDICT=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Helpers ─────────────────────────────────────────────────────────────────

log_info()  { echo -e "${BLUE}[ralph]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[ralph]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[ralph]${NC} $1"; }
log_error() { echo -e "${RED}[ralph]${NC} $1"; }
log_step()  { echo -e "${CYAN}[ralph]${NC} ${BOLD}$1${NC}"; }
divider()   { echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"; }

have_jq() { command -v jq &>/dev/null; }

# version_gte 2.1.301 2.1.259 → true. Missing parts count as 0.
version_gte() {
    awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN {
        na = split(a, x, "."); nb = split(b, y, ".")
        for (i = 1; i <= (na > nb ? na : nb); i++) {
            if (x[i] + 0 > y[i] + 0) exit 0
            if (x[i] + 0 < y[i] + 0) exit 1
        }
        exit 0
    }'
}

in_container() {
    [[ -f /.dockerenv || -f /run/.containerenv || -n "${container:-}" || -n "${RALPH_IN_CONTAINER:-}" ]]
}

# Bash has no floats; all money math goes through awk.
fadd() { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.4f", a + b }'; }
fsub() { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.4f", a - b }'; }
fmin() { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.4f", (a < b ? a : b) }'; }
fgt()  { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { exit !(a + 0 >  b + 0) }'; }
fgte() { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { exit !(a + 0 >= b + 0) }'; }
fmt_usd() { awk -v a="${1:-0}" 'BEGIN { printf "%.2f", a }'; }

# ─── Graceful Shutdown ───────────────────────────────────────────────────────

request_stop() {
    if [[ $STOP_REQUESTED -eq 0 ]]; then
        STOP_REQUESTED=1
        echo ""
        log_warn "⏸  Stop requested. Finishing current iteration, then exiting."
        log_warn "   (Press Ctrl+C again to force quit immediately)"
    else
        echo ""
        log_error "Force quit requested. Exiting now."
        # claude runs in its own process group (see start_isolated), so the
        # terminal's Ctrl+C never reached it. SIGTERM the whole group: the CLI
        # kills any Bash command it is running, then exits 143.
        if [[ -s "$CLAUDE_PID_FILE" ]]; then
            kill -TERM -- "-$(cat "$CLAUDE_PID_FILE")" 2>/dev/null || true
            rm -f "$CLAUDE_PID_FILE"
        fi
        exit 130
    fi
}

trap request_stop SIGINT SIGTERM

save_state() {
    local iteration="$1"
    local status="${2:-stopped}"
    local total_cost="${3:-$(load_total_cost)}"
    mkdir -p "$(dirname "$STATE_FILE")"
    cat > "$STATE_FILE" << EOF
# Ralph Loop State — auto-generated, do not edit
LAST_ITERATION=${iteration}
STATUS=${status}
TOTAL_COST_USD=${total_cost}
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
EOF
}

load_state() {
    if [[ -f "$STATE_FILE" ]]; then
        local last_iter status
        last_iter=$(grep '^LAST_ITERATION=' "$STATE_FILE" | cut -d= -f2)
        status=$(grep '^STATUS=' "$STATE_FILE" | cut -d= -f2)
        if [[ -n "$last_iter" && "$status" == "stopped" ]]; then
            echo "$last_iter"
            return 0
        fi
    fi
    echo "0"
}

load_total_cost() {
    local cost=""
    [[ -f "$STATE_FILE" ]] && cost=$(grep '^TOTAL_COST_USD=' "$STATE_FILE" | cut -d= -f2)
    echo "${cost:-0}"
}

clear_state() {
    rm -f "$STATE_FILE" "$STOP_FILE"
}

check_stop_requested() {
    [[ $STOP_REQUESTED -eq 1 ]] || [[ -f "$STOP_FILE" ]]
}

run_stop() {
    mkdir -p "$(dirname "$STOP_FILE")"
    touch "$STOP_FILE"
    log_ok "Stop signal written. The loop will exit after the current iteration."
    exit 0
}

# ─── PRD Parser ──────────────────────────────────────────────────────────────

extract_project_name() {
    # Try a few common patterns, then fall back to the directory name.
    local prd="${PROJECT_ROOT}/PRD.md"

    if grep -qi "^\*\*Project Name:\*\*" "$prd" 2>/dev/null; then
        grep -i "^\*\*Project Name:\*\*" "$prd" | head -1 \
            | sed 's/^\*\*Project Name:\*\* *//' | sed 's/`//g'
    elif grep -qi "^Project Name:" "$prd" 2>/dev/null; then
        grep -i "^Project Name:" "$prd" | head -1 | sed 's/^Project Name: *//'
    elif grep -q "^# " "$prd" 2>/dev/null; then
        grep "^# " "$prd" | head -1 | sed 's/^# *//'
    else
        basename "$PROJECT_ROOT"
    fi
}

extract_prd_quality_gates() {
    # Parse PRD.md for a "## Quality Gates" section and return the first code
    # block within it. Empty output means no PRD-defined gates.
    local prd="${PROJECT_ROOT}/PRD.md"
    [[ -f "$prd" ]] || return

    awk '
        /^##+ Quality Gates/ { in_section=1; next }
        in_section && /^```/ {
            if (in_block) exit;
            in_block=1; next
        }
        in_section && in_block { print }
        in_section && /^##[^#]/ && !in_block { exit }
    ' "$prd"
}

quality_gates_block() {
    local gates
    gates=$(extract_prd_quality_gates)
    if [[ -n "$gates" ]]; then
        echo "$gates"
    else
        cat << 'FALLBACK_EOF'
# No "## Quality Gates" section in PRD.md — detect the project's own checks
# (package.json scripts, Makefile targets, pyproject.toml, Cargo.toml, ...)
# and run tests, lint, typecheck, and build. If the project defines none,
# record that as a blocker in progress.md and propose what should be added.
FALLBACK_EOF
    fi
}

has_specs_dir() {
    [[ -d "${PROJECT_ROOT}/specs" ]] && [[ -n "$(ls -A "${PROJECT_ROOT}/specs" 2>/dev/null)" ]]
}

# ─── Progress Format Detection ───────────────────────────────────────────────

count_total_tasks() {
    # Supports checkbox format ("- [ ]" / "- [x]"), Status: format, and
    # T-XX: section headings. First format with any matches wins.
    local progress="${PROJECT_ROOT}/progress.md"
    local checkbox_total status_total task_headings

    checkbox_total=$(grep -c '^\- \[' "$progress" 2>/dev/null) || checkbox_total=0
    status_total=$(grep -cE '^\- \*\*Status:\*\* (COMPLETE|BLOCKED|IN-PROGRESS)' "$progress" 2>/dev/null) || status_total=0
    task_headings=$(grep -cE '^##+ T-[0-9]+' "$progress" 2>/dev/null) || task_headings=0

    if [[ $checkbox_total -gt 0 ]]; then
        echo "$checkbox_total"
    elif [[ $status_total -gt 0 ]]; then
        echo "$status_total"
    elif [[ $task_headings -gt 0 ]]; then
        echo "$task_headings"
    else
        echo "0"
    fi
}

count_done_tasks() {
    local progress="${PROJECT_ROOT}/progress.md"
    local checkbox_total status_total

    checkbox_total=$(grep -c '^\- \[' "$progress" 2>/dev/null) || checkbox_total=0
    status_total=$(grep -cE '^\- \*\*Status:\*\* (COMPLETE|BLOCKED|IN-PROGRESS)' "$progress" 2>/dev/null) || status_total=0

    if [[ $checkbox_total -gt 0 ]]; then
        local done; done=$(grep -c '^\- \[x\]' "$progress" 2>/dev/null) || done=0
        echo "$done"
    elif [[ $status_total -gt 0 ]]; then
        local done; done=$(grep -cE '^\- \*\*Status:\*\* COMPLETE' "$progress" 2>/dev/null) || done=0
        echo "$done"
    else
        echo "0"
    fi
}

count_remaining_tasks() {
    local progress="${PROJECT_ROOT}/progress.md"
    local checkbox_remaining
    checkbox_remaining=$(grep -c '^\- \[ \]' "$progress" 2>/dev/null) || checkbox_remaining=0

    if [[ $checkbox_remaining -gt 0 ]]; then
        echo "$checkbox_remaining"
    else
        local total done
        total=$(count_total_tasks)
        done=$(count_done_tasks)
        echo $(( total - done ))
    fi
}

has_remaining_tasks() {
    # Returns 0 (true) if there is work to do.
    local total remaining
    total=$(count_total_tasks)
    remaining=$(count_remaining_tasks)

    if [[ $total -eq 0 ]]; then
        # No structured tasks yet — let Claude derive them from the PRD.
        if grep -q "ALL TASKS COMPLETE" "${PROJECT_ROOT}/progress.md" 2>/dev/null; then
            return 1
        fi
        return 0
    fi

    [[ $remaining -gt 0 ]]
}

progress_signature() {
    # Fingerprint of "did anything actually happen". Drives stall detection:
    # an iteration that moves neither git nor progress.md did nothing useful.
    local head done_count hash
    head=$(git rev-parse --short HEAD 2>/dev/null || echo "none")
    done_count=$(count_done_tasks)
    hash=$(shasum "${PROJECT_ROOT}/progress.md" 2>/dev/null | cut -d' ' -f1 || true)
    echo "${head}:${done_count}:${hash}"
}

# ─── Claude Invocation ───────────────────────────────────────────────────────

render_stream() {
    # Turn the stream-json event stream into readable terminal output.
    # `fromjson? // empty` makes this tolerant of any non-JSON line.
    jq -R --unbuffered -r '
        fromjson? // empty
        | if .type == "system" and .subtype == "api_retry" then
              "  ↻ API retry " + ((.attempt // 0) | tostring) + "/"
              + ((.max_retries // 0) | tostring) + " (" + (.error // "error") + ")"
          elif .type == "system" and .subtype == "permission_denied" then
              "  ⊘ permission denied: " + ((.tool_name // .tool // "tool") | tostring)
          elif .type == "system" and .subtype == "compact_boundary" then
              "  ⚠ context compacted — this task is too big for one iteration"
          elif .type == "rate_limit_event"
               and ((.rate_limit_info.status // "allowed") | startswith("allowed") | not) then
              "  ⏳ rate limited (" + (.rate_limit_info.rateLimitType // "?") + ")"
          elif .type == "assistant" then
              ( .message.content[]?
                | if .type == "text" then (.text // empty)
                  elif .type == "tool_use" then
                      "  · " + (.name // "tool")
                      + ( (.input.command // .input.file_path // .input.pattern
                           // .input.description // "")
                          | tostring | gsub("\n"; " ") | .[0:88]
                          | if . == "" then "" else "  " + . end )
                  else empty end )
          elif .type == "result" then
              "\n[" + (.subtype // "result") + "]"
              + "  cost=$" + ((.total_cost_usd // 0) | tostring)
              + "  turns=" + ((.num_turns // 0) | tostring)
              + "  time=" + ((((.duration_ms // 0) / 1000) | floor) | tostring) + "s"
          else empty end
    '
}

start_isolated() {
    # exec claude in a new process group and record its pgid. Ctrl+C signals the
    # terminal's foreground group; `claude -p` treats SIGINT as "end the turn"
    # and Node ignores an inherited SIG_IGN, so without this the first Ctrl+C
    # cut the iteration off mid-edit instead of letting it finish.
    if command -v perl &>/dev/null; then
        exec perl -e 'setpgrp(0, 0);
                      if (open(my $f, ">", shift)) { print $f $$; close $f }
                      exec @ARGV or die "exec $ARGV[0]: $!\n"' \
            "$CLAUDE_PID_FILE" claude "$@"
    fi
    exec claude "$@"
}

wait_for_child() {
    # `wait` returns early whenever a trapped signal arrives (that is what lets
    # request_stop print immediately), so keep waiting until the child is gone.
    local pid="$1"
    while kill -0 "$pid" 2>/dev/null; do
        wait "$pid" 2>/dev/null || true
    done
}

# run_claude <log-tag> <model-or-empty> <budget-usd-or-0> <prompt>
# Sets RC_EXIT, RC_COST, RC_SUBTYPE, RC_LOG, RC_DENIALS, RC_COMPACTIONS,
# RC_API_ERROR, RC_RATE_STATUS, RC_RATE_RESETS.
run_claude() {
    local tag="$1" model="$2" budget="$3" prompt="$4"

    local flags=("${CLAUDE_FLAGS[@]}")
    case "$PERMISSION_MODE" in
        bypass) flags+=(--dangerously-skip-permissions) ;;
        *)      flags+=(--permission-mode auto --permission-prompts none) ;;
    esac
    # Deny rules hold in every permission mode, bypass included, so the agent
    # cannot commit even when told to; commit_work does it as the user.
    local settings='"permissions":{"deny":["Bash(git commit *)","Bash(git commit)"]}'
    [[ "$SANDBOX" == "1" ]] && settings+=',"sandbox":{"enabled":true,"allowUnsandboxedCommands":false,"failIfUnavailable":true}'
    flags+=(--settings "{${settings}}")
    [[ "$BARE" == "1" ]]       && flags+=(--bare)
    [[ -n "$model" ]]          && flags+=(--model "$model")
    [[ -n "$FALLBACK_MODEL" ]] && flags+=(--fallback-model "$FALLBACK_MODEL")
    [[ -n "$EFFORT" ]]         && flags+=(--effort "$EFFORT")
    if fgt "$budget" 0; then flags+=(--max-budget-usd "$budget"); fi

    RC_COST=0
    RC_SUBTYPE="unknown"
    RC_DENIALS=0
    RC_COMPACTIONS=0
    RC_API_ERROR=""
    RC_RATE_STATUS=""
    RC_RATE_RESETS=0

    local status_file="${LOG_DIR}/${tag}.exit"
    rm -f "$CLAUDE_PID_FILE" "$status_file" "$COMMIT_MSG_FILE"

    # The pipeline runs in the background so `wait` can be interrupted by the
    # SIGINT trap. A backgrounded non-interactive subshell ignores SIGINT, so
    # tee and jq keep draining claude's output through a graceful stop.
    set +e
    if have_jq; then
        # stream-json gives us live output *and* the cost/turn accounting that
        # plain text output throws away.
        RC_LOG="${LOG_DIR}/${tag}.jsonl"
        flags+=(--output-format stream-json --verbose)
        (
            start_isolated "${flags[@]}" "$prompt" </dev/null 2>"${LOG_DIR}/${tag}.err" \
                | tee "$RC_LOG" | render_stream
            echo "${PIPESTATUS[0]}" > "$status_file"
        ) &
    else
        RC_LOG="${LOG_DIR}/${tag}.log"
        (
            start_isolated "${flags[@]}" "$prompt" </dev/null 2>&1 | tee "$RC_LOG"
            echo "${PIPESTATUS[0]}" > "$status_file"
        ) &
    fi
    wait_for_child "$!"
    set -e
    rm -f "$CLAUDE_PID_FILE"
    RC_EXIT=$(cat "$status_file" 2>/dev/null || echo 1)
    rm -f "$status_file"

    if have_jq; then
        local result
        result=$(jq -R -c 'fromjson? // empty | select(.type == "result")' "$RC_LOG" 2>/dev/null | tail -1 || true)
        if [[ -n "$result" ]]; then
            RC_SUBTYPE=$(jq -r '.subtype // "unknown"' <<< "$result")
            RC_DENIALS=$(jq -r '(.permission_denials // []) | length' <<< "$result")
            RC_API_ERROR=$(jq -r '.api_error_status // empty' <<< "$result")
        fi
        # A session can emit several `result` events (a finished subagent emits
        # one of its own). The final event's total_cost_usd is cumulative for the
        # whole session, so take the max — summing would double-count.
        RC_COST=$(jq -R -r 'fromjson? // empty | select(.type == "result") | (.total_cost_usd // 0)' \
                    "$RC_LOG" 2>/dev/null | awk '{ if ($1 + 0 > m) m = $1 + 0 } END { printf "%.6f", m + 0 }' || true)
        RC_COMPACTIONS=$(jq -R -r 'fromjson? // empty
                    | select(.type == "system" and .subtype == "compact_boundary") | 1' \
                    "$RC_LOG" 2>/dev/null | wc -l | tr -d ' ' || true)
        local rate
        rate=$(jq -R -r 'fromjson? // empty | select(.type == "rate_limit_event")
                    | "\(.rate_limit_info.status // "") \(.rate_limit_info.resetsAt // 0)"' \
                    "$RC_LOG" 2>/dev/null | tail -1 || true)
        RC_RATE_STATUS="${rate%% *}"
        RC_RATE_RESETS="${rate##* }"
        [[ -s "${LOG_DIR}/${tag}.err" ]] && log_warn "stderr: $(tail -3 "${LOG_DIR}/${tag}.err")"
    fi

    [[ -n "${RC_SUBTYPE:-}" ]]     || RC_SUBTYPE="unknown"
    [[ -n "${RC_COST:-}" ]]        || RC_COST=0
    [[ "${RC_DENIALS:-}" =~ ^[0-9]+$ ]]     || RC_DENIALS=0
    [[ "${RC_COMPACTIONS:-}" =~ ^[0-9]+$ ]] || RC_COMPACTIONS=0
    [[ "${RC_RATE_RESETS:-}" =~ ^[0-9]+$ ]] || RC_RATE_RESETS=0
    return 0
}

# commit_work <default-message> — commit everything the last call changed,
# authored by the user's git identity. The agent's proposed message is used
# when it left one, minus any Claude attribution trailers. Commit hooks run
# normally; if one rejects the commit, the work stays in the tree.
commit_work() {
    local default_msg="$1" msg=""
    [[ -n "$(git status --porcelain 2>/dev/null)" ]] || { rm -f "$COMMIT_MSG_FILE"; return 0; }

    if [[ -s "$COMMIT_MSG_FILE" ]]; then
        msg=$(grep -viE '^(co-authored-by:.*(claude|anthropic)|.*generated with \[?claude code)' \
                "$COMMIT_MSG_FILE" || true)
    fi
    rm -f "$COMMIT_MSG_FILE"
    [[ -n "${msg//[[:space:]]/}" ]] || msg="$default_msg"

    if git add -A && git commit -q -F - <<< "$msg"; then
        log_ok "Committed as $(git config user.name): $(git log -1 --format=%s)"
    else
        log_warn "Commit failed (a git hook may have rejected it) — changes left uncommitted."
    fi
}

agent_text() {
    # Only what the agent itself said. The raw stream-json log also holds tool
    # results, so an agent that merely Reads PROMPT.md would otherwise "claim"
    # <promise>COMPLETE</promise> by echoing the instructions back.
    local log="$1"
    if [[ "$log" == *.jsonl ]]; then
        jq -R -r 'fromjson? // empty
            | if .type == "assistant" then (.message.content[]? | select(.type == "text") | .text // empty)
              elif .type == "result" then (.result // empty)
              else empty end' "$log" 2>/dev/null || true
    else
        cat "$log" 2>/dev/null || true
    fi
}

# last_verdict <log> → PASS, FAIL, or empty. The last tag wins, so a verifier
# that quotes both options before deciding is read correctly.
last_verdict() {
    agent_text "$1" | grep -oE '<verdict>(PASS|FAIL)</verdict>' | tail -1 \
        | sed -E 's/<\/?verdict>//g' || true
}

rate_limited() {
    # True when the last call failed because a usage window is exhausted, as
    # opposed to the agent getting nothing done.
    [[ "$RC_API_ERROR" == "429" ]] && return 0
    [[ -n "$RC_RATE_STATUS" && "$RC_RATE_STATUS" != allowed* ]]
}

wait_for_rate_limit() {
    # Sleep until the window resets (+60s slack), capped at MAX_RATE_WAIT.
    # Returns 1 if the wait would exceed the cap, so the caller can stop.
    local now wait_s
    now=$(date +%s)
    if [[ "$RC_RATE_RESETS" -gt "$now" ]]; then
        wait_s=$(( RC_RATE_RESETS - now + 60 ))
    else
        wait_s=300   # no reset time reported; back off five minutes
    fi
    if [[ $wait_s -gt $MAX_RATE_WAIT ]]; then
        log_error "Rate-limit window resets in $(( wait_s / 60 )) min — longer than --max-rate-wait."
        return 1
    fi
    log_warn "Rate limited. Sleeping $(( wait_s / 60 )) min until the window resets"
    log_warn "(this iteration does not count as a stall)."
    sleep "$wait_s" || true
    return 0
}

# ─── Preflight Checks ────────────────────────────────────────────────────────

preflight() {
    local errors=0

    if ! command -v claude &>/dev/null; then
        log_error "claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        errors=$((errors + 1))
    fi

    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "Not inside a git repository. Run: git init"
        errors=$((errors + 1))
    fi

    if [[ ! -f "${PROJECT_ROOT}/PRD.md" ]]; then
        log_error "PRD.md not found in project root."
        errors=$((errors + 1))
    fi

    case "$PERMISSION_MODE" in
        auto|bypass) ;;
        *) log_error "--permission-mode must be 'auto' or 'bypass' (got '${PERMISSION_MODE}')."
           errors=$((errors + 1)) ;;
    esac

    if [[ "$PERMISSION_MODE" == "auto" ]] && command -v claude &>/dev/null; then
        local version
        version=$(claude --version 2>/dev/null | awk '{ print $1 }')
        if ! version_gte "$version" "2.1.259"; then
            log_error "claude ${version:-?} is too old for auto mode in -p runs (needs 2.1.259+)."
            log_error "Upgrade (npm install -g @anthropic-ai/claude-code) or pass --permission-mode bypass."
            errors=$((errors + 1))
        fi
    fi

    if [[ "$BARE" == "1" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
        log_error "--bare needs ANTHROPIC_API_KEY: bare mode never reads a subscription login."
        errors=$((errors + 1))
    fi

    if git rev-parse --is-inside-work-tree &>/dev/null \
            && [[ -z "$(git config user.name)" || -z "$(git config user.email)" ]]; then
        log_error "git user.name / user.email not set — the loop commits as you."
        log_error "Run: git config --global user.name 'You'; git config --global user.email you@example.com"
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        log_error "Preflight failed with $errors error(s). Fix the above and retry."
        exit 2
    fi

    if [[ "$PERMISSION_MODE" == "bypass" && "$SANDBOX" != "1" ]] && ! in_container; then
        log_warn "--permission-mode bypass runs every command unchecked on this machine."
        log_warn "Anthropic recommends it only inside a container or VM. Add --sandbox,"
        log_warn "or use the default auto mode."
    fi

    if ! have_jq; then
        log_warn "jq not found — run-level cost tracking and --budget are disabled."
        log_warn "Per-iteration ceilings still apply; live output falls back to plain text."
        log_warn "Install it: brew install jq  |  apt install jq"
    fi

    mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$STATE_FILE")"
    ignore_ralph_dir

    # Generate any missing state files. CLAUDE.md is intentionally minimal
    # because it is loaded into every future iteration's context.
    [[ -f "${PROJECT_ROOT}/PROMPT.md" ]]   || { log_info "Generating PROMPT.md...";   generate_prompt; }
    [[ -f "${PROJECT_ROOT}/progress.md" ]] || { log_info "Generating progress.md..."; initialize_progress; }
    [[ -f "${PROJECT_ROOT}/CLAUDE.md" ]]   || { log_info "Generating CLAUDE.md...";   initialize_claude_md; }

    log_ok "Preflight passed."
}

ignore_ralph_dir() {
    # .ralph/ holds the live pid file, logs, and run state. If git can see it,
    # the agent's `git add -A` commits it, and a later worktree checks out a
    # stale state file and "resumes" a run it never started. info/exclude needs
    # no .gitignore, never touches project files, and is shared by worktrees.
    local exclude
    exclude="$(git rev-parse --git-common-dir 2>/dev/null)/info/exclude" || return 0
    [[ "$exclude" == /info/exclude ]] && return 0
    mkdir -p "$(dirname "$exclude")"
    grep -qxF '.ralph/' "$exclude" 2>/dev/null || printf '.ralph/\n' >> "$exclude"
}

warn_if_unisolated() {
    # A loop rewrites files hundreds of times. Best practice is to run it on a
    # dedicated branch or worktree so a bad run is one `git worktree remove`.
    local branch default_branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    default_branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)
    [[ -n "$default_branch" ]] || default_branch="main"

    if [[ "$branch" == "$default_branch" || "$branch" == "master" ]]; then
        log_warn "Running on '${branch}'. Consider isolating this run:"
        log_warn "  ./ralph.sh --worktree <name>   (dedicated worktree + branch)"
    fi
}

# ─── File Generators ─────────────────────────────────────────────────────────

generate_prompt() {
    local project_name specs_line
    project_name=$(extract_project_name)

    if has_specs_dir; then
        specs_line='- `@specs/` — detailed specs. Load only the file(s) this task needs, never the whole directory.'
    else
        specs_line='- Git history — what previous iterations already shipped, and why.'
    fi

    # Built in parts rather than one heredoc: the content is full of backticks
    # and `$`, and quoted heredocs let it through untouched.
    {
        printf '# %s — Ralph Loop\n\n' "$project_name"

        cat << 'PROMPT_PART1'
You start every iteration with **fresh context**. Nothing carries over except
what is on disk:

- `@PRD.md` — the requirements. Source of truth. Never modify it.
- `@progress.md` — the task queue and the append-only iteration log.
- `@CLAUDE.md` — project memory: build commands, patterns, gotchas.
PROMPT_PART1
        printf '%s\n' "$specs_line"

        cat << 'PROMPT_PART2'

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
PROMPT_PART2

        printf '\n```bash\n%s\n```\n' "$(quality_gates_block)"

        cat << 'PROMPT_PART3'

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
PROMPT_PART3
    } > "${PROJECT_ROOT}/PROMPT.md"

    log_ok "Generated PROMPT.md"
}

initialize_progress() {
    cat > "${PROJECT_ROOT}/progress.md" << 'PROGRESS_EOF'
# Ralph Loop Progress

State for the autonomous loop. Iterations append to this file; log entries are
never deleted or rewritten. The task queue is disposable — regenerate it with
`./ralph.sh --replan` if it drifts from reality.

## Task Queue

Tasks derived from PRD.md, ordered by dependency and priority.
Mark `[x]` when complete. Do NOT reorder or delete tasks.

### Planning
- [ ] Read PRD.md and replace this section with a real task breakdown

<!-- The first iteration replaces the Planning section above with concrete, -->
<!-- project-specific tasks derived from PRD.md. Do not add placeholder tasks. -->

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
PROGRESS_EOF

    log_ok "Initialized progress.md (planning-first: Claude derives tasks from PRD.md)"
}

initialize_claude_md() {
    local project_name
    project_name=$(extract_project_name)

    {
        printf '# %s — Project Memory\n\n' "$project_name"
        cat << 'CLAUDE_EOF'
Loaded into every Ralph iteration. **Keep this file slim** — every line costs
tokens on every run. Add an entry only when it saves a future iteration from a
mistake or wasted exploration. One or two sentences each.

## Build & Test Commands

<!-- One line each. Examples: "Tests: npm test", "Lint: ruff check src/" -->
<!-- Leave blank until the first iteration discovers them.                -->

## Discovered Patterns

<!-- One sentence per entry. Patterns reused across the codebase.        -->

## Known Gotchas

<!-- One sentence per entry. Things that bit a previous iteration.        -->

## Ralph Loop Files

- `PRD.md` — requirements, source of truth, never modified
- `specs/` — detailed specs, loaded on demand (optional)
- `progress.md` — task queue + append-only iteration log
- `PROMPT.md` — per-iteration build instructions
- This file — project memory across iterations
CLAUDE_EOF
    } > "${PROJECT_ROOT}/CLAUDE.md"

    log_ok "Initialized CLAUDE.md (slim by design)"
}

# ─── Init Command ────────────────────────────────────────────────────────────

run_init() {
    log_step "Initializing project from PRD.md..."

    if [[ ! -f "${PROJECT_ROOT}/PRD.md" ]]; then
        log_error "PRD.md not found in project root. Create it first."
        exit 2
    fi
    if ! command -v claude &>/dev/null; then
        log_warn "claude CLI not found. Install before running the loop."
    fi
    have_jq || log_warn "jq not found — install it to enable cost tracking and budgets."

    mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$STATE_FILE")"
    ignore_ralph_dir

    if [[ -f "${PROJECT_ROOT}/PROMPT.md" ]] || [[ -f "${PROJECT_ROOT}/progress.md" ]]; then
        log_warn "Project files already exist. Use --reset to start fresh."
        read -p "Overwrite existing files? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Initialization cancelled."
            exit 0
        fi
    fi

    generate_prompt
    initialize_progress
    [[ -f "${PROJECT_ROOT}/CLAUDE.md" ]] || initialize_claude_md

    # .ralph/ is machine-local run state, not project history.
    if [[ -f "${PROJECT_ROOT}/.gitignore" ]] && ! grep -qxF '.ralph/' "${PROJECT_ROOT}/.gitignore"; then
        printf '\n# Ralph loop run state\n.ralph/\n' >> "${PROJECT_ROOT}/.gitignore"
        log_info "Added .ralph/ to .gitignore"
    fi

    log_ok "Project initialized."
    log_info "Next steps:"
    log_info "  1. Review progress.md and PROMPT.md"
    log_info "  2. ./ralph.sh --plan                     (dry-run task analysis)"
    log_info "  3. ./ralph.sh --worktree build --budget 25   (isolated, cost-capped run)"
    exit 0
}

# ─── Status Command ──────────────────────────────────────────────────────────

show_status() {
    local project_name
    project_name=$(extract_project_name)

    divider
    echo -e "${BOLD}  ${project_name} — Current Status${NC}"
    divider
    echo ""

    if [[ ! -f "${PROJECT_ROOT}/progress.md" ]]; then
        log_warn "No progress.md found. Run ./ralph.sh --init to initialize."
        exit 0
    fi

    render_progress
    divider
    exit 0
}

render_progress() {
    local total completed remaining pct
    total=$(count_total_tasks)
    completed=$(count_done_tasks)
    remaining=$(count_remaining_tasks)
    pct=0
    [[ $total -gt 0 ]] && pct=$(( (completed * 100) / total ))

    echo -e "  Tasks:     ${GREEN}${completed}${NC} / ${total} complete (${pct}%)"
    echo -e "  Remaining: ${YELLOW}${remaining}${NC} tasks"

    local spent
    spent=$(load_total_cost)
    if fgt "$spent" 0; then
        echo -e "  Spent:     ${CYAN}\$$(fmt_usd "$spent")${NC} this run"
    fi
    echo ""

    local bar_width=50
    local filled=$(( (pct * bar_width) / 100 ))
    local empty=$(( bar_width - filled ))
    printf "  ["
    if [[ $filled -gt 0 ]]; then
        printf "${GREEN}"
        printf '%0.s█' $(seq 1 $filled)
        printf "${NC}"
    fi
    if [[ $empty -gt 0 ]]; then
        printf '%0.s░' $(seq 1 $empty)
    fi
    printf "] %d%%\n" "$pct"
    echo ""

    display_task_list

    # Count real BLOCKED markers, skipping HTML comments in the template.
    local blocked
    blocked=$(grep -v '<!--' "${PROJECT_ROOT}/progress.md" 2>/dev/null \
              | grep -c 'BLOCKED') || blocked=0
    if [[ $blocked -gt 0 ]]; then
        echo -e "  ${RED}⚠ ${blocked} blocked task(s)${NC}"
        echo ""
    fi
}

display_task_list() {
    local progress="${PROJECT_ROOT}/progress.md"
    [[ -f "$progress" ]] || return

    local total
    total=$(count_total_tasks)
    [[ $total -gt 0 ]] || return

    echo -e "  ${BOLD}Task List:${NC}"
    local next_marked=0
    while IFS= read -r line; do
        if echo "$line" | grep -q '^\- \[x\]'; then
            local task_name
            task_name=$(echo "$line" | sed 's/^- \[x\] //')
            echo -e "    ${GREEN}✓${NC} ${task_name}"
        elif echo "$line" | grep -q '^\- \[ \]'; then
            local task_name
            task_name=$(echo "$line" | sed 's/^- \[ \] //')
            if [[ $next_marked -eq 0 ]]; then
                echo -e "    ${YELLOW}▸${NC} ${CYAN}${task_name}${NC}  ${YELLOW}← NEXT${NC}"
                next_marked=1
            else
                echo -e "    ${YELLOW}○${NC} ${task_name}"
            fi
        fi
    done < "$progress"
    echo ""
}

show_status_inline() {
    local project_name
    project_name=$(extract_project_name)

    echo ""
    divider
    echo -e "${BOLD}  ${project_name} — Iteration Status${NC}"
    divider
    echo ""

    if [[ ! -f "${PROJECT_ROOT}/progress.md" ]]; then
        log_warn "No progress.md found."
        return
    fi

    render_progress
    divider
}

# ─── Archive / Reset ─────────────────────────────────────────────────────────

archive_run() {
    local archive_path="${ARCHIVE_DIR}/${TIMESTAMP}"
    mkdir -p "$archive_path"

    for f in progress.md CLAUDE.md PROMPT.md; do
        [[ -f "${PROJECT_ROOT}/$f" ]] && cp "${PROJECT_ROOT}/$f" "$archive_path/"
    done

    [[ -d "$LOG_DIR" ]] && cp -r "$LOG_DIR" "$archive_path/logs" 2>/dev/null || true

    log_ok "Archived current run to $archive_path"

    # Reset: only delete files that are NOT tracked by git. Tracked files are
    # preserved — the user manages their lifecycle through git.
    for f in progress.md CLAUDE.md PROMPT.md; do
        local fpath="${PROJECT_ROOT}/$f"
        if [[ -f "$fpath" ]]; then
            if git ls-files --error-unmatch "$fpath" &>/dev/null; then
                log_info "Keeping $f (tracked by git)."
            else
                rm -f "$fpath"
                log_info "Removed $f (untracked)."
            fi
        fi
    done

    rm -rf "$LOG_DIR"
    clear_state

    log_info "Run ./ralph.sh --init to start a fresh loop."
    exit 0
}

# ─── Worktree Isolation ──────────────────────────────────────────────────────

run_worktree() {
    # Run the loop in a dedicated git worktree + branch. The main working tree
    # is never touched, and a bad run is thrown away with `git worktree remove`.
    local name="$1"; shift
    local relay=(${@+"$@"})

    if [[ -n "${RALPH_IN_WORKTREE:-}" ]]; then
        log_error "Already inside a ralph worktree. Refusing to nest."
        exit 2
    fi
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "Not inside a git repository. Run: git init"
        exit 2
    fi

    local branch="ralph/${name}"
    local dir="$(dirname "$PROJECT_ROOT")/$(basename "$PROJECT_ROOT")-${name}"

    if [[ -d "$dir" ]]; then
        log_info "Reusing existing worktree: $dir"
    else
        log_step "Creating worktree ${dir} on branch ${branch}..."
        if git show-ref --verify --quiet "refs/heads/${branch}"; then
            git worktree add "$dir" "$branch"
        else
            git worktree add -b "$branch" "$dir"
        fi
    fi

    # Seed the worktree with loop inputs that git doesn't carry (untracked PRD,
    # specs, and memory files are common in greenfield runs).
    local f
    for f in PRD.md specs CLAUDE.md progress.md PROMPT.md; do
        if [[ -e "${PROJECT_ROOT}/$f" && ! -e "${dir}/$f" ]]; then
            cp -R "${PROJECT_ROOT}/$f" "${dir}/"
            log_info "Seeded $f into the worktree."
        fi
    done

    # Project Claude config: hooks, agents, skills, scripts, and MCP servers.
    # Merge rather than skip — a tracked .claude/ still arrives without its
    # gitignored settings.local.json (local permissions, env). -n never
    # overwrites what the branch already has.
    if [[ -d "${PROJECT_ROOT}/.claude" ]]; then
        mkdir -p "${dir}/.claude"
        cp -Rn "${PROJECT_ROOT}/.claude/." "${dir}/.claude/" 2>/dev/null || true
        log_info "Seeded missing .claude/ files into the worktree."
    fi
    if [[ -f "${PROJECT_ROOT}/.mcp.json" && ! -e "${dir}/.mcp.json" ]]; then
        cp "${PROJECT_ROOT}/.mcp.json" "${dir}/"
        log_info "Seeded .mcp.json into the worktree."
    fi

    log_ok "Loop will run in: $dir"
    log_info "When it finishes:  git -C '$PROJECT_ROOT' merge ${branch}"
    log_info "To throw it away:  git -C '$PROJECT_ROOT' worktree remove '$dir' --force"
    echo ""

    cd "$dir"
    RALPH_IN_WORKTREE=1 exec "$SCRIPT_PATH" ${relay[@]+"${relay[@]}"}
}

# ─── Planning Modes ──────────────────────────────────────────────────────────

run_plan() {
    log_step "Running in PLANNING mode (no implementation)..."

    local plan_prompt
    plan_prompt="Read @PRD.md, then @progress.md, then survey the codebase.

Analyze the gap between the PRD requirements and what actually exists on disk.
Use subagents in parallel for the survey so the reading cost stays out of your
main context. Output a prioritized TODO list of what needs to happen next,
honoring the principles and constraints in PRD.md.

Do NOT write or modify any code or content files. Do NOT commit.
You MAY update @progress.md if tasks are missing or need reordering.
Do NOT modify @PRD.md.

Explain your analysis and recommendations."

    mkdir -p "$LOG_DIR"
    run_claude "plan-${TIMESTAMP}" "${ESCALATE_MODEL:-$MODEL}" "$ITER_BUDGET_USD" "$plan_prompt"
    commit_work "Ralph plan: update task queue"

    echo ""
    log_ok "Planning complete. Review the output above."
    fgt "$RC_COST" 0 && log_info "Cost: \$$(fmt_usd "$RC_COST")"
    exit 0
}

run_replan() {
    # The task queue is disposable. When Ralph drifts — duplicated work, tasks
    # that no longer match reality — regenerate the queue from the actual code
    # rather than trying to patch it incrementally.
    log_step "Rebuilding the task queue from the codebase..."

    local replan_prompt
    replan_prompt="The task queue in @progress.md has drifted from reality. Rebuild it.

1. Fan out subagents in parallel to audit the codebase against @PRD.md (and
   @specs/ if it exists). Each should report what is genuinely implemented,
   what is stubbed or partial, and what is missing entirely.
2. Treat stubs, placeholders, and TODOs as NOT implemented.
3. Replace ONLY the '## Task Queue' section of @progress.md with a fresh,
   dependency-ordered checklist. Mark '[x]' only what you verified exists and
   works. Carry forward any BLOCKED items with their original error text.
4. Leave the '## Iteration Log' section untouched — it is append-only history.
5. Do NOT modify @PRD.md. Do NOT write or refactor any product code.

Finish by summarizing what changed in the queue and why."

    mkdir -p "$LOG_DIR"
    run_claude "replan-${TIMESTAMP}" "${ESCALATE_MODEL:-$MODEL}" "$ITER_BUDGET_USD" "$replan_prompt"
    commit_work "Ralph replan: rebuild task queue from the codebase"

    echo ""
    log_ok "Replan complete."
    fgt "$RC_COST" 0 && log_info "Cost: \$$(fmt_usd "$RC_COST")"
    show_status_inline
    exit 0
}

# ─── Verification Gate ───────────────────────────────────────────────────────

verifier_prompt() {
    cat << 'VERIFY_EOF'
You are an INDEPENDENT VERIFIER, not the builder. A separate agent claims to
have completed work in this repository. Your job is to disprove that claim.
Assume nothing it wrote in the log is true until you have seen the code.

1. Read @progress.md and @PRD.md.
2. For every task marked complete, find the code that implements it. Use
   subagents in parallel for the search. A task is NOT done if you find
   placeholders, stubs, `TODO`, `NotImplemented`, hardcoded values that only
   satisfy the tests, or an implementation that ignores a PRD constraint.
3. Run the project's quality gates yourself:

VERIFY_EOF
    printf '```bash\n%s\n```\n' "$(quality_gates_block)"
    cat << 'VERIFY_EOF2'

4. Append one entry to the '## Iteration Log' section of @progress.md:

   ### Verification — <today's date> — PASS or FAIL
   - **Checked:** which tasks you inspected
   - **Gate results:** what the quality gates actually printed
   - **Reopened:** any task you un-checked, with the specific evidence

5. If a task marked `[x]` is not genuinely finished, change it back to `[ ]`
   and add a sub-bullet stating exactly what is missing. Un-checking is the
   only edit you may make to the task queue.

You MUST NOT implement, fix, or refactor anything. You MUST NOT modify @PRD.md.
You MUST NOT run `git commit` — the loop commits your progress.md entry.
You MUST NOT weaken, skip, or rewrite a failing check.

End your output with exactly one of:
<verdict>PASS</verdict>
<verdict>FAIL</verdict>
VERIFY_EOF2
}

# run_verifier <log-tag> — returns 0 on PASS, 1 on FAIL/indeterminate.
run_verifier() {
    local tag="$1"
    echo ""
    log_step "🔍 VERIFICATION GATE  —  independent fresh-context review"
    echo -e "${DIM}   (an agent grading its own homework gives itself an A every time)${NC}"
    echo ""

    local budget
    budget=$(iteration_budget)
    run_claude "$tag" "${ESCALATE_MODEL:-$MODEL}" "$budget" "$(verifier_prompt)"
    account_for_cost "$RC_COST"

    local verdict
    verdict=$(last_verdict "$RC_LOG")
    commit_work "Ralph verification: ${verdict:-no verdict}"
    if [[ "$verdict" == "PASS" ]]; then
        LAST_VERDICT="PASS"
        log_ok "Verification PASSED."
        return 0
    fi
    LAST_VERDICT="FAIL"
    if [[ "$verdict" == "FAIL" ]]; then
        log_warn "Verification FAILED — reopened work is back in the queue."
    else
        log_warn "Verifier returned no verdict (exit ${RC_EXIT}). Treating as FAIL."
    fi
    return 1
}

run_verify_once() {
    mkdir -p "$LOG_DIR"
    SESSION_COST=$(load_total_cost)
    if run_verifier "verify-${TIMESTAMP}"; then
        show_status_inline
        exit 0
    fi
    show_status_inline
    exit 1
}

# ─── Budget Accounting ───────────────────────────────────────────────────────

iteration_budget() {
    # Per-invocation ceiling, clamped so a single iteration can never blow past
    # what remains of the whole-run budget.
    if fgt "$RUN_BUDGET_USD" 0; then
        local remaining
        remaining=$(fsub "$RUN_BUDGET_USD" "$SESSION_COST")
        fgt "$remaining" 0 || { echo "0.01"; return; }
        fmin "$ITER_BUDGET_USD" "$remaining"
    else
        echo "$ITER_BUDGET_USD"
    fi
}

account_for_cost() {
    SESSION_COST=$(fadd "$SESSION_COST" "${1:-0}")
    save_state "$(load_state)" "stopped" "$SESSION_COST"
}

over_budget() {
    fgt "$RUN_BUDGET_USD" 0 || return 1
    fgte "$SESSION_COST" "$RUN_BUDGET_USD"
}

# ─── Core Loop ───────────────────────────────────────────────────────────────

run_loop() {
    local project_name
    project_name=$(extract_project_name)

    rm -f "$STOP_FILE"
    warn_if_unisolated
    SESSION_COST=$(load_total_cost)

    local start_iteration=1
    local resumed=0
    local saved_iter
    saved_iter=$(load_state)
    if [[ "$saved_iter" -gt 0 ]]; then
        start_iteration=$((saved_iter + 1))
        resumed=1
        log_ok "Resuming from iteration ${start_iteration} (last completed: ${saved_iter})"
    else
        save_state 0 "stopped" 0
    fi

    local start_sha
    start_sha=$(git rev-parse HEAD 2>/dev/null || echo "")

    divider
    echo -e "${BOLD}  ${project_name} — Ralph Loop${NC}"
    divider
    echo ""
    echo -e "  Max iterations:  ${YELLOW}${MAX_ITERATIONS}${NC}"
    [[ $resumed -eq 1 ]] && echo -e "  Resuming from:   ${GREEN}iteration ${start_iteration}${NC}"
    echo -e "  Project root:    ${PROJECT_ROOT}"
    echo -e "  Branch:          $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if fgt "$RUN_BUDGET_USD" 0; then
        echo -e "  Run budget:      ${CYAN}\$$(fmt_usd "$RUN_BUDGET_USD")${NC} (spent: \$$(fmt_usd "$SESSION_COST"))"
    else
        echo -e "  Run budget:      ${YELLOW}unlimited${NC}  ${DIM}(set one with --budget)${NC}"
    fi
    echo -e "  Per-iteration:   \$$(fmt_usd "$ITER_BUDGET_USD")"
    echo -e "  Model:           ${MODEL:-cli default}${ESCALATE_MODEL:+  (escalates to ${ESCALATE_MODEL} on stall)}"
    if [[ "$PERMISSION_MODE" == "bypass" ]]; then
        echo -e "  Permissions:     ${RED}bypass${NC} (every action runs unchecked)"
    else
        echo -e "  Permissions:     auto (classifier reviews each action)"
    fi
    [[ "$SANDBOX" == "1" ]] && echo -e "  Bash sandbox:    ${GREEN}on${NC} (strict)"
    [[ "$BARE" == "1" ]]    && echo -e "  Bare mode:       on (no hooks — project ones included — plugins, or MCP)"
    if [[ $VERIFY_ENABLED -eq 1 ]]; then
        echo -e "  Verification:    every ${VERIFY_EVERY} iterations + before exit"
    else
        echo -e "  Verification:    ${YELLOW}disabled${NC}"
    fi
    echo -e "  Circuit breaker: stop after ${MAX_STALLS} consecutive stalled iterations"
    echo -e "  Commits:         by this script as $(git config user.name) <$(git config user.email)> — the agent cannot commit"
    echo -e "  Started at:      ${TIMESTAMP}"
    echo -e "  Stop gracefully: ${CYAN}Ctrl+C${NC} or ${CYAN}./ralph.sh --stop${NC}"
    echo ""
    divider
    echo ""

    if [[ $start_iteration -gt $MAX_ITERATIONS ]]; then
        log_warn "Already completed ${start_iteration} iterations (max: ${MAX_ITERATIONS})."
        log_info "Run with a higher max: ./ralph.sh $((start_iteration + 5))"
        return
    fi

    local i=$start_iteration
    local stalls=0
    local exit_reason="max iterations reached"

    while [[ $i -le $MAX_ITERATIONS ]]; do
        if check_stop_requested; then
            echo ""
            log_warn "╔═══════════════════════════════════════╗"
            log_warn "║     GRACEFUL STOP — loop paused       ║"
            log_warn "╚═══════════════════════════════════════╝"
            echo ""
            save_state "$((i - 1))" "stopped"
            log_info "Run ./ralph.sh to resume from iteration ${i}."
            rm -f "$STOP_FILE"
            exit_reason="stopped by user"
            break
        fi

        if over_budget; then
            echo ""
            log_warn "╔═══════════════════════════════════════╗"
            log_warn "║   BUDGET EXHAUSTED — loop stopped     ║"
            log_warn "╚═══════════════════════════════════════╝"
            log_warn "Spent \$$(fmt_usd "$SESSION_COST") of \$$(fmt_usd "$RUN_BUDGET_USD")."
            log_info "Raise it and resume: ./ralph.sh --budget <higher>"
            save_state "$((i - 1))" "stopped"
            exit_reason="budget exhausted"
            break
        fi

        local total completed pct
        total=$(count_total_tasks)
        completed=$(count_done_tasks)
        pct=0
        [[ $total -gt 0 ]] && pct=$(( (completed * 100) / total ))

        echo ""
        divider
        log_step "ITERATION ${i} / ${MAX_ITERATIONS}  [FRESH CONTEXT]  —  ${completed}/${total} tasks (${pct}%)"
        divider
        echo ""

        if grep -q "ALL TASKS COMPLETE" "${PROJECT_ROOT}/progress.md" 2>/dev/null; then
            log_ok "All tasks already marked complete."
            if [[ $VERIFY_ENABLED -eq 1 ]] && ! run_verifier "verify-final-${i}-$(date +%H%M%S)"; then
                log_warn "Verifier reopened work — continuing the loop."
                sed -i.bak '/^## ALL TASKS COMPLETE$/d' "${PROJECT_ROOT}/progress.md" \
                    && rm -f "${PROJECT_ROOT}/progress.md.bak"
            else
                clear_state
                exit_reason="all tasks complete (verified)"
                break
            fi
        fi

        if ! has_remaining_tasks; then
            if [[ "$LAST_VERDICT" == "FAIL" ]]; then
                # The verifier rejected the work but reopened nothing, so the
                # queue looks empty while the build is not actually sound.
                log_error "Queue is empty but the last verification FAILED."
                log_info "The verifier found problems without reopening a task."
                log_info "Inspect its findings in progress.md, then: ./ralph.sh --replan"
                save_state "$((i - 1))" "stopped"
                exit_reason="verification failed with an empty queue"
            else
                log_ok "No remaining tasks in progress.md."
                clear_state
                exit_reason="no remaining tasks"
            fi
            break
        fi

        local remaining
        remaining=$(count_remaining_tasks)
        log_info "Remaining tasks: ${remaining}"

        # Escalate to a stronger model once the cheap one has stalled. Cheap
        # generator + strong escalation is far cheaper than running strong
        # throughout, and far more likely to finish than running cheap forever.
        local iter_model="$MODEL"
        # The commit rule is repeated here so a PROMPT.md generated by an older
        # ralph.sh can't steer the agent into `git commit`.
        local iter_prompt="Follow @PROMPT.md. Study @progress.md first, then execute exactly one task.
Never run git commit (it is denied). Put your commit message in .ralph/commit-msg; the loop commits as the user."
        if [[ $stalls -gt 0 && -n "$ESCALATE_MODEL" ]]; then
            iter_model="$ESCALATE_MODEL"
            log_warn "Stalled ${stalls}x — escalating to model: ${ESCALATE_MODEL}"
        fi
        if [[ $stalls -gt 0 ]]; then
            iter_prompt="${iter_prompt}

The previous ${stalls} iteration(s) produced no commit and no change to
progress.md. Diagnose why before doing anything else: read the last entries in
progress.md, check \`git log\` and \`git status\`, and identify what blocked
forward motion. Then either unblock it or mark the task BLOCKED with the exact
error and move to the next one. Do not repeat the previous approach."
        fi

        local budget
        budget=$(iteration_budget)
        log_info "Launching Claude Code (fresh context, cap \$$(fmt_usd "$budget"))..."
        echo ""

        local before_sig
        before_sig=$(progress_signature)

        local head_before
        head_before=$(git rev-parse HEAD 2>/dev/null || echo "none")
        run_claude "iteration-${i}-$(date +%H%M%S)" "$iter_model" "$budget" "$iter_prompt"
        local iter_log="$RC_LOG"
        account_for_cost "$RC_COST"
        echo ""
        if [[ "$(git rev-parse HEAD 2>/dev/null || echo none)" != "$head_before" ]]; then
            log_warn "The agent made a commit itself despite the deny rule. Review: git log ${head_before:0:7}..HEAD"
        fi
        commit_work "Ralph iteration ${i}"

        save_state "$i" "stopped"

        # ── Post-iteration accounting ────────────────────────────────────────
        case "$RC_SUBTYPE" in
            error_max_budget_usd)
                log_warn "Iteration hit its \$$(fmt_usd "$budget") cap and was cut off mid-task."
                log_warn "Raise it with --iteration-budget, or split the task in progress.md."
                ;;
            error_during_execution|error_max_turns)
                log_warn "Iteration ended abnormally: ${RC_SUBTYPE}"
                ;;
        esac
        if [[ $RC_EXIT -ne 0 && "$RC_SUBTYPE" == "unknown" ]]; then
            log_warn "claude exited ${RC_EXIT}. See ${iter_log}"
        fi
        if [[ $RC_DENIALS -gt 0 ]]; then
            log_warn "${RC_DENIALS} action(s) denied by the permission classifier."
            log_warn "If they were legitimate, allow them in .claude/settings.json (permissions.allow"
            log_warn "or autoMode.environment) — see: claude auto-mode config"
        fi
        if [[ $RC_COMPACTIONS -gt 0 ]]; then
            # Compaction means the iteration outgrew its context window and
            # worked from a lossy summary — the opposite of what Ralph is for.
            log_warn "Context was compacted ${RC_COMPACTIONS}x this iteration. The task is too big —"
            log_warn "split it into smaller items in progress.md."
        fi

        if fgt "$RC_COST" 0; then
            log_info "Cost: \$$(fmt_usd "$RC_COST") this iteration  ·  \$$(fmt_usd "$SESSION_COST") total"
        fi

        # Only a rejected commit (see commit_work) leaves the tree dirty here.
        # .ralph/ is the loop's own logs and state, not the agent's work.
        if [[ -n "$(git status --porcelain -- . ':!.ralph' 2>/dev/null)" ]]; then
            log_warn "Working tree is still dirty — these changes were not committed:"
            git status --short -- . ':!.ralph' 2>/dev/null | head -8 | sed 's/^/         /' || true
        fi

        show_status_inline

        # ── Circuit breaker ──────────────────────────────────────────────────
        if [[ "$(progress_signature)" == "$before_sig" ]] && rate_limited; then
            # Hitting a usage limit is not the agent spinning; don't spend a
            # stall strike or escalate the model. Wait for the window instead.
            if ! wait_for_rate_limit; then
                exit_reason="rate limited past --max-rate-wait"
                break
            fi
        elif [[ "$(progress_signature)" == "$before_sig" ]]; then
            stalls=$((stalls + 1))
            log_warn "No commit and no progress.md change — stall ${stalls}/${MAX_STALLS}."
            if [[ $stalls -ge $MAX_STALLS ]]; then
                echo ""
                log_error "╔═══════════════════════════════════════╗"
                log_error "║  CIRCUIT BREAKER — loop is spinning   ║"
                log_error "╚═══════════════════════════════════════╝"
                log_error "${MAX_STALLS} consecutive iterations changed nothing. Stopping to save budget."
                log_info "Try:  ./ralph.sh --replan          (task queue drifted from reality)"
                log_info "      ./ralph.sh --plan            (see what the agent thinks is left)"
                log_info "      tail -100 ${iter_log}"
                exit_reason="circuit breaker: ${MAX_STALLS} stalled iterations"
                break
            fi
        else
            [[ $stalls -gt 0 ]] && log_ok "Progress resumed — stall counter reset."
            stalls=0
        fi

        # ── Completion claim ─────────────────────────────────────────────────
        if agent_text "$iter_log" | grep -q '<promise>COMPLETE</promise>' \
                && has_remaining_tasks; then
            log_warn "COMPLETE was claimed but progress.md still has open tasks. Continuing."
        elif agent_text "$iter_log" | grep -q '<promise>COMPLETE</promise>'; then
            if [[ $VERIFY_ENABLED -eq 0 ]] || run_verifier "verify-${i}-$(date +%H%M%S)"; then
                echo ""
                log_ok "╔═══════════════════════════════════════╗"
                log_ok "║         ALL TASKS COMPLETE!           ║"
                log_ok "╚═══════════════════════════════════════╝"
                echo ""
                clear_state
                exit_reason="all tasks complete"
                [[ $VERIFY_ENABLED -eq 1 ]] && exit_reason="all tasks complete (verified)"
                break
            fi
            log_warn "COMPLETE was claimed but not verified. Continuing."
        elif [[ $VERIFY_ENABLED -eq 1 && $VERIFY_EVERY -gt 0 && $(( i % VERIFY_EVERY )) -eq 0 ]]; then
            # Periodic checkpoint: catch drift early instead of at the finish line.
            run_verifier "verify-${i}-$(date +%H%M%S)" || true
        fi

        local latest_commit
        latest_commit=$(git log --oneline -1 2>/dev/null || echo "none")
        log_info "Latest commit: ${latest_commit}"

        if [[ $i -lt $MAX_ITERATIONS ]]; then
            local wait="$COOLDOWN"
            # Back off harder after a stall — usually a transient API or lock issue.
            [[ $stalls -gt 0 ]] && wait=$(( COOLDOWN * (stalls + 1) ))
            log_info "Cooling down ${wait}s before the next iteration..."
            log_info "(Press Ctrl+C now to stop after this iteration)"
            sleep "$wait" || true
        fi
        i=$((i + 1))
    done

    print_summary "$start_sha" "$exit_reason"
}

print_summary() {
    local start_sha="$1" exit_reason="$2"

    echo ""
    divider
    log_step "Ralph loop finished — ${exit_reason}"
    echo ""

    local final_total final_done
    final_total=$(count_total_tasks)
    final_done=$(count_done_tasks)
    echo -e "  Tasks completed: ${GREEN}${final_done}${NC} / ${final_total}"

    if [[ -n "$start_sha" ]]; then
        local commits
        commits=$(git rev-list --count "${start_sha}..HEAD" 2>/dev/null || echo "0")
        [[ -n "$commits" ]] || commits=0
        echo -e "  Commits made:    ${commits}"
    fi

    if fgt "$SESSION_COST" 0; then
        echo -e "  Total cost:      ${CYAN}\$$(fmt_usd "$SESSION_COST")${NC}"
    elif ! have_jq; then
        echo -e "  Total cost:      ${DIM}unknown (install jq to track spend)${NC}"
    fi
    echo -e "  Logs:            ${LOG_DIR}"

    if [[ $final_done -lt $final_total ]]; then
        echo ""
        log_warn "Some tasks remain. Run ./ralph.sh again to resume."
    fi

    divider
}

# ─── Main ────────────────────────────────────────────────────────────────────

show_help() {
    cat << 'HELP_EOF'
Usage: ./ralph.sh [options] [max_iterations]

An autonomous Ralph loop: fresh context each iteration, one task at a time,
all state on disk and in git.

Commands:
  ./ralph.sh                    Run the loop (default 20 iterations)
  ./ralph.sh 50                 Run with a max of 50 iterations
  ./ralph.sh --init             Scaffold PROMPT.md / progress.md / CLAUDE.md
  ./ralph.sh --plan             Analyze the PRD-vs-code gap, write no code
  ./ralph.sh --replan           Rebuild the task queue from the actual codebase
  ./ralph.sh --verify           Run the independent verification gate once
  ./ralph.sh --status           Show progress, spend, and the next task
  ./ralph.sh --reset            Archive this run and start fresh
  ./ralph.sh --stop             Gracefully stop a running loop
  ./ralph.sh --help             This message

Options:
  --worktree <name>             Run in an isolated git worktree on branch
                                ralph/<name>; your working tree is untouched
  --budget <usd>                Hard ceiling for the whole run (default: none)
  --iteration-budget <usd>      Ceiling per iteration (default: 5.00)
  --model <name>                Model for build iterations (e.g. sonnet)
  --escalate-model <name>       Stronger model used after a stall (e.g. opus)
  --fallback-model <name>       Used when the primary model is overloaded
  --effort <level>              low | medium | high | xhigh | max
  --max-stalls <n>              Stop after N iterations that change nothing (3)
  --verify-every <n>            Run the verification gate every N iterations (5)
  --no-verify                   Trust the agent's own COMPLETE claim (not advised)
  --cooldown <seconds>          Pause between iterations (default: 5)
  --permission-mode <mode>      auto (default): a classifier reviews each
                                action; anything that would prompt is denied
                                bypass: --dangerously-skip-permissions —
                                container or VM only
  --sandbox                     OS-level Bash sandbox, strict (macOS/Linux/WSL2)
  --bare                        Skip hooks (project ones too), plugins, MCP,
                                auto-memory for reproducible runs
                                (needs ANTHROPIC_API_KEY)
  --max-rate-wait <seconds>     Longest to sleep for a rate-limit reset (21600)

Every option also reads an env var: RALPH_BUDGET_USD, RALPH_ITER_BUDGET_USD,
RALPH_MODEL, RALPH_ESCALATE_MODEL, RALPH_FALLBACK_MODEL, RALPH_EFFORT,
RALPH_MAX_STALLS, RALPH_VERIFY_EVERY, RALPH_VERIFY, RALPH_COOLDOWN,
RALPH_MAX_ITERATIONS, RALPH_PERMISSION_MODE, RALPH_SANDBOX, RALPH_BARE,
RALPH_MAX_RATE_WAIT.

Typical overnight run:
  ./ralph.sh --worktree nightly --budget 40 --model sonnet --escalate-model opus 60

Guardrails, and why they exist:
  * Auto permissions     — unattended runs need no prompts, but "no prompts"
                           should not mean "no checks" outside a container.
  * Budget ceilings      — a runaway loop is the #1 way these get expensive.
  * Circuit breaker      — 3 iterations that change nothing means the loop is
                           spinning; more iterations will not fix it. Replan.
  * Verification gate    — an agent grading its own homework gives itself an A
                           every time. A separate session re-checks the work.
  * Worktree isolation   — the loop rewrites files hundreds of times.
  * One task per loop    — not "one task plus a quick refactor while I'm here."
                           A compacted context means the task was too big.

Smaller jobs are better served by Claude Code's built-ins, which are supported
and survive version updates:
  /goal   — keep working until a verifiable condition holds
            (headless: claude -p "/goal <condition>")
  /loop   — repeat a prompt on an interval
  /batch  — one mechanical change across parallel worktree agents
  /plugin install ralph-loop@claude-plugins-official

Reference: https://ghuntley.com/ralph/
HELP_EOF
}

need_value() {
    [[ -n "${2:-}" && "${2:0:1}" != "-" ]] || { log_error "$1 requires a value."; exit 2; }
}

main() {
    cd "$PROJECT_ROOT"

    local action="" worktree_name=""
    local relay=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|-s)  action="status";  relay+=("$1"); shift ;;
            --plan|-p)    action="plan";    relay+=("$1"); shift ;;
            --replan)     action="replan";  relay+=("$1"); shift ;;
            --verify)     action="verify";  relay+=("$1"); shift ;;
            --reset|-R)   action="reset";   relay+=("$1"); shift ;;
            --init|-i)    action="init";    relay+=("$1"); shift ;;
            --stop|-S)    action="stop";    relay+=("$1"); shift ;;
            --help|-h)    action="help";    shift ;;
            --no-verify)  VERIFY_ENABLED=0; relay+=("$1"); shift ;;
            --sandbox)    SANDBOX=1;        relay+=("$1"); shift ;;
            --bare)       BARE=1;           relay+=("$1"); shift ;;

            # --worktree is deliberately NOT relayed: the re-exec must not nest.
            --worktree)
                need_value "$1" "${2:-}"
                action="worktree"; worktree_name="$2"; shift 2 ;;

            --budget)
                need_value "$1" "${2:-}"; RUN_BUDGET_USD="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --iteration-budget)
                need_value "$1" "${2:-}"; ITER_BUDGET_USD="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --model)
                need_value "$1" "${2:-}"; MODEL="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --escalate-model)
                need_value "$1" "${2:-}"; ESCALATE_MODEL="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --fallback-model)
                need_value "$1" "${2:-}"; FALLBACK_MODEL="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --effort)
                need_value "$1" "${2:-}"; EFFORT="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --max-stalls)
                need_value "$1" "${2:-}"; MAX_STALLS="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --verify-every)
                need_value "$1" "${2:-}"; VERIFY_EVERY="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --cooldown)
                need_value "$1" "${2:-}"; COOLDOWN="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --permission-mode)
                need_value "$1" "${2:-}"; PERMISSION_MODE="$2"
                relay+=("$1" "$2"); shift 2 ;;
            --max-rate-wait)
                need_value "$1" "${2:-}"; MAX_RATE_WAIT="$2"
                relay+=("$1" "$2"); shift 2 ;;

            --*)
                log_error "Unknown flag: $1"
                echo "Run ./ralph.sh --help for usage."
                exit 2 ;;
            *)
                if [[ "$1" =~ ^[0-9]+$ ]]; then
                    if [[ "$1" -eq 0 ]]; then
                        log_error "Max iterations must be greater than 0."
                        exit 2
                    fi
                    MAX_ITERATIONS="$1"
                    relay+=("$1")
                else
                    log_error "Unexpected argument: $1"
                    echo "Run ./ralph.sh --help for usage."
                    exit 2
                fi
                shift ;;
        esac
    done

    case "$action" in
        status)   preflight; show_status ;;
        plan)     preflight; run_plan ;;
        replan)   preflight; run_replan ;;
        verify)   preflight; run_verify_once ;;
        reset)    archive_run ;;
        init)     run_init ;;
        stop)     run_stop ;;
        help)     show_help; exit 0 ;;
        worktree) run_worktree "$worktree_name" ${relay[@]+"${relay[@]}"} ;;
    esac

    preflight
    run_loop
}

main "$@"
