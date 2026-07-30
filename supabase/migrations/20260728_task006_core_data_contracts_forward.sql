-- Task 006 — Core data contracts (FORWARD) v1.1 (PR18 review fixes)
-- Idempotent / additive. NEVER apply to production without Gate C.
-- contract_version: task006_v1

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1) emotional_states (canonical new schema)
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

ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS dominant_emotion TEXT;
ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS intensity DOUBLE PRECISION;
ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;
ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS context TEXT;
ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.emotional_states ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Bounds: intensity/confidence in [0,1] when present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'emotional_states_intensity_range'
  ) THEN
    ALTER TABLE public.emotional_states
      ADD CONSTRAINT emotional_states_intensity_range
      CHECK (intensity IS NULL OR (intensity >= 0 AND intensity <= 1));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'emotional_states_confidence_range'
  ) THEN
    ALTER TABLE public.emotional_states
      ADD CONSTRAINT emotional_states_confidence_range
      CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_emotional_states_user_created
  ON public.emotional_states (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 2) xiaochenguang_reflections
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

ALTER TABLE public.xiaochenguang_reflections ADD COLUMN IF NOT EXISTS reflection_key UUID;
ALTER TABLE public.xiaochenguang_reflections ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION DEFAULT 0.0;
ALTER TABLE public.xiaochenguang_reflections ADD COLUMN IF NOT EXISTS ai_id TEXT DEFAULT 'xiaochenguang_v1';
ALTER TABLE public.xiaochenguang_reflections ADD COLUMN IF NOT EXISTS contract_version TEXT DEFAULT 'task006_v1';

UPDATE public.xiaochenguang_reflections
SET reflection_key = gen_random_uuid()
WHERE reflection_key IS NULL;

ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN reflection_key SET DEFAULT gen_random_uuid();

-- Enforce NOT NULL (ADR alignment)
ALTER TABLE public.xiaochenguang_reflections
  ALTER COLUMN reflection_key SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'xiaochenguang_reflections_reflection_key_key'
  ) THEN
    ALTER TABLE public.xiaochenguang_reflections
      ADD CONSTRAINT xiaochenguang_reflections_reflection_key_key UNIQUE (reflection_key);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'reflections_confidence_score_range'
  ) THEN
    ALTER TABLE public.xiaochenguang_reflections
      ADD CONSTRAINT reflections_confidence_score_range
      CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1));
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Reflections legacy owner backfill (PR18 review round 3, P1-B)
-- Same class of fix as memories: existing reflections with NULL/empty user_id
-- or ai_id are the known single-user / single-AI legacy owner — NOT readable by
-- all. Set defaults, backfill BOTH user_id AND ai_id, then guarded NOT NULL.
-- ---------------------------------------------------------------------------
ALTER TABLE public.xiaochenguang_reflections ALTER COLUMN user_id SET DEFAULT 'default_user';
ALTER TABLE public.xiaochenguang_reflections ALTER COLUMN ai_id   SET DEFAULT 'xiaochenguang_v1';

UPDATE public.xiaochenguang_reflections
  SET user_id = 'default_user'
  WHERE user_id IS NULL OR btrim(user_id) = '';
UPDATE public.xiaochenguang_reflections
  SET ai_id = 'xiaochenguang_v1'
  WHERE ai_id IS NULL OR btrim(ai_id) = '';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.xiaochenguang_reflections WHERE user_id IS NULL) THEN
    ALTER TABLE public.xiaochenguang_reflections ALTER COLUMN user_id SET NOT NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.xiaochenguang_reflections WHERE ai_id IS NULL) THEN
    ALTER TABLE public.xiaochenguang_reflections ALTER COLUMN ai_id SET NOT NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_reflections_conversation_created
  ON public.xiaochenguang_reflections (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reflections_user_ai_created
  ON public.xiaochenguang_reflections (user_id, ai_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3) user_preferences (Gate C C4: explicit two-layer data-plane security)
-- The backend uses an elevated key (service_role/secret) which BYPASSES RLS.
-- We do NOT rely on Supabase default Data API grants (changing in 2026): we
-- define BOTH layers explicitly below — RLS ON (no permissive policy) AND
-- table/sequence grants locked to service_role only. anon/authenticated get
-- neither rows (RLS) nor privileges (grants). No JWT/anon policy is created here.
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

-- --- user_preferences security: RLS ON + explicit table/sequence grants ------
-- (1) RLS on, with NO permissive policy → PostgREST/anon/authenticated see 0 rows.
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

-- (2) Table DML: revoke from public roles; grant only to service_role (backend).
REVOKE ALL ON TABLE public.user_preferences FROM PUBLIC;
REVOKE ALL ON TABLE public.user_preferences FROM anon;
REVOKE ALL ON TABLE public.user_preferences FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_preferences TO service_role;

-- (3) Identity sequence (BIGSERIAL id): revoke from public roles; grant to service_role.
--     Resolve the sequence name robustly (do not hard-code) and lock it down.
DO $$
DECLARE seq text := pg_get_serial_sequence('public.user_preferences', 'id');
BEGIN
  IF seq IS NOT NULL THEN
    EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC', seq);
    EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM anon', seq);
    EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM authenticated', seq);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO service_role', seq);
  END IF;
