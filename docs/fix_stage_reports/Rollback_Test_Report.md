# Rollback Test Report

## Feature flags

```text
MEMORY_V2_ENABLED=false
TOKEN_LEDGER_ENABLED=false
NIGHT_GROWTH_ENABLED=false
```

## Guarantees

- V1 conversation rows untouched by flag off
- Identity version files remain on disk (not deleted)
- Graph JSON retained but unused when V2 off
- Night Growth endpoint can be disabled via `NIGHT_GROWTH_ENDPOINT_ENABLED=false`
- No destructive Supabase drop in this stage

## Identity rollback

`IdentityEngine.rollback(version)` creates a **new** formal version (history preserved).

## Verified locally

- Identity rollback unit test PASS
- Night Growth day skip / force PASS
- Graph integrity empty graph ok
