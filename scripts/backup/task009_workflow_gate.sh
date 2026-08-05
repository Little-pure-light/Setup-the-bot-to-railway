#!/usr/bin/env bash
# Task009-007A — activation gate for the encrypted remote backup workflow.
#
# Decides, from the triggering event and the TASK009_BACKUP_ENABLED repo variable,
# whether the backup runs and in which mode. Fail-closed by default.
#
# Inputs (env):
#   EVENT_NAME      : github.event_name  (schedule | workflow_dispatch | ...)
#   BACKUP_ENABLED  : vars.TASK009_BACKUP_ENABLED  ('true' to enable live/scheduled)
#   DRY_RUN_INPUT   : inputs.dry_run for workflow_dispatch ('true' | 'false'); empty for schedule
#
# Outputs (stdout, and appended to $GITHUB_OUTPUT when set):
#   should_run : true | false
#   mode       : dryrun | live | skip
#
# Rules (see docs/TASK009_RESTORE_RUNBOOK.md 007A):
#   - schedule NEVER dry-runs; it runs the live backup ONLY when enabled, else SKIP.
#   - manual dry_run=true  -> RUN dry-run, allowed even when disabled (no secrets/DB/upload).
#   - manual dry_run=false -> live backup ONLY when enabled, else SKIP.
#   - anything else / unexpected -> SKIP (fail-closed).
set -euo pipefail

event="${EVENT_NAME:-}"
enabled="false"
if [ "${BACKUP_ENABLED:-}" = "true" ]; then enabled="true"; fi
dry_in="${DRY_RUN_INPUT:-}"

should_run="false"
mode="skip"

case "$event" in
  schedule)
    # schedule is always live-or-skip; never dry-run
    if [ "$enabled" = "true" ]; then
      should_run="true"; mode="live"
    else
      should_run="false"; mode="skip"
    fi
    ;;
  workflow_dispatch)
    if [ "$dry_in" = "true" ]; then
      should_run="true"; mode="dryrun"        # dry-run permitted regardless of enabled
    elif [ "$dry_in" = "false" ]; then
      if [ "$enabled" = "true" ]; then
        should_run="true"; mode="live"        # manual live only when enabled
      else
        should_run="false"; mode="skip"
      fi
    else
      should_run="false"; mode="skip"         # missing/unexpected input -> fail-closed
    fi
    ;;
  *)
    should_run="false"; mode="skip"
    ;;
esac

echo "should_run=${should_run}"
echo "mode=${mode}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "should_run=${should_run}"
    echo "mode=${mode}"
  } >> "$GITHUB_OUTPUT"
fi
