"""
🔍 自動測試驗證 — SemanticMemoryUploaderMini
說明：
本測試用來驗證 Pinata IPFS 上傳與 Google Sheets 寫入是否正常。
"""

import os
import sys
from datetime import datetime

# 確保可以導入專案模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ipfs_tools import upload_to_ipfs
from record_store import save_record
from summarizer import generate_summary


def run_tests():
    """執行所有測試"""
    print("🚀 開始自動測試 SemanticMemoryUploaderMini ...")
    print("=" * 60)
    
    try:
        # === 測試 1：檢查環境變數 ===
        print("\n【測試 1】檢查環境變數...")
        pinata = os.getenv("PINATA_JWT")
        sheet_id = os.getenv("SPREADSHEET_ID")
        svc = os.getenv("SERVICE_ACCOUNT_JSON")
        
        assert pinata, "❌ 缺少 PINATA_JWT"
        assert sheet_id, "❌ 缺少 SPREADSHEET_ID"
        assert svc, "❌ 缺少 SERVICE_ACCOUNT_JSON"
        print("✅ 環境變數檢查通過")
        
        # === 測試 2：摘要生成 ===
        print("\n【測試 2】測試摘要生成...")
        sample_text = """這是一段測試對話。
AI: 你好呀！今天過得如何？
Human: 很好，謝謝你的關心。
AI: 很高興聽到這個消息！有什麼我可以幫助你的嗎？
Human: 我想了解如何使用這個系統。"""
        
        summary = generate_summary(sample_text)
        assert len(summary) > 0, "❌ 摘要生成失敗"
        print(f"✅ 摘要生成通過：{summary[:50]}...")
        
        # === 測試 3：上傳到 IPFS ===
        print("\n【測試 3】測試上傳到 Pinata IPFS...")
        test_file = "test_memory.txt"
        
        # 建立測試檔案
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(sample_text)
        
        try:
            upload_result = upload_to_ipfs(test_file)
            assert "cid" in upload_result, "❌ IPFS 回傳缺少 CID"
            assert "gateway" in upload_result, "❌ IPFS 回傳缺少 Gateway URL"
            print(f"✅ 上傳成功！")
            print(f"   CID: {upload_result['cid']}")
            print(f"   Gateway: {upload_result['gateway'][:60]}...")
        finally:
            # 清理測試檔案
            if os.path.exists(test_file):
                os.remove(test_file)
        
        # === 測試 4：寫入 Google Sheets ===
        print("\n【測試 4】測試寫入 Google Sheets...")
        record = {
            "filename": "test_memory.txt",
            "summary": summary,
            "cid": upload_result["cid"],
            "gateway": upload_result["gateway"],
        }
        save_record(record)
        print("✅ Google Sheets 寫入成功")
        
        # === 完成 ===
        print("\n" + "=" * 60)
        print("🎉 全部測試通過，系統可正式使用！")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ 測試失敗：{str(e)}")
        print("\n💡 請檢查：")
        print("   1. 環境變數是否已在 Replit Secrets 中正確設定")
        print("   2. Pinata JWT 是否有效")
        print("   3. Google Sheets 是否已共用給服務帳號")
        return False
        
    except Exception as e:
        print(f"\n❌ 發生錯誤：{str(e)}")
        print("\n💡 請參閱「使用說明書.md」進行故障排除")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
