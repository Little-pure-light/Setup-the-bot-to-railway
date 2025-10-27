"""
記憶模組 - AI 數字宇宙的中樞神經資料層
Memory Module - Central Neural Data Layer of AI Digital Universe

本模組負責：
1. 對話紀錄數字化（Token encoding）
2. 短期記憶（Redis）與長期記憶（Supabase）
3. 反思紀錄索引
4. IPFS 日誌索引（CID）
5. 統一介面供所有模組調用
"""

from .core import MemoryCore
from .tokenizer import TokenizerEngine
from .io_contract import validate_and_normalize

__all__ = ['MemoryCore', 'TokenizerEngine', 'validate_and_normalize']
__version__ = '1.0.0'
