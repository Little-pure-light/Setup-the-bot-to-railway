-- Task 006 — isolated pgvector contract smoke test (CI only)
-- Runs AFTER forward migration (applied twice for idempotency) on a DISPOSABLE
-- pgvector database. Proves match_memories_v2 isolation + reflection owner
-- constraints. Any failed assertion raises an exception and fails the CI job.
-- NEVER run against production Supabase.

\set ON_ERROR_STOP on

-- 1536-dim constant embedding literal for all rows (cosine distance = 0 → sim 1.0)
-- Build once as a helper expression.

-- Seed two users, two AIs, two conversations
INSERT INTO public.xiaochenguang_memories
  (conversation_id, user_id, ai_id, user_message, assistant_message, memory_type, embedding)
VALUES
  ('c1', 'userA', 'aiA', 'A-aiA-c1', 'r', 'conversation',
     ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector),
  ('c2', 'userA', 'aiA', 'A-aiA-c2', 'r', 'conversation',
     ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector),
  ('c1', 'userB', 'aiA', 'B-aiA-c1', 'r', 'conversation',
     ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector),
  ('c1', 'userA', 'aiB', 'A-aiB-c1', 'r', 'conversation',
     ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector);

DO $$
DECLARE
  n int;
  q vector(1536);
BEGIN
  q := ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector;

  -- (a) userA + aiA recalled ACROSS conversations (c1 + c2) = 2 rows
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, NULL, 'userA', 'aiA', 0.0);
  IF n <> 2 THEN RAISE EXCEPTION 'cross-conversation recall failed: expected 2, got %', n; END IF;

  -- (b) no cross-USER leak (querying userA must never surface userB)
  SELECT count(*) INTO n
    FROM public.match_memories_v2(q, 50, NULL, 'userA', 'aiA', 0.0)
    WHERE user_id <> 'userA';
  IF n <> 0 THEN RAISE EXCEPTION 'cross-user leak: %', n; END IF;

  -- (c) no cross-AI leak (aiA query must never surface aiB)
  SELECT count(*) INTO n
    FROM public.match_memories_v2(q, 50, NULL, 'userA', 'aiA', 0.0)
    WHERE ai_id <> 'aiA';
  IF n <> 0 THEN RAISE EXCEPTION 'cross-ai leak: %', n; END IF;

  -- (d) userB isolated to its own single row
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, NULL, 'userB', 'aiA', 0.0);
  IF n <> 1 THEN RAISE EXCEPTION 'userB isolation failed: expected 1, got %', n; END IF;

  -- (e) fail-closed: missing user_id → zero rows
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, NULL, NULL, 'aiA', 0.0);
  IF n <> 0 THEN RAISE EXCEPTION 'missing user_id must yield 0, got %', n; END IF;

  -- (f) fail-closed: missing ai_id → zero rows
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, NULL, 'userA', NULL, 0.0);
  IF n <> 0 THEN RAISE EXCEPTION 'missing ai_id must yield 0, got %', n; END IF;

  -- (g) fail-closed: empty-string owner → zero rows
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, NULL, '', 'aiA', 0.0);
  IF n <> 0 THEN RAISE EXCEPTION 'empty user_id must yield 0, got %', n; END IF;

  -- (h) conversation narrowing works (c1 only) = 1 row
  SELECT count(*) INTO n FROM public.match_memories_v2(q, 50, 'c1', 'userA', 'aiA', 0.0);
  IF n <> 1 THEN RAISE EXCEPTION 'conversation narrowing failed: expected 1, got %', n; END IF;

  RAISE NOTICE 'match_memories_v2 isolation smoke: PASSED';
END $$;

-- Retired legacy match_memories must raise (no public bypass)
DO $$
DECLARE ok boolean := false;
BEGIN
  BEGIN
    PERFORM * FROM public.match_memories(
      ('[' || array_to_string(array_fill(0.1::float8, ARRAY[1536]), ',') || ']')::vector, 3, 'c1');
  EXCEPTION WHEN others THEN
    ok := true;
  END;
  IF NOT ok THEN RAISE EXCEPTION 'legacy match_memories should be retired/raise'; END IF;
  RAISE NOTICE 'legacy match_memories retired: PASSED';
END $$;

-- Reflection owner columns exist AND are NOT NULL after migration (guarded on empty table)
DO $$
DECLARE c int;
BEGIN
  SELECT count(*) INTO c FROM information_schema.columns
    WHERE table_schema='public' AND table_name='xiaochenguang_reflections'
      AND column_name IN ('user_id','ai_id');
  IF c <> 2 THEN RAISE EXCEPTION 'reflections owner columns missing (got %)', c; END IF;

  SELECT count(*) INTO c FROM information_schema.columns
    WHERE table_schema='public' AND table_name='xiaochenguang_reflections'
      AND column_name IN ('user_id','ai_id') AND is_nullable='NO';
  IF c <> 2 THEN RAISE EXCEPTION 'reflections user_id/ai_id must be NOT NULL after migration (got %)', c; END IF;

  -- confidence_score range constraint exists
  SELECT count(*) INTO c FROM pg_constraint WHERE conname = 'reflections_confidence_score_range';
  IF c <> 1 THEN RAISE EXCEPTION 'reflections confidence range constraint missing'; END IF;

  RAISE NOTICE 'reflections owner constraint smoke: PASSED';
END $$;

SELECT 'TASK006_PGVECTOR_SMOKE_PASSED' AS result;
