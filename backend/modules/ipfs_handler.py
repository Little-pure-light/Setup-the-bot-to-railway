"""
IPFS 處理器 - IPFS Handler
輕量級 CID (Content Identifier) 生成與管理

設計理念：
- 不依賴完整 IPFS 節點
- 生成標準的 CIDv1（base32）
- 支援未來與真實 IPFS 網路整合
"""
import hashlib
import base64
import json
from typing import Dict, Any, Optional
from datetime import datetime


class IPFSHandler:
    """IPFS 內容識別符處理器"""
    
    def __init__(self):
        """初始化 IPFS 處理器"""
        self.cid_version = "1"
        self.multicodec_prefix = "dag-json"  # 使用 DAG-JSON 編碼
        self.hash_algorithm = "sha256"
    
    def generate_cid(self, content: str | Dict[str, Any]) -> str:
        """
        生成 CID (Content Identifier)
        
        使用 SHA-256 雜湊生成內容識別符
        格式: CIDv1 = base32(multicodec + multihash)
        
        參數:
            content: 要生成 CID 的內容（字串或字典）
        
        返回:
            CID 字串（base32 編碼）
        """
        # 1. 正規化內容
        normalized_content = self._normalize_content(content)
        
        # 2. 生成 SHA-256 雜湊
        content_hash = hashlib.sha256(normalized_content.encode('utf-8')).digest()
        
        # 3. 構建 Multihash (hash_func_code + hash_length + hash_value)
        # SHA-256 的 multicodec code 是 0x12, 長度是 32 bytes
        multihash = b'\x12' + b'\x20' + content_hash
        
        # 4. 添加 CIDv1 multicodec 前綴（dag-json = 0x0129）
        cid_bytes = b'\x01' + b'\x29\x01' + multihash
        
        # 5. Base32 編碼
        cid_base32 = self._base32_encode(cid_bytes)
        
        return f"b{cid_base32}"  # CIDv1 以 'b' 開頭表示 base32
    
    def _normalize_content(self, content: str | Dict[str, Any]) -> str:
        """
        正規化內容為一致的字串表示
        
        確保相同內容總是生成相同的 CID
        """
        if isinstance(content, dict):
            # 字典：按鍵排序後轉為 JSON
            return json.dumps(content, sort_keys=True, ensure_ascii=False)
        elif isinstance(content, str):
            # 字串：直接使用
            return content
        else:
            # 其他類型：轉為字串
            return str(content)
    
    def _base32_encode(self, data: bytes) -> str:
        """
        Base32 編碼（小寫，無填充）
        
        IPFS 使用小寫的 base32 編碼（RFC 4648）
        """
        encoded = base64.b32encode(data).decode('ascii')
        # 移除填充的 '=' 並轉為小寫
        return encoded.rstrip('=').lower()
    
    def generate_conversation_cid(
        self,
        user_message: str,
        assistant_message: str,
        timestamp: Optional[str] = None
    ) -> str:
        """
        生成對話記錄的 CID
        
        參數:
            user_message: 使用者訊息
            assistant_message: AI 回覆
            timestamp: 時間戳（可選，預設使用當前時間）
        
        返回:
            對話的 CID
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        conversation_data = {
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": timestamp
        }
        
        return self.generate_cid(conversation_data)
    
    def generate_reflection_cid(self, reflection: Dict[str, Any]) -> str:
        """
        生成反思記錄的 CID
        
        參數:
            reflection: 反思數據
        
        返回:
            反思的 CID
        """
        # 提取核心反思數據
        core_reflection = {
            "summary": reflection.get("summary", ""),
            "causes": reflection.get("causes", []),
            "improvements": reflection.get("improvements", []),
            "confidence": reflection.get("confidence", 0)
        }
        
        return self.generate_cid(core_reflection)
    
    def verify_cid(self, content: str | Dict[str, Any], expected_cid: str) -> bool:
        """
        驗證內容的 CID 是否匹配
        
        參數:
            content: 內容
            expected_cid: 預期的 CID
        
        返回:
            是否匹配
        """
        actual_cid = self.generate_cid(content)
        return actual_cid == expected_cid
    
    def get_cid_info(self, cid: str) -> Dict[str, Any]:
        """
        解析 CID 資訊
        
        參數:
            cid: CID 字串
        
        返回:
            CID 資訊
        """
        if not cid or len(cid) < 2:
            return {"valid": False, "error": "CID too short"}
        
        if not cid.startswith('b'):
            return {"valid": False, "error": "Not a base32 CIDv1"}
        
        return {
            "valid": True,
            "version": "1",
            "encoding": "base32",
            "multicodec": self.multicodec_prefix,
            "hash_algorithm": self.hash_algorithm,
            "cid": cid
        }
    
    async def upload_to_ipfs(self, content: str | Dict[str, Any]) -> Dict[str, Any]:
        """
        上傳內容到 IPFS（預留接口）
        
        當前實現：只生成 CID，不實際上傳
        未來可整合：
        - Infura IPFS API
        - Pinata IPFS 服務
        - Web3.Storage
        - 本地 IPFS 節點
        
        參數:
            content: 要上傳的內容
        
        返回:
            上傳結果
        """
        cid = self.generate_cid(content)
        
        return {
            "success": True,
            "cid": cid,
            "uploaded": False,  # 當前未實際上傳
            "message": "CID 已生成，實際上傳功能待實現",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def retrieve_from_ipfs(self, cid: str) -> Dict[str, Any]:
        """
        從 IPFS 檢索內容（預留接口）
        
        當前實現：返回 CID 資訊
        未來可整合 IPFS gateway
        
        參數:
            cid: 內容識別符
        
        返回:
            檢索結果
        """
        cid_info = self.get_cid_info(cid)
        
        if not cid_info.get("valid"):
            return {
                "success": False,
                "error": cid_info.get("error", "Invalid CID")
            }
        
        return {
            "success": True,
            "cid": cid,
            "retrieved": False,  # 當前未實際檢索
            "message": "CID 有效，實際檢索功能待實現",
            "gateway_urls": [
                f"https://ipfs.io/ipfs/{cid}",
                f"https://gateway.pinata.cloud/ipfs/{cid}",
                f"https://cloudflare-ipfs.com/ipfs/{cid}"
            ]
        }


# 全域單例
_ipfs_handler = None

def get_ipfs_handler() -> IPFSHandler:
    """取得 IPFS 處理器單例"""
    global _ipfs_handler
    if _ipfs_handler is None:
        _ipfs_handler = IPFSHandler()
    return _ipfs_handler
