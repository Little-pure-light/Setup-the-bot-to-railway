"""
IPFS 處理器 - IPFS Handler
輕量級 CID (Content Identifier) 生成與管理 + Pinata 上傳整合

設計理念：
- 不依賴完整 IPFS 節點
- 生成標準的 CIDv1（base32）
- 整合 Pinata API 實現真實 IPFS 上傳
"""
import hashlib
import base64
import json
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger("ipfs_handler")


class IPFSHandler:
    """IPFS 內容識別符處理器 + Pinata 上傳"""
    
    def __init__(self):
        """初始化 IPFS 處理器"""
        self.cid_version = "1"
        self.multicodec_prefix = "raw"
        self.hash_algorithm = "sha256"
        
        self.pinata_jwt = os.getenv("PINATA_JWT")
        self.pinata_api_url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
        self.pinata_file_url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        
        if self.pinata_jwt:
            logger.info("✅ Pinata API 已配置，支援實際 IPFS 上傳")
        else:
            logger.warning("⚠️ 未配置 PINATA_JWT，將僅生成本地 CID")
    
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
        normalized_content = self._normalize_content(content)
        content_hash = hashlib.sha256(normalized_content.encode('utf-8')).digest()
        multihash = b'\x12\x20' + content_hash
        cid_bytes = b'\x01\x55' + multihash
        cid_base32 = self._base32_encode(cid_bytes)
        return f"b{cid_base32}"
    
    def _normalize_content(self, content: str | Dict[str, Any]) -> str:
        """正規化內容為一致的字串表示"""
        if isinstance(content, dict):
            return json.dumps(content, sort_keys=True, ensure_ascii=False)
        elif isinstance(content, str):
            return content
        else:
            return str(content)
    
    def _base32_encode(self, data: bytes) -> str:
        """Base32 編碼（小寫，無填充）"""
        encoded = base64.b32encode(data).decode('ascii')
        return encoded.rstrip('=').lower()
    
    def generate_conversation_cid(
        self,
        user_message: str,
        assistant_message: str,
        timestamp: Optional[str] = None
    ) -> str:
        """生成對話記錄的 CID"""
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        conversation_data = {
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": timestamp
        }
        
        return self.generate_cid(conversation_data)
    
    def generate_reflection_cid(self, reflection: Dict[str, Any]) -> str:
        """生成反思記錄的 CID"""
        core_reflection = {
            "summary": reflection.get("summary", ""),
            "causes": reflection.get("causes", []),
            "improvements": reflection.get("improvements", []),
            "confidence": reflection.get("confidence", 0)
        }
        return self.generate_cid(core_reflection)
    
    def verify_cid(self, content: str | Dict[str, Any], expected_cid: str) -> bool:
        """驗證內容的 CID 是否匹配"""
        actual_cid = self.generate_cid(content)
        return actual_cid == expected_cid
    
    def get_cid_info(self, cid: str) -> Dict[str, Any]:
        """解析 CID 資訊"""
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
    
    async def upload_json_to_pinata(
        self,
        json_data: Dict[str, Any],
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上傳 JSON 資料到 Pinata IPFS
        
        參數:
            json_data: 要上傳的 JSON 資料
            name: 檔案名稱（可選）
        
        返回:
            上傳結果（包含 CID）
        """
        if not self.pinata_jwt:
            logger.warning("未配置 PINATA_JWT，無法上傳")
            return {
                "success": False,
                "error": "PINATA_JWT not configured",
                "local_cid": self.generate_cid(json_data)
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {self.pinata_jwt}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "pinataContent": json_data,
                "pinataMetadata": {
                    "name": name or f"xiaochenguang_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                }
            }
            
            response = requests.post(
                self.pinata_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ipfs_hash = result.get("IpfsHash", "")
                
                logger.info(f"✅ 成功上傳到 Pinata IPFS: {ipfs_hash}")
                
                return {
                    "success": True,
                    "cid": ipfs_hash,
                    "ipfs_hash": ipfs_hash,
                    "uploaded": True,
                    "timestamp": result.get("Timestamp", datetime.utcnow().isoformat()),
                    "gateway_url": f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
                }
            else:
                logger.error(f"❌ Pinata 上傳失敗: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Pinata API error: {response.status_code}",
                    "local_cid": self.generate_cid(json_data)
                }
                
        except Exception as e:
            logger.error(f"❌ Pinata 上傳異常: {e}")
            return {
                "success": False,
                "error": str(e),
                "local_cid": self.generate_cid(json_data)
            }
    
    async def upload_to_ipfs(self, content: str | Dict[str, Any], name: Optional[str] = None) -> Dict[str, Any]:
        """
        上傳內容到 IPFS（透過 Pinata）
        
        參數:
            content: 要上傳的內容
            name: 檔案名稱（可選）
        
        返回:
            上傳結果
        """
        if isinstance(content, dict):
            return await self.upload_json_to_pinata(content, name)
        elif isinstance(content, str):
            json_data = {"content": content, "type": "text"}
            return await self.upload_json_to_pinata(json_data, name)
        else:
            return {
                "success": False,
                "error": "Unsupported content type"
            }
    
    async def retrieve_from_ipfs(self, cid: str) -> Dict[str, Any]:
        """
        從 IPFS 檢索內容
        
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
            "gateway_urls": [
                f"https://ipfs.io/ipfs/{cid}",
                f"https://gateway.pinata.cloud/ipfs/{cid}",
                f"https://cloudflare-ipfs.com/ipfs/{cid}"
            ]
        }


_ipfs_handler = None

def get_ipfs_handler() -> IPFSHandler:
    """取得 IPFS 處理器單例"""
    global _ipfs_handler
    if _ipfs_handler is None:
        _ipfs_handler = IPFSHandler()
    return _ipfs_handler
