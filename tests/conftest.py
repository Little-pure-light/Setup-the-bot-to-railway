"""
全域 pytest fixtures。

原則：
- 不連線正式 OpenAI / Supabase / Redis / Railway
- 不寫入正式資料庫
- 測試用假憑證僅存在環境變數 mock
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 專案根目錄
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 測試環境假憑證（絕不使用正式 key）
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("SUPABASE_URL", "http://mock.supabase.local")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")
os.environ.setdefault("API_SECRET", "")
os.environ.setdefault("DAILY_TOKEN_BUDGET_USD", "100.0")
os.environ.setdefault("USER_DAILY_TOKEN_BUDGET_USD", "10.0")
os.environ.setdefault("TOKEN_USAGE_LOG", str(ROOT / "data" / "test_token_usage.jsonl"))


@pytest.fixture
def tmp_token_log(tmp_path):
    """TokenTracker 用的暫時 JSONL 路徑。"""
    return tmp_path / "token_usage.jsonl"


@pytest.fixture
def emotion_detector():
    from modules.emotion_detector import EnhancedEmotionDetector

    return EnhancedEmotionDetector()


@pytest.fixture
def empty_registry():
    """空白 ToolRegistry（不含內建工具）。"""
    from backend.tools.registry import ToolRegistry

    return ToolRegistry()
