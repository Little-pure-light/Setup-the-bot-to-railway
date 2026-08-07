#!/usr/bin/env bash
# Task009-007B — CI-only proof that the EXACT orchestrator aws-cli argument shape is
# syntactically valid, with ZERO network, using DUMMY bucket/endpoint and a temp file.
#
# Why: the post-recipient-fix live run stopped at `stage=s3_upload exit=252`. AWS CLI v2
# return code 252 means invalid syntax / unknown parameter / incorrect parameter value that
# prevents the command from running (NOT token/network). This proves the argument shape the
# orchestrator uses (age .age upload with --metadata/--endpoint-url/--only-show-errors, and the
# plain manifest/SHA256SUMS upload) is itself valid — isolating a live 252 to the production
# bucket/endpoint parameter VALUE rather than the code's CLI syntax.
#
# Safety: NEVER uses the production R2 bucket/endpoint/token/secret. `--dryrun` makes no network
# call and needs no real credentials. Dummy creds/host below are non-production placeholders.
# Prints only fixed safe markers + aws product/version. Never prints production values.
set -euo pipefail

fail() { echo "S3_ARGSHAPE_FAILED reason=$1"; exit 1; }

command -v aws >/dev/null 2>&1 || fail "aws_not_installed"
aws --version   # product/version only — safe

# Non-production dummies. --dryrun short-circuits before any network/auth for `aws s3 cp`.
export AWS_ACCESS_KEY_ID="dummy-ci-not-real"
export AWS_SECRET_ACCESS_KEY="dummy-ci-not-real"
export AWS_DEFAULT_REGION="auto"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf 'ciphertext-placeholder' > "$tmp/backup.tar.age"

BUCKET="dummy-ci-bucket"
ENDPOINT="https://dummy.ci.invalid"
PREFIX="xcg/pg/public/00000000_000000Z-ci"

# A) exact .age upload shape: s3 cp <file> s3://<bucket>/<key> --endpoint-url <ep> --metadata sha256=<hex> --only-show-errors
aws s3 cp "$tmp/backup.tar.age" "s3://${BUCKET}/${PREFIX}/backup.tar.age" \
  --endpoint-url "$ENDPOINT" --metadata "sha256=deadbeefdeadbeefdeadbeefdeadbeef" \
  --only-show-errors --dryrun >/dev/null 2>&1 || fail "cp_age_metadata_shape_exit_$?"

# B) exact manifest/SHA256SUMS upload shape (no metadata); also prove --dryrun is genuinely no-network
out="$(aws s3 cp "$tmp/backup.tar.age" "s3://${BUCKET}/${PREFIX}/manifest.json" \
  --endpoint-url "$ENDPOINT" --dryrun 2>&1)" || fail "cp_plain_shape_exit_$?"
case "$out" in
  *"(dryrun)"*) : ;;
  *) fail "dryrun_marker_absent" ;;
esac

echo "S3_ARGSHAPE_OK"
