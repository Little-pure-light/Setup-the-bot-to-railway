# XiaoChenGuang AI Soul System

## Overview

XiaoChenGuang (小宸光) is an AI companion system with personality learning, emotional intelligence, and memory capabilities. Originally a Telegram bot, it has been migrated to a web-based architecture featuring:

- **Intelligent Memory**: Vector-based long-term memory storage and retrieval using pgvector
- **Emotional Detection**: 9-emotion classification system with sentiment analysis
- **Dynamic Personality**: AI personality traits that evolve based on interactions
- **Reflection System**: Self-aware improvement mechanism using "causal retrospection"
- **Modular Architecture**: Phase 2 design with 5 core modules (Memory, Reflection, Knowledge Hub, Behavior, FineTune)

The system combines Vue 3 frontend with FastAPI backend, using Supabase PostgreSQL for persistence and Redis for short-term memory caching.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack**: Vue 3 + Vite (Port 5000)

The frontend is a single-page application (SPA) with:
- **ChatInterface.vue**: Main conversation interface
- **StatusPage.vue**: System health monitoring
- **ModulesMonitor.vue**: Module status dashboard
- Vue Router for navigation
- Axios for API communication

**Design Decision**: Chose Vue 3 for its reactivity system and lightweight footprint, suitable for real-time chat interfaces. Vite provides fast development builds and optimized production bundles.

### Backend Architecture

**Technology Stack**: FastAPI (Python 3.11, Port 8000)

The backend follows a modular plugin architecture with:

1. **Core Controller Pattern** (`core_controller.py`):
   - Central module registry and lifecycle manager
   - Dynamic module loading/unloading
   - Inter-module communication bus
   - Health monitoring for all modules

2. **Module System** (5 core modules):
   - **Memory Module** (Priority 1): Handles tokenization, short-term (Redis) and long-term (Supabase) storage
   - **Reflection Module** (Priority 2): Implements "causal retrospection" for self-improvement
   - **Knowledge Hub**: Global knowledge indexing and retrieval
   - **Behavior Module**: Dynamic personality vector adjustment based on reflection
   - **FineTune Module**: Experimental QLoRA-based model fine-tuning (disabled by default)

3. **Router-based API** (`*_router.py`):
   - `chat_router`: Main conversation endpoints
   - `memory_router`: Memory retrieval endpoints
   - `openai_handler`: OpenAI API integration
   - `file_upload`: File handling capabilities

**Design Rationale**: The modular architecture allows components to be enabled/disabled independently, facilitating incremental development and testing. Each module inherits from `BaseModule` and implements standard lifecycle methods (load, unload, process, health_check).

### Data Layer

**Two-tier Memory Architecture**:

1. **Short-term Memory** (Redis/Mock):
   - 2-day TTL for recent conversations
   - Batch flush mechanism to Supabase every 5 minutes
   - Reduces database write load during active conversations
   - Fallback to `RedisMock` if Redis unavailable

2. **Long-term Memory** (Supabase PostgreSQL):
   - Tables: `xiaochenguang_memories`, `emotional_states`, `user_preferences`
   - Vector embeddings using OpenAI `text-embedding-3-small`
   - Importance scoring and access count tracking
   - Platform-agnostic storage (Web/Telegram)

**Token Processing**:
- Uses `tiktoken` (cl100k_base encoding) for accurate token counting
- Fallback to UTF-8 byte counting if tiktoken unavailable
- Critical for managing OpenAI API costs and context windows

### AI Processing Pipeline

**Conversation Flow**:
```
User Input → Emotion Analysis → Memory Recall → Personality Prompt Generation → 
OpenAI GPT-4o-mini → Response → Reflection Analysis → Behavior Adjustment → 
Memory Storage (Redis + Supabase)
```

**Key Components**:

1. **Emotion Detection** (`emotion_detector.py`):
   - 9 emotion types: joy, sadness, anger, fear, love, tired, confused, grateful, neutral
   - Keyword matching + regex patterns
   - Intensity multipliers for emotional depth

2. **Personality Engine** (`personality_engine.py`):
   - 4 core traits: curiosity, empathy, humor, technical_depth
   - Loads from `user_profile.json` and Supabase
   - Dynamic adjustment via Behavior Module

3. **Soul System** (`soul.py`):
   - Character profile: Name (小宸光), Age (18), MBTI (ENFJ-A)
   - Language patterns: Catchphrases and addressing styles
   - Backstory integration for consistent personality

4. **Reflection System** (`reflection_module`):
   - "Causal Retrospection" methodology
   - Multi-level analysis: Direct → Indirect → Systemic causes
   - Generates improvement suggestions fed to Behavior Module

### Background Jobs

**Memory Flush Worker** (`memory_flush_worker.py`):
- Automated batch writes from Redis to Supabase
- 5-minute intervals with configurable batch size (100 records)
- Retry mechanism (3 attempts) with exponential backoff
- Graceful shutdown handling
- Integrated via FastAPI lifespan context manager

**Design Choice**: Background jobs prevent blocking the main API thread and optimize database writes by batching operations.

## External Dependencies

### Third-party Services

1. **OpenAI API**:
   - Model: GPT-4o-mini
   - Embeddings: text-embedding-3-small (1536 dimensions)
   - Required: `OPENAI_API_KEY`, optional `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`

2. **Supabase (PostgreSQL + Storage)**:
   - PostgreSQL with pgvector extension
   - Storage buckets for file uploads
   - Required: `SUPABASE_URL`, `SUPABASE_ANON_KEY`
   - Tables: `xiaochenguang_memories`, `emotional_states`, `user_preferences`, `xiaochenguang_reflections`

3. **Redis** (optional):
   - Short-term memory cache
   - Falls back to in-memory mock if unavailable
   - Optional: `REDIS_URL`

### Python Dependencies

Core packages (from `requirements.txt`):
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **openai**: OpenAI API client
- **supabase**: Supabase client
- **tiktoken**: Token counting
- **redis**: Redis client (optional)
- **python-multipart**: File upload handling
- **pydantic**: Data validation

### Frontend Dependencies

From `frontend/package.json`:
- **vue** (3.3.11): UI framework
- **vue-router** (4.5.1): Routing
- **axios** (1.6.5): HTTP client
- **vite** (5.0.11): Build tool
- **@vitejs/plugin-vue**: Vue 3 plugin for Vite

### Deployment Configuration

**CORS Settings**: Allows multiple origins including production domains (ai.dreamground.net, ai2.dreamground.net), Cloudflare Pages, Replit, and localhost variants.

**Environment Variables**:
- Frontend: `VITE_API_URL` for API endpoint configuration
- Backend: Uses `python-dotenv` for `.env` file loading
- Supports Replit-specific configurations (host 0.0.0.0, HMR client port 443)

### Experimental Features

**IPFS Handler** (`backend/modules/ipfs_handler.py`):
- Generates CIDv1 content identifiers
- Lightweight implementation without full IPFS node
- Reserved for future decentralized storage integration
- Currently generates SHA-256 based CIDs locally