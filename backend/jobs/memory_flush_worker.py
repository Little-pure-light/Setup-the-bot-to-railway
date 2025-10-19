"""
記憶刷寫工作器 - Memory Flush Worker
後台排程：將 Redis 短期記憶批量刷寫到 Supabase 長期儲存

執行策略：
1. 每 5 分鐘自動執行一次
2. 每次處理最多 100 筆記錄
3. 失敗重試機制（最多 3 次）
4. 不阻塞主 API 執行緒
"""
import asyncio
import os
import time
from typing import Dict, Any
from datetime import datetime

class MemoryFlushWorker:
    """記憶刷寫工作器"""
    
    def __init__(self, memory_core=None, interval_seconds: int = 300):
        """
        初始化工作器
        
        參數:
            memory_core: 記憶核心實例
            interval_seconds: 執行間隔（秒）
        """
        self.memory_core = memory_core
        self.interval_seconds = interval_seconds
        self.batch_size = int(os.getenv("MEMORY_FLUSH_BATCH_SIZE", "100"))
        self.max_retries = 3
        self.is_running = False
    
    async def start(self):
        """啟動工作器"""
        if not self.memory_core:
            print("❌ 記憶核心未初始化，無法啟動刷寫工作器")
            return
        
        print(f"🚀 記憶刷寫工作器已啟動（間隔: {self.interval_seconds}秒）")
        self.is_running = True
        
        while self.is_running:
            try:
                await self._flush_cycle()
            except Exception as e:
                print(f"❌ 刷寫循環錯誤: {e}")
            
            await asyncio.sleep(self.interval_seconds)
    
    def stop(self):
        """停止工作器"""
        print("⏹️ 停止記憶刷寫工作器...")
        self.is_running = False
    
    async def _flush_cycle(self):
        """執行一次刷寫循環"""
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"🔄 開始刷寫循環 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self.memory_core.flush_redis_to_supabase(
                    batch_size=self.batch_size
                )
                
                if result.get("success"):
                    flushed_count = result.get("flushed_count", 0)
                    failed_count = result.get("failed_count", 0)
                    
                    if flushed_count > 0:
                        print(f"✅ 成功刷寫 {flushed_count} 筆記錄")
                        if failed_count > 0:
                            print(f"⚠️ 失敗 {failed_count} 筆記錄")
                    else:
                        print("ℹ️ 沒有待刷寫記錄")
                    
                    break
                else:
                    error = result.get("error", "未知錯誤")
                    print(f"❌ 刷寫失敗（嘗試 {attempt}/{self.max_retries}）: {error}")
                    
                    if attempt < self.max_retries:
                        backoff_time = 2 ** (attempt - 1)
                        print(f"⏳ 等待 {backoff_time} 秒後重試...")
                        await asyncio.sleep(backoff_time)
                    else:
                        print("❌ 達到最大重試次數，放棄本次刷寫")
                
            except Exception as e:
                print(f"❌ 刷寫異常（嘗試 {attempt}/{self.max_retries}）: {e}")
                
                if attempt < self.max_retries:
                    backoff_time = 2 ** (attempt - 1)
                    await asyncio.sleep(backoff_time)
        
        elapsed_time = time.time() - start_time
        print(f"⏱️ 刷寫循環完成（耗時: {elapsed_time:.2f}秒）")
        print(f"{'='*60}\n")
    
    async def manual_flush(self) -> Dict[str, Any]:
        """
        手動觸發刷寫
        
        返回:
            刷寫結果
        """
        print("🔧 手動觸發記憶刷寫...")
        
        try:
            result = self.memory_core.flush_redis_to_supabase(
                batch_size=self.batch_size
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取工作器統計資訊
        
        返回:
            統計資訊
        """
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "batch_size": self.batch_size,
            "max_retries": self.max_retries
        }


def create_flush_worker(memory_core, interval_seconds: int = 300) -> MemoryFlushWorker:
    """
    創建刷寫工作器實例
    
    參數:
        memory_core: 記憶核心實例
        interval_seconds: 執行間隔（秒）
    
    返回:
        工作器實例
    """
    return MemoryFlushWorker(memory_core, interval_seconds)


async def run_worker_standalone():
    """
    獨立運行工作器（用於測試）
    """
    from backend.modules.memory.core import MemoryCore
    
    memory_core = MemoryCore()
    worker = create_flush_worker(memory_core, interval_seconds=60)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        print("\n👋 收到中斷信號")
        worker.stop()


if __name__ == "__main__":
    asyncio.run(run_worker_standalone())
