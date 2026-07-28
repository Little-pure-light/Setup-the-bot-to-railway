-- Task 006 — Core data contracts (ROLLBACK)
-- Reversible as far as additive objects allow.
-- Cannot restore dropped production data; this only removes Task006-added objects.
-- DO NOT apply to production without explicit rollback authorization.
-- contract_version: task006_v1

BEGIN;

-- Drop RPC functions (wrapper first)
DROP FUNCTION IF EXISTS public.match_memories(vector, integer, text);
DROP FUNCTION IF EXISTS public.match_memories_v2(vector, integer, text, text, text, double precision);

-- Optional: drop indexes created by forward migration
DROP INDEX IF EXISTS public.idx_memories_user_ai_created;
DROP INDEX IF EXISTS public.idx_memories_conversation_created;
DROP INDEX IF EXISTS public.idx_emotional_states_user_created;
DROP INDEX IF EXISTS public.idx_reflections_conversation_created;
DROP INDEX IF EXISTS public.idx_reflections_user_created;
DROP INDEX IF EXISTS public.idx_user_preferences_user_id;
DROP INDEX IF EXISTS public.idx_user_preferences_conversation_id;

-- user_preferences: only drop if empty and created by this task (operator decision)
-- Default rollback keeps table to avoid destroying new preference data.
-- To fully remove: DROP TABLE IF EXISTS public.user_preferences;

-- Remove additive columns only when safe (nullable / defaults). Operators may
-- choose to leave columns in place. Explicit DROP kept commented for safety:
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS reflection_key;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS confidence_score;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS ai_id;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS contract_version;

-- NOTE: Do not drop emotional_states.dominant_emotion / created_at — those are
-- the new schema baseline, not Task006 inventions.

COMMIT;
