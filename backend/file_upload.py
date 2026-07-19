from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
from backend.redis_interface import RedisInterface
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
    'image': ['.png', '.jpg', '.jpeg']
}

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

async def analyze_image_with_vision(file_bytes: bytes, filename: str) -> dict:
    """使用 OpenAI Vision API 分析圖片"""
    try:
        openai_client = get_openai_client()
        
        file_ext = os.path.splitext(filename.lower())[1]
        mime_type = "image/jpeg"
        if file_ext == '.png':
            mime_type = "image/png"
        elif file_ext in ['.jpg', '.jpeg']:
            mime_type = "image/jpeg"
        
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "請用繁體中文簡短描述這張圖片的內容（不超過100字）。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        
        description = response.choices[0].message.content
        
        return {
            "content": description,
            "summary": f"圖片檔案 ({filename})，AI 分析: {description[:100]}...",
            "type": "image",
            "parsed": True,
            "vision_analysis": description
        }
    except Exception as e:
        logger.error(f"Vision API 分析失敗: {e}")
        return {
            "content": "",
            "summary": f"圖片檔案 ({filename})",
            "type": "image",
            "parsed": False,
            "error": str(e)
        }

@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    user_id: str = Form(default="default_user")
):
    """
    檔案上傳端點
    支援格式: .txt, .md, .json, .pdf, .docx, .png, .jpg, .jpeg
    雙重儲存: Redis (2天) + Supabase Storage (永久)
    ✨ 新增：自動調用 AI 分析檔案內容並返回回應
    """
    try:
        file_bytes = await file.read()
        filename = file.filename
        file_ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        all_supported = SUPPORTED_EXTENSIONS['text'] + SUPPORTED_EXTENSIONS['document'] + SUPPORTED_EXTENSIONS['image']
        if file_ext not in all_supported:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的檔案格式。支援: {', '.join(all_supported)}"
            )
        
        logger.info(f"📤 收到檔案上傳: {filename} ({len(file_bytes)} bytes)")
        
        if file_ext in SUPPORTED_EXTENSIONS['text']:
            parsed_data = await parse_text_file(file_bytes, filename)
        elif file_ext == '.pdf':
            parsed_data = await parse_pdf_file(file_bytes)
        elif file_ext == '.docx':
            parsed_data = await parse_docx_file(file_bytes)
        elif file_ext in SUPPORTED_EXTENSIONS['image']:
            parsed_data = await analyze_image_with_vision(file_bytes, filename)
        else:
            parsed_data = {
                "content": "",
                "summary": "未知檔案類型",
                "type": "unknown",
                "parsed": False
            }
        
        try:
            storage_path = f"{conversation_id}/{filename}"
            supabase.storage.from_("uploads").upload(
                storage_path,
                file_bytes,
                {
                    "content-type": file.content_type or "application/octet-stream",
                    "upsert": "true"
                }
            )
            
            file_url = supabase.storage.from_("uploads").get_public_url(storage_path)
            logger.info(f"✅ 檔案已上傳到 Supabase Storage: {storage_path}")
            
        except Exception as e:
            logger.warning(f"⚠️ Supabase Storage 上傳失敗: {e}")
            file_url = None
        
        redis_key = f"upload:{conversation_id}:{filename}"
        redis_data = {
            "file_name": filename,
            "file_type": file_ext,
            "summary": parsed_data.get("summary", ""),
            "content": parsed_data.get("content", "")[:5000],
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_url": file_url,
            "parsed": parsed_data.get("parsed", False)
        }
        
        try:
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
                openai_client = get_openai_client()
                
                file_content = parsed_data.get("content", "")
                file_type = parsed_data.get("type", "unknown")
                
                if file_type == "image":
                    analysis_prompt = f"""我上傳了一張圖片「{filename}」。

圖片分析結果：
{file_content}

請用繁體中文簡短回應，告訴我你看到了什麼，以及你的想法或建議（不超過150字）。"""
                else:
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
            "temporary_key": redis_key,
            "file_url": file_url,
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
