"""Persistence root inspection (Gate 1).

目的：讓「data/ 根目錄有沒有真的掛在 Railway 持久卷上」可被客觀、去敏地驗證，
杜絕「重部署掉記憶」被假成功掩蓋。

核心信號 = **mount 偵測**（`st_dev` 比對）：
  Railway persistent volume 會以獨立檔案系統掛在某個 mount path。若 volume 掛在 data/ 根，
  則 data/ 的裝置編號（st_dev）會與其父目錄（容器暫時層）不同 → 判定 "volume"。
  若無掛卷，data/ 與父目錄同屬容器暫時層、st_dev 相同 → 判定 "ephemeral"。
  這是單次開機即可判定、不需跨啟動狀態的可靠信號；且只比較整數 st_dev，
  從不外流檔案內容、secret 或使用者資料。

注意：偵測前提是 volume 掛在「data/ 根」本身（見 Runbook）。若誤掛在其父層（例如整個 /app），
data/ 會與父目錄同 st_dev 而被標為 ephemeral —— 這是保守（不假成功）的失敗方向。

去敏原則：本模組回傳的 root 為容器內檔案系統路徑（非機密），以及布林／固定字串；
不回傳任何檔案內容、環境變數值、secret 或使用者識別資訊。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# 固定探測檔名（啟動時寫入後即刪除；絕不含機密內容）
_WRITE_PROBE_NAME = ".persistence_write_probe"


def data_root() -> Path:
    """持久化根目錄（Railway 持久卷應掛載於此）。

    解析順序：
      1. 環境變數 PERSISTENCE_DATA_ROOT（若設定）。
      2. 預設 <repo_root>/data —— 以程式碼位置錨定（parents[2]），與 CWD 無關，
         與 identity_engine / graph_manager / night_growth_safety / token_counter 的
         data/ 預設根一致。
    """
    env = (os.getenv("PERSISTENCE_DATA_ROOT") or "").strip()
    if env:
        return Path(env)
    # backend/modules/persistence.py -> parents[2] = repo root
    return Path(__file__).resolve().parents[2] / "data"


def _is_separate_mount(path: Path) -> bool:
    """path 是否位於與其父目錄不同的裝置（= 有獨立卷掛在 path）。

    只比較 os.stat().st_dev 整數；任何錯誤一律回 False（保守：不假成功）。
    """
    try:
        p = path.resolve()
        parent = p.parent
        return os.stat(p).st_dev != os.stat(parent).st_dev
    except Exception:
        return False


def _writable(path: Path) -> bool:
    """去敏可寫檢查：實際寫入固定探測檔再刪除；只回布林，不外流任何內容。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / _WRITE_PROBE_NAME
        probe.write_text("ok", encoding="utf-8")
        try:
            probe.unlink()
        except Exception:
            pass
        return True
    except Exception:
        return False


def persistence_status(*, probe_write: bool = False) -> Dict[str, Any]:
    """回傳持久化根目錄的去敏狀態。

    probe_write=False（預設，供高頻 /ready 用）：可寫性以 os.access 估計，不做任何寫入。
    probe_write=True（供啟動檢查用）：實際寫入固定探測檔驗證可寫。

    mode 判定：
      - exists 且為獨立 mount → "volume"
      - exists 但非獨立 mount → "ephemeral"
      - 不存在或無法判定 → "unknown"
    """
    root = data_root()
    exists = False
    try:
        exists = root.exists()
    except Exception:
        exists = False

    is_mount = _is_separate_mount(root) if exists else False

    if probe_write:
        writable = _writable(root)
        # _writable 可能建立了目錄；重新確認 exists
        try:
            exists = root.exists()
        except Exception:
            pass
        is_mount = _is_separate_mount(root) if exists else is_mount
    else:
        try:
            writable = bool(exists and os.access(root, os.W_OK))
        except Exception:
            writable = False

    if not exists:
        mode = "unknown"
    elif is_mount:
        mode = "volume"
    else:
        mode = "ephemeral"

    return {
        "mode": mode,
        "root": str(root),
        "exists": exists,
        "writable": writable,
        "is_mount": is_mount,
    }


def ensure_persistence_root() -> Dict[str, Any]:
    """啟動用：建立 data/ 根（若不存在）並以實際寫入驗證可寫；回傳去敏狀態。

    永不拋例外（fail-open）：即使建立/寫入失敗，也只回報狀態，讓服務照常啟動、
    退回既有暫時磁碟行為（與掛卷前現況一致）。
    """
    root = data_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return persistence_status(probe_write=True)
