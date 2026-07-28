-- Task 006 — Core data contracts (FORWARD)
-- Idempotent / additive only. Safe on new exported schema and empty schema.
-- DO NOT apply to production without Gate C approval.
-- contract_version: task006_v1

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1) emotional_states: ensure canonical columns (new schema already has them)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.emotional_states (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  dominant_emotion TEXT,
  intensity DOUBLE PRECISION,
  confidence DOUBLE PRECISION,
  context TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS dominant_emotion TEXT;
ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS intensity DOUBLE PRECISION;
ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;
ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS context TEXT;
ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.emotional_states
  ADD COLUMN IF NOT EXISTS user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_emotional_states_user_created
  ON public.emotional_states (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 2) xiaochenguang_reflections: keep bigint id; add reflection_key + confidence
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.xiaochenguang_reflections (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT,
  user_id TEXT,
  reflection_content TEXT,
  analysis_tags JSONB,
  reflection_level JSONB,
  personality_embedding JSONB,
  related_message_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.xiaochenguang_reflections
  ADD COLUMN IF NOT EXISTS reflection_key UUID;
ALTER TABLE public.xiaochenguang_reflections
  ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION DEFAULT 0.0;
ALTER TABLE public.xiaochenguang_reflections
  ADD COLUMN IF NOT EXISTS ai_id TEXT DEFAULT 'xiaochenguang_v1';
ALTER TABLE public.xiaochenguang_reflections
  ADD COLUMN IF NOT EXISTS contract_version TEXT DEFAULT 'task006_v1';

-- Backfill reflection_key for existing rows
UPDATE public.xiaochenguang_reflections
SET reflection_key = gen_random_uuid()
WHERE reflection_key IS NULL;

ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN reflection_key SET DEFAULT gen_random_uuid();

-- Unique only when non-null during transition; then enforce NOT NULL via new inserts default
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'xiaochenguang_reflections_reflection_key_key'
  ) THEN
    ALTER TABLE public.xiaochenguang_reflections
      ADD CONSTRAINT xiaochenguang_reflections_reflection_key_key UNIQUE (reflection_key);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_reflections_conversation_created
  ON public.xiaochenguang_reflections (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reflections_user_created
  ON public.xiaochenguang_reflections (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3) user_preferences (canonical from active call sites)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_preferences (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  conversation_id TEXT,
  personality_profile JSONB,
  voice_settings JSONB,
  language TEXT,
  timezone TEXT,
  notification_enabled BOOLEAN DEFAULT TRUE,
  personality_preset TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_preferences_user_id
  ON public.user_preferences (user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_conversation_id
  ON public.user_preferences (conversation_id);

-- RLS note: service-role backend is expected for server paths.
-- Policy proposals are documented in ADR; not invented here.
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 4) memories table: ensure ai_id / user_id exist (new schema already has them)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.xiaochenguang_memories (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT,
  user_id TEXT DEFAULT 'default_user',
  user_message TEXT,
  assistant_message TEXT,
  memory_type TEXT DEFAULT 'conversation',
  platform TEXT DEFAULT 'Web',
  document_content TEXT,
  embedding vector(1536),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  access_count INTEGER DEFAULT 1,
  importance_score DOUBLE PRECISION DEFAULT 0.5,
  file_name TEXT,
  ai_id TEXT DEFAULT 'xiaochenguang_v1',
  message_type TEXT DEFAULT 'text'
);

ALTER TABLE public.xiaochenguang_memories
  ADD COLUMN IF NOT EXISTS user_id TEXT DEFAULT 'default_user';
ALTER TABLE public.xiaochenguang_memories
  ADD COLUMN IF NOT EXISTS ai_id TEXT DEFAULT 'xiaochenguang_v1';

CREATE INDEX IF NOT EXISTS idx_memories_user_ai_created
  ON public.xiaochenguang_memories (user_id, ai_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_conversation_created
  ON public.xiaochenguang_memories (conversation_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5) match_memories_v2 — cosine distance, explicit filters, isolation
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_memories_v2(
  query_embedding vector(1536),
  match_count integer DEFAULT 3,
  filter_conversation_id text DEFAULT NULL,
  filter_user_id text DEFAULT NULL,
  filter_ai_id text DEFAULT NULL,
  min_similarity double precision DEFAULT 0.0
)
RETURNS TABLE (
  user_message text,
  assistant_message text,
  created_at timestamptz,
  similarity double precision,
  conversation_id text,
  user_id text,
  ai_id text
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    m.user_message,
    m.assistant_message,
    m.created_at,
    (1 - (m.embedding <=> query_embedding))::double precision AS similarity,
    m.conversation_id,
    m.user_id,
    m.ai_id
  FROM public.xiaochenguang_memories m
  WHERE m.embedding IS NOT NULL
    AND m.memory_type = 'conversation'
    AND (filter_conversation_id IS NULL OR m.conversation_id = filter_conversation_id)
    AND (
      filter_user_id IS NULL
      OR filter_user_id = ''
      OR filter_user_id = 'default_user'
      OR m.user_id = filter_user_id
    )
    AND (
      filter_ai_id IS NULL
      OR filter_ai_id = ''
      OR m.ai_id = filter_ai_id
    )
    AND (1 - (m.embedding <=> query_embedding)) >= min_similarity
  ORDER BY m.embedding <=> query_embedding
  LIMIT GREATEST(COALESCE(match_count, 3), 1);
$$;

COMMENT ON FUNCTION public.match_memories_v2 IS
  'Task006 v1 cosine memory match with optional conversation/user/ai isolation filters';

-- ---------------------------------------------------------------------------
-- 6) Legacy-compatible match_memories wrapper (conversation-scoped only)
--     Prefer application using match_memories_v2. Wrapper kept for rollout.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_memories(
  query_embedding vector,
  match_count integer,
  conversation_id text
)
RETURNS TABLE (
  user_message text,
  assistant_message text,
  created_at timestamptz,
  similarity double precision
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    v.user_message,
    v.assistant_message,
    v.created_at,
    v.similarity
  FROM public.match_memories_v2(
    query_embedding::vector(1536),
    match_count,
    conversation_id,
    NULL,
    NULL,
    0.0
  ) AS v;
$$;

GRANT EXECUTE ON FUNCTION public.match_memories_v2(
  vector, integer, text, text, text, double precision
) TO anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.match_memories(
  vector, integer, text
) TO anon, authenticated, service_role;

COMMIT;
