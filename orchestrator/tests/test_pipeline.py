"""Tests for the full LangGraph pipeline (requires mock agent running)."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_query_returns_response(client):
    """Smoke test — pipeline runs even if mock agent is down."""
    resp = await client.post("/query", json={"query": "prix du gasoil"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "agents_used" in data
    assert "confidence" in data
