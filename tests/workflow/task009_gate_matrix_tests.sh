#!/usr/bin/env bash
# Task009-007A — activation gate matrix tests (deterministic; no network, no secrets).
# Proves scripts/backup/task009_workflow_gate.sh returns the correct should_run/mode for every
# event x enabled x dry_run combination — especially the four required by CODEX_009_007_ACTIVATION_PREFLIGHT.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GATE="$(cd "$HERE/../.." && pwd)/scripts/backup/task009_workflow_gate.sh"
[ -f "$GATE" ] || { echo "gate script not found: $GATE"; exit 1; }

fail=0
check() {
  # args: name event enabled dry_in expect_run expect_mode
  local name="$1" event="$2" enabled="$3" dry="$4" exp_run="$5" exp_mode="$6"
  local out sr md
  out="$(EVENT_NAME="$event" BACKUP_ENABLED="$enabled" DRY_RUN_INPUT="$dry" GITHUB_OUTPUT="" bash "$GATE")"
  sr="$(printf '%s\n' "$out" | sed -n 's/^should_run=//p')"
  md="$(printf '%s\n' "$out" | sed -n 's/^mode=//p')"
  if [ "$sr" = "$exp_run" ] && [ "$md" = "$exp_mode" ]; then
    echo "OK  $name -> should_run=$sr mode=$md"
  else
    echo "FAIL $name -> got should_run=$sr mode=$md ; expected should_run=$exp_run mode=$exp_mode"
    fail=1
  fi
}

# --- The four required matrix rows (CODEX_009_007_ACTIVATION_PREFLIGHT) ---
check "manual dry_run=true + disabled  => RUN dry-run"   workflow_dispatch ""     true  true  dryrun
check "manual dry_run=false + disabled => SKIP"          workflow_dispatch ""     false false skip
check "schedule + disabled             => SKIP"          schedule          ""     ""    false skip
check "schedule + enabled              => RUN live"      schedule          true   ""    true  live
check "manual dry_run=false + enabled  => RUN live"      workflow_dispatch true   false true  live

# --- Additional safety rows ---
check "manual dry_run=true + enabled   => RUN dry-run (never auto-live on dry)" workflow_dispatch true  true  true  dryrun
check "schedule + enabled NEVER dry-run (mode must be live)"                    schedule          true  ""    true  live
check "schedule + explicit-ish junk enabled=false => SKIP"                      schedule          false ""    false skip
check "manual + missing dry_run input => SKIP (fail-closed)"                    workflow_dispatch true  ""    false skip
check "manual + enabled empty + dry=false => SKIP"                              workflow_dispatch ""    false false skip
check "unknown event => SKIP"                                                   push              true  true  false skip
check "enabled='TRUE' (case-sensitive, not 'true') + schedule => SKIP"          schedule          TRUE  ""    false skip

# --- Static assertion: workflows must NOT invoke the shell scripts via a bare relative path
# (both scripts are committed with git mode 100644 / non-executable; Ubuntu runners need `bash <file>`).
REPO="$(cd "$HERE/../.." && pwd)"
assert_bash_invocation() {
  local wf="$1" script="$2"
  # any run line referencing the script must be prefixed with `bash ` (allow leading ./). Fail if a bare ./<script> run exists.
  if grep -nE "run:[[:space:]]*\./${script}([[:space:]]|$)" "$wf" >/dev/null 2>&1; then
    echo "FAIL static: $wf invokes ./$script directly (needs 'bash ./$script')"; fail=1
  else
    echo "OK  static: $wf does not invoke ./$script directly"
  fi
  if grep -nE "run:[[:space:]]*bash[[:space:]]+\./${script}" "$wf" >/dev/null 2>&1; then
    echo "OK  static: $wf invokes $script via bash"
  fi
}
assert_bash_invocation "$REPO/.github/workflows/task009-backup.yml" "scripts/backup/task009_workflow_gate.sh"
assert_bash_invocation "$REPO/.github/workflows/ci.yml"              "tests/workflow/task009_gate_matrix_tests.sh"

if [ "$fail" -ne 0 ]; then
  echo "TASK009_WORKFLOW_GATE_TESTS_FAIL"
  exit 1
fi
echo "TASK009_WORKFLOW_GATE_TESTS_PASS"
