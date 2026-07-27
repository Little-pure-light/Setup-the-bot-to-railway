"""
Silence Engine — minimal prototype (response-path switch, not delay).

Default OFF. No sleep / countdown / fake typing / second LLM call.
Removable module: chat path unchanged when SILENCE_ENGINE_ENABLED=false.

Routes (selection report shortlist):
  C1n — narrow relational dual-hypothesis
  C2  — surface task vs load fork (direct-answer exit required)
  C3n — value-conflict expansion then actionable step
  C5  — mandatory bypass (facts, calc, direct commands, urgent, low confidence)
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("silence_engine")

RouteId = str  # "none" | "C1n" | "C2" | "C3n"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() not in ("0", "false", "no", "off", "")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def silence_engine_enabled() -> bool:
    """Master switch. Default false."""
    return _env_bool("SILENCE_ENGINE_ENABLED", "false")


def silence_engine_mode() -> str:
    """observe | shadow | active. Default observe."""
    mode = (os.getenv("SILENCE_ENGINE_MODE") or "observe").strip().lower()
    if mode not in ("observe", "shadow", "active"):
        return "observe"
    return mode


def silence_min_confidence() -> float:
    return max(0.0, min(1.0, _env_float("SILENCE_ENGINE_MIN_CONFIDENCE", 0.75)))


def silence_max_hypotheses() -> int:
    return max(1, min(2, _env_int("SILENCE_ENGINE_MAX_HYPOTHESES", 2)))


def silence_logging_enabled() -> bool:
    return _env_bool("SILENCE_ENGINE_LOGGING_ENABLED", "true")


def _parse_allowlist() -> Dict[str, set]:
    """
    SILENCE_ENGINE_ALLOWLIST formats (comma-separated tokens):
      user:<id>  conv:<id>  conversation:<id>  ai:<id>  client:<id>
      bare token matches user/conv/ai/any (not client)
    Empty allowlist → no identity is allowlisted (active cannot alter answers).
    """
    raw = (os.getenv("SILENCE_ENGINE_ALLOWLIST") or "").strip()
    out: Dict[str, set] = {
        "user": set(),
        "conv": set(),
        "ai": set(),
        "client": set(),
        "any": set(),
    }
    if not raw:
        return out
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        lower = token.lower()
        if lower.startswith("user:"):
            out["user"].add(token.split(":", 1)[1].strip())
        elif lower.startswith("conv:") or lower.startswith("conversation:"):
            out["conv"].add(token.split(":", 1)[1].strip())
        elif lower.startswith("ai:"):
            out["ai"].add(token.split(":", 1)[1].strip())
        elif lower.startswith("client:"):
            out["client"].add(token.split(":", 1)[1].strip())
        else:
            out["any"].add(token)
    return out


def resolve_allowlist_match(
    *,
    user_id: str = "",
    conversation_id: str = "",
    ai_id: str = "",
    client_id: str = "",
) -> Tuple[bool, str]:
    """
    Returns (matched, match_source).
    match_source is one of: client|user|conv|ai|any|none
    Does not return raw IDs (safe for logs).
    Priority: client → user → conv → ai → any (first hit).
    """
    al = _parse_allowlist()
    if not any(al.values()):
        return False, "none"
    cid = (client_id or "").strip()
    if cid and cid in al["client"]:
        return True, "client"
    uid = (user_id or "").strip()
    if uid and uid in al["user"]:
        return True, "user"
    conv = (conversation_id or "").strip()
    if conv and conv in al["conv"]:
        return True, "conv"
    aid = (ai_id or "").strip()
    if aid and aid in al["ai"]:
        return True, "ai"
    # bare tokens match user/conv/ai only (not client — client requires client: prefix)
    if uid and uid in al["any"]:
        return True, "any"
    if conv and conv in al["any"]:
        return True, "any"
    if aid and aid in al["any"]:
        return True, "any"
    return False, "none"


def is_allowlisted(
    *,
    user_id: str = "",
    conversation_id: str = "",
    ai_id: str = "",
    client_id: str = "",
) -> bool:
    matched, _src = resolve_allowlist_match(
        user_id=user_id,
        conversation_id=conversation_id,
        ai_id=ai_id,
        client_id=client_id,
    )
    return matched


# ---------------------------------------------------------------------------
# Decision result
# ---------------------------------------------------------------------------

@dataclass
class SilenceDecision:
    silence_engine_enabled: bool = False
    silence_engine_mode: str = "observe"
    silence_route_candidate: RouteId = "none"
    silence_route_selected: RouteId = "none"
    silence_bypass_reason: str = ""
    silence_confidence: float = 0.0
    silence_structure_changed: str = "unknown"  # true|false|unknown
    silence_direct_exit_offered: bool = False
    silence_engine_ms: int = 0
    silence_allowlisted: bool = False
    silence_match_source: str = "none"  # client|user|conv|ai|any|none
    silence_apply_framing: bool = False  # only true in active + allowlist + route
    framing_instruction: str = ""
    hypotheses: List[str] = field(default_factory=list)
    notes: str = ""

    def public_metadata(self) -> Dict[str, Any]:
        """Compact, public-safe route metadata (no chain-of-thought)."""
        return {
            "silence_engine_enabled": self.silence_engine_enabled,
            "silence_engine_mode": self.silence_engine_mode,
            "silence_route_candidate": self.silence_route_candidate,
            "silence_route_selected": self.silence_route_selected,
            "silence_bypass_reason": self.silence_bypass_reason or None,
            "silence_confidence": round(self.silence_confidence, 3),
            "silence_structure_changed": self.silence_structure_changed,
            "silence_direct_exit_offered": self.silence_direct_exit_offered,
            "silence_engine_ms": self.silence_engine_ms,
            "silence_allowlisted": self.silence_allowlisted,
            "silence_match_source": self.silence_match_source or "none",
            "silence_apply_framing": self.silence_apply_framing,
        }

    def log(self) -> None:
        if not silence_logging_enabled():
            return
        if not self.silence_engine_enabled and not os.getenv(
            "SILENCE_ENGINE_LOG_WHEN_DISABLED"
        ):
            return
        logger.info(
            "silence_engine enabled=%s mode=%s candidate=%s selected=%s "
            "bypass=%s conf=%.2f structure=%s direct_exit=%s ms=%s "
            "allowlist=%s match_source=%s apply=%s",
            self.silence_engine_enabled,
            self.silence_engine_mode,
            self.silence_route_candidate,
            self.silence_route_selected,
            self.silence_bypass_reason or "-",
            self.silence_confidence,
            self.silence_structure_changed,
            self.silence_direct_exit_offered,
            self.silence_engine_ms,
            self.silence_allowlisted,
            self.silence_match_source or "none",
            self.silence_apply_framing,
        )


# ---------------------------------------------------------------------------
# Bypass (C5) and classifiers — rule-based, no second LLM
# ---------------------------------------------------------------------------

_RE_ARITH = re.compile(
    r"(?:"
    r"\d+\s*[\+\-\*/×÷]\s*\d+"
    r"|\d+\s*的?\s*平方"
    r"|等於多少|等于多少|calculate|what\s+is\s+\d"
    r"|1\s*\+\s*1"
    r")",
    re.I,
)
_RE_FACT_LOOKUP = re.compile(
    r"(?:"
    r"今天天氣|今天天气|weather\s+(?:in|today)|氣溫|气温"
    r"|首都是|人口有多少|是幾年|是哪一年"
    r"|誰發明|谁发明|定義是什麼|定义是什么"
    r")",
    re.I,
)
_RE_DIRECT_CMD = re.compile(
    r"(?:"
    r"直接給|直接说|直接說|只要清單|只要步骤|只要步驟|不要分析|別分析|别分析"
    r"|簡潔回答|简洁回答|be\s+concise|just\s+(?:give|list|answer)"
    r"|翻譯成|翻译成|translate\s+to|格式化|改寫成|改写成|summarize|摘要一下"
    r"|refactor|convert\s+this\s+code"
    r")",
    re.I,
)
_RE_URGENT = re.compile(
    r"(?:"
    r"急救|緊急|紧急|報警|报警|自殺|自杀|自殘|自残|emergency|overdose"
    r"|現在就要|现在就要|立刻救命"
    r")",
    re.I,
)
_RE_C1 = re.compile(
    r"(?:"
    r"算了|沒事|没事|沒關係|没关系"
    r"|你最近.*忙|是不是比較忙|是不是比较忙|很忙嗎|很忙吗"
    r"|我很好|在嗎|在吗|還好嗎|还好吗"
    r"|不想說了|不想说了|先這樣|先这样"
    r")",
    re.I,
)
_RE_C2 = re.compile(
    r"(?:"
    r"更有效率|提高效率|生產力|生产力|拖延|怎麼變得|怎么变得"
    r"|自我改善|勵志|励志|motivation|productivity|怎麼才能更快|怎么才能更快"
    r"|時間管理|时间管理|我該怎麼變|我该怎么变"
    r"|如何更專注|如何更专注"
    r")",
    re.I,
)
_RE_C3 = re.compile(
    r"(?:"
    r"還是先|还是先|還是該|还是该|還是要|还是要"
    r"|誠實.*保護|保护.*诚实|誠實告訴|诚实告诉"
    r"|兩難|两难|價值衝突|价值冲突|左右為難|左右两难"
    r"|該不該|该不该|要不要告訴|要不要告诉"
    r"|一定答應|一定答应"
    r")",
    re.I,
)


def check_bypass(text: str) -> Tuple[bool, str]:
    """C5 mandatory bypass. Returns (should_bypass, reason)."""
    t = (text or "").strip()
    if not t:
        return True, "empty_message"
    if _RE_URGENT.search(t):
        return True, "urgent"
    if _RE_ARITH.search(t):
        return True, "arithmetic"
    if _RE_FACT_LOOKUP.search(t):
        return True, "closed_fact"
    if _RE_DIRECT_CMD.search(t):
        return True, "direct_command"
    # Very long explicit task dumps → not silence material
    if len(t) > 400 and ("```" in t or t.count("\n") >= 5):
        return True, "long_task_payload"
    return False, ""


def _short_relational(text: str) -> bool:
    t = (text or "").strip()
    # Short utterance; allow slightly longer but still compact
    if len(t) > 48:
        return False
    # Need relational cue, not any short sentence
    if not _RE_C1.search(t):
        return False
    # Explicit task markers kill C1
    if re.search(r"(幫我|帮我|請你|请你|write|implement|code|api)", t, re.I):
        return False
    return True


def score_routes(text: str) -> Dict[RouteId, float]:
    """Heuristic confidence scores in [0, 1]."""
    t = (text or "").strip()
    scores: Dict[RouteId, float] = {"C1n": 0.0, "C2": 0.0, "C3n": 0.0}

    if _short_relational(t):
        # Ambiguity boost: very short + relational particle
        base = 0.78
        if len(t) <= 12:
            base = 0.88
        if re.search(r"算了|沒事|没事|我很好", t):
            base = max(base, 0.9)
        scores["C1n"] = min(1.0, base)

    if _RE_C2.search(t):
        scores["C2"] = 0.86
        if re.search(r"只要|直接|步驟|步骤|list", t, re.I):
            scores["C2"] = 0.0  # will be bypassed earlier usually

    if _RE_C3.search(t):
        scores["C3n"] = 0.87
        # "一定答應" style manipulation is value/success-definition; still C3n framing
        # for structure; safety remains outside this module.
        if re.search(r"一定答應|一定答应|保證答應|保证答应", t):
            scores["C3n"] = 0.9

    return scores


def pick_route(
    scores: Dict[RouteId, float], min_conf: float
) -> Tuple[RouteId, float]:
    best: RouteId = "none"
    best_s = 0.0
    # Stable priority on ties: C3n > C2 > C1n (more explicit structure first)
    order: Sequence[RouteId] = ("C3n", "C2", "C1n")
    for rid in order:
        s = float(scores.get(rid) or 0.0)
        if s > best_s:
            best_s = s
            best = rid
    if best_s < min_conf:
        return "none", best_s
    return best, best_s


def build_framing(route: RouteId, text: str, max_hyp: int = 2) -> Tuple[str, List[str], bool]:
    """
    Public framing instruction injected into system prompt (active mode only).
    Returns (instruction, hypotheses, direct_exit_offered).
    """
    max_hyp = max(1, min(2, max_hyp))
    if route == "C1n":
        hyps = [
            "對方可能在確認關係／是否還被接住",
            "對方可能在表達自己也有壓力或想先結束話題",
        ][:max_hyp]
        inst = (
            "【Silence route C1n — 關係意圖雙假設｜窄版】\n"
            "使用者這句話可能同時有字面意思與關係功能。\n"
            "規則：\n"
            f"1. 最多提出 {max_hyp} 種「可能」假設，必須標成可能／不確定，禁止說成已讀懂內心的事實。\n"
            "2. 把選擇權交回使用者（例如較接近哪一種）。\n"
            "3. 若使用者只要字面回答，立刻改為字面回應，不要繼續讀心。\n"
            "4. 不要裝睡、倒數、省略號思考，或宣稱有主觀感受已被證明。\n"
            f"假設提示（僅供你組織回答，勿逐條表演）：{'；'.join(hyps)}"
        )
        return inst, hyps, True

    if route == "C2":
        inst = (
            "【Silence route C2 — 任務 vs 負荷分叉】\n"
            "使用者在問自我改善／效率類問題。\n"
            "規則：\n"
            "1. 先用一句話提供兩個選項：A) 直接給方法／步驟；B) 先釐清是否已經過載。\n"
            "2. 必須立刻提供「直接給方法」的退路；若使用者只要步驟，不要繞情緒。\n"
            "3. 禁止在未確認前斷定對方疲勞、憂鬱或逃避。\n"
            "4. 不要 sleep、倒數或假裝思考動畫。"
        )
        return inst, [], True

    if route == "C3n":
        inst = (
            "【Silence route C3n — 價值衝突展開後回行動】\n"
            "使用者呈現價值或選擇兩難。\n"
            "規則：\n"
            "1. 簡短展開互相拉扯的價值（最多兩個軸），不要宣判唯一正確答案。\n"
            "2. 展開後必須回到一個具體的下一步問題、決策條件或可執行動作。\n"
            "3. 禁止停在抽象哲學、相對主義長文。\n"
            "4. 若涉及醫療／法律／財務／安全高風險，遵守既有安全政策，不給危險建議。\n"
            "5. 不要 sleep 或表演思考。"
        )
        return inst, [], True

    return "", [], False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_silence_route(
    user_message: str,
    *,
    user_id: str = "",
    conversation_id: str = "",
    ai_id: str = "",
    client_id: str = "",
    force_enabled: Optional[bool] = None,
    force_mode: Optional[str] = None,
) -> SilenceDecision:
    """
    Classify and optionally prepare framing. Never sleeps.
    No second LLM call.
    """
    t0 = time.perf_counter()
    enabled = silence_engine_enabled() if force_enabled is None else force_enabled
    mode = silence_engine_mode() if force_mode is None else force_mode
    if mode not in ("observe", "shadow", "active"):
        mode = "observe"

    decision = SilenceDecision(
        silence_engine_enabled=bool(enabled),
        silence_engine_mode=mode,
    )
    allow, match_source = resolve_allowlist_match(
        user_id=user_id or "",
        conversation_id=conversation_id or "",
        ai_id=ai_id or "",
        client_id=client_id or "",
    )
    decision.silence_allowlisted = allow
    decision.silence_match_source = match_source

    if not enabled:
        decision.silence_bypass_reason = "master_disabled"
        decision.silence_structure_changed = "false"
        decision.silence_engine_ms = int((time.perf_counter() - t0) * 1000)
        return decision

    bypass, reason = check_bypass(user_message)
    if bypass:
        decision.silence_bypass_reason = reason
        decision.silence_route_candidate = "none"
        decision.silence_route_selected = "none"
        decision.silence_structure_changed = "false"
        decision.silence_engine_ms = int((time.perf_counter() - t0) * 1000)
        return decision

    min_conf = silence_min_confidence()
    scores = score_routes(user_message)
    candidate, conf = pick_route(scores, min_conf=0.0)  # raw best
    decision.silence_confidence = conf
    decision.silence_route_candidate = candidate if conf > 0 else "none"

    if conf < min_conf or candidate == "none":
        decision.silence_bypass_reason = "low_confidence"
        decision.silence_route_selected = "none"
        decision.silence_structure_changed = "false"
        decision.silence_engine_ms = int((time.perf_counter() - t0) * 1000)
        return decision

    # Eligible route selected for metadata; apply only in active+allowlist
    decision.silence_route_selected = candidate
    framing, hyps, direct_exit = build_framing(
        candidate, user_message, max_hyp=silence_max_hypotheses()
    )
    decision.framing_instruction = framing
    decision.hypotheses = hyps
    decision.silence_direct_exit_offered = direct_exit

    if mode == "active" and allow:
        decision.silence_apply_framing = True
        decision.silence_structure_changed = "true"
    elif mode in ("observe", "shadow"):
        decision.silence_apply_framing = False
        # structure may change only if applied; in observe/shadow user answer unchanged
        decision.silence_structure_changed = "false"
        decision.notes = f"{mode}_no_user_visible_change"
    else:
        # active but not allowlisted
        decision.silence_apply_framing = False
        decision.silence_structure_changed = "false"
        decision.silence_bypass_reason = decision.silence_bypass_reason or "not_allowlisted"
        decision.notes = "active_without_allowlist"

    decision.silence_engine_ms = int((time.perf_counter() - t0) * 1000)
    return decision


def apply_silence_framing(
    messages: List[Dict[str, Any]], decision: SilenceDecision
) -> List[Dict[str, Any]]:
    """
    Inject framing into system message when decision.silence_apply_framing.
    Returns messages (possibly a shallow-copied list with updated system content).
    """
    if not decision.silence_apply_framing or not decision.framing_instruction:
        return messages
    if not messages:
        return [
            {"role": "system", "content": decision.framing_instruction},
        ]
    out = list(messages)
    first = dict(out[0])
    if first.get("role") == "system":
        content = first.get("content") or ""
        first["content"] = f"{content}\n\n{decision.framing_instruction}".strip()
        out[0] = first
    else:
        out.insert(0, {"role": "system", "content": decision.framing_instruction})
    return out


def run_silence_for_chat(
    messages: List[Dict[str, Any]],
    user_message: str,
    *,
    user_id: str = "",
    conversation_id: str = "",
    ai_id: str = "",
    client_id: str = "",
) -> Tuple[List[Dict[str, Any]], SilenceDecision]:
    """
    Single entry used by chat_router. Safe when disabled.
    """
    decision = evaluate_silence_route(
        user_message,
        user_id=user_id,
        conversation_id=conversation_id,
        ai_id=ai_id,
        client_id=client_id,
    )
    try:
        decision.log()
    except Exception:
        pass
    if decision.silence_apply_framing:
        messages = apply_silence_framing(messages, decision)
    return messages, decision
