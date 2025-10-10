from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import sys
import os
import aiofiles
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.supabase_handler import get_supabase_client
from modules.file_handler import handle_file

router = APIRouter()

class FileUploadResponse(BaseModel):
    success: bool
    message: str
    file_url: str = None
    file_name: str = None

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...)
):
    """處理檔案上傳到 Supabase Storage"""
    try:
        temp_file_path = f"/tmp/{file.filename}"
        
        async with aiofiles.open(temp_file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        supabase = get_supabase_client()
        
        success, message, file_url = await handle_file(
            temp_file_path, 
            supabase, 
            bucket_name="files"
        )
        
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if success:
            return FileUploadResponse(
                success=True,
                message=message,
                file_url=file_url,
                file_name=file.filename
            )
        else:
            raise HTTPException(status_code=500, detail=message)
            
    except Exception as e:
        print(f"❌ File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
