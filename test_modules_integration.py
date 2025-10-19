"""
模組整合測試腳本
驗證 CoreController 和各模組的載入與通信
"""
import asyncio
import sys
import os

# 確保可以導入 backend 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_core_controller():
    """測試核心控制器"""
    print("=" * 60)
    print("🧪 開始測試 CoreController 與模組整合")
    print("=" * 60)
    
    from backend.core_controller import get_core_controller
    
    # 1. 初始化控制器
    print("\n1️⃣ 初始化 CoreController...")
    controller = await get_core_controller()
    
    # 2. 檢查模組列表
    print("\n2️⃣ 檢查模組列表...")
    module_list = controller.get_module_list()
    print(f"   發現 {len(module_list)} 個模組配置:")
    for mod in module_list:
        status = "✅ 已載入" if mod["loaded"] else "❌ 未載入"
        enabled = "🟢 啟用" if mod["enabled"] else "⚪ 停用"
        print(f"   - {mod['name']} v{mod['version']} | {status} | {enabled}")
    
    # 3. 測試各模組健康檢查
    print("\n3️⃣ 測試模組健康檢查...")
    health = await controller.health_check_all()
    print(f"   控制器狀態: {health['controller']}")
    print(f"   已載入模組: {health['total_modules']}/{len(module_list)}")
    print(f"   已啟用模組: {health.get('enabled_modules', 0)}")
    
    for name, status in health['modules'].items():
        print(f"   - {name}: {status.get('status', 'unknown')}")
    
    # 4. 測試記憶模組
    print("\n4️⃣ 測試記憶模組功能...")
    try:
        memory_module = await controller.get_module("memory")
        if memory_module:
            # 測試 Token 化
            result = await memory_module.process({
                "operation": "tokenize_text",
                "text": "你好，這是一個測試訊息！"
            })
            if result.get("success"):
                tokens_data = result.get("tokens_data", {})
                print(f"   ✅ Token 化成功:")
                print(f"      - 方法: {tokens_data.get('method')}")
                print(f"      - Token 數量: {tokens_data.get('total_count')}")
            else:
                print(f"   ❌ Token 化失敗: {result.get('error')}")
            
            # 測試對話儲存
            result = await memory_module.process({
                "operation": "store_conversation",
                "conversation_id": "test_conv_001",
                "user_message": "測試訊息",
                "assistant_message": "測試回覆",
                "reflection": "這是一個測試"
            })
            if result.get("success"):
                print(f"   ✅ 對話儲存成功")
                print(f"      - Redis Key: {result.get('redis_key')}")
            else:
                print(f"   ❌ 對話儲存失敗: {result.get('error')}")
        else:
            print("   ⚠️ 記憶模組未載入")
    except Exception as e:
        print(f"   ❌ 測試記憶模組時發生錯誤: {e}")
    
    # 5. 測試反思模組
    print("\n5️⃣ 測試反思模組功能...")
    try:
        reflection_module = await controller.get_module("reflection")
        if reflection_module:
            result = await reflection_module.process({
                "user_message": "什麼是 AI？",
                "assistant_message": "AI 是人工智慧。",
                "emotion_analysis": {"dominant_emotion": "neutral", "intensity": 0.5}
            })
            if result.get("success"):
                reflection = result.get("reflection", {})
                print(f"   ✅ 反思分析成功:")
                print(f"      - 摘要: {reflection.get('summary')}")
                print(f"      - 原因: {reflection.get('causes')}")
            else:
                print(f"   ❌ 反思分析失敗: {result.get('error')}")
        else:
            print("   ⚠️ 反思模組未載入")
    except Exception as e:
        print(f"   ❌ 測試反思模組時發生錯誤: {e}")
    
    # 6. 測試行為模組
    print("\n6️⃣ 測試行為調節模組...")
    try:
        behavior_module = await controller.get_module("behavior")
        if behavior_module:
            result = await behavior_module.process({
                "reflection": {"causes": ["缺少實例"]},
                "emotion_analysis": {"dominant_emotion": "joy", "intensity": 0.8}
            })
            if result.get("success"):
                personality = result.get("personality_vector", {})
                print(f"   ✅ 行為調節成功:")
                print(f"      - 人格向量: {personality}")
            else:
                print(f"   ❌ 行為調節失敗: {result.get('error')}")
        else:
            print("   ⚠️ 行為調節模組未載入")
    except Exception as e:
        print(f"   ❌ 測試行為模組時發生錯誤: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 測試完成！")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_core_controller())
