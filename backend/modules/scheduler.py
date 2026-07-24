"""
Scheduler interface for Night Growth and infrastructure jobs.

Provides in-process scheduling hooks; production may wire APScheduler / cron
to the same interface. Does not block the FastAPI event loop when using
run_in_executor for heavy jobs.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("scheduler")


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: float
    callback: Callable[[], Any]
    last_run: Optional[float] = None
    run_count: int = 0
    enabled: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


class GrowthScheduler:
    """
    Minimal scheduler:
      - register(name, interval_seconds, callback)
      - start() / stop() background thread
      - tick() for tests (run due jobs once)
    """

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        interval_seconds: float,
        callback: Callable[[], Any],
        *,
        enabled: bool = True,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._jobs[name] = ScheduledJob(
                name=name,
                interval_seconds=max(1.0, float(interval_seconds)),
                callback=callback,
                enabled=enabled,
                meta=meta or {},
            )
            logger.info("scheduled job registered: %s every %ss", name, interval_seconds)

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._jobs.pop(name, None) is not None

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": j.name,
                    "interval_seconds": j.interval_seconds,
                    "enabled": j.enabled,
                    "last_run": j.last_run,
                    "run_count": j.run_count,
                    "meta": j.meta,
                }
                for j in self._jobs.values()
            ]

    def tick(self, *, now: Optional[float] = None) -> List[str]:
        """Run all due jobs once (synchronous). Returns names run."""
        now = now if now is not None else time.time()
        ran: List[str] = []
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            if not job.enabled:
                continue
            if job.last_run is None or (now - job.last_run) >= job.interval_seconds:
                try:
                    job.callback()
                    job.last_run = now
                    job.run_count += 1
                    ran.append(job.name)
                except Exception as e:
                    logger.exception("job %s failed: %s", job.name, e)
        return ran

    async def tick_async(self) -> List[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.tick)

    def start(self, poll_seconds: float = 30.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def _loop():
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(poll_seconds)

        self._thread = threading.Thread(target=_loop, name="growth-scheduler", daemon=True)
        self._thread.start()
        logger.info("GrowthScheduler started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("GrowthScheduler stopped")


# Module-level singleton for optional app wiring
_global_scheduler: Optional[GrowthScheduler] = None


def get_scheduler() -> GrowthScheduler:
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = GrowthScheduler()
    return _global_scheduler


def register_night_growth_daily(
    night_growth_runner: Callable[[], Any],
    *,
    interval_seconds: float = 86400.0,
) -> GrowthScheduler:
    """
    Convenience: register Night Growth on the global scheduler.
    interval default = 24h.
    """
    sched = get_scheduler()
    sched.register(
        "night_growth_daily",
        interval_seconds,
        night_growth_runner,
        meta={
            "kind": "night_growth",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return sched
