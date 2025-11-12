# XiaoChenGuang AI System

## Overview

XiaoChenGuang (小宸光) is a modular AI conversation system featuring advanced memory management, emotional intelligence, and self-reflection capabilities. The system migrated from a Telegram bot to a modern web application, providing personalized AI companionship with persistent memory across conversations.

**Core Features:**
- Multi-layered memory architecture (Redis for short-term, Supabase for long-term storage)
- Emotional detection and adaptive response styling
- Self-reflection module using "Causal Retrospection" methodology
- Dynamic personality adjustment based on interaction patterns
- File upload and intelligent content analysis
- IPFS integration for conversation archiving

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Technology Stack

**Frontend:**
- Vue 3 with Vite build system
- Axios for HTTP requests
- Vue Router for navigation
- Deployed on Cloudflare Pages with HMR support

**Backend:**
- FastAPI (Python) for REST API
- OpenAI GPT-4o-mini for AI responses
- Modular architecture with pluggable components

**Data Layer:**
- Redis (Upstash) for short-term memory caching (24-48 hour TTL)
- Supabase (PostgreSQL) for permanent storage with pgvector for semantic search
- Pinecone for reflection embeddings and similarity retrieval

### Architectural Patterns

**1. Modular Plugin System**
The application uses a base module pattern where all functional modules inherit from `BaseModule`. Each module is self-contained with its own:
- Configuration file (`config.json`)
- Load/unload lifecycle methods
- Health check endpoints
- Independent processing logic

Key modules include:
- **Memory Module**: Token-based conversation storage with dual-layer caching
- **Reflection Module**: Self-analysis using "reverse causation" methodology
- **Knowledge Hub**: Structured knowledge indexing and retrieval
- **Behavior Module**: Dynamic personality vector adjustment
- **FineTune Module**: Experimental QLoRA-based model tuning (disabled by default)

**2. Memory Architecture**

The system implements a three-tier memory strategy:

- **Tier 1 - Redis Cache**: Stores recent conversations with automatic expiration. Uses `conversations:{conversation_id}` keys with JSON-serialized message objects containing user messages, assistant responses, reflections, and timestamps.

- **Tier 2 - Supabase Database**: Permanent storage in `xiaochenguang_memories` table with fields for conversation tracking, token counts, importance scoring, and access frequency. Supports semantic search via embedding vectors.

- **Tier 3 - Pinecone Vector Store**: Specialized storage for reflection embeddings enabling similarity-based retrieval of past insights.

**3. Prompt Engineering Pipeline**

The `PromptEngine` class orchestrates multi-factor prompt construction:
- Emotion analysis via `EnhancedEmotionDetector` (9 emotion categories)
- Personality vector integration from `PersonalityEngine`
- Memory recall from conversation history
- File content injection when documents are uploaded
- Dynamic tone adjustment based on emotional context

**4. Token Management**

Uses `tiktoken` library (cl100k_base encoding) for accurate token counting with UTF-8 byte fallback. Token data is stored alongside messages to track API usage and enable intelligent context window management.

**5. Reflection System**

Implements "Causal Retrospection" - asking "what causes led to this response" rather than "why did I respond this way". Features:
- Multi-level causal analysis (direct → indirect → systemic causes)
- Quality scoring based on response length, keyword alignment, and emotional intensity
- Automatic personality adjustment triggers based on reflection insights
- Persistent reflection history with CID (Content Identifier) tracking

**6. File Processing Pipeline**

Supports multiple file types through type-specific parsers:
- Text files (.txt, .md, .json): Direct text extraction
- Documents (.pdf, .docx): Text extraction via specialized libraries
- Images (.png, .jpg, .jpeg): OpenAI Vision API for content description

Uploaded files are:
1. Parsed and summarized immediately
2. Stored in Redis with conversation context
3. Content injected into prompt context for AI awareness
4. Auto-expired after 2 days

**7. Background Job System**

Implements async workers for non-blocking operations:
- `MemoryFlushWorker`: Batches Redis data to Supabase every 5 minutes with retry logic
- Graceful shutdown handling ensures final flush on application termination

## External Dependencies

### Cloud Services

**Supabase** (PostgreSQL + Storage):
- Tables: `xiaochenguang_memories`, `xiaochenguang_reflections`, `emotional_states`, `user_preferences`
- Enables pgvector extension for semantic similarity search
- Stores conversation embeddings generated via OpenAI `text-embedding-3-small` model
- Environment variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`

**Redis (Upstash)**:
- Cloud-hosted Redis with SSL support
- Configured via `REDIS_ENDPOINT` and `REDIS_TOKEN` or `REDIS_URL`
- Falls back to in-memory mock if unavailable
- Used for conversation caching and pending memory flush queue

**Pinecone**:
- Serverless vector database (AWS us-east-1 region)
- Index: `xiaochenguang-reflections-v2` (1536 dimensions)
- Stores reflection embeddings for semantic retrieval
- Environment variables: `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_ENVIRONMENT`

**OpenAI API**:
- Primary model: `gpt-4o-mini` for conversation generation
- Embedding model: `text-embedding-3-small` (1536 dimensions)
- Vision API for image content analysis
- Environment variables: `OPENAI_API_KEY`, `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`

**Pinata (IPFS)**:
- Decentralized storage for conversation archives
- Generates CID (Content Identifier) for immutable records
- Environment variable: `PINATA_JWT`

### Python Libraries

Core dependencies (see `requirements.txt`):
- `fastapi` + `uvicorn`: Web framework and ASGI server
- `openai>=1.35.0`: OpenAI API client
- `supabase>=2.3.4`: Supabase client
- `redis>=5.0.0`: Redis interface
- `pinecone`: Vector database client
- `tiktoken>=0.5.0`: Token counting
- `pdfplumber`, `python-docx`: Document parsing
- `aiofiles>=23.2.1`: Async file operations

### Deployment Configuration

**CORS Settings**: Configured for Cloudflare Pages, Replit, and localhost origins

**Environment Detection**: Supports both development (Replit) and production (Cloudflare Tunnel) deployments with automatic API base URL configuration

**Port Configuration**:
- Backend: Port 8000 (FastAPI)
- Frontend: Port 5000 (Vite dev server with proxy to backend)