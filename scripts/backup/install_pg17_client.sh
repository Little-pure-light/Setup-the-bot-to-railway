#!/usr/bin/env bash
# Task009-007B — install & verify the PostgreSQL 17 CLIENT on a throwaway GitHub runner.
#
# Why: the formal live diagnostic proved server major = 17 but the runner's generic
# `postgresql-client` resolved to major 16 (client_major < server_major -> pg_dump aborts).
# This installs ONLY the versioned client from the official PostgreSQL PGDG Apt repo,
# resolves the exact major-17 binaries, verifies them, and (in Actions) exports their
# paths so the orchestrator uses them via PSQL_PATH / PG_DUMP_PATH / PG_RESTORE_PATH.
#
# Contract / safety:
#   - Installs postgresql-client-17 ONLY. Never the unversioned postgresql-client, nor
#     any postgresql server / meta package.
#   - Official PGDG repo over HTTPS with the official signing key referenced via Signed-By.
#     No deprecated apt-key, no curl-pipe-shell, no unofficial binaries, no floating latest.
#   - fail-closed: any repo/install/verify error stops with a fixed safe marker and a
#     non-zero exit; there is NO fallback to Ubuntu's major 16.
#   - Reads NO backup secrets; safe to run in PR CI on a public runner.
#   - Prints only tool product/version strings and fixed safe markers — never environment,
#     secrets, host, user, database, endpoint, token, or connection strings.
set -euo pipefail

PG_MAJOR=17
PG_BIN="/usr/lib/postgresql/${PG_MAJOR}/bin"
KEY_PATH="/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc"
KEY_URL="https://www.postgresql.org/media/keys/ACCC4CF8.asc"
LIST_PATH="/etc/apt/sources.list.d/pgdg.list"

fail() { echo "PG17_CLIENT_INSTALL_FAILED reason=$1"; exit 1; }

# --- resolve Ubuntu codename (official PGDG expects <codename>-pgdg) ---
CODENAME=""
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  CODENAME="${VERSION_CODENAME:-}"
fi
if [ -z "$CODENAME" ] && command -v lsb_release >/dev/null 2>&1; then
  CODENAME="$(lsb_release -cs)"
fi
[ -n "$CODENAME" ] || fail "codename_unresolved"

# --- official PGDG repo: HTTPS key via Signed-By (no apt-key) ---
sudo install -d /usr/share/postgresql-common/pgdg || fail "keydir"
sudo curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  -o "$KEY_PATH" "$KEY_URL" || fail "key_download"
[ -s "$KEY_PATH" ] || fail "key_empty"

ARCH="$(dpkg --print-architecture)"
echo "deb [signed-by=${KEY_PATH} arch=${ARCH}] https://apt.postgresql.org/pub/repos/apt ${CODENAME}-pgdg main" \
  | sudo tee "$LIST_PATH" >/dev/null || fail "repo_list"

sudo apt-get update || fail "apt_update"

# --- install ONLY the versioned client (no server, no unversioned meta) ---
sudo apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" || fail "apt_install"

# --- resolve & verify the EXACT major-17 binaries (no /usr/bin wrapper / PATH reliance) ---
verify_tool() {
  local tool="$1" bin ver major
  bin="${PG_BIN}/${tool}"
  [ -x "$bin" ] || fail "missing_binary_${tool}"
  ver="$("$bin" --version)" || fail "version_call_${tool}"
  # e.g. "pg_dump (PostgreSQL) 17.2 (Ubuntu 17.2-1.pgdg24.04+1)" -> first integer = major
  major="$(printf '%s' "$ver" | grep -oE '[0-9]+' | head -n1 || true)"
  [ "$major" = "$PG_MAJOR" ] || fail "major_mismatch_${tool}_got_${major:-none}"
  echo "$ver"   # product/version only — safe
}

verify_tool psql
verify_tool pg_dump
verify_tool pg_restore

# --- export exact paths for the following live step (Actions only); harmless elsewhere ---
if [ -n "${GITHUB_ENV:-}" ]; then
  {
    echo "PSQL_PATH=${PG_BIN}/psql"
    echo "PG_DUMP_PATH=${PG_BIN}/pg_dump"
    echo "PG_RESTORE_PATH=${PG_BIN}/pg_restore"
  } >> "$GITHUB_ENV" || fail "github_env_export"
fi

echo "PG17_CLIENT_OK bin=${PG_BIN}"
