#!/usr/bin/env bash
# Task009-007B — deterministic static contract tests for the PostgreSQL 17 client fix.
# No network / no runner install here; pure static assertions over the repo files so the
# contract cannot silently regress (e.g. drift back to the unversioned major-16 client).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WF="$ROOT/.github/workflows/task009-backup.yml"
CI="$ROOT/.github/workflows/ci.yml"
INST="$ROOT/scripts/backup/install_pg17_client.sh"
GATE="$ROOT/scripts/backup/task009_workflow_gate.sh"
GATE_TEST="$ROOT/tests/workflow/task009_gate_matrix_tests.sh"

fails=0
ok()  { echo "OK   $1"; }
bad() { echo "FAIL $1"; fails=$((fails+1)); }
have() { [ -f "$1" ] || { bad "missing file: $1"; return 1; }; }

have "$WF" && have "$CI" && have "$INST" && have "$GATE" && have "$GATE_TEST" || { echo "TASK009_PG17_CONTRACT_TESTS_FAIL"; exit 1; }

# ── backup workflow ───────────────────────────────────────────────────────────
if grep -q 'install_pg17_client.sh' "$WF"; then ok "workflow invokes install_pg17_client.sh"; else bad "workflow does not invoke the pg17 installer"; fi
# workflow must NOT install any postgresql client/server via apt directly anymore
if grep -qE 'postgresql-client' "$WF"; then bad "workflow still references postgresql-client (must delegate to installer)"; else ok "workflow has no direct postgresql-client apt install"; fi
if grep -qE 'postgresql-server|postgresql-common' "$WF"; then bad "workflow references a postgresql server package"; else ok "workflow installs no postgresql server package"; fi

# Code-only view (strip comments) so prose describing what we AVOID cannot false-trip
# the negative package/version assertions.
INST_CODE="$(sed 's/#.*//' "$INST")"

# ── installer: versioned client only ─────────────────────────────────────────
if grep -q 'postgresql-client-17' "$INST"; then ok "installer installs postgresql-client-17"; else bad "installer does not install postgresql-client-17"; fi
# no unversioned postgresql-client (postgresql-client NOT followed by a dash) — code only
if grep -qE 'postgresql-client([^-]|$)' <<<"$INST_CODE"; then bad "installer references the unversioned postgresql-client"; else ok "installer has no unversioned postgresql-client (code)"; fi
# no server / meta package — code only
if grep -qE 'postgresql-server|(^|[[:space:]"])postgresql([[:space:]"]|$)' <<<"$INST_CODE"; then bad "installer references a postgresql server/meta package"; else ok "installer installs no server/meta package (code)"; fi

# ── installer: official PGDG, Signed-By, HTTPS, no apt-key, no curl|sh ────────
if grep -q 'signed-by=' "$INST"; then ok "installer uses Signed-By"; else bad "installer does not use Signed-By"; fi
if grep -q 'https://www.postgresql.org/media/keys' "$INST" && grep -q 'https://apt.postgresql.org' "$INST"; then ok "installer uses official PGDG HTTPS key + repo"; else bad "installer does not use the official PGDG HTTPS key/repo"; fi
if grep -qw 'apt-key' <<<"$INST_CODE"; then bad "installer uses deprecated apt-key"; else ok "installer does not use apt-key (code)"; fi
if grep -qE 'curl[^\n]*\|[^\n]*(sh|bash)' <<<"$INST_CODE"; then bad "installer uses curl-pipe-shell"; else ok "installer does not curl-pipe-shell (code)"; fi

# ── installer: fail-closed, no major-16 fallback ─────────────────────────────
if grep -q 'set -euo pipefail' "$INST"; then ok "installer is fail-closed (set -euo pipefail)"; else bad "installer missing set -euo pipefail"; fi
if grep -qE 'apt-get install[^\n]*\|\|[^\n]*true' <<<"$INST_CODE"; then bad "installer swallows apt-get install failure"; else ok "installer does not swallow install failure"; fi
if grep -q '16' <<<"$INST_CODE"; then bad "installer code references 16 (possible major-16 fallback)"; else ok "installer code has no major-16 fallback"; fi

# ── installer: builds the EXACT major-17 binary paths and exports them ────────
if grep -q 'PG_MAJOR=17' "$INST"; then ok "installer pins PG_MAJOR=17"; else bad "installer does not pin PG_MAJOR=17"; fi
if grep -q '/usr/lib/postgresql/${PG_MAJOR}/bin' "$INST"; then ok "installer resolves /usr/lib/postgresql/\${PG_MAJOR}/bin"; else bad "installer does not use the versioned bin dir"; fi
for pair in 'PSQL_PATH=${PG_BIN}/psql' 'PG_DUMP_PATH=${PG_BIN}/pg_dump' 'PG_RESTORE_PATH=${PG_BIN}/pg_restore'; do
  if grep -qF "$pair" "$INST"; then ok "installer exports $pair"; else bad "installer does not export $pair"; fi
done

# ── CI runs the same installer on a real runner ──────────────────────────────
if grep -q 'install_pg17_client.sh' "$CI"; then ok "CI runs the pg17 installer on a real runner"; else bad "CI does not run the pg17 installer"; fi
if grep -qE 'PG17_CLIENT_PATHS_VERIFIED|major.*17|PG_DUMP_PATH' "$CI"; then ok "CI verifies exported major-17 paths"; else bad "CI does not verify exported major-17 paths"; fi

# ── activation matrix unchanged (gate still wired; triggers intact) ──────────
if grep -q 'task009_workflow_gate.sh' "$WF"; then ok "workflow still resolves via task009_workflow_gate.sh"; else bad "workflow no longer uses the activation gate"; fi
if grep -q 'workflow_dispatch' "$WF" && grep -q 'schedule' "$WF"; then ok "workflow keeps manual + schedule triggers"; else bad "workflow trigger matrix changed"; fi

echo
if [ "$fails" -eq 0 ]; then
  echo "TASK009_PG17_CONTRACT_TESTS_PASS"
  exit 0
else
  echo "TASK009_PG17_CONTRACT_TESTS_FAIL ($fails)"
  exit 1
fi
