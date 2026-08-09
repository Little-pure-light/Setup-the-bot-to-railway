"""
Night Growth v2 — cognitive consolidation with Decision + Semantic + Identity.

Pipeline:
  Conversation → Reflection → Semantic Builder → Decision Engine
  → Identity / Attention / Transformation → Graph → Archive

Safety (Fix stage):
  - idempotency key per user+day
  - file lock
  - execution record with step timestamps
  - no in-process auto-start on multi-replica (use internal endpoint)
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.modules.memory_classifier import MemoryClassifier
from backend.modules.semantic_builder import SemanticBuilder
from backend.modules.decision_engine import DecisionEngine
from backend.modules.identity_engine import IdentityEngine
from backend.modules.reflection_contract import normalize_reflection
from backend.modules.night_growth_safety import (
    NightGrowthExecutionStore,
    _utc_date,
    finish_step,
    new_step,
)

logger = logging.getLogger("memory.night_growth")


def _bounded_positive_int(value: Any, default: int, *, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _positive_int_env(name: str, default: int, *, maximum: int) -> int:
    """Read a bounded positive integer without allowing an unsafe high limit."""
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        logger.warning("invalid night growth limit; using safe default name=%s", name)
        value = default
    return _bounded_positive_int(value, default, maximum=maximum)


def _estimate_turn_tokens(turn: Dict[str, Any]) -> int:
    """Conservative local estimate; no tokenizer or external API is called."""
    payload = {
        "user_message": turn.get("user_message") or "",
        "assistant_message": turn.get("assistant_message") or "",
        "reflection": turn.get("reflection") or {},
        "emotion": turn.get("emotion") or {},
    }
    text = json.dumps(payload, ensure_ascii=False, default=str)
    non_ascii_chars = sum(1 for char in text if ord(char) > 127)
    ascii_chars = len(text) - non_ascii_chars
    # CJK is conservatively counted as one token per character; ASCII uses 4:1.
    return max(1, non_ascii_chars + (ascii_chars + 3) // 4)


def _log_run_summary(report: Dict[str, Any]) -> None:
    """Log operational counts only; never log ids or conversation content."""
    usage = report.get("usage") or {}
    logger.info(
        "night growth run summary status=%s dry_run=%s turns=%s "
        "estimated_input_tokens=%s outputs=%s",
        report.get("status"),
        bool(report.get("dry_run")),
        usage.get("turns_processed", 0),
        usage.get("estimated_input_tokens", 0),
        usage.get("outputs_total", 0),
    )


class NightGrowth:
    def __init__(
        self,
        memory_manager,
        *,
        classifier: Optional[MemoryClassifier] = None,
        semantic_builder: Optional[SemanticBuilder] = None,
        decision_engine: Optional[DecisionEngine] = None,
        identity_engine: Optional[IdentityEngine] = None,
        execution_store: Optional[NightGrowthExecutionStore] = None,
        max_turns: Optional[int] = None,
        max_conversations: Optional[int] = None,
        max_input_tokens: Optional[int] = None,
    ):
        self.manager = memory_manager
        self.classifier = classifier or MemoryClassifier()
        self.semantic = semantic_builder or SemanticBuilder()
        self.decisions = decision_engine or DecisionEngine()
        self.identity = identity_engine
        self.store = execution_store or NightGrowthExecutionStore()
        self.max_turns = (
            _bounded_positive_int(max_turns, 20, maximum=200)
            if max_turns is not None
            else _positive_int_env("NIGHT_GROWTH_MAX_TURNS", 20, maximum=200)
        )
        self.max_conversations = (
            _bounded_positive_int(max_conversations, 5, maximum=50)
            if max_conversations is not None
            else _positive_int_env("NIGHT_GROWTH_MAX_CONVERSATIONS", 5, maximum=50)
        )
        self.max_input_tokens = (
            _bounded_positive_int(max_input_tokens, 12000, maximum=100000)
            if max_input_tokens is not None
            else _positive_int_env(
                "NIGHT_GROWTH_MAX_INPUT_TOKENS", 12000, maximum=100000
            )
        )

    async def run_once(
        self,
        *,
        user_id: str = "default_user",
        conversation_id: Optional[str] = None,
        recent_turns: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Safe entry: lock + idempotency + execution record.
        force=True bypasses same-day completed skip (still uses lock).
        """
        day = _utc_date()
        execution_id = f"ng_{uuid.uuid4().hex[:12]}"
        idem = self.store.idempotency_key(user_id, day)
        report: Dict[str, Any] = {
            "execution_id": execution_id,
            "idempotency_key": idem,
            "day": day,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "version": "night_growth_v2",
            "steps": {},
            "step_details": [],
            "dry_run": dry_run,
            "force": force,
            "saved_ids": [],
            "archived_ids": [],
            "decisions": [],
            "status": "running",
            "error": None,
            "identity_version_id": None,
            "graph_edge_ids": [],
        }

        # idempotency: completed same day
        if not force and self.store.is_day_completed(user_id, day):
            prev = self.store.get_day_record(user_id, day)
            report["status"] = "skipped_duplicate"
            report["error"] = None
            report["message"] = "already_completed_today"
            report["previous"] = prev
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.store.write_execution(report)
            _log_run_summary(report)
            return report

        if not self.store.acquire_lock(user_id):
            report["status"] = "failed"
            report["error"] = "lock_held"
            report["message"] = "another_run_in_progress"
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.store.write_execution(report)
            _log_run_summary(report)
            return report

        self.store.write_execution(report)
        try:
            pipeline = await self._run_pipeline(
                user_id=user_id,
                conversation_id=conversation_id,
                recent_turns=recent_turns,
                dry_run=dry_run,
                execution_id=execution_id,
            )
            report.update(pipeline)
            if pipeline.get("fatal_error"):
                report["status"] = "failed"
                report["error"] = pipeline.get("fatal_error")
            elif dry_run:
                # dry_run must not consume daily idempotency
                report["status"] = "completed_dry_run"
            else:
                report["status"] = "completed"
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.store.write_execution(report)
            _log_run_summary(report)
            return report
        except Exception as e:
            logger.exception("night growth failed: %s", e)
            report["status"] = "failed"
            report["error"] = str(e)
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.store.write_execution(report)
            _log_run_summary(report)
            return report
        finally:
            self.store.release_lock(user_id)

    async def _run_pipeline(
        self,
        *,
        user_id: str,
        conversation_id: Optional[str],
        recent_turns: Optional[List[Dict[str, Any]]],
        dry_run: bool,
        execution_id: str,
    ) -> Dict[str, Any]:
        if self.identity is None:
            self.identity = IdentityEngine(user_id=user_id)

        step_details: List[Dict[str, Any]] = []
        steps_summary: Dict[str, Any] = {}
        saved_ids: List[Any] = []
        archived_ids: List[Any] = []
        decision_logs: List[Dict[str, Any]] = []
        identity_patches = 0
        identity_version_id = None
        attention_saves = 0
        transform_saves = 0
        knowledge_saves = 0
        graph_edge_ids: List[str] = []
        graph_edges = 0

        # load turns
        s_load = new_step("load_turns")
        try:
            loaded_turns = (
                recent_turns
                if recent_turns is not None
                else await self._load_recent_turns(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=self.max_turns,
                )
            )
            turns, usage = self._apply_budget(loaded_turns)
            finish_step(s_load, status="ok")
        except Exception as e:
            finish_step(s_load, status="failed", error=str(e))
            step_details.append(s_load)
            return {
                "steps": {"load_turns": s_load},
                "step_details": [s_load],
                "fatal_error": str(e),
                "saved_ids": [],
                "archived_ids": [],
                "decisions": [],
            }
        step_details.append(s_load)
        steps_summary["load_turns"] = {
            "count": len(turns),
            "loaded": len(loaded_turns),
            "status": s_load["status"],
        }

        # 1 Reflection
        s_ref = new_step("reflection")
        reflections = []
        try:
            for t in turns:
                if t.get("reflection"):
                    reflections.append(normalize_reflection(t["reflection"]))
            finish_step(s_ref, status="ok")
        except Exception as e:
            finish_step(s_ref, status="failed", error=str(e))
        step_details.append(s_ref)
        steps_summary["reflection"] = {"count": len(reflections), "status": s_ref["status"]}

        for t in turns:
            um = t.get("user_message") or ""
            am = t.get("assistant_message") or ""
            refl = normalize_reflection(t["reflection"]) if t.get("reflection") else None
            clf = self.classifier.classify(
                conversation=t,
                emotion=t.get("emotion"),
                reflection=refl,
            )
            semantic_items = self.semantic.generate_semantic_memory(
                user_message=um,
                assistant_message=am,
                reflection=refl,
            )
            decision = self.decisions.decide(
                user_message=um,
                assistant_message=am,
                classification=clf.to_dict(),
                reflection=refl,
                semantic_items=semantic_items,
                importance=clf.importance,
            )
            decision_logs.append(decision.to_dict())

            if dry_run:
                continue

            if decision.forget and not decision.save:
                continue

            related_ids: List[str] = []

            if decision.save:
                rec = await self.manager.save(
                    user_message=um,
                    bot_response=am,
                    conversation_id=conversation_id
                    or t.get("conversation_id")
                    or f"night_{user_id}",
                    user_id=user_id,
                    emotion=t.get("emotion"),
                    reflection=refl,
                    force_type=clf.memory_type,
                    skip_v1_conversation=True,
                )
                if rec and rec.get("id"):
                    saved_ids.append(rec["id"])
                    related_ids.append(str(rec["id"]))

            if decision.form_long_term_knowledge:
                for item in semantic_items[:5]:
                    rec = await self.manager.save(
                        user_message=item.get("text") or "",
                        bot_response="[semantic_builder]",
                        conversation_id=conversation_id or f"night_{user_id}",
                        user_id=user_id,
                        force_type="semantic",
                        skip_v1_conversation=True,
                    )
                    if rec and rec.get("id"):
                        saved_ids.append(rec["id"])
                        related_ids.append(str(rec["id"]))
                        knowledge_saves += 1

            if decision.update_attention:
                rec = await self.manager.save(
                    user_message=um or "[attention]",
                    bot_response=am or "",
                    conversation_id=conversation_id or f"night_{user_id}",
                    user_id=user_id,
                    emotion=t.get("emotion"),
                    force_type="attention",
                    skip_v1_conversation=True,
                )
                if rec and rec.get("id"):
                    saved_ids.append(rec["id"])
                    related_ids.append(str(rec["id"]))
                    attention_saves += 1

            # Identity evolution (quality stage): do NOT lower confidence threshold.
            # Root causes of patches=0 historically:
            #  1) no reflection on turns → no lessons
            #  2) IDENTITY_UPDATE_MODE=candidate → formal patches stay 0 by design
            #  3) hollow reflections skipped
            # Fix: use actionable reflection lessons OR structured preference/self-intro
            # signals with real confidence from classifier/reflection (still gated).
            if decision.update_identity:
                try:
                    id_result = self._maybe_identity_update(
                        user_message=um,
                        reflection=refl,
                        classification=clf.to_dict(),
                        execution_id=execution_id,
                        decision_identity_update=True,
                    )
                    if id_result:
                        if id_result.get("status") == "formal":
                            identity_patches += 1
                            ch = id_result.get("charter") or {}
                            identity_version_id = (
                                f"{ch.get('identity_id')}:v{ch.get('version')}"
                            )
                        elif id_result.get("status") == "candidate":
                            steps_summary.setdefault("identity_candidates", 0)
                            steps_summary["identity_candidates"] = (
                                int(steps_summary.get("identity_candidates") or 0) + 1
                            )
                except Exception as e:
                    logger.warning("identity update failed: %s", e)

            if clf.memory_type == "transformation" or (
                refl and float(refl.get("confidence") or 0) >= 0.55
            ):
                rec = await self.manager.save(
                    user_message="[transformation]",
                    bot_response=str(refl or clf.to_dict())[:400],
                    conversation_id=conversation_id or f"night_{user_id}",
                    user_id=user_id,
                    reflection=refl,
                    force_type="transformation",
                    skip_v1_conversation=True,
                )
                if rec and rec.get("id"):
                    saved_ids.append(rec["id"])
                    related_ids.append(str(rec["id"]))
                    transform_saves += 1

            if getattr(self.manager, "graph", None) and len(related_ids) >= 2:
                g = self.manager.graph
                g.user_id = user_id
                try:
                    e = g.add_edge(
                        related_ids[0],
                        related_ids[1],
                        "derived_from",
                        confidence=0.6,
                        created_by="night_growth",
                        meta={"pipeline": "night_growth_v2", "execution_id": execution_id},
                    )
                    if e:
                        graph_edges += 1
                        if e.get("id"):
                            graph_edge_ids.append(str(e["id"]))
                except Exception as e:
                    logger.warning("graph edge failed: %s", e)

            if decision.archive and related_ids:
                try:
                    await self.manager.archive(related_ids[0])
                    archived_ids.append(related_ids[0])
                except Exception as e:
                    logger.warning("archive failed: %s", e)

        s_sem = new_step("semantic_builder")
        finish_step(s_sem, status="ok", saved_memory_ids=[])
        step_details.append(s_sem)
        steps_summary["semantic_builder"] = {
            "status": "ok",
            "knowledge_saves": knowledge_saves,
        }

        s_dec = new_step("decision_engine")
        finish_step(s_dec, status="ok")
        step_details.append(s_dec)
        steps_summary["decision_engine"] = {
            "status": "ok",
            "count": len(decision_logs),
        }

        s_id = new_step("identity_update")
        finish_step(
            s_id,
            status="ok",
            identity_version_id=identity_version_id,
        )
        step_details.append(s_id)
        steps_summary["identity_update"] = {
            "status": "ok",
            "patches": identity_patches,
            "identity_version_id": identity_version_id,
        }

        s_att = new_step("attention_update")
        finish_step(s_att, status="ok", saved_memory_ids=[])
        step_details.append(s_att)
        steps_summary["attention_update"] = {"status": "ok", "saves": attention_saves}

        s_tr = new_step("transformation_update")
        finish_step(s_tr, status="ok")
        step_details.append(s_tr)
        steps_summary["transformation_update"] = {"status": "ok", "saves": transform_saves}

        s_g = new_step("graph_update")
        finish_step(s_g, status="ok", graph_edge_ids=graph_edge_ids)
        step_details.append(s_g)
        steps_summary["graph_update"] = {"status": "ok", "edges": graph_edges}

        s_ar = new_step("archive")
        finish_step(s_ar, status="ok", saved_memory_ids=archived_ids)
        step_details.append(s_ar)
        steps_summary["archive"] = {"status": "ok", "archived": len(archived_ids)}

        return {
            "steps": steps_summary,
            "step_details": step_details,
            "saved_ids": saved_ids,
            "archived_ids": archived_ids,
            "decisions": decision_logs[:50],
            "identity_version_id": identity_version_id,
            "graph_edge_ids": graph_edge_ids,
            "turns_considered": len(turns),
            "usage": {
                **usage,
                "outputs_total": (
                    len(saved_ids)
                    + len(archived_ids)
                    + graph_edges
                    + int(steps_summary.get("identity_candidates") or 0)
                    + identity_patches
                ),
                "saved_count": len(saved_ids),
                "archived_count": len(archived_ids),
                "graph_edges_count": graph_edges,
                "identity_candidates_count": int(
                    steps_summary.get("identity_candidates") or 0
                ),
                "identity_patches_count": identity_patches,
            },
            "fatal_error": None,
        }

    def _apply_budget(
        self, turns: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Keep newest turns within conversation, turn, and estimated-token limits."""
        selected_reversed: List[Dict[str, Any]] = []
        conversations: set[str] = set()
        estimated_tokens = 0

        for turn in reversed(list(turns)):
            if len(selected_reversed) >= self.max_turns:
                break
            conversation_key = str(turn.get("conversation_id") or "__unspecified__")
            if (
                conversation_key not in conversations
                and len(conversations) >= self.max_conversations
            ):
                continue
            turn_tokens = _estimate_turn_tokens(turn)
            if estimated_tokens + turn_tokens > self.max_input_tokens:
                continue
            conversations.add(conversation_key)
            selected_reversed.append(turn)
            estimated_tokens += turn_tokens

        selected = list(reversed(selected_reversed))
        return selected, {
            "turns_loaded": len(turns),
            "turns_processed": len(selected),
            "turns_dropped": len(turns) - len(selected),
            "conversations_processed": len(conversations),
            "estimated_input_tokens": estimated_tokens,
            "limits": {
                "max_turns": self.max_turns,
                "max_conversations": self.max_conversations,
                "max_input_tokens": self.max_input_tokens,
            },
        }

    def _maybe_identity_update(
        self,
        *,
        user_message: str,
        reflection: Optional[Dict[str, Any]],
        classification: Dict[str, Any],
        execution_id: str,
        decision_identity_update: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Propose identity change without lowering confidence thresholds.
        Prefer actionable reflection lessons; else preference/self-intro patches.
        """
        from backend.modules.reflection_contract import (
            is_actionable_reflection,
            normalize_reflection,
        )

        patch: Dict[str, Any] = {}
        reason = ""
        conf = 0.0
        source = f"night_growth:{execution_id}"

        refl = normalize_reflection(reflection) if reflection else None
        if refl and is_actionable_reflection(refl) and refl.get("lessons"):
            conf = float(refl.get("confidence") or 0.0)
            lesson = str((refl.get("lessons") or [""])[0])[:120]
            if lesson and conf >= 0.55:
                cur = self.identity.load()
                principles = list(
                    dict.fromkeys((cur.get("principles") or []) + [lesson])
                )[:20]
                patch = {"principles": principles}
                reason = "night_growth_actionable_reflection"
                source = f"night_growth:reflection:{execution_id}"

        # Preference / self-intro → relationship_context (not core_values), still versioned
        if not patch:
            um = (user_message or "").strip()
            tags = list(classification.get("tags") or [])
            conf = float(classification.get("confidence") or 0.0)
            # require solid classifier confidence — same spirit as threshold, not relaxed
            if conf < 0.55:
                return None
            cur = self.identity.load()
            rel = dict(cur.get("relationship_context") or {})
            changed = False
            if "self_intro" in tags or "我叫" in um or "我的名字" in um:
                # capture short self label
                label = um[:80]
                if rel.get("last_self_intro") != label:
                    rel["last_self_intro"] = label
                    changed = True
                    reason = "night_growth_self_intro"
            if "preference" in tags or "我喜歡" in um or "我偏好" in um:
                prefs = list(rel.get("preferences") or [])
                item = um[:100]
                if item and item not in prefs:
                    prefs = (prefs + [item])[-20:]
                    rel["preferences"] = prefs
                    changed = True
                    reason = reason or "night_growth_preference"
            if changed:
                patch = {"relationship_context": rel}
                source = f"night_growth:signal:{execution_id}"

        if not patch or not reason:
            return None

        return self.identity.update(
            patch,
            change_reason=reason,
            confidence=conf,
            source=source,
            decision_identity_update=decision_identity_update,
        )

    def register_scheduler(self, *, interval_seconds: float = 86400.0, user_id: str = "default_user"):
        """
        Register on global scheduler interface — does NOT auto-start process.
        Multi-replica must not call start(); prefer external cron → internal endpoint.
        When NIGHT_GROWTH_ENABLED is false, registered job is a no-op guard.
        """
        from backend.modules.scheduler import register_night_growth_daily
        import asyncio

        enabled = os.getenv("NIGHT_GROWTH_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        def _runner():
            if not enabled:
                logger.info("scheduled night growth no-op (NIGHT_GROWTH_ENABLED off)")
                return
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self.run_once(user_id=user_id, dry_run=False, force=False)
                    )
                finally:
                    loop.close()
            except Exception as e:
                logger.exception("scheduled night growth failed: %s", e)

        return register_night_growth_daily(_runner, interval_seconds=interval_seconds)

    async def _load_recent_turns(
        self,
        *,
        user_id: str,
        conversation_id: Optional[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        ms = getattr(self.manager, "v1", None)
        if ms is None or not getattr(ms, "supabase", None):
            return []
        try:
            table = ms.memories_table
            q = (
                ms.supabase.table(table)
                .select(
                    "user_message, assistant_message, conversation_id, user_id, memory_type"
                )
                .eq("memory_type", "conversation")
                .limit(limit)
            )
            if conversation_id:
                q = q.eq("conversation_id", conversation_id)
            elif user_id and user_id != "default_user":
                q = q.eq("user_id", user_id)
            result = q.order("created_at", desc=True).execute()
            rows = list(reversed(result.data or []))
            return [
                {
                    "user_message": r.get("user_message") or "",
                    "assistant_message": r.get("assistant_message") or "",
                    "conversation_id": r.get("conversation_id"),
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("night load turns failed: %s", e)
            return []
