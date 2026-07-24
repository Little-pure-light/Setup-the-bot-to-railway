# Staging Deployment Report

## Status

| Item | Status |
|------|--------|
| Code + unit/integration tests | **Ready** (pytest full green locally) |
| Railway Staging deploy | **Pending operator action** (secrets + service create/update) |
| Production MEMORY_V2 | **Remains default false** |
| Redis migration | **Not done** (explicitly deferred) |

## Recommended Staging variables

```text
APP_ENV=staging
MEMORY_V2_ENABLED=true
TOKEN_LEDGER_ENABLED=true
NIGHT_GROWTH_ENABLED=false
NIGHT_GROWTH_INTERNAL_TOKEN=<generate-secret>
IDENTITY_UPDATE_MODE=candidate
REFLECTION_INCLUDE_STATUS=true
# existing: OPENAI_API_KEY, SUPABASE_*, REDIS_*, API_SECRET
```

## Pre-deploy checklist

- [ ] Supabase schema backup
- [ ] Staging uses independent test user_ids
- [ ] Secrets not committed
- [ ] Health `/health` after deploy
- [ ] `git_commit` visible on health when RAILWAY_GIT_COMMIT_SHA set

## Deploy steps (operator)

1. Commit + push branch or main (after review)
2. Railway Staging service set env above
3. Deploy
4. Smoke: `/health`, `/api/chat`, `/v1/models`
5. Night growth dry_run via internal endpoint
6. Record Staging URL here: `________________`

## Honest note

Agent completed code path verification. **Live Railway Staging URL is not available until you deploy.**  
Do not treat local green as deployed.
