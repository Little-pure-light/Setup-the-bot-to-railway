"""
Semantic Builder — extract abstract knowledge from turns.

Must NOT save full chat transcripts as knowledge.
Only compact semantic statements / facts.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Set


_SENT_SPLIT = re.compile(r"[。！？!?\n]+")
_NOISE = re.compile(
    r"^(嗯|哦|好|ok|okay|哈哈|呵呵|謝謝|你好|嗨)[\s！!。.~]*$",
    re.I,
)


def _norm(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_norm(text).lower().encode("utf-8")).hexdigest()[:16]


class SemanticBuilder:
    """Rule-based knowledge extraction (no LLM required)."""

    def extract_knowledge(
        self,
        *,
        user_message: str = "",
        assistant_message: str = "",
        reflection: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return list of knowledge items:
          {text, source, kind, fingerprint}
        """
        items: List[Dict[str, Any]] = []
        # Prefer reflection lessons / causes as abstract knowledge
        if reflection:
            for lesson in reflection.get("lessons") or reflection.get("improvements") or []:
                s = _norm(str(lesson))
                if len(s) >= 4:
                    items.append(
                        {
                            "text": s[:300],
                            "source": "reflection_lesson",
                            "kind": "lesson",
                            "fingerprint": _fingerprint(s),
                        }
                    )
            for cause in reflection.get("causes") or []:
                s = _norm(str(cause))
                if len(s) >= 4:
                    items.append(
                        {
                            "text": f"可能原因：{s}"[:300],
                            "source": "reflection_cause",
                            "kind": "cause",
                            "fingerprint": _fingerprint("cause:" + s),
                        }
                    )

        # Abstract preference patterns from user (not full chat)
        um = _norm(user_message)
        if um and not _NOISE.match(um) and len(um) >= 4:
            # capture "我喜歡X" style
            m = re.search(r"我(喜歡|愛|討厭|偏好|習慣)([^。！？\n]{2,40})", um)
            if m:
                fact = f"使用者{m.group(1)}{m.group(2).strip()}"
                items.append(
                    {
                        "text": fact,
                        "source": "user_preference",
                        "kind": "preference",
                        "fingerprint": _fingerprint(fact),
                    }
                )
            # definition-like
            m2 = re.search(r"(.+?)是(.+)", um)
            if m2 and 4 <= len(um) <= 80 and "什麼" not in um:
                fact = _norm(um)[:120]
                items.append(
                    {
                        "text": fact,
                        "source": "user_statement",
                        "kind": "statement",
                        "fingerprint": _fingerprint(fact),
                    }
                )

        # From assistant: only short definitional sentences, never full reply dump
        am = _norm(assistant_message)
        if am:
            for sent in _SENT_SPLIT.split(am):
                s = _norm(sent)
                if 10 <= len(s) <= 100 and ("是" in s or "可以" in s):
                    # skip overly chit-chat
                    if any(x in s for x in ("哈尼", "嘿嘿", "😊", "～")):
                        continue
                    items.append(
                        {
                            "text": s,
                            "source": "assistant_abstract",
                            "kind": "factoid",
                            "fingerprint": _fingerprint(s),
                        }
                    )
                    if len(items) >= 8:
                        break

        return self.remove_duplicates(items)

    def merge_similar(self, items: List[Dict[str, Any]], *, threshold: float = 0.85) -> List[Dict[str, Any]]:
        """Greedy merge near-duplicate strings by containment / fingerprint."""
        if not items:
            return []
        kept: List[Dict[str, Any]] = []
        for it in items:
            text = _norm(it.get("text") or "")
            if not text:
                continue
            dup = False
            for k in kept:
                kt = _norm(k.get("text") or "")
                if not kt:
                    continue
                if it.get("fingerprint") and it["fingerprint"] == k.get("fingerprint"):
                    dup = True
                    break
                if text in kt or kt in text:
                    # keep longer
                    if len(text) > len(kt):
                        k.update(it)
                    dup = True
                    break
                # simple token overlap
                a, b = set(text), set(kt)
                if a and b:
                    j = len(a & b) / max(1, len(a | b))
                    if j >= threshold and abs(len(text) - len(kt)) < 20:
                        dup = True
                        break
            if not dup:
                kept.append(dict(it))
        return kept

    def remove_duplicates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Set[str] = set()
        out = []
        for it in items:
            fp = it.get("fingerprint") or _fingerprint(it.get("text") or "")
            if fp in seen:
                continue
            seen.add(fp)
            it = dict(it)
            it["fingerprint"] = fp
            out.append(it)
        return out

    def generate_semantic_memory(
        self,
        *,
        user_message: str = "",
        assistant_message: str = "",
        reflection: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        raw = self.extract_knowledge(
            user_message=user_message,
            assistant_message=assistant_message,
            reflection=reflection,
        )
        return self.merge_similar(raw)
