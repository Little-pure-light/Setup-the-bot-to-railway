"""
Copilot Memory Brain - Configuration
配置管理模組
"""

import os
from typing import Optional

class Config:
    """Copilot 記憶腦配置"""
    
    # 伺服器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # API 配置
    API_PREFIX: str = "/api"
    
    # Redis 配置（共用小宸光 Redis）
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_ENDPOINT: str = os.getenv("REDIS_ENDPOINT", "")
    REDIS_TOKEN: str = os.getenv("REDIS_TOKEN", "")
    
    # Supabase 配置（共用小宸光 Supabase）
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_MEMORIES_TABLE: str = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    SUPABASE_REFLECTIONS_TABLE: str = "xiaochenguang_reflections"
    SUPABASE_PERSONALITY_TABLE: str = "xiaochenguang_personality"
    
    # OpenAI 配置（用於反思生成）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Copilot 配置
    COPILOT_PLATFORM: str = "vscode"
    COPILOT_AI_ID: str = "copilot_v1"
    COPILOT_MEMORY_TYPE: str = "copilot_session"
    
    # Session 配置
    SESSION_TTL: int = 3600  # 1 小時
    
    # 記憶檢索配置
    RECENT_MEMORIES_LIMIT: int = 5
    
    @classmethod
    def validate(cls) -> bool:
        """驗證必要的環境變數"""
        required = [
            cls.SUPABASE_URL,
            cls.SUPABASE_ANON_KEY,
            cls.OPENAI_API_KEY
        ]
        
        if not all(required):
            missing = []
            if not cls.SUPABASE_URL:
                missing.append("SUPABASE_URL")
            if not cls.SUPABASE_ANON_KEY:
                missing.append("SUPABASE_ANON_KEY")
            if not cls.OPENAI_API_KEY:
                missing.append("OPENAI_API_KEY")
            
            print(f"❌ 缺少必要環境變數: {', '.join(missing)}")
            return False
        
        return True

config = Config()
