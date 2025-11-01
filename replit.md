# XiaoChenGuang AI Soul System

## Overview

XiaoChenGuang (小宸光) is an AI companion system designed for personality learning, emotional intelligence, and memory retention. It offers intelligent memory using vector-based storage, a 9-emotion classification system, dynamic personality traits, and a self-improving reflection mechanism. The system is built with a modular architecture, combining a Vue 3 frontend with a FastAPI backend, utilizing Supabase PostgreSQL for persistent data, Redis for caching, and integrating external services like OpenAI and Pinata for IPFS archiving. Its core purpose is to provide an engaging, evolving AI companion experience.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Decisions

The frontend is a single-page application (SPA) built with Vue 3 and Vite, accessible on Port 5000. Key components include `ChatInterface.vue` for conversations, `StatusPage.vue` for system health, and `ModulesMonitor.vue` for module status. The design prioritizes a clean, focused user interface, relocating elements like reflection displays to dedicated sidebars for improved visual hierarchy.

### Technical Implementations

The backend, running on FastAPI (Python 3.11, Port 8000), employs a modular plugin architecture managed by a `Core Controller`. This enables dynamic loading and unloading of modules, facilitating incremental development.

**Core Modules:**
-   **Memory Module**: Manages short-term (Redis) and long-term (Supabase) memory, tokenization, and vector embeddings.
-   **Reflection Module**: Implements "causal retrospection" for self-improvement and stores reflections across Redis, Supabase, and Pinecone.
-   **Knowledge Hub**: For global knowledge indexing and retrieval.
-   **Behavior Module**: Adjusts AI personality based on reflection insights.
-   **FineTune Module**: An experimental module for QLoRA-based model fine-tuning.

**AI Processing Pipeline:**
The conversation flow integrates emotion analysis, memory recall, dynamic personality prompting, OpenAI GPT-4o-mini processing, response generation, reflection analysis, behavior adjustment, and memory storage.

**Key AI Components:**
-   **Emotion Detection**: Classifies 9 emotions using keyword matching and regex.
-   **Personality Engine**: Manages 4 core traits (curiosity, empathy, humor, technical_depth) that dynamically adjust.
-   **Soul System**: Defines the AI's core character profile, backstory, and language patterns for consistent personality.
-   **Reflection System**: Utilizes "Causal Retrospection" for multi-level analysis and generating improvement suggestions.

### System Design Choices

**Data Layer:** Features a two-tier memory architecture:
-   **Short-term Memory (Redis/Mock)**: For recent conversations with a 2-day TTL, batch-flushed to Supabase. Includes automatic `redis://` to `rediss://` conversion for Upstash compatibility.
-   **Long-term Memory (Supabase PostgreSQL)**: Stores persistent data, emotional states, user preferences, and reflections using pgvector for embeddings.
-   **Reflection Storage**: Three-tier system for reflections using Redis (cache), Supabase (permanent), and Pinecone (vector embeddings).

**File Upload System**: Supports 7 file formats (`.txt`, `.md`, `.json`, `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`) with content parsing, pdfplumber for PDFs, python-docx for DOCX, and OpenAI Vision API (gpt-4o-mini) for image analysis. Files are stored in Redis (2-day TTL) and Supabase Storage (permanent).

**Conversation Archiving**: Enables packaging conversations and attachments into JSON, uploading them to IPFS via Pinata, storing the CID in Supabase, and providing a public gateway URL. Prioritizes Supabase data for archive completeness.

**Background Jobs**: A `Memory Flush Worker` performs automated batch writes from Redis to Supabase every 5 minutes to optimize database load.

## External Dependencies

### Third-party Services

1.  **OpenAI API**: Used for GPT-4o-mini for conversation generation, `text-embedding-3-small` for vector embeddings, and Vision API for image analysis.
2.  **Supabase**: Provides PostgreSQL with pgvector extension for long-term memory, emotional states, user preferences, and reflection storage, along with Supabase Storage for file uploads.
3.  **Redis**: Utilized for short-term memory caching. Falls back to an in-memory mock if unavailable.
4.  **Pinata**: Integrated for IPFS archiving of conversation data.
5.  **Pinecone**: Used for vector embeddings and similarity search of reflections.

### Python Dependencies

-   `fastapi`, `uvicorn`, `openai`, `supabase`, `tiktoken`, `redis`, `python-multipart`, `pydantic`.

### Frontend Dependencies

-   `vue`, `vue-router`, `axios`, `vite`, `@vitejs/plugin-vue`.

### Deployment Configuration

-   **CORS Settings**: Configured to allow multiple origins including production domains, Cloudflare Pages, Replit, and localhost.
-   **Environment Variables**: Managed via `python-dotenv` for backend, and `VITE_API_URL` for frontend API endpoints.