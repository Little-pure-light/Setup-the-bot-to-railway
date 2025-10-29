#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()

redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_ENDPOINT")

# 自動修正：將 redis:// 改成 rediss://（啟用 SSL）
if redis_url and redis_url.startswith("redis://"):
    redis_url_ssl = redis_url.replace("redis://", "rediss://", 1)
    print(f"📍 原始 URL: redis://...")
    print(f"✨ 修正為: rediss://...")
else:
    redis_url_ssl = redis_url

if redis_url_ssl:
    try:
        import redis
        r = redis.from_url(redis_url_ssl, decode_responses=True)
        r.ping()
        print("✅ PING 成功！")
        r.set("test:xiaochenguang", "test:value", ex=60)
        print("✅ 寫入成功！")
        val = r.get("test:xiaochenguang")
        print(f"✅ 讀取成功！Value: {val}")
        r.delete("test:xiaochenguang")
        print("🎉 Redis 連接測試成功！")
        print("\n💡 解決方案：將 REDIS_ENDPOINT 中的 'redis://' 改成 'rediss://'")
    except Exception as e:
        print(f"❌ 失敗：{type(e).__name__}: {e}")
else:
    print("❌ REDIS_URL/ENDPOINT 未設定")
