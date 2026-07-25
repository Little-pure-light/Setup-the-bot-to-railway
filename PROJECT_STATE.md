# PROJECT_STATE — 小宸光

Last updated: 2026-07-25

## Current stage

**Memory V2 Quality Improvement v1.0** (complete, pending deploy of quality commit)

Prior stages landed on `main`:

- Infrastructure (reflection contract, token ledger, finetune JSONL)
- Memory V2 Phase 2 (Identity / Semantic / Decision / Night Growth / Graph / Retrieval)
- Fix + Staging verification (§9 PASS on `ai2.dreamground.net` @ `791506d`)

## Live deployment (as of last verify)

| Surface | Value |
|---------|--------|
| Backend | `https://ai2.dreamground.net` |
| Commit verified | `791506d` (pre-quality; quality changes need redeploy) |
| Open WebUI | `https://open-webui-production-df5b.up.railway.app` |
| `MEMORY_V2_ENABLED` | true on Backend |
| Redis readiness | degraded / unavailable |

## Quality stage summary

| Task | Status |
|------|--------|
| A Classifier High/Med/Low + write gate | Done |
| B Retrieval ranking weights | Done |
| C Reflection insight quality | Done |
| D Identity evolution analysis + fix | Done |
| E Graph utilization in retrieval | Done |
| F Benchmark suite + reports | Done |

## Key paths

- Docs: `docs/XIAOCHENGUANG_V2_ARCHITECTURE_AND_DEPLOYMENT_STATUS.md`
- Quality reports: `docs/quality_reports/*`
- Verify script: `scripts/verify_memory_v2_staging.py`

## Next recommended

1. Commit + push quality changes; redeploy Backend  
2. Optional re-run §9 smoke + Night Growth dry_run  
3. Redis health / volume persistence for identity+graph  
4. Rotate API_SECRET if exposed in chat history  
