-- Task 006 — Core data contracts (ROLLBACK) v1.2 (Gate C expand-only)
-- Reverses ONLY the Task006-added, additive objects/constraints.
-- EXPAND-ONLY invariant: this rollback MUST NEVER drop or alter the legacy
-- public.match_memories(vector, integer, text). The forward migration no longer
-- creates/replaces/retires it, and its original body cannot be restored, so we
-- leave any existing legacy function completely untouched.
-- DO NOT apply to production without explicit rollback authorization.
-- contract_version: task006_v1

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Drop ONLY the NEW additive RPC (match_memories_v2).
--    Do NOT touch legacy public.match_memories — forward never created/altered
--    it, so rollback must not drop it either.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.match_memories_v2(vector, integer, text, text, text, double precision);

-- ---------------------------------------------------------------------------
-- 2) Drop Task006-added CHECK / UNIQUE constraints (safe; additive)
-- ---------------------------------------------------------------------------
ALTER TABLE public.emotional_states
  DROP CONSTRAINT IF EXISTS emotional_states_intensity_range;
ALTER TABLE public.emotional_states
  DROP CONSTRAINT IF EXISTS emotional_states_confidence_range;
ALTER TABLE public.xiaochenguang_reflections
  DROP CONSTRAINT IF EXISTS reflections_confidence_score_range;
ALTER TABLE public.xiaochenguang_reflections
  DROP CONSTRAINT IF EXISTS xiaochenguang_reflections_reflection_key_key;

-- ---------------------------------------------------------------------------
-- 3) Relax NOT NULL constraints added by the forward migration.
--    Columns and backfilled owner values are KEPT (data safety). The legacy
--    owner backfill (NULL → default_user / xiaochenguang_v1) cannot be
--    automatically reverted to NULL and is intentionally preserved.
-- ---------------------------------------------------------------------------
ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN reflection_key DROP NOT NULL;
ALTER TABLE public.xiaochenguang_memories
  ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE public.xiaochenguang_memories
  ALTER COLUMN ai_id DROP NOT NULL;
ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN ai_id DROP NOT NULL;

-- ---------------------------------------------------------------------------
-- 4) Drop indexes created by the forward migration (names must match forward)
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS public.idx_memories_user_ai_created;
DROP INDEX IF EXISTS public.idx_memories_conversation_created;
DROP INDEX IF EXISTS public.idx_emotional_states_user_created;
DROP INDEX IF EXISTS public.idx_reflections_conversation_created;
DROP INDEX IF EXISTS public.idx_reflections_user_ai_created;
DROP INDEX IF EXISTS public.idx_user_preferences_user_id;
DROP INDEX IF EXISTS public.idx_user_preferences_conversation_id;

-- ---------------------------------------------------------------------------
-- 5) user_preferences: keep table by default to avoid destroying new
--    preference data. To fully remove (operator decision):
--    DROP TABLE IF EXISTS public.user_preferences;
--    Forward did NOT enable RLS, so there is no RLS state to revert.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 6) Additive columns are kept by default. Explicit drops left commented so an
--    operator can decide (dropping loses generated reflection_key / scores):
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS reflection_key;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS confidence_score;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS ai_id;
-- ALTER TABLE public.xiaochenguang_reflections DROP COLUMN IF EXISTS contract_version;
-- ALTER TABLE public.xiaochenguang_memories DROP COLUMN IF EXISTS ai_id;

-- NOTE: Do not drop emotional_states.dominant_emotion / created_at — those are
-- the new schema baseline, not Task006 inventions.

COMMIT;
