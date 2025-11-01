from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.supabase_handler import get_supabase
from backend.modules.memory.redis_interface import RedisInterface
from backend.modules.ipfs_handler import get_ipfs_handler
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

router = APIRouter()
logger = logging.getLogger("archive_conversation")

supabase = get_supabase()
redis_interface = RedisInterface()
ipfs_handler = get_ipfs_handler()

class ArchiveRequest(BaseModel):
    conversation_id: str
    user_id: str = "default_user"
    include_attachments: bool = True

class ArchiveResponse(BaseModel):
    success: bool
    ipfs_cid: Optional[str] = None
    gateway_url: Optional[str] = None
    archive_id: Optional[str] = None
    message: str
    archived_at: str

async def get_conversation_from_redis(conversation_id: str) -> List[Dict]:
    """從 Redis 獲取對話記錄"""
    try:
        redis_key = f"conversations:{conversation_id}"
        conversations = []
        
        raw_data = redis_interface.redis.lrange(redis_key, 0, -1)
        
        for item in raw_data:
            if isinstance(item, bytes):
                item = item.decode('utf-8')
            try:
                conversations.append(json.loads(item))
            except:
                pass
        
        logger.info(f"📥 從 Redis 讀取 {len(conversations)} 條對話記錄")
        return conversations
        
    except Exception as e:
        logger.warning(f"⚠️ Redis 讀取失敗: {e}")
        return []

async def get_conversation_from_supabase(conversation_id: str) -> List[Dict]:
    """從 Supabase 獲取對話記錄"""
    try:
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
        
        response = supabase.table(memories_table).select("*").eq(
            "conversation_id", conversation_id
        ).order("created_at", desc=False).execute()
        
        if response.data:
            logger.info(f"📥 從 Supabase 讀取 {len(response.data)} 條對話記錄")
            return response.data
        return []
        
    except Exception as e:
        logger.error(f"❌ Supabase 讀取失敗: {e}")
        return []

async def get_uploaded_files(conversation_id: str) -> List[Dict]:
    """獲取對話中上傳的檔案摘要"""
    try:
        pattern = f"upload:{conversation_id}:*"
        file_keys = []
        
        try:
            cursor = '0'
            while cursor != 0:
                cursor, keys = redis_interface.redis.scan(cursor, match=pattern, count=100)
                file_keys.extend(keys)
                if cursor == 0 or cursor == '0':
                    break
        except:
            file_keys = []
        
        files = []
        for key in file_keys:
            try:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                file_data = redis_interface.redis.get(key)
                if file_data:
                    if isinstance(file_data, bytes):
                        file_data = file_data.decode('utf-8')
                    files.append(json.loads(file_data))
            except Exception as e:
                logger.warning(f"⚠️ 讀取檔案資料失敗: {e}")
        
        logger.info(f"📎 找到 {len(files)} 個上傳檔案")
        return files
        
    except Exception as e:
        logger.error(f"❌ 獲取檔案列表失敗: {e}")
        return []

@router.post("/archive_conversation", response_model=ArchiveResponse)
async def archive_conversation(request: ArchiveRequest):
    """
    對話封存端點
    將完整對話打包並上傳到 IPFS，同時儲存 CID 到 Supabase
    """
    try:
        logger.info(f"🗂️ 開始封存對話: {request.conversation_id}")
        
        redis_conversations = await get_conversation_from_redis(request.conversation_id)
        supabase_conversations = await get_conversation_from_supabase(request.conversation_id)
        
        all_conversations = supabase_conversations if supabase_conversations else redis_conversations
        
        logger.info(f"📊 數據來源 - Redis: {len(redis_conversations)} 條, Supabase: {len(supabase_conversations)} 條")
        logger.info(f"📦 使用 {'Supabase (完整)' if supabase_conversations else 'Redis (快取)'} 數據進行封存")
        
        if not all_conversations:
            raise HTTPException(
                status_code=404,
                detail="找不到對話記錄"
            )
        
        uploaded_files = []
        if request.include_attachments:
            uploaded_files = await get_uploaded_files(request.conversation_id)
        
        messages = []
        for conv in all_conversations:
            if isinstance(conv, dict):
                messages.append({
                    "role": "user",
                    "content": conv.get("user_message", ""),
                    "timestamp": conv.get("created_at", conv.get("timestamp", ""))
                })
                messages.append({
                    "role": "assistant",
                    "content": conv.get("assistant_message", ""),
                    "timestamp": conv.get("created_at", conv.get("timestamp", ""))
                })
        
        archive_data = {
            "conversation_id": request.conversation_id,
            "user_id": request.user_id,
            "ai_id": os.getenv("AI_ID", "xiaochenguang_v1"),
            "archived_at": datetime.utcnow().isoformat(),
            "message_count": len(messages),
            "messages": messages,
            "attachments": [
                {
                    "file_name": f.get("file_name"),
                    "file_type": f.get("file_type"),
                    "summary": f.get("summary"),
                    "uploaded_at": f.get("uploaded_at")
                }
                for f in uploaded_files
            ],
            "metadata": {
                "total_messages": len(messages),
                "total_attachments": len(uploaded_files),
                "archive_version": "1.0"
            }
        }
        
        logger.info(f"📦 準備上傳封存: {len(messages)} 條訊息, {len(uploaded_files)} 個附件")
        
        ipfs_result = await ipfs_handler.upload_to_ipfs(
            archive_data,
            name=f"conversation_{request.conversation_id}"
        )
        
        ipfs_cid = ipfs_result.get("cid") or ipfs_result.get("ipfs_hash") or ipfs_result.get("local_cid")
        
        if not ipfs_cid:
            raise HTTPException(
                status_code=500,
                detail=f"無法生成 CID: {ipfs_result.get('error', 'Unknown error')}"
            )
        
        uploaded_to_pinata = ipfs_result.get("success", False)
        gateway_url = ipfs_result.get("gateway_url", f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}")
        
        if uploaded_to_pinata:
            logger.info(f"✅ 對話已上傳到 Pinata IPFS: {ipfs_cid}")
        else:
            logger.warning(f"⚠️ Pinata 上傳失敗，使用本地 CID: {ipfs_cid}")
            gateway_url = f"ipfs://{ipfs_cid}"
        
        try:
            archive_table = os.getenv("SUPABASE_ARCHIVE_TABLE", "conversation_archive")
            archive_record = {
                "conversation_id": request.conversation_id,
                "user_id": request.user_id,
                "ipfs_cid": ipfs_cid,
                "gateway_url": gateway_url,
                "message_count": len(messages),
                "attachment_count": len(uploaded_files),
                "created_at": datetime.utcnow().isoformat()
            }
            
            db_response = supabase.table(archive_table).insert(archive_record).execute()
            
            archive_id = None
            if db_response.data and len(db_response.data) > 0:
                archive_id = db_response.data[0].get("id")
                logger.info(f"✅ 封存記錄已儲存到 Supabase: {archive_id}")
            
        except Exception as e:
            logger.warning(f"⚠️ Supabase 儲存失敗（不影響 IPFS 上傳）: {e}")
            archive_id = None
        
        return ArchiveResponse(
            success=True,
            ipfs_cid=ipfs_cid,
            gateway_url=gateway_url,
            archive_id=archive_id,
            message=f"對話已成功封存到 IPFS（{len(messages)} 條訊息）",
            archived_at=datetime.utcnow().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 對話封存失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"封存失敗: {str(e)}")
