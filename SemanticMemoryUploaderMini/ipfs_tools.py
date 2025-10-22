"""
📦 Pinata IPFS 上傳工具
功能：將檔案上傳到 Pinata IPFS 服務
需要：PINATA_JWT 環境變數
"""

import os
import requests
from typing import Dict


def upload_to_ipfs(file_path: str) -> Dict[str, str]:
    """
    上傳檔案到 Pinata IPFS
    
    參數:
        file_path: 要上傳的檔案路徑
    
    回傳:
        包含 CID 和 Gateway URL 的字典
        格式：{"cid": "Qmxxxx", "gateway": "https://gateway.pinata.cloud/ipfs/Qmxxxx"}
    
    錯誤:
        如果 JWT 無效或 API 回傳錯誤，會拋出 RuntimeError
    """
    # 從環境變數取得 Pinata JWT
    pinata_jwt = os.getenv("PINATA_JWT")
    
    if not pinata_jwt:
        raise RuntimeError("❌ 錯誤：缺少 PINATA_JWT 環境變數。請先設定 Pinata 的 JWT Token。")
    
    # 檢查檔案是否存在
    if not os.path.exists(file_path):
        raise RuntimeError(f"❌ 錯誤：找不到檔案 {file_path}")
    
    # Pinata API 端點
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    
    # 設定請求標頭
    headers = {
        "Authorization": f"Bearer {pinata_jwt}"
    }
    
    try:
        # 開啟檔案並上傳
        with open(file_path, 'rb') as file:
            files = {'file': file}
            
            print(f"📤 正在上傳檔案到 Pinata IPFS...")
            response = requests.post(url, headers=headers, files=files)
        
        # 檢查回應狀態
        if response.status_code != 200:
            error_msg = response.text
            raise RuntimeError(f"❌ Pinata API 錯誤（狀態碼 {response.status_code}）：{error_msg}")
        
        # 解析回應
        data = response.json()
        cid = data.get("IpfsHash")
        
        if not cid:
            raise RuntimeError(f"❌ API 回應缺少 CID：{data}")
        
        # 建立 Gateway URL
        gateway_url = f"https://gateway.pinata.cloud/ipfs/{cid}"
        
        print(f"✅ 上傳成功！CID: {cid}")
        
        return {
            "cid": cid,
            "gateway": gateway_url
        }
    
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ 網路錯誤：{str(e)}")


if __name__ == "__main__":
    # 簡單測試（需要先設定 PINATA_JWT 環境變數）
    print("📦 Pinata IPFS 上傳工具測試")
    print("提示：請先在 Secrets 中設定 PINATA_JWT")
