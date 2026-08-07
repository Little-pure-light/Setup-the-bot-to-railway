#!/usr/bin/env bash
# Task009-007B — CI-only proof that the runner's REAL age binary can parse a recipient
# and round-trip encrypt/decrypt, exercising the exact orchestrator invocation shape
# (age -r <recipient> -o <out> <in>).
#
# Safety:
#   - Uses a TEMPORARY keypair generated on the runner. NEVER the production recipient,
#     the production TASK009_AGE_RECIPIENT secret, or the age private identity.
#   - Reads no secrets. Prints only fixed safe markers + age product/version. Never prints
#     the generated recipient/identity, ciphertext, or any path-embedded value.
#   - This isolates the failing surface: if this round-trip PASSES on the runner but a live
#     backup fails at age_encrypt, the age binary + invocation are sound and the production
#     recipient value / platform configuration is the suspect (a platform correction, not code).
set -euo pipefail

fail() { echo "AGE_ROUNDTRIP_FAILED reason=$1"; exit 1; }

command -v age >/dev/null 2>&1 || fail "age_not_installed"
command -v age-keygen >/dev/null 2>&1 || fail "age_keygen_not_installed"

age --version   # product/version only — safe

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# temporary identity + recipient (throwaway; never production, never printed)
age-keygen -o "$tmp/id.txt" >/dev/null 2>&1 || fail "keygen"
recipient="$(age-keygen -y "$tmp/id.txt" 2>/dev/null || true)"
case "$recipient" in
  age1*) : ;;
  *) fail "recipient_shape" ;;
esac

printf '%s\n' "TASK009_AGE_ROUNDTRIP_PLAINTEXT" > "$tmp/in.txt"

# exact orchestrator invocation shape
age -r "$recipient" -o "$tmp/out.age" "$tmp/in.txt" || fail "encrypt"
[ -s "$tmp/out.age" ] || fail "empty_ciphertext"
cmp -s "$tmp/in.txt" "$tmp/out.age" && fail "not_encrypted"

age -d -i "$tmp/id.txt" -o "$tmp/dec.txt" "$tmp/out.age" || fail "decrypt"
cmp -s "$tmp/in.txt" "$tmp/dec.txt" || fail "decrypt_mismatch"

echo "AGE_ROUNDTRIP_OK"
