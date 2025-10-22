"""
🔍 Pinata API 診斷工具
幫你找出 Pinata 錯誤的真正原因
"""

import os
import requests
import tempfile

def diagnose_pinata():
    """完整診斷 Pinata API 問題"""
    
    print("=" * 60)
    print("🔍 Pinata API 診斷工具")
    print("=" * 60)
    print()
    
    # 步驟 1：檢查 JWT 是否存在
    print("步驟 1：檢查 PINATA_JWT 環境變數")
    print("-" * 60)
    
    pinata_jwt = os.getenv("PINATA_JWT")
    
    if not pinata_jwt:
        print("❌ 錯誤：找不到 PINATA_JWT 環境變數")
        print("💡 請先在 Replit Secrets 中設定 PINATA_JWT")
        return
    
    print(f"✅ 找到 JWT（長度：{len(pinata_jwt)} 字元）")
    print(f"   開頭：{pinata_jwt[:20]}...")
    print(f"   結尾：...{pinata_jwt[-20:]}")
    print()
    
    # 步驟 2：檢查 JWT 格式
    print("步驟 2：檢查 JWT 格式")
    print("-" * 60)
    
    # JWT 應該有兩個點號（三個部分）
    if pinata_jwt.count('.') == 2:
        print("✅ JWT 格式看起來正確（包含 3 個部分）")
    else:
        print(f"⚠️ 警告：JWT 格式可能不正確（包含 {pinata_jwt.count('.') + 1} 個部分，應該是 3 個）")
    
    # 檢查是否有多餘的空格或換行
    if pinata_jwt != pinata_jwt.strip():
        print("⚠️ 警告：JWT 前後有多餘的空格或換行符號")
        print("💡 請重新複製 JWT，確保沒有多餘的空格")
    else:
        print("✅ JWT 沒有多餘的空格")
    
    print()
    
    # 步驟 3：測試 Pinata API 連線
    print("步驟 3：測試 Pinata API 連線")
    print("-" * 60)
    
    # 建立測試檔案
    test_content = "這是測試檔案，用來診斷 Pinata API 問題。\nHello from Pinata Diagnosis Tool! 🔍"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
        tmp_file.write(test_content)
        tmp_file_path = tmp_file.name
    
    try:
        # 上傳測試檔案
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        
        headers = {
            "Authorization": f"Bearer {pinata_jwt.strip()}"
        }
        
        print(f"📤 正在上傳測試檔案到 Pinata...")
        print(f"   API 端點：{url}")
        print(f"   授權標頭：Bearer {pinata_jwt.strip()[:20]}...")
        print()
        
        with open(tmp_file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(url, headers=headers, files=files, timeout=30)
        
        print(f"📊 API 回應狀態碼：{response.status_code}")
        print()
        
        # 分析回應
        if response.status_code == 200:
            print("🎉 成功！Pinata API 正常運作！")
            print()
            data = response.json()
            print("回應內容：")
            print(f"  - IPFS Hash (CID)：{data.get('IpfsHash')}")
            print(f"  - 檔案大小：{data.get('PinSize')} bytes")
            print(f"  - 時間戳記：{data.get('Timestamp')}")
            print()
            print(f"🌐 Gateway URL：https://gateway.pinata.cloud/ipfs/{data.get('IpfsHash')}")
            print()
            print("✅ 診斷結論：你的 Pinata 設定完全正確！")
            
        elif response.status_code == 401:
            print("❌ 錯誤：授權失敗（401 Unauthorized）")
            print()
            print("可能的原因：")
            print("  1. JWT Token 無效或已過期")
            print("  2. JWT Token 複製時有誤（多餘空格、換行等）")
            print("  3. JWT Token 權限不足")
            print()
            print("解決方法：")
            print("  1. 登入 Pinata 網站（https://app.pinata.cloud/）")
            print("  2. 前往 API Keys 頁面")
            print("  3. 刪除舊的 API Key，建立一個新的")
            print("  4. 複製新的 JWT Token（確保完整複製，不要有空格）")
            print("  5. 在 Replit Secrets 中更新 PINATA_JWT")
            print()
            print("📋 API 回應內容：")
            print(response.text)
            
        elif response.status_code == 403:
            print("❌ 錯誤：權限被拒絕（403 Forbidden）")
            print()
            print("可能的原因：")
            print("  1. API Key 權限設定不正確")
            print("  2. 帳號額度已用完（免費帳號有上傳限制）")
            print()
            print("解決方法：")
            print("  1. 檢查 Pinata 帳號的使用額度")
            print("  2. 確認 API Key 有 'pinFileToIPFS' 權限")
            print()
            print("📋 API 回應內容：")
            print(response.text)
            
        else:
            print(f"❌ 錯誤：API 回傳錯誤（狀態碼 {response.status_code}）")
            print()
            print("📋 完整 API 回應內容：")
            print(response.text)
            print()
            print("💡 建議：")
            print("  1. 複製上面的錯誤訊息")
            print("  2. 告訴我這個錯誤訊息，我來幫你解決")
    
    except requests.exceptions.Timeout:
        print("❌ 錯誤：連線超時")
        print("💡 可能是網路問題，請稍後再試")
        
    except requests.exceptions.ConnectionError:
        print("❌ 錯誤：無法連線到 Pinata API")
        print("💡 請檢查網路連線")
        
    except Exception as e:
        print(f"❌ 未預期的錯誤：{str(e)}")
        print(f"   錯誤類型：{type(e).__name__}")
    
    finally:
        # 清理測試檔案
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
    
    print()
    print("=" * 60)
    print("診斷完成")
    print("=" * 60)


if __name__ == "__main__":
    diagnose_pinata()
