"""Tests for the SQL Agent — endpoint + database (mocked)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app, _match_query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Keyword matching unit tests (no DB needed)
# ---------------------------------------------------------------------------

def test_match_prix_gazoil():
    m = _match_query("Quel est le prix du gazoil ?")
    assert m is not None
    assert "gazoil" in m["sql"].lower()


def test_match_commandes():
    m = _match_query("Combien de commandes en livraison ?")
    assert m is not None
    assert "commandes" in m["sql"].lower()


def test_match_reclamation():
    m = _match_query("Quelles sont les reclamations ouvertes ?")
    assert m is not None
    assert "reclamations" in m["sql"].lower()


def test_no_match_unknown():
    m = _match_query("Bonjour comment ça va ?")
    assert m is None


# ---------------------------------------------------------------------------
# Endpoint tests (database mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db(monkeypatch):
    """Patch execute_query to return fake rows without hitting PostgreSQL."""
    from app.services import database as db_mod

    async def fake_execute(sql):
        if "produits" in sql.lower() and "gazoil" in sql.lower():
            return [
                {"nom": "Gazoil 50 ppm", "prix_unitaire": 12.45,
                 "unite": "L", "date_maj": "2025-03-28"}
            ]
        if "commandes" in sql.lower() and "group by" in sql.lower():
            return [
                {"statut": "livree", "nb": 7},
                {"statut": "en_livraison", "nb": 4},
            ]
        return []

    monkeypatch.setattr(db_mod, "execute_query", fake_execute)

    # Also prevent lifespan from connecting to real PostgreSQL
    async def fake_get_pool():
        return None
    async def fake_close_pool():
        pass
    monkeypatch.setattr(db_mod, "get_pool", fake_get_pool)
    monkeypatch.setattr(db_mod, "close_pool", fake_close_pool)


async def test_endpoint_prix_gazoil(client, mock_db):
    resp = await client.post("/query", json={"query": "Quel est le prix du gazoil ?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "sql"
    assert data["confidence"] > 0.0
    assert "12.45" in data["answer"]
    assert data["data"]["rows_returned"] >= 1


async def test_endpoint_not_implemented(client, mock_db):
    """Query with no keyword match returns not_implemented response."""
    resp = await client.post("/query", json={"query": "Bonjour"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == 0.0
    assert data["metadata"]["status"] == "not_implemented"
