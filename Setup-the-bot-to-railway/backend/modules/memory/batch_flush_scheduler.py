"""
批次刷寫排程器 - Batch Flush Scheduler
自動將 Redis 短期記憶批次刷寫到 Supabase 長期儲存

使用方式：
1. 方法A：獨立執行（適合背景任務）
   python batch_flush_scheduler.py

2. 方法B：整合到主程式
   from modules.memory.batch_flush_scheduler import start_flush_scheduler
   start_flush_scheduler(memory_core, interval_minutes=5)
"""

import time
import schedule
from typing import Optional
from datetime import datetime

def batch_flush_job(memory_core):
    """
    批次刷寫任務
    
    參數:
        memory_core: MemoryCore 實例
    """
    try:
        print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 開始批次刷寫...")
        
        # 先檢查待刷寫隊列長度
        stats = memory_core.redis.get_stats()
        pending_count = stats.get("pending_queue_length", 0)
        
        if pending_count == 0:
            print("   ℹ️  沒有待刷寫記錄，跳過本次刷寫")
            return
        
        print(f"   📊 待刷寫記錄：{pending_count} 筆")
        
        # 執行批次刷寫
        result = memory_core.flush_redis_to_supabase(batch_size=200)
        
        if result.get("success"):
            flushed = result.get("flushed_count", 0)
            failed = result.get("failed_count", 0)
            
            if flushed > 0:
                print(f"   ✅ 成功刷寫：{flushed} 筆")
            
            if failed > 0:
                print(f"   ⚠️  失敗：{failed} 筆")
        else:
            error = result.get("error", "未知錯誤")
            print(f"   ❌ 刷寫失敗：{error}")
    
    except Exception as e:
        print(f"   ❌ 批次刷寫任務異常：{e}")

def start_flush_scheduler(
    memory_core, 
    interval_minutes: int = 5,
    batch_size: int = 200
):
    """
    啟動批次刷寫排程器
    
    參數:
        memory_core: MemoryCore 實例
        interval_minutes: 刷寫間隔（分鐘）
        batch_size: 每批次刷寫筆數
    """
    print(f"🚀 批次刷寫排程器已啟動")
    print(f"   ⏱️  刷寫間隔：每 {interval_minutes} 分鐘")
    print(f"   📦 批次大小：{batch_size} 筆/次")
    print(f"   🔄 Redis TTL：{memory_core.redis.ttl_seconds} 秒")
    print(f"   ⏸️  按 Ctrl+C 停止\n")
    
    # 註冊定時任務
    schedule.every(interval_minutes).minutes.do(
        lambda: batch_flush_job(memory_core)
    )
    
    # 立即執行一次
    batch_flush_job(memory_core)
    
    # 循環執行
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # 每 30 秒檢查一次
    except KeyboardInterrupt:
        print("\n\n⏹️  批次刷寫排程器已停止")

# ============================================
# 獨立執行模式
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧠 小宸光記憶系統 - 批次刷寫排程器")
    print("=" * 60)
    
    # 初始化記憶核心
    try:
        from backend.modules.memory.core import MemoryCore
        from backend.supabase_handler import supabase
        import redis
        import os
        
        # 初始化 Redis 客戶端
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url)
        
        # 初始化記憶核心
        memory_core = MemoryCore(
            redis_client=redis_client,
            supabase_client=supabase
        )
        
        # 啟動排程器（每 5 分鐘刷寫一次）
        start_flush_scheduler(
            memory_core=memory_core,
            interval_minutes=5,
            batch_size=200
        )
        
    except Exception as e:
        print(f"❌ 初始化失敗：{e}")
        print("\n請確認：")
        print("1. Redis 服務已啟動")
        print("2. Supabase 連接正常")
        print("3. 環境變數已設定（REDIS_URL, SUPABASE_URL, SUPABASE_KEY）")
