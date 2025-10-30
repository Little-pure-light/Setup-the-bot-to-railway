import os
from pinecone import Pinecone

# ✅ 使用新版 SDK 建立 Pinecone 實例
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# ✅ 列出所有索引
indexes = pc.list_indexes().names()

print("📂 目前索引清單：")
if indexes:
    for index in indexes:
        print(" -", index)
else:
    print("⚠️ 沒有找到任何索引，請確認你的帳號設定")

# ✅ 顯示索引詳細資料（選擇第一個測試）
if indexes:
    index_name = indexes[0]
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    print(f"\n📊 索引「{index_name}」的統計資訊：")
    print(stats)