END $$;
-- No anon/authenticated policy is created (intentionally). service_role bypasses RLS.

-- ---------------------------------------------------------------------------
-- 4) memories indexes
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

ALTER TABLE public.xiaochenguang_memories ADD COLUMN IF NOT EXISTS user_id TEXT DEFAULT 'default_user';
ALTER TABLE public.xiaochenguang_memories ADD COLUMN IF NOT EXISTS ai_id TEXT DEFAULT 'xiaochenguang_v1';

-- ---------------------------------------------------------------------------
-- Legacy owner backfill (PR18 review round 2, P1)
-- ADD COLUMN IF NOT EXISTS does NOT set a default or backfill when the column
-- ALREADY exists (the new schema already has user_id/ai_id). Without this,
-- strict isolation would make existing single-user / single-AI memories with
-- NULL owner suddenly unretrievable. This project historically ran as ONE user
-- and ONE AI, so a NULL owner is that known legacy owner — NOT "readable by all".
-- ---------------------------------------------------------------------------
-- 1) Ensure the column defaults exist even when columns pre-existed.
ALTER TABLE public.xiaochenguang_memories ALTER COLUMN user_id SET DEFAULT 'default_user';
ALTER TABLE public.xiaochenguang_memories ALTER COLUMN ai_id  SET DEFAULT 'xiaochenguang_v1';

-- 2) Backfill existing NULL/empty owners to the known legacy owner.
UPDATE public.xiaochenguang_memories
  SET user_id = 'default_user'
  WHERE user_id IS NULL OR btrim(user_id) = '';
UPDATE public.xiaochenguang_memories
  SET ai_id = 'xiaochenguang_v1'
  WHERE ai_id IS NULL OR btrim(ai_id) = '';

-- 3) Enforce NOT NULL ONLY after backfill leaves zero NULLs (guarded — if any
--    NULL somehow remains, we DO NOT force NOT NULL; the row stays quarantined
--    as nullable rather than failing the migration or hiding data silently).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.xiaochenguang_memories WHERE user_id IS NULL) THEN
    ALTER TABLE public.xiaochenguang_memories ALTER COLUMN user_id SET NOT NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.xiaochenguang_memories WHERE ai_id IS NULL) THEN
    ALTER TABLE public.xiaochenguang_memories ALTER COLUMN ai_id SET NOT NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_memories_user_ai_created
  ON public.xiaochenguang_memories (user_id, ai_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_conversation_created
  ON public.xiaochenguang_memories (conversation_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5) match_memories_v2 — fail-closed owner filters + cosine + conservative floor
-- Scope decision (product): long-term semantic memory is **same user_id + ai_id
-- across conversations**. filter_conversation_id is optional narrowing only.
-- filter_user_id and filter_ai_id are REQUIRED (NULL → empty result set).
-- default min_similarity 0.55 (calibrate upward with real samples at Gate C).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_memories_v2(
  query_embedding vector(1536),
  match_count integer DEFAULT 3,
  filter_conversation_id text DEFAULT NULL,
  filter_user_id text DEFAULT NULL,
  filter_ai_id text DEFAULT NULL,
  min_similarity double precision DEFAULT 0.55
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
    -- fail-closed: missing owner filters yield zero rows
    AND filter_user_id IS NOT NULL
    AND btrim(filter_user_id) <> ''
    AND filter_ai_id IS NOT NULL
    AND btrim(filter_ai_id) <> ''
    AND m.user_id = filter_user_id
    AND m.ai_id = filter_ai_id
    AND (filter_conversation_id IS NULL OR m.conversation_id = filter_conversation_id)
    AND (1 - (m.embedding <=> query_embedding)) >= COALESCE(min_similarity, 0.55)
  ORDER BY m.embedding <=> query_embedding
  LIMIT GREATEST(COALESCE(match_count, 3), 1);
$$;

COMMENT ON FUNCTION public.match_memories_v2 IS
  'task006_v1: cosine match; requires filter_user_id+filter_ai_id; optional conversation; default min_sim 0.55';

-- ---------------------------------------------------------------------------
-- 6) EXPAND-ONLY grants for the NEW v2 RPC (Gate C)
--
-- IMPORTANT (Gate C, expand-only): this migration MUST NOT create, replace,
-- revoke, grant, drop, or otherwise alter the legacy
-- public.match_memories(vector, integer, text). The current production baseline
-- has NO custom public RPC; if an UNKNOWN legacy match_memories exists on the
-- real target, its body cannot be safely restored, so we never touch it here.
-- Legacy retirement/cleanup is a SEPARATE, later, environment-specific task
-- (see C7), performed only after the new contract is verified stable.
--
-- Only the NEW, additive match_memories_v2 is locked down to service_role so
-- that anon/authenticated cannot run an unscoped memory search. This does not
-- introduce any public bypass.
-- ---------------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.match_memories_v2(vector, integer, text, text, text, double precision)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_memories_v2(vector, integer, text, text, text, double precision)
  TO service_role;

COMMIT;
