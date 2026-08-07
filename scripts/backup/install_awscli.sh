#!/usr/bin/env bash
# Task009 — single source of truth for the pinned AWS CLI v2 version used by BOTH the live
# backup workflow and the CI S3 arg-shape proof, so CI and live cannot drift.
#
# The version is read from scripts/backup/awscli_version.txt. Installs the pinned AWS CLI v2
# from the official installer over HTTPS and verifies the exact reported version. Fail-closed
# on any mismatch. Reads no secrets; safe in PR CI.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
AWSCLI_VERSION="$(tr -d ' \t\r\n' < "${here}/awscli_version.txt")"
[ -n "$AWSCLI_VERSION" ] || { echo "AWSCLI_VERSION_UNRESOLVED"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" -o "$tmp/awscliv2.zip"
unzip -q "$tmp/awscliv2.zip" -d "$tmp"
sudo "$tmp/aws/install" --update

installed="$(aws --version 2>&1 || true)"
echo "$installed"
case "$installed" in
  *"aws-cli/${AWSCLI_VERSION}"*) echo "AWSCLI_PINNED_OK aws-cli/${AWSCLI_VERSION}" ;;
  *) echo "ERROR: AWS CLI version mismatch (expected aws-cli/${AWSCLI_VERSION})"; exit 1 ;;
esac
