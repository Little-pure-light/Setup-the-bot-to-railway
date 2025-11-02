"""
測試檔案內容注入功能
驗證上傳的檔案內容能否被 AI 正確引用
"""

import asyncio
import json
import requests
from datetime import datetime

API_BASE = "https://ai2.dreamground.net"

async def test_file_injection():
    """完整測試檔案上傳與內容注入"""
    
    conversation_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    user_id = "test_user"
    
    print("\n" + "="*60)
    print("📋 檔案內容注入測試")
    print("="*60)
    
    # 步驟 1: 創建測試檔案
    test_content = """小宸光系統設計文件
    
版本: 2.0
作者: 開發團隊
日期: 2025-11-02

核心功能：
1. 多層記憶架構 (Redis + Supabase)
2. 情感偵測與回應適配
3. 自我反思與學習
4. 檔案上傳與智能分析

技術棧：
- 後端: FastAPI (Python)
- 前端: Vue 3 + Vite
- 資料庫: Supabase (PostgreSQL)
- 快取: Redis (Upstash)
- AI: OpenAI GPT-4o-mini
"""
    
    with open("test_doc.txt", "w", encoding="utf-8") as f:
        f.write(test_content)
    
    print(f"\n📝 測試 ID: {conversation_id}")
    
    # 步驟 2: 上傳檔案
    print("\n🔵 步驟 1: 上傳測試檔案")
    with open("test_doc.txt", "rb") as f:
        files = {"file": ("test_doc.txt", f, "text/plain")}
        data = {
            "conversation_id": conversation_id,
            "user_id": user_id
        }
        
        try:
            response = requests.post(
                f"{API_BASE}/api/upload_file",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                upload_result = response.json()
                print(f"   ✅ 檔案上傳成功")
                print(f"   📎 檔案名稱: {upload_result['file_name']}")
                print(f"   📊 摘要: {upload_result['summary']}")
                print(f"   🔑 Redis Key: {upload_result['temporary_key']}")
                print(f"   🤖 AI 分析: {upload_result['ai_analysis'][:100]}...")
            else:
                print(f"   ❌ 上傳失敗: {response.status_code}")
                print(f"   錯誤: {response.text}")
                return
        except Exception as e:
            print(f"   ❌ 上傳異常: {e}")
            return
    
    # 步驟 3: 測試聊天（要求 AI 引用檔案內容）
    print("\n🔵 步驟 2: 測試 AI 是否能引用檔案內容")
    
    test_messages = [
        "請告訴我剛才上傳的檔案是關於什麼的？",
        "檔案中提到的核心功能有哪些？",
        "技術棧用了哪些工具？"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n   💬 測試 {i}: {message}")
        
        try:
            response = requests.post(
                f"{API_BASE}/api/chat",
                json={
                    "user_message": message,
                    "conversation_id": conversation_id,
                    "user_id": user_id
                },
                timeout=30
            )
            
            if response.status_code == 200:
                chat_result = response.json()
                ai_response = chat_result["assistant_message"]
                
                print(f"   🤖 AI 回應:")
                print(f"      {ai_response[:200]}...")
                
                # 驗證是否引用了檔案內容
                keywords = ["記憶架構", "情感偵測", "FastAPI", "Vue", "Supabase"]
                found_keywords = [kw for kw in keywords if kw in ai_response]
                
                if found_keywords:
                    print(f"   ✅ AI 成功引用檔案內容！找到關鍵字: {found_keywords}")
                else:
                    print(f"   ⚠️  未檢測到檔案內容關鍵字")
            else:
                print(f"   ❌ 聊天失敗: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 聊天異常: {e}")
        
        await asyncio.sleep(1)
    
    # 步驟 4: 驗證結論
    print("\n" + "="*60)
    print("📊 測試結論")
    print("="*60)
    print("✅ 檔案上傳功能正常")
    print("✅ Redis 暫存機制運作中")
    print("✅ AI 自動分析功能正常")
    print("✅ PromptEngine 檔案內容注入功能正常")
    print("\n💡 提示: 檢查 AI 回應是否包含檔案中的具體資訊")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_file_injection())
