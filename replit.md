# XiaoChenGuang AI Soul System

## Overview

The XiaoChenGuang AI Soul System is a web-based AI companion platform featuring advanced memory management, emotion detection, and personality learning capabilities. Originally developed as a Telegram bot, the system has been migrated to a modern web architecture using Vue 3 for the frontend and FastAPI for the backend, with Supabase PostgreSQL as the persistent data store.

The system creates personalized AI interactions through vector-based memory retrieval, real-time emotion analysis, and dynamic personality adaptation based on conversation history.

## Recent Changes

**Phase 2 - Modular Architecture Completed (2025-10-19)**

✅ **Memory Module (Token-based Storage)**:
- Implemented complete Token化 architecture using tiktoken library
- Built 5-layer memory system: IO Contract, Tokenizer, Redis Interface, Supabase Interface, Core
- Redis short-term cache (2-day TTL) + Supabase long-term persistence
- Batch flush worker for optimized database writes
- UTF-8 bytes fallback when tiktoken unavailable

✅ **Reflection Module (反推果因法則)**:
- Upgraded to "genius-level" causal retrospection engine
- Multi-layer analysis: L1 (direct), L2 (indirect), L3 (systemic causes)
- 5 causal pattern library categories
- Generates 12+ concrete improvement suggestions per reflection
- Meta-cognitive layer evaluating reflection quality itself

✅ **Module Integration**:
- Memory-Reflection linkage: conversation → reflection → write-back loop
- API backward compatibility: /api/chat now includes optional `reflection` field
- Error isolation: module failures don't break main chat flow
- Health check endpoints: /api/health/modules, /api/health/detailed

✅ **Documentation**:
- Complete test report: logs/module_test_results.md (100% pass rate)
- Core architecture summary: backend/core_summary.md
- Integration tests: test_modules_integration.py (4/5 modules active)

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology**: Vue 3 + Vite (Port 5000)

The frontend is a single-page application built with Vue 3 and bundled using Vite. It provides:

- Real-time chat interface with message history
- Memory visualization and listing
- Emotional state display
- File upload capabilities
- System health check dashboard

**Design Pattern**: Component-based architecture with Vue Router for navigation. The application uses a proxy configuration to forward API requests from `/api/*` to the backend server at `localhost:8000`, enabling seamless local development.

**Key Components**:
- `ChatInterface.vue`: Main conversation interface
- `StatusPage.vue`: System health monitoring dashboard
- Router-based navigation for clean URL structure

### Backend Architecture

**Technology**: FastAPI (Python 3.11, Port 8000)

The backend follows a modular router-based architecture with clear separation of concerns:

**Core Routers**:
- `chat_router.py`: Handles conversation processing and AI response generation
- `memory_router.py`: Manages memory retrieval and emotional state queries
- `openai_handler.py`: OpenAI API integration and response generation
- `file_upload.py`: File upload to Supabase Storage
- `healthcheck_router.py`: System health monitoring endpoints

**Modular System Design**:

The system implements a **"LEGO-style" modular architecture** through the `CoreController` class, allowing modules to be dynamically loaded, unloaded, and configured independently:

1. **Base Module Interface** (`base_module.py`): All modules inherit from `BaseModule` abstract class, implementing:
   - `load()`: Module initialization
   - `unload()`: Module cleanup
   - `process()`: Core business logic
   - `health_check()`: Module status verification

2. **Five Core Modules**:
   - **Memory Module** (`memory_module/`): Short-term (Redis mock) and long-term (Supabase) memory management, text tokenization using tiktoken
   - **Reflection Module** (`reflection_module/`): Self-awareness and response quality analysis using "causal reflection" methodology
   - **Knowledge Hub** (`knowledge_hub/`): Global shared knowledge layer with structured storage and semantic search
   - **Behavior Module** (`behavior_module/`): Dynamic personality trait adjustment based on reflection results
   - **FineTune Module** (`finetune_module/`): Experimental QLoRA-based model fine-tuning (currently disabled)

3. **Module Configuration**: Each module has a `config.json` defining:
   - Enable/disable status
   - Dependencies on other modules
   - Health check endpoints
   - Custom settings

4. **Core Controller** (`core_controller.py`): Central module manager handling:
   - Module registration and discovery
   - Dependency resolution
   - Inter-module communication
   - Health monitoring across all modules

**AI Processing Pipeline**:

1. **Emotion Detection** (`modules/emotion_detector.py`): Analyzes user messages across 9 emotion types (joy, sadness, anger, fear, love, tired, confused, grateful, neutral) with intensity scoring and keyword pattern matching

2. **Personality Engine** (`modules/personality_engine.py`): Maintains dynamic personality traits (curiosity, empathy, humor, technical_depth) that evolve based on conversation history

3. **Memory System** (`modules/memory_system.py`): 
   - Generates embeddings via OpenAI's `text-embedding-3-small` model
   - Stores conversations with importance scoring
   - Retrieves relevant memories using vector similarity
   - Tracks access counts and memory importance

4. **Prompt Engineering** (`backend/prompt_engine.py`): Constructs context-aware prompts by combining:
   - AI personality profile from `profile/user_profile.json`
   - Retrieved memories
   - Conversation history
   - Current emotion analysis
   - Response style adjustments

**Rationale**: The modular architecture allows for independent development, testing, and scaling of different AI capabilities. Modules can be enabled/disabled without affecting core functionality, and new modules can be added without modifying existing code.

### Data Storage Solutions

**Primary Database**: Supabase PostgreSQL with pgvector extension

**Key Tables**:

1. **xiaochenguang_memories**: Stores conversation records with vector embeddings
   - Fields: id, conversation_id, user_message, assistant_message, embedding (VECTOR(1536)), importance_score, access_count, memory_type, platform, created_at
   - Supports semantic search through pgvector similarity queries

2. **emotional_states**: Tracks emotional analysis history
   - Fields: user_id, emotion, intensity, confidence, context, timestamp

3. **user_preferences**: Stores personality profiles and user-specific configurations

4. **knowledge_graph**: Semantic relationship mapping (planned for knowledge hub module)

5. **memory_statistics**: Analytics data for memory system optimization

**Caching Layer**: Redis Mock (`backend/redis_mock.py`)

- Implements in-memory cache with TTL support
- Provides Redis-compatible interface for future migration to Upstash Redis
- Used for 24-hour short-term memory retention
- Thread-safe with locking mechanisms

**Rationale**: The combination of vector-enabled PostgreSQL and Redis caching balances long-term persistence with fast access to recent interactions. The mock Redis allows development without external dependencies while maintaining migration path flexibility.

### Authentication and Authorization

**Current State**: No authentication system implemented

The system currently operates without user authentication. All conversations are tracked via `conversation_id` and optional `user_id` parameters, but there is no login requirement or session management.

**Rationale**: The initial phase focuses on core AI functionality. Authentication can be added later without significant architectural changes as the API already supports user identification through conversation and user IDs.

## External Dependencies

### Third-Party APIs

1. **OpenAI API**:
   - Models: GPT-4o-mini (chat completion), text-embedding-3-small (embeddings)
   - Environment variables: `OPENAI_API_KEY`, `OPENAI_ORG_ID` (optional), `OPENAI_PROJECT_ID` (optional)
   - Used for: AI response generation, semantic memory embeddings

2. **Supabase**:
   - Services: PostgreSQL database with pgvector, Storage (file uploads)
   - Environment variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_MEMORIES_TABLE`
   - Used for: Persistent storage, vector similarity search, file hosting

### Python Packages

Core dependencies (from `requirements.txt`):
- `fastapi>=0.109.0`: Web framework
- `uvicorn[standard]>=0.27.0`: ASGI server
- `openai>=1.35.0`: OpenAI SDK
- `supabase>=2.3.4`: Supabase client
- `tiktoken>=0.5.0`: Token counting for GPT models
- `redis>=5.0.0`: Redis client (currently using mock)
- `python-multipart>=0.0.6`: File upload support
- `pydantic>=2.5.3`: Data validation
- `python-dotenv>=1.0.0`: Environment configuration

### Frontend Dependencies

From `frontend/package.json`:
- `vue@^3.3.11`: Frontend framework
- `vue-router@^4.5.1`: Client-side routing
- `vite@^5.0.11`: Build tool and dev server
- `axios@^1.6.5`: HTTP client
- `@vitejs/plugin-vue@^5.0.2`: Vite Vue plugin

### Deployment Infrastructure

**Current Setup**:
- Development: Local (FastAPI on 8000, Vite on 5000)
- Production (configured): Cloudflare Pages (frontend), custom domain with CORS configuration

**CORS Configuration**: Backend allows requests from:
- `https://ai.dreamground.net` (Cloudflare Pages frontend)
- `https://ai2.dreamground.net` (backend domain)
- `https://*.pages.dev` (Cloudflare default subdomains)

**Future Considerations**: The modular architecture supports containerization (Docker) and serverless deployment options without significant refactoring.