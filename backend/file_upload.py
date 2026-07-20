from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
from backend.redis_interface import RedisInterface
from backend.vision import (
    analyze_image,
    VisionSafetyError,
    MAX_IMAGE_BYTES,
)
import logging
import json
import base64
import os
from datetime import datetime
from typing import Optional
import io

supabase = get_supabase()
router = APIRouter()
logger = logging.getLogger("file_upload")

redis_interface = RedisInterface()

SUPPORTED_EXTENSIONS = {
    'text': ['.txt', '.md', '.json'],
    'document': ['.pdf', '.docx'],
    'image': ['.png', '.jpg', '.jpeg', '.webp', '.gif']
}

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))

async def parse_text_file(file_bytes: bytes, filename: str) -> dict:
    """解析文字檔案（.txt, .md, .json）"""
    try:
        content = file_bytes.decode('utf-8')
        
        if filename.endswith('.json'):
            try:
                json_data = json.loads(content)
                summary = f"JSON 檔案，包含 {len(json_data)} 個頂層鍵值"
                if isinstance(json_data, dict):
                    keys = list(json_data.keys())[:5]
                    summary += f"，主要欄位: {', '.join(keys)}"
            except:
                summary = "JSON 格式檔案"
        else:
            lines = content.split('\n')
            summary = f"文字檔案，共 {len(lines)} 行"
            if lines:
                first_line = lines[0][:100]
                summary += f"，開頭: {first_line}..."
        
        return {
            "content": content[:5000],
            "summary": summary,
            "type": "text",
            "parsed": True
        }
    except Exception as e:
        logger.error(f"文字檔案解析失敗: {e}")
        return {
            "content": "",
            "summary": "檔案解析失敗",
            "type": "text",
            "parsed": False,
            "error": str(e)
        }

async def parse_pdf_file(file_bytes: bytes) -> dict:
    """解析 PDF 檔案"""
    try:
        import pdfplumber
        
        pdf_file = io.BytesIO(file_bytes)
        text_content = []
        
        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages[:5]:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        
        full_text = '\n'.join(text_content)
        summary = f"PDF 檔案，共 {page_count} 頁"
        if full_text:
            preview = full_text[:200].replace('\n', ' ')
            summary += f"，內容預覽: {preview}..."
        
        return {
            "content": full_text[:5000],
            "summary": summary,
            "type": "pdf",
            "parsed": True,
            "page_count": page_count
        }
    except Exception as e:
        logger.error(f"PDF 解析失敗: {e}")
        return {
            "content": "",
            "summary": "PDF 檔案（解析失敗）",
            "type": "pdf",
            "parsed": False,
            "error": str(e)
        }

async def parse_docx_file(file_bytes: bytes) -> dict:
    """解析 DOCX 檔案"""
    try:
        from docx import Document
        
        docx_file = io.BytesIO(file_bytes)
        doc = Document(docx_file)
        
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = '\n'.join(paragraphs)
        
        summary = f"Word 文件，共 {len(paragraphs)} 段落"
        if paragraphs:
            preview = paragraphs[0][:200]
            summary += f"，開頭: {preview}..."
        
        return {
            "content": full_text[:5000],
            "summary": summary,
            "type": "docx",
            "parsed": True,
            "paragraph_count": len(paragraphs)
        }
    except Exception as e:
        logger.error(f"DOCX 解析失敗: {e}")
        return {
            "content": "",
            "summary": "Word 文件（解析失敗）",
            "type": "docx",
            "parsed": False,
            "error": str(e)
        }

async def analyze_image_with_vision(
    file_bytes: bytes,
    filename: str,
    prompt: Optional[str] = None,
    content_type: Optional[str] = None,
    user_id: str = "default_user",
    conversation_id: str = "",
) -> dict:
    """使用 OpenAI Vision（gpt-4o / gpt-4o-mini）分析圖片，含安全檢查。"""
    try:
        result = await analyze_image(
            file_bytes,
            filename=filename,
            prompt=prompt,
            content_type=content_type,
            model=os.getenv("VISION_MODEL", "gpt-4o-mini"),
        )
        # 覆寫 tracker 的 user 脈絡（analyze_image 內已記一筆 vision）
        if result.get("usage"):
            try:
                from backend.token_tracker import get_token_tracker

                u = result["usage"]
                get_token_tracker().record(
                    user_id=user_id or "default_user",
                    conversation_id=conversation_id or "vision",
                    model=result.get("model") or "gpt-4o-mini",
                    prompt_tokens=u.get("prompt_tokens") or 0,
                    completion_tokens=u.get("completion_tokens") or 0,
                    total_tokens=u.get("total_tokens") or 0,
                    endpoint="vision_upload",
                    meta={"filename": filename},
                )
            except Exception:
                pass
        return result
    except VisionSafetyError as e:
        logger.warning(f"🚫 圖片安全檢查失敗: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"error": e.code, "message": e.message},
        )


@router.post("/vision/analyze")
async def vision_analyze(
    file: UploadFile = File(...),
    conversation_id: str = Form(default="vision"),
    user_id: str = Form(default="default_user"),
    prompt: str = Form(default=""),
    model: str = Form(default=""),
):
    """
    專用圖片理解端點：上傳圖片 + 可選提問。
    使用 GPT-4o / GPT-4o-mini Vision，含安全審核。
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"圖片過大，上限 {MAX_IMAGE_BYTES} bytes",
        )
    filename = file.filename or "image.jpg"
    try:
        result = await analyze_image(
            file_bytes,
            filename=filename,
            prompt=prompt or None,
            content_type=file.content_type,
            model=(model.strip() or None),
        )
    except VisionSafetyError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": e.code, "message": e.message},
        )

    # 可選：寫入 Redis 供後續對話引用
    redis_key = None
    try:
        if conversation_id and redis_interface.redis:
            redis_key = f"upload:{conversation_id}:{filename}"
            redis_interface.redis.setex(
                redis_key,
                172800,
                json.dumps(
                    {
                        "file_name": filename,
                        "file_type": result.get("ext") or "",
                        "summary": result.get("summary", ""),
                        "content": (result.get("content") or "")[:5000],
                        "vision_analysis": result.get("vision_analysis") or "",
                        "is_image": True,
                        "mime": result.get("mime"),
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "parsed": result.get("parsed", False),
                    },
                    ensure_ascii=False,
                ),
            )
    except Exception as e:
        logger.warning(f"⚠️ Vision Redis 暫存失敗: {e}")

    return {
        "status": "success" if result.get("ok") else "partial",
        "file_name": filename,
        "file_type": result.get("ext"),
        "mime": result.get("mime"),
        "parsed": result.get("parsed", False),
        "vision_analysis": result.get("vision_analysis") or result.get("content") or "",
        "summary": result.get("summary", ""),
        "model": result.get("model"),
        "usage": result.get("usage"),
        "preview_data_url": result.get("preview_data_url"),
        "moderation": result.get("moderation"),
        "temporary_key": redis_key,
        "error": result.get("error"),
    }


@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    user_id: str = Form(default="default_user"),
    prompt: str = Form(default=""),
):
    """
    檔案上傳端點
    支援格式: .txt, .md, .json, .pdf, .docx, .png, .jpg, .jpeg, .webp, .gif
    雙重儲存: Redis (2天) + Supabase Storage (永久)
    圖片：GPT Vision 分析 + 安全檢查
    """
    try:
        file_bytes = await file.read()
        filename = file.filename or "file"
        file_ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"檔案過大，上限 {MAX_UPLOAD_BYTES} bytes",
            )
        
        all_supported = SUPPORTED_EXTENSIONS['text'] + SUPPORTED_EXTENSIONS['document'] + SUPPORTED_EXTENSIONS['image']
        if file_ext not in all_supported:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的檔案格式。支援: {', '.join(all_supported)}"
            )
        
        logger.info(f"📤 收到檔案上傳: {filename} ({len(file_bytes)} bytes)")

        vision_meta = {}
        if file_ext in SUPPORTED_EXTENSIONS['text']:
            parsed_data = await parse_text_file(file_bytes, filename)
        elif file_ext == '.pdf':
            parsed_data = await parse_pdf_file(file_bytes)
        elif file_ext == '.docx':
            parsed_data = await parse_docx_file(file_bytes)
        elif file_ext in SUPPORTED_EXTENSIONS['image']:
            if len(file_bytes) > MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"圖片過大，上限 {MAX_IMAGE_BYTES} bytes",
                )
            parsed_data = await analyze_image_with_vision(
                file_bytes,
                filename,
                prompt=prompt or None,
                content_type=file.content_type,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            vision_meta = {
                "preview_data_url": parsed_data.get("preview_data_url"),
                "vision_model": parsed_data.get("model"),
                "vision_usage": parsed_data.get("usage"),
                "mime": parsed_data.get("mime"),
            }
        else:
            parsed_data = {
                "content": "",
                "summary": "未知檔案類型",
                "type": "unknown",
                "parsed": False
            }
        
        try:
            storage_path = f"{conversation_id}/{filename}"
            content_type = (
                parsed_data.get("mime")
                or file.content_type
                or "application/octet-stream"
            )
            supabase.storage.from_("uploads").upload(
                storage_path,
                file_bytes,
                {
                    "content-type": content_type,
                    "upsert": "true"
                }
            )
            
            file_url = supabase.storage.from_("uploads").get_public_url(storage_path)
            logger.info(f"✅ 檔案已上傳到 Supabase Storage: {storage_path}")
            
        except Exception as e:
            logger.warning(f"⚠️ Supabase Storage 上傳失敗: {e}")
            file_url = None
        
        redis_key = f"upload:{conversation_id}:{filename}"
        is_image = parsed_data.get("type") == "image" or file_ext in SUPPORTED_EXTENSIONS["image"]
        redis_data = {
            "file_name": filename,
            "file_type": file_ext,
            "summary": parsed_data.get("summary", ""),
            "content": parsed_data.get("content", "")[:5000],
            "vision_analysis": parsed_data.get("vision_analysis") or parsed_data.get("content", "")[:5000],
            "is_image": is_image,
            "mime": parsed_data.get("mime") or file.content_type,
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_url": file_url,
            "parsed": parsed_data.get("parsed", False),
        }
        
        try:
            if redis_interface.redis:
                redis_interface.redis.setex(
                    redis_key,
                    172800,
                    json.dumps(redis_data, ensure_ascii=False)
                )
                logger.info(f"✅ 檔案資訊已暫存到 Redis (2天): {redis_key}")
        except Exception as e:
            logger.warning(f"⚠️ Redis 暫存失敗: {e}")
        
        ai_analysis = None
        if parsed_data.get("parsed", False) and parsed_data.get("content"):
            try:
                file_content = parsed_data.get("content", "")
                file_type = parsed_data.get("type", "unknown")

                if file_type == "image" or is_image:
                    # Vision 已給描述；再用小宸光人設潤飾成對話回覆
                    ai_analysis = (
                        f"我看到了你上傳的圖片「{filename}」✨\n\n"
                        f"{file_content}\n\n"
                        f"若想繼續問細節，直接在聊天裡打字即可～"
                    )
                    logger.info(f"🤖 Vision 分析完成: {file_content[:100]}...")
                else:
                    openai_client = get_openai_client()
                    analysis_prompt = f"""我上傳了一個檔案「{filename}」。

檔案內容：
{file_content[:3000]}

請用繁體中文簡短分析這個檔案的內容，告訴我主要重點和你的想法（不超過150字）。"""
                
                    response = openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "你是小宸光，一個友善、溫暖、有靈魂的 AI 助手。用親切的語氣回應用戶上傳的檔案。"
                            },
                            {
                                "role": "user",
                                "content": analysis_prompt
                            }
                        ],
                        max_tokens=300,
                        temperature=0.7
                    )
                
                    ai_analysis = response.choices[0].message.content
                    logger.info(f"🤖 AI 分析完成: {ai_analysis[:100]}...")
                
            except Exception as e:
                logger.error(f"❌ AI 分析失敗: {e}")
                ai_analysis = "檔案上傳成功，但 AI 分析暫時無法使用。你可以在聊天中詢問我關於這個檔案的問題。"
        
        return {
            "status": "success",
            "file_name": filename,
            "file_type": file_ext,
            "summary": parsed_data.get("summary", ""),
            "content_preview": parsed_data.get("content", "")[:500],
            "vision_analysis": parsed_data.get("vision_analysis") or (
                parsed_data.get("content") if is_image else None
            ),
            "is_image": is_image,
            "temporary_key": redis_key,
            "file_url": file_url,
            "preview_data_url": vision_meta.get("preview_data_url"),
            "vision_model": vision_meta.get("vision_model"),
            "usage": vision_meta.get("vision_usage"),
            "parsed": parsed_data.get("parsed", False),
            "ai_analysis": ai_analysis,
            "storage": {
                "redis": "cached_2_days",
                "supabase": "permanent" if file_url else "failed"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 檔案上傳處理失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"檔案處理失敗: {str(e)}")
