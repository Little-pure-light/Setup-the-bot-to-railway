# Remaining Issues

1. **Staging not live** until operator deploys Railway with secrets.
2. **Production soak** not recommended until Staging dialogue matrix (spec §9.2) passes on real Redis/Supabase/OpenAI.
3. **chat_router** still large (out of scope for this stage).
4. **Reflection bounded wait** default 0 — status is usually `pending` immediately (honest); completed reflections require later fetch or wait_ms > 0.
5. **Identity** still filesystem — multi-device sync needs future store (not this stage).
6. **Embedding dimension** depends on OpenAI model; Fake client uses dim=8 in tests only.
7. **Night Growth** load turns still depends on Supabase conversation rows quality.
8. **Observability**: request_id exists globally; memory-specific structured metrics can be deepened later.
9. **Redis migration** deferred by design.
10. **Uncommitted code** — commit hash for this fix stage is pending until git commit.

## Recommend Production soak?

**No — not yet.**  
Recommend: deploy Staging → run §9.2 manual scenarios → then decide soak with `MEMORY_V2_ENABLED` still false on Production.
