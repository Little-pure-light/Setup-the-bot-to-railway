from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.supabase_handler import supabase
import logging

router = APIRouter()
logger = logging.getLogger("file_upload")

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # 將檔案內容讀取為 bytes
        file_bytes = await file.read()
        file_name = file.filename

        # 使用 Supabase Storage 上傳
        response = supabase.storage.from_("uploads").upload(file_name, file_bytes)

        if response.get("error"):
            logger.error(f"Upload failed: {response['error']['message']}")
            raise HTTPException(status_code=500, detail="Upload failed")

        return {"message": "Upload successful", "path": response["data"]["path"]}
    
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(e))
