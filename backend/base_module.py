"""
模組基礎介面定義
所有模組都需繼承此基類並實作必要方法
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json

class BaseModule(ABC):
    """模組基礎類別"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        self.module_name = module_name
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.version = self.config.get("version", "1.0.0")
        self.description = self.config.get("description", "")
        self._initialized = False
    
    @abstractmethod
    async def load(self) -> bool:
        """
        模組載入時調用
        返回 True 表示載入成功，False 表示失敗
        """
        pass
    
    @abstractmethod
    async def unload(self) -> bool:
        """
        模組卸載時調用
        返回 True 表示卸載成功，False 表示失敗
        """
        pass
    
    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行模組邏輯
        
        參數:
            data: 輸入數據字典
        
        返回:
            處理後的數據字典
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回:
            健康狀態字典
        """
        return {
            "module": self.module_name,
            "status": "healthy" if self._initialized else "not_initialized",
            "enabled": self.enabled,
            "version": self.version
        }
    
    def get_info(self) -> Dict[str, Any]:
        """
        獲取模組資訊
        
        返回:
            模組資訊字典
        """
        return {
            "name": self.module_name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
            "initialized": self._initialized,
            "config": self.config
        }
    
    def _log(self, level: str, message: str):
        """內部日誌方法"""
        print(f"[{level.upper()}] [{self.module_name}] {message}")
    
    def log_info(self, message: str):
        """記錄資訊日誌"""
        self._log("info", message)
    
    def log_warning(self, message: str):
        """記錄警告日誌"""
        self._log("warning", message)
    
    def log_error(self, message: str):
        """記錄錯誤日誌"""
        self._log("error", message)


class ModuleConfig:
    """模組配置管理類別"""
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        從 JSON 檔案載入配置
        
        參數:
            config_path: 配置檔案路徑
        
        返回:
            配置字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ 配置檔案不存在: {config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ 配置檔案格式錯誤: {e}")
            return {}
    
    @staticmethod
    def save_config(config_path: str, config: Dict[str, Any]) -> bool:
        """
        儲存配置到 JSON 檔案
        
        參數:
            config_path: 配置檔案路徑
            config: 配置字典
        
        返回:
            是否儲存成功
        """
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ 儲存配置失敗: {e}")
            return False
