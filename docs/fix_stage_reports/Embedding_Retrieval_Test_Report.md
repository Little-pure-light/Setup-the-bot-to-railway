# Embedding & Retrieval Test Report

## Write path

Typed memory insert (`MemoryManager._insert_typed_record`):

- Uses `EMBEDDING_MODEL` (default `text-embedding-3-small`)
- Sets `embedding_status` in document meta: `ready` | `failed` | `unavailable`
- Embedding failure **does not** drop the memory row

## Rank path

Score blend:

- 40% vector similarity
- 20% memory_type match
- 15% importance
- 15% recency
- 10% graph relation confidence

Keyword fallback retained; item `source` = `typed_keyword_fallback` and result `fallback_used=true`.

## Isolation

Typed fetch filters `user_id`; cross-user rows excluded.

## Tests

- embedding ready on save
- embedding timeout → row kept, status failed
- identity/semantic intent types
- user isolation
