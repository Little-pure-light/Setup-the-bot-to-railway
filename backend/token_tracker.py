"""
Token 使用量監控與成本控制

- 記錄每次 OpenAI 呼叫的 input/output token 與估算成本
- 提供每日 / 使用者預算上限檢查
- 記憶體 + JSONL 持久化（可選 Redis）
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("token_tracker")

# USD per 1M tokens（約略定價，可用環境變數覆寫）
DEFAULT_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "omni-moderation-latest": {"input": 0.0, "output": 0.0},
    "text-moderation-latest": {"input": 0.0, "output": 0.0},
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return date.today().isoformat()


def estimate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """依模型定價估算成本（USD）。"""
    pricing = DEFAULT_MODEL_PRICING.get(model) or DEFAULT_MODEL_PRICING.get(
        model.split("-")[0] if model else "",
        {"input": 0.15, "output": 0.60},
    )
    # 允許環境變數覆寫：PRICE_GPT_4O_MINI_INPUT 等（可選，簡化只讀通用）
    input_price = float(os.getenv(f"PRICE_{model.replace('-', '_').replace('.', '_').upper()}_INPUT", pricing["input"]))
    output_price = float(os.getenv(f"PRICE_{model.replace('-', '_').replace('.', '_').upper()}_OUTPUT", pricing["output"]))
    cost = (prompt_tokens / 1_000_000.0) * input_price + (
        completion_tokens / 1_000_000.0
    ) * output_price
    return round(cost, 8)


def usage_from_openai(usage_obj: Any) -> Dict[str, int]:
    """從 OpenAI usage 物件抽出 token 數。"""
    if usage_obj is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if isinstance(usage_obj, dict):
        p = int(usage_obj.get("prompt_tokens") or usage_obj.get("input_tokens") or 0)
        c = int(usage_obj.get("completion_tokens") or usage_obj.get("output_tokens") or 0)
        t = int(usage_obj.get("total_tokens") or (p + c))
        return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": t}
    p = int(getattr(usage_obj, "prompt_tokens", 0) or getattr(usage_obj, "input_tokens", 0) or 0)
    c = int(getattr(usage_obj, "completion_tokens", 0) or getattr(usage_obj, "output_tokens", 0) or 0)
    t = int(getattr(usage_obj, "total_tokens", 0) or (p + c))
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": t}


class TokenTracker:
    def __init__(self, storage_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._records: List[Dict[str, Any]] = []
        default_path = Path(__file__).resolve().parents[1] / "data" / "token_usage.jsonl"
        self.storage_path = Path(storage_path or os.getenv("TOKEN_USAGE_LOG", str(default_path)))
        self.daily_budget_usd = float(os.getenv("DAILY_TOKEN_BUDGET_USD", "10.0"))
        self.user_daily_budget_usd = float(os.getenv("USER_DAILY_TOKEN_BUDGET_USD", "2.0"))
        self._load_today()

    def _load_today(self) -> None:
        """啟動時載入今日紀錄（若有檔案）。"""
        try:
            if not self.storage_path.exists():
                return
            today = _today_str()
            with self.storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(row.get("day") or "") == today:
                        self._records.append(row)
            logger.info(f"✅ TokenTracker 載入今日紀錄 {len(self._records)} 筆")
        except Exception as e:
            logger.warning(f"⚠️ TokenTracker 載入失敗: {e}")

    def _append_file(self, row: Dict[str, Any]) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"⚠️ Token 用量寫檔失敗: {e}")

    def record(
        self,
        *,
        user_id: str,
        conversation_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        endpoint: str = "chat",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """記錄一次 API 呼叫用量。"""
        p = int(prompt_tokens or 0)
        c = int(completion_tokens or 0)
        t = int(total_tokens if total_tokens is not None else (p + c))
        cost = (
            float(cost_usd)
            if cost_usd is not None
            else estimate_cost_usd(model, p, c)
        )
        row = {
            "id": str(uuid.uuid4()),
            "ts": _utc_now_iso(),
            "day": _today_str(),
            "user_id": user_id or "default_user",
            "conversation_id": conversation_id or "",
            "model": model or "unknown",
            "endpoint": endpoint,
            "prompt_tokens": p,
            "completion_tokens": c,
            "total_tokens": t,
            "cost_usd": cost,
            "meta": meta or {},
        }
        with self._lock:
            self._records.append(row)
            # 只保留最近 5000 筆在記憶體
            if len(self._records) > 5000:
                self._records = self._records[-5000:]
        self._append_file(row)
        logger.info(
            f"📊 Token usage user={row['user_id'][:8]}... model={model} "
            f"in={p} out={c} cost=${cost:.6f}"
        )
        return row

    def record_from_openai_usage(
        self,
        *,
        user_id: str,
        conversation_id: str,
        model: str,
        usage_obj: Any,
        endpoint: str = "chat",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        u = usage_from_openai(usage_obj)
        return self.record(
            user_id=user_id,
            conversation_id=conversation_id,
            model=model,
            prompt_tokens=u["prompt_tokens"],
            completion_tokens=u["completion_tokens"],
            total_tokens=u["total_tokens"],
            endpoint=endpoint,
            meta=meta,
        )

    def _filter_today(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        today = _today_str()
        with self._lock:
            rows = [r for r in self._records if r.get("day") == today]
        if user_id:
            rows = [r for r in rows if r.get("user_id") == user_id]
        return rows

    def summarize(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = sum(int(r.get("prompt_tokens") or 0) for r in rows)
        completion = sum(int(r.get("completion_tokens") or 0) for r in rows)
        total = sum(int(r.get("total_tokens") or 0) for r in rows)
        cost = sum(float(r.get("cost_usd") or 0) for r in rows)
        return {
            "calls": len(rows),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "cost_usd": round(cost, 6),
        }

    def get_user_daily_summary(self, user_id: str) -> Dict[str, Any]:
        rows = self._filter_today(user_id)
        summary = self.summarize(rows)
        summary.update(
            {
                "user_id": user_id,
                "day": _today_str(),
                "budget_usd": self.user_daily_budget_usd,
                "remaining_usd": round(
                    max(0.0, self.user_daily_budget_usd - summary["cost_usd"]), 6
                ),
                "budget_exceeded": summary["cost_usd"] >= self.user_daily_budget_usd
                if self.user_daily_budget_usd > 0
                else False,
                "recent": rows[-10:],
            }
        )
        return summary

    def get_global_daily_summary(self) -> Dict[str, Any]:
        rows = self._filter_today()
        summary = self.summarize(rows)
        summary.update(
            {
                "day": _today_str(),
                "budget_usd": self.daily_budget_usd,
                "remaining_usd": round(
                    max(0.0, self.daily_budget_usd - summary["cost_usd"]), 6
                ),
                "budget_exceeded": summary["cost_usd"] >= self.daily_budget_usd
                if self.daily_budget_usd > 0
                else False,
            }
        )
        return summary

    def check_budget(self, user_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        檢查是否還能繼續呼叫。
        回傳 (allowed, reason, context)
        """
        user_sum = self.get_user_daily_summary(user_id)
        global_sum = self.get_global_daily_summary()
        ctx = {"user": user_sum, "global": global_sum}

        if self.user_daily_budget_usd > 0 and user_sum["cost_usd"] >= self.user_daily_budget_usd:
            return (
                False,
                f"使用者今日預算已用盡（${user_sum['cost_usd']:.4f} / ${self.user_daily_budget_usd:.2f}）",
                ctx,
            )
        if self.daily_budget_usd > 0 and global_sum["cost_usd"] >= self.daily_budget_usd:
            return (
                False,
                f"系統今日總預算已用盡（${global_sum['cost_usd']:.4f} / ${self.daily_budget_usd:.2f}）",
                ctx,
            )
        return True, "ok", ctx


_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker
