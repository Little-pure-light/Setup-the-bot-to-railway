# XiaoChenGuang AI Soul System - Web Version

## Project Overview
A complete AI conversational system ported from a Telegram Bot to a Vue 3 + FastAPI + Supabase architecture, featuring memory, emotion detection, and personality systems.

## Technology Stack

### Backend (Python + FastAPI)
- **Framework**: FastAPI
- **Port**: 8000
- **Core Modules**:
  - XiaoChenGuangSoul: AI personality and soul configuration
  - PersonalityEngine: Learning personality engine
  - EnhancedEmotionDetector: Emotion detection system
  - MemorySystem: Memory retrieval and storage

### Frontend (Vue 3)
- **Framework**: Vue 3 + Vite
- **Port**: 5000
- **Features**:
  - Real-time chat interface
  - Memory list display
  - Emotion state visualization
  - File upload functionality

### Database (Supabase)
- **xiaochenguang_memories** table: Stores conversation memories
- **emotional_states** table: Tracks emotional states

## Project Structure

```
/
├── BotDesign/BotDesign/
│   ├── backend/                 # FastAPI backend
│   │   ├── main.py             # Main application entry
│   │   ├── chat_router.py      # Chat API
│   │   ├── memory_router.py    # Memory management API
│   │   ├── file_upload.py      # File upload API
│   │   ├── openai_handler.py   # OpenAI integration
│   │   ├── supabase_handler.py # Supabase integration
│   │   ├── prompt_engine.py    # Prompt engine
│   │   └── requirements.txt    # Python dependencies
│   │
│   ├── frontend/               # Vue 3 frontend
│   │   ├── src/
│   │   │   ├── App.vue        # Main app
│   │   │   ├── components/
│   │   │   │   ├── ChatInterface.vue  # Chat interface
│   │   │   │   ├── StatusPage.vue     # Status page
│   │   │   │   └── HealthStatus.vue   # Health check
│   │   │   ├── router/
│   │   │   │   └── index.js   # Vue router
│   │   │   └── main.js
│   │   ├── vite.config.js
│   │   └── package.json
│   │
│   ├── modules/               # Core soul modules
│   │   ├── emotion_detector.py    # Emotion detection
│   │   ├── soul.py               # Soul configuration
│   │   ├── personality_engine.py # Personality engine
│   │   ├── memory_system.py      # Memory system
│   │   └── file_handler.py       # File handling
│   │
│   └── profile/              # Personality configuration
│       └── user_profile.json
```

## Environment Variables

The following environment variables are required for full functionality:

### Required Secrets (Set in Replit Secrets)
- `OPENAI_API_KEY`: OpenAI API key for chat completions and embeddings
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous/service key

### Optional Configuration
- `SUPABASE_MEMORIES_TABLE`: Memory table name (default: xiaochenguang_memories)
- `AI_ID`: AI instance identifier (default: xiaochenguang_v1)

**Note**: The backend will start even without these secrets set, but certain features will be unavailable. You'll see warning messages in the logs indicating which features are disabled.

## Running the Application

### Workflows
Two workflows are configured:
1. **Backend** - Runs on port 8000 (console output)
2. **Frontend** - Runs on port 5000 (webview output)

Both workflows start automatically when you run the Repl.

## API Endpoints

- `GET /`: API status
- `GET /health`: Health check
- `POST /api/chat`: Chat conversation
- `GET /api/memories/{conversation_id}`: Get conversation memories
- `GET /api/emotional-states/{user_id}`: Get emotional states
- `POST /api/upload`: File upload

## Core Features

### 1. Emotion Detection System
- Supports 9 emotions: joy, sadness, anger, fear, love, tired, confused, grateful, neutral
- Intensity analysis and confidence scoring
- Automatic response style adjustment

### 2. Memory System
- Vector-based memory retrieval (OpenAI embeddings)
- Memory importance scoring
- Access count tracking
- Conversation history management

### 3. Personality Engine
- Learning personality traits from interactions
- Emotional profile recording
- Knowledge domain tracking
- Dynamic personality adjustment

### 4. File Upload
- Supabase Storage integration
- File record association

## Database Setup

**Important**: For full functionality, you must set up Supabase database tables. See `BotDesign/BotDesign/DATABASE_SETUP.md` for detailed instructions.

Required tables:
1. **xiaochenguang_memories** - Stores conversation memories
2. **emotional_states** - Tracks emotional states
3. **match_memories** RPC function - Vector similarity search

Common issues:
- If you see "column assistant_mes does not exist" error, refer to DATABASE_SETUP.md
- pgvector extension must be enabled for vector embedding support

## Recent Setup Changes (2025-10-13)

- Created missing main.py FastAPI application entry point
- Added Python and Node.js dependencies
- Configured Vite for Replit proxy compatibility (HMR on port 443)
- Updated supabase_handler to gracefully handle missing environment variables
- Fixed frontend router configuration
- Installed vue-router dependency
- Set up workflows for both backend and frontend

## Deployment

To deploy this application:
1. Set all required environment variables in Replit Secrets
2. Complete database setup following DATABASE_SETUP.md
3. Use the Deploy/Publish button in Replit

## Troubleshooting

### Backend won't start
- Check that all required environment variables are set
- Review backend logs for specific error messages

### Frontend shows errors
- Ensure all npm packages are installed: `cd BotDesign/BotDesign/frontend && npm install`
- Check that backend is running on port 8000

### Database errors
- Verify Supabase credentials are correct
- Follow DATABASE_SETUP.md to create required tables
- Enable pgvector extension in Supabase

### Memory/Chat features not working
- Ensure OPENAI_API_KEY is set
- Verify Supabase tables are created correctly
- Check backend logs for detailed error messages
