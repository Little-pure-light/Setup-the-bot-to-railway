# XiaoChenGuang AI System

## Overview

XiaoChenGuang (小宸光) is a modular AI companion system featuring memory management, emotional intelligence, self-reflection capabilities, and personality adaptation. The system evolved from a Telegram bot into a web-based application with a Vue.js frontend and FastAPI backend.

**Core Purpose**: To provide personalized AI conversations with persistent memory, emotional awareness, and continuous self-improvement through a reflection-based learning system.

**Key Features**:
- Multi-layer memory architecture (Redis short-term + Supabase long-term)
- Emotional detection and response adaptation across 9 emotion types
- Self-reflection module using "Causal Retrospection" methodology
- Dynamic personality adjustment based on interaction patterns
- File upload support (text, documents, images)
- Conversation archiving to IPFS

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology**: Vue 3 + Vite (Port 5000)

**Structure**:
- Single-page application with Vue Router
- Components:
  - `ChatInterface.vue` - Main conversation interface
  - `StatusPage.vue` - System health monitoring
  - `ModulesMonitor.vue` - Module status dashboard
- API communication via Axios
- Environment-based API URL configuration (`VITE_API_URL`)

**Design Pattern**: Component-based architecture with reactive state management

### Backend Architecture

**Technology**: FastAPI (Python) on Port 8000

**Core Design Pattern**: Modular plugin architecture with a central controller

**Module System**:
1. **CoreController** (`backend/core_controller.py`) - Central orchestrator that:
   - Dynamically loads/unloads modules
   - Manages inter-module communication
   - Provides health check monitoring
   - Implements lifecycle management

2. **Base Module Interface** (`backend/base_module.py`) - Abstract base class requiring:
   - `load()` - Module initialization
   - `unload()` - Cleanup operations
   - `process()` - Main logic execution
   - `health_check()` - Status reporting

**Active Modules**:

1. **Memory Module** (`backend/modules/memory/`)
   - **Purpose**: Central data layer managing short-term (Redis) and long-term (Supabase) memory
   - **Components**:
     - `tokenizer.py` - Text-to-token conversion using tiktoken (fallback to UTF-8)
     - `redis_interface.py` - Fast cache layer with 24-48 hour TTL
     - `supabase_interface.py` - Permanent storage interface
     - `core.py` - Coordinates tokenization, caching, and persistence
   - **Strategy**: Write to Redis immediately, batch flush to Supabase via background worker

2. **Reflection Module** (`backend/reflection_module/`)
   - **Purpose**: Self-awareness and quality assessment using "Causal Retrospection"
   - **Methodology**: Analyzes responses by asking "what caused me to answer this way" rather than "why"
   - **Depth**: 3-level causal chain analysis (direct → indirect → systemic causes)
   - **Output**: Improvement suggestions, quality scores, root cause analysis

3. **Behavior Module** (`backend/behavior_module/`)
   - **Purpose**: Dynamic personality adaptation based on reflection results
   - **Vectors**: Adjusts empathy, curiosity, humor, technical_depth
   - **Rate**: 0.02 adjustment per reflection cycle
   - **Persistence**: Saves evolution history to `personality_vector.json`

4. **Knowledge Hub** (`backend/knowledge_hub/`)
   - **Purpose**: Structured knowledge storage and retrieval
   - **Status**: Basic functionality operational
   - **Future**: Semantic similarity search integration

5. **FineTune Module** (`backend/finetune_module/`)
   - **Status**: Experimental, disabled by default
   - **Planned**: QLoRA-based model fine-tuning using reflection data

**API Router Structure**:
- `/api/chat` - Main conversation endpoint with reflection integration
- `/api/memories/{conversation_id}` - Memory retrieval
- `/api/upload_file` - File processing (text/PDF/images via OpenAI Vision)
- `/api/archive` - IPFS conversation archiving
- `/api/health` - System health monitoring

**Background Jobs**:
- `memory_flush_worker.py` - Automated Redis → Supabase batch flush every 5 minutes
- Retry mechanism with exponential backoff (max 3 retries)
- Graceful shutdown with final flush

### Data Storage Architecture

**Three-Layer Storage Strategy**:

1. **Cache Layer - Redis/Upstash**
   - **Purpose**: Ultra-fast recent conversation access
   - **Format**: JSON strings with conversation metadata
   - **TTL**: 24-48 hours
   - **Key Pattern**: `conversations:{conversation_id}` (list structure)
   - **Connection**: Supports SSL via `rediss://` protocol for Upstash
   - **Fallback**: In-memory mock if Redis unavailable

2. **Persistence Layer - Supabase (PostgreSQL)**
   - **Primary Tables**:
     - `xiaochenguang_memories` - Conversation records with embeddings
     - `xiaochenguang_reflections` - Reflection analysis results
     - `emotional_states` - User emotion history
     - `user_preferences` - Personality profiles
   
   - **Key Fields** (xiaochenguang_memories):
     - `conversation_id`, `user_id`, `user_message`, `assistant_message`
     - `embedding` - Vector embeddings for semantic search
     - `token_data` - Tokenization metadata
     - `importance_score` - Memory significance (0-1)
     - `access_count` - Retrieval frequency tracking
     - `memory_type` - Classification (conversation/personality/etc)
     - `cid` - IPFS content identifier (optional)
   
   - **Schema Design**: Preserves all original Telegram bot fields for backward compatibility

3. **Vector Search Layer - Pinecone** (Optional)
   - **Purpose**: Semantic similarity search for personality embeddings
   - **Model**: Uses Pinecone's llama-text-embed-v2 (4096 dimensions)
   - **Index Strategy**: Cosine similarity on serverless infrastructure
   - **Status**: Integrated but optional (system functions without it)

### Authentication & Authorization

**Current State**: No authentication system implemented
- User identification via `conversation_id` and `user_id` parameters
- No login required for access
- Designed for single-user or trusted environment deployment

**Future Consideration**: Authentication system mentioned as "not required initially" in design docs

### Personality & Emotion Systems

**Soul Profile** (`profile/user_profile.json`):
- Static personality definition (name, age, MBTI, traits)
- Language patterns and catchphrases
- Emotional tendency baselines

**Dynamic Components**:
- `PersonalityEngine` - Loads and evolves traits based on interaction history
- `EnhancedEmotionDetector` - 9-emotion classification with intensity scoring
- Emotion types: joy, sadness, anger, fear, love, tired, confused, grateful, neutral
- Uses keyword matching + regex patterns + intensity multipliers

**Adaptation Loop**:
```
User Input → Emotion Detection → Personality Context → AI Response → 
Reflection Analysis → Behavior Adjustment → Updated Personality Vector
```

## External Dependencies

### Cloud Services

1. **OpenAI**
   - **Models**: GPT-4o-mini for conversations, text-embedding-3-small for vectors
   - **Vision API**: Image content analysis for uploaded files
   - **Environment Variables**: `OPENAI_API_KEY`, `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`

2. **Supabase**
   - **Service**: PostgreSQL database with pgvector extension
   - **Features**: Real-time subscriptions, storage buckets, RPC functions
   - **Environment Variables**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`
   - **Tables**: Custom schema (see Data Storage section)

3. **Upstash Redis**
   - **Type**: Serverless Redis with REST API
   - **SSL Required**: Yes (rediss:// protocol)
   - **Environment Variables**: `REDIS_ENDPOINT`, `REDIS_TOKEN` OR `REDIS_URL`
   - **Fallback**: In-memory mock implementation if unavailable

4. **Pinecone** (Optional)
   - **Purpose**: Vector database for semantic search
   - **Environment Variables**: `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME`
   - **Status**: Optional feature, system works without it

5. **IPFS via Pinata** (Experimental)
   - **Purpose**: Decentralized conversation archiving
   - **Environment Variable**: `PINATA_JWT`
   - **Endpoints**: `pinJSONToIPFS`, `pinFileToIPFS`
   - **Status**: Basic implementation, not critical path

### Python Packages

**Core Dependencies**:
- `fastapi` + `uvicorn` - Web framework and ASGI server
- `openai>=1.35.0` - OpenAI API client
- `supabase>=2.3.4` - Supabase Python client
- `redis>=5.0.0` - Redis client (with SSL support)
- `tiktoken>=0.5.0` - Token counting for OpenAI models

**File Processing**:
- `pdfplumber` - PDF text extraction
- `python-docx` - Word document parsing
- `aiofiles` - Async file operations
- `python-multipart` - File upload handling

**Optional**:
- `pinecone` - Vector database client
- `requests` - HTTP client for external APIs

### Frontend Dependencies

- `vue@^3.3.11` - Core framework
- `vue-router@^4.5.1` - Routing
- `axios@^1.6.5` - HTTP client
- `vite@^5.0.11` - Build tool
- `@vitejs/plugin-vue@^5.0.2` - Vue 3 plugin

### Deployment Platforms

**Primary**: Replit (development environment with always-on hosting)
**Frontend CDN**: Cloudflare Pages (static site deployment)
**Fallback**: Railway (mentioned as backup option)

**CORS Configuration**: Allows multiple origins including Replit, Cloudflare Pages, and localhost variants