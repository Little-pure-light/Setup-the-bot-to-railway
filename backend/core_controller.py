"""
核心控制器 - 模組管理與通信中心
負責所有模組的註冊、載入、卸載與通信
"""
import os
import json
import importlib
from typing import Dict, Any, Optional, List
from backend.base_module import BaseModule, ModuleConfig

class CoreController:
    """核心控制器類別"""
    
    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        self.module_configs: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    async def initialize(self):
        """初始化核心控制器"""
        if self._initialized:
            print("⚠️ CoreController 已經初始化")
            return
        
        print("🚀 初始化 CoreController...")
        
        # 掃描並載入所有模組配置
        await self._scan_modules()
        
        # 載入啟用的模組
        await self._load_enabled_modules()
        
        self._initialized = True
        print(f"✅ CoreController 初始化完成，已載入 {len(self.modules)} 個模組")
    
    async def _scan_modules(self):
        """掃描所有模組目錄並載入配置"""
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 定義模組目錄與類別對應
        module_mapping = {
            "memory_module": ("memory_module.main", "MemoryModule"),
            "reflection_module": ("reflection_module.main", "ReflectionModule"),
            "knowledge_hub": ("knowledge_hub.main", "KnowledgeHub"),
            "behavior_module": ("behavior_module.main", "BehaviorModule"),
            "finetune_module": ("finetune_module.main", "FineTuneModule")
        }
        
        for module_dir, (module_path, class_name) in module_mapping.items():
            config_path = os.path.join(backend_dir, module_dir, "config.json")
            
            if os.path.exists(config_path):
                config = ModuleConfig.load_config(config_path)
                if config:
                    module_name = config.get("name", module_dir)
                    config["_module_path"] = f"backend.{module_path}"
                    config["_class_name"] = class_name
                    self.module_configs[module_name] = config
                    print(f"📦 發現模組配置: {module_name} v{config.get('version', 'unknown')}")
    
    async def _load_enabled_modules(self):
        """載入所有啟用的模組"""
        for module_name, config in self.module_configs.items():
            if config.get("enabled", False):
                try:
                    await self.load_module(module_name, config)
                except Exception as e:
                    print(f"❌ 載入模組 {module_name} 失敗: {e}")
    
    async def load_module(self, module_name: str, config: Dict[str, Any]) -> bool:
        """
        載入單一模組
        
        參數:
            module_name: 模組名稱
            config: 模組配置
        
        返回:
            是否載入成功
        """
        try:
            print(f"📥 正在載入模組: {module_name}")
            
            # 取得模組路徑與類別名稱
            module_path = config.get("_module_path")
            class_name = config.get("_class_name")
            
            if not module_path or not class_name:
                print(f"⚠️ 模組 {module_name} 配置缺少路徑或類別名稱")
                return False
            
            # 動態導入模組
            module = importlib.import_module(module_path)
            module_class = getattr(module, class_name)
            
            # 建立模組實例
            module_instance = module_class(module_name, config)
            
            # 載入模組
            load_success = await module_instance.load()
            
            if load_success:
                self.modules[module_name] = module_instance
                print(f"✅ 模組 {module_name} 已成功載入並註冊")
                return True
            else:
                print(f"⚠️ 模組 {module_name} 載入失敗")
                return False
            
        except Exception as e:
            print(f"❌ 載入模組 {module_name} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def unload_module(self, module_name: str) -> bool:
        """
        卸載單一模組
        
        參數:
            module_name: 模組名稱
        
        返回:
            是否卸載成功
        """
        if module_name not in self.modules:
            print(f"⚠️ 模組 {module_name} 不存在")
            return False
        
        try:
            module = self.modules[module_name]
            await module.unload()
            del self.modules[module_name]
            print(f"✅ 模組 {module_name} 已卸載")
            return True
        except Exception as e:
            print(f"❌ 卸載模組 {module_name} 失敗: {e}")
            return False
    
    async def get_module(self, module_name: str) -> Optional[BaseModule]:
        """
        獲取模組實例
        
        參數:
            module_name: 模組名稱
        
        返回:
            模組實例或 None
        """
        return self.modules.get(module_name)
    
    async def process_data(self, module_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        通過指定模組處理數據
        
        參數:
            module_name: 模組名稱
            data: 輸入數據
        
        返回:
            處理後的數據
        """
        module = await self.get_module(module_name)
        if not module:
            return {"error": f"模組 {module_name} 不存在"}
        
        try:
            return await module.process(data)
        except Exception as e:
            return {"error": f"處理數據時發生錯誤: {str(e)}"}
    
    async def dispatch(self, module_name: str, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        派發任務到指定模組
        
        參數:
            module_name: 模組名稱
            operation: 操作名稱
            data: 輸入數據
        
        返回:
            處理結果
        """
        data["operation"] = operation
        return await self.process_data(module_name, data)
    
    async def health_check_all(self) -> Dict[str, Any]:
        """
        檢查所有模組的健康狀態
        
        返回:
            所有模組的健康狀態
        """
        health_status = {
            "controller": "healthy" if self._initialized else "not_initialized",
            "total_modules": len(self.modules),
            "enabled_modules": sum(1 for m in self.modules.values() if m.enabled),
            "modules": {}
        }
        
        for module_name, module in self.modules.items():
            try:
                health_status["modules"][module_name] = await module.health_check()
            except Exception as e:
                health_status["modules"][module_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return health_status
    
    def get_module_list(self) -> List[Dict[str, Any]]:
        """
        獲取所有已註冊模組的資訊列表
        
        返回:
            模組資訊列表
        """
        return [
            {
                "name": name,
                "config": config,
                "loaded": name in self.modules,
                "enabled": config.get("enabled", False),
                "version": config.get("version", "unknown")
            }
            for name, config in self.module_configs.items()
        ]


# 全局單例
_core_controller_instance: Optional[CoreController] = None

async def get_core_controller() -> CoreController:
    """獲取核心控制器實例（單例模式）"""
    global _core_controller_instance
    if _core_controller_instance is None:
        _core_controller_instance = CoreController()
        await _core_controller_instance.initialize()
    return _core_controller_instance
