# Task 006 Canonical Data Contract (task006_v1)

See collaboration folder copy: `GROK_006_CANONICAL_DATA_CONTRACT.md` for full ADR delivered to Codex.
This repo copy is the source-of-truth summary for migrations.

## Memory RPC
- Primary: `match_memories_v2(query_embedding vector(1536), match_count, filter_conversation_id, filter_user_id, filter_ai_id, min_similarity)`
- Distance: cosine `<=>` → similarity `1 - distance`
- **Fail-closed**: `filter_user_id` AND `filter_ai_id` are required (NULL/empty → zero rows). `default_user` is a real owner value, NOT a bypass.
- Scope: long-term semantic memory is **same user_id + ai_id across conversations**; `filter_conversation_id` is optional narrowing only.
- App paths use `match_memories_v2` **only**; the app never calls any legacy `match_memories`.
- **Gate C expand-only**: the current production baseline has **no** custom public RPC. The forward migration MUST NOT create, replace, revoke, grant, drop, or alter the legacy `public.match_memories(vector, integer, text)` — its body is unknown/unrestorable. Legacy retirement/cleanup is a **separate, deferred, environment-specific** task (C7), only after the new contract is verified stable (and may be "no action" if no legacy RPC exists).
- Grants: only the **new** `match_memories_v2` is locked to `service_role`; `anon`/`authenticated`/`PUBLIC` are revoked from it (no unscoped public memory search, no public bypass introduced).
- Env: `MEMORY_RPC_NAME` default `match_memories_v2`; `MEMORY_MIN_SIMILARITY` default **`0.55`** (conservative cosine floor; calibrate upward with real samples at Gate C); `MEMORY_SEMANTIC_SCOPE` default `user_ai_cross_conversation`.

## Emotion
- Table `emotional_states`: `user_id`, `dominant_emotion`, `intensity`, `confidence`, `context`, `created_at`
- Writers/readers must not use `emotion_type` / `timestamp`

## Reflection
- Table `xiaochenguang_reflections`: keep bigint `id` serial; runtime inserts `reflection_key UUID`, `confidence_score`, optional `ai_id`, `contract_version`
- Durable success = Supabase only; Redis is cache; Pinecone is vector

## User preferences
- Table `user_preferences`: unique `user_id`, JSONB `personality_profile` / `voice_settings`, optional conversation_id, timestamps
- **RLS is NOT enabled by this migration.** Enabling RLS without policies while the backend may run on an anon key would break `user_preferences` read/write. The forward migration intentionally leaves RLS off.
- Data-plane identity: backend prefers `SUPABASE_SERVICE_ROLE_KEY` (see `supabase_handler.py`). Earlier claims that "the backend already uses service role" were **not** accurate — the handler previously preferred the anon key. It now prefers service_role and falls back to anon with a loud warning.
- Least-privilege JWT/RLS policies for end-users are deferred to Gate C auth design and must be reviewed by Codex before any "secure multi-tenant isolation" claim.
