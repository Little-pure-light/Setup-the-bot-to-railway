# Task 006 Canonical Data Contract (task006_v1)

See collaboration folder copy: `GROK_006_CANONICAL_DATA_CONTRACT.md` for full ADR delivered to Codex.
This repo copy is the source-of-truth summary for migrations.

## Memory RPC
- Primary: `match_memories_v2(query_embedding vector(1536), match_count, filter_conversation_id, filter_user_id, filter_ai_id, min_similarity)`
- Distance: cosine `<=>` → similarity `1 - distance`
- Legacy wrapper: `match_memories(query_embedding, match_count, conversation_id)` delegates to v2
- Env: `MEMORY_RPC_NAME` default `match_memories_v2`; `MEMORY_MIN_SIMILARITY` default `0.0`

## Emotion
- Table `emotional_states`: `user_id`, `dominant_emotion`, `intensity`, `confidence`, `context`, `created_at`
- Writers/readers must not use `emotion_type` / `timestamp`

## Reflection
- Table `xiaochenguang_reflections`: keep bigint `id` serial; runtime inserts `reflection_key UUID`, `confidence_score`, optional `ai_id`, `contract_version`
- Durable success = Supabase only; Redis is cache; Pinecone is vector

## User preferences
- Table `user_preferences`: unique `user_id`, JSONB `personality_profile` / `voice_settings`, optional conversation_id, timestamps
- RLS enabled; policies require auth audit before production (service role backend expected)
