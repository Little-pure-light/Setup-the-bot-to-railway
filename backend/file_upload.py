from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.supabase_handler import get_supabase
supabase = get_supabase()
import logging
router = APIRouter()
logger = logging.getLogger("file_upload")

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        file_name = file.filename

        # ✅ 上傳到 Supabase Storage（你的 bucket 名稱是 uploads）
        response = supabase.storage.from_("uploads").upload(file_name, file_bytes)

        if response.get("error"):
            logger.error(f"Upload failed: {response['error']['message']}")
            raise HTTPException(status_code=500, detail="Upload failed")

        return {"message": "File uploaded successfully", "filename": file_name}

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")


