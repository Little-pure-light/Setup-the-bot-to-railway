from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.internal_night_growth_router as router_module
import backend.modules.night_growth as night_growth_module


class _FakeNightGrowth:
    def __init__(self, manager):
        self.manager = manager

    async def run_once(self, **kwargs):
        return {
            "execution_id": "dry_test",
            "status": "completed_dry_run",
            "day": "2026-08-09",
            "dry_run": True,
            "force": False,
            "steps": {},
            "saved_ids": [],
            "archived_ids": [],
            "graph_edge_ids": [],
            "usage": {"turns_processed": 0},
            "error": None,
        }


@pytest.mark.asyncio
async def test_live_run_is_blocked_by_default(monkeypatch):
    monkeypatch.setenv("NIGHT_GROWTH_INTERNAL_TOKEN", "unit-test-token")
    monkeypatch.delenv("NIGHT_GROWTH_ENABLED", raising=False)

    with pytest.raises(HTTPException) as exc:
        await router_module.run_night_growth(
            router_module.NightGrowthRunRequest(dry_run=False),
            authorization="Bearer unit-test-token",
            x_internal_token=None,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Night growth live runs disabled"


@pytest.mark.asyncio
async def test_dry_run_remains_available_while_live_is_off(monkeypatch):
    monkeypatch.setenv("NIGHT_GROWTH_INTERNAL_TOKEN", "unit-test-token")
    monkeypatch.delenv("NIGHT_GROWTH_ENABLED", raising=False)
    monkeypatch.setattr(router_module, "_build_manager", lambda: object())
    monkeypatch.setattr(night_growth_module, "NightGrowth", _FakeNightGrowth)

    response = await router_module.run_night_growth(
        router_module.NightGrowthRunRequest(dry_run=True),
        authorization="Bearer unit-test-token",
        x_internal_token=None,
    )

    assert response["ok"] is True
    assert response["status"] == "completed_dry_run"
    assert response["usage"] == {"turns_processed": 0}
