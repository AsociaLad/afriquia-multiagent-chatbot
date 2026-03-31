"""Integration smoke tests: orchestrator → real SQL Agent (port 8006).

These tests require the real SQL Agent to be running:
    uvicorn app.main:app --port 8006  (from agents/sql_agent/)

Skip gracefully if the agent is unreachable.
"""

from __future__ import annotations

import pytest
import httpx


# ---------------------------------------------------------------------------
# Helper: check if real SQL Agent is reachable before running
# ---------------------------------------------------------------------------

def _sql_agent_running() -> bool:
    try:
        r = httpx.get("http://localhost:8006/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


skip_if_down = pytest.mark.skipif(
    not _sql_agent_running(),
    reason="Real SQL Agent not running on port 8006 — skipping integration test",
)


# ---------------------------------------------------------------------------
# Config check (no HTTP needed)
# ---------------------------------------------------------------------------

def test_sql_agent_config_points_to_8006():
    """agents_config.json must route sql to port 8006 /query."""
    import json, pathlib
    cfg_path = pathlib.Path(__file__).parents[1] / "agents_config.json"
    configs = json.loads(cfg_path.read_text())
    sql_cfg = next(c for c in configs if c["agent_type"] == "sql")
    assert sql_cfg["port"] == 8006, f"Expected 8006, got {sql_cfg['port']}"
    assert sql_cfg["path"] == "/query", f"Expected /query, got {sql_cfg['path']}"


# ---------------------------------------------------------------------------
# Live integration: orchestrator calls real SQL Agent
# ---------------------------------------------------------------------------

@skip_if_down
def test_sql_agent_health_direct():
    """Direct health check of the real SQL Agent."""
    r = httpx.get("http://localhost:8006/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@skip_if_down
def test_sql_agent_prix_gazoil_direct():
    """Direct POST to real SQL Agent — prix gazoil query."""
    r = httpx.post(
        "http://localhost:8006/query",
        json={"query": "Quel est le prix du gazoil ?"},
        timeout=10.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["agent"] == "sql"
    assert data["confidence"] > 0.0
    assert "12.45" in data["answer"]


@skip_if_down
def test_sql_agent_commandes_direct():
    """Direct POST to real SQL Agent — commandes query."""
    r = httpx.post(
        "http://localhost:8006/query",
        json={"query": "Combien de commandes par statut ?"},
        timeout=10.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["agent"] == "sql"
    assert data["confidence"] > 0.0
    assert "livree" in data["answer"] or "commande" in data["answer"].lower()
