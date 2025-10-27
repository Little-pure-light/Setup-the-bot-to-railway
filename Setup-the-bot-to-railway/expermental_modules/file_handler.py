import os
from typing import Optional, Tuple
import mimetypes

async def handle_file(file_path: str, supabase_client, bucket_name: str = "files") -> Tuple[bool, str, Optional[str]]:
    """
    處理檔案上傳到 Supabase Storage
    
    Returns:
        Tuple[success: bool, message: str, file_url: Optional[str]]
    """
    try:
        if not os.path.exists(file_path):
            return False, "檔案不存在", None
        
        file_name = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        result = supabase_client.storage.from_(bucket_name).upload(
            file_name,
            file_data,
            file_options={"content-type": mime_type}
        )
        
        file_url = supabase_client.storage.from_(bucket_name).get_public_url(file_name)
        
        return True, f"檔案上傳成功: {file_name}", file_url
        
    except Exception as e:
        return False, f"檔案上傳失敗: {str(e)}", None

async def download_full_file(file_url: str, save_path: str) -> Tuple[bool, str]:
    """
    從 Supabase Storage 下載檔案
    
    Returns:
        Tuple[success: bool, message: str]
    """
    try:
        import requests
        
        response = requests.get(file_url)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return True, f"檔案下載成功: {save_path}"
        
    except Exception as e:
        return False, f"檔案下載失敗: {str(e)}"
