"""Tests for the SQL Agent — endpoint + database (mocked)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app, _match_query
import app.main as main_mod  # for monkeypatching generate_sql


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
        if "clients" in sql.lower() and "casablanca" in sql.lower():
            return [
                {"nom": "Youssef El Amrani", "ville": "Casablanca"},
            ]
        if "clients" in sql.lower() and "tombouctou" in sql.lower():
            return []
        return []

    monkeypatch.setattr(db_mod, "execute_query", fake_execute)

    async def fake_get_pool():
        return None
    async def fake_close_pool():
        pass
    monkeypatch.setattr(db_mod, "get_pool", fake_get_pool)
    monkeypatch.setattr(db_mod, "close_pool", fake_close_pool)


@pytest.fixture
def mock_ollama_off(monkeypatch):
    """Make NL-to-SQL always fail so keyword mapping is used."""
    async def fake_generate(question):
        raise RuntimeError("Ollama not available")

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)


@pytest.fixture
def mock_ollama_casablanca(monkeypatch):
    """Mock Ollama to return valid SQL for Casablanca clients."""
    async def fake_generate(question):
        return (
            "<think>\nI need to find clients in Casablanca.\n</think>\n"
            "```sql\n"
            "SELECT nom, ville FROM clients WHERE ville ILIKE '%Casablanca%';\n"
            "```"
        )

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)


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
# Endpoint — keyword mapping (Ollama OFF)
# ---------------------------------------------------------------------------

async def test_endpoint_prix_gazoil(client, mock_db, mock_ollama_off):
    resp = await client.post("/query", json={"query": "Quel est le prix du gazoil ?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "sql"
    assert data["confidence"] > 0.0
    assert "12.45" in data["answer"]
    assert data["data"]["rows_returned"] >= 1
    assert data["metadata"]["strategy"] == "mvp_keyword_match"


async def test_endpoint_unsupported(client, mock_db, mock_ollama_off):
    """No NL-to-SQL + no keyword match → unsupported."""
    resp = await client.post("/query", json={"query": "Bonjour"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == 0.0
    assert data["metadata"]["strategy"] == "unsupported"


# ---------------------------------------------------------------------------
# Endpoint — NL-to-SQL pipeline (Ollama mocked)
# ---------------------------------------------------------------------------

async def test_nl_to_sql_casablanca(client, mock_db, mock_ollama_casablanca):
    """NL-to-SQL handles a question not covered by keyword mapping."""
    resp = await client.post(
        "/query",
        json={"query": "Quels clients habitent à Casablanca ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["strategy"] == "nl_to_sql"
    assert data["confidence"] > 0.0
    assert data["data"]["rows_returned"] >= 1
    assert "clients" in data["data"]["sql"].lower()


async def test_nl_to_sql_invalid_falls_back(client, mock_db, monkeypatch):
    """Ollama generates dangerous SQL → rejected → fallback to keyword mapping."""
    async def fake_generate(question):
        return "DROP TABLE produits;"

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)

    resp = await client.post(
        "/query",
        json={"query": "Quel est le prix du gazoil ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["strategy"] == "mvp_keyword_match"
    assert "12.45" in data["answer"]


async def test_nl_to_sql_zero_rows(client, mock_db, monkeypatch):
    """NL-to-SQL returns 0 rows → stays nl_to_sql, does NOT fall back."""
    async def fake_generate(question):
        return "SELECT nom FROM clients WHERE ville = 'Tombouctou';"

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)

    resp = await client.post(
        "/query",
        json={"query": "Clients à Tombouctou ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["strategy"] == "nl_to_sql"
    assert data["data"]["rows_returned"] == 0
    assert "Aucun résultat" in data["answer"]


# ---------------------------------------------------------------------------
# Retry SQL — execution error → retry → success
# ---------------------------------------------------------------------------

async def test_retry_succeeds(client, monkeypatch):
    """First SQL has bad column → retry generates correct SQL → success."""
    from app.services import database as db_mod

    # generate_sql returns SQL with a typo (bad column name)
    async def fake_generate(question):
        return "SELECT nome FROM clients WHERE ville ILIKE '%Casablanca%';"

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)

    # retry_generate_sql returns corrected SQL
    async def fake_retry(question, previous_sql, pg_error):
        return "SELECT nom FROM clients WHERE ville ILIKE '%Casablanca%';"

    monkeypatch.setattr(main_mod, "retry_generate_sql", fake_retry)

    # DB: first call fails (bad column), second call succeeds
    call_count = 0

    async def fake_execute(sql):
        nonlocal call_count
        call_count += 1
        if "nome" in sql:
            raise Exception('column "nome" does not exist')
        return [{"nom": "Youssef El Amrani", "ville": "Casablanca"}]

    monkeypatch.setattr(db_mod, "execute_query", fake_execute)

    async def fake_get_pool():
        return None
    async def fake_close_pool():
        pass
    monkeypatch.setattr(db_mod, "get_pool", fake_get_pool)
    monkeypatch.setattr(db_mod, "close_pool", fake_close_pool)

    resp = await client.post(
        "/query",
        json={"query": "Quels clients habitent à Casablanca ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["strategy"] == "nl_to_sql"
    assert data["metadata"]["retry_used"] is True
    assert data["metadata"]["retry_success"] is True
    assert data["data"]["rows_returned"] >= 1
    # Confidence should be lower than normal (0.72 vs 0.82)
    assert data["confidence"] == pytest.approx(0.72)
    assert call_count == 2


# ---------------------------------------------------------------------------
# Retry SQL — execution error → retry also fails → fallback
# ---------------------------------------------------------------------------

async def test_retry_fails_then_fallback(client, monkeypatch):
    """First SQL fails, retry also fails → falls back to keyword mapping."""
    from app.services import database as db_mod

    # generate_sql returns bad SQL
    async def fake_generate(question):
        return "SELECT nome FROM produits WHERE nom ILIKE '%gazoil%';"

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)

    # retry also returns bad SQL (different but still broken)
    async def fake_retry(question, previous_sql, pg_error):
        return "SELECT namme FROM produits WHERE nom ILIKE '%gazoil%';"

    monkeypatch.setattr(main_mod, "retry_generate_sql", fake_retry)

    # DB: always fails with SQL errors
    async def fake_execute(sql):
        if "nome" in sql:
            raise Exception('column "nome" does not exist')
        if "namme" in sql:
            raise Exception('column "namme" does not exist')
        # Keyword mapping queries work fine
        if "produits" in sql.lower() and "gazoil" in sql.lower():
            return [
                {"nom": "Gazoil 50 ppm", "prix_unitaire": 12.45,
                 "unite": "L", "date_maj": "2025-03-28"}
            ]
        return []

    monkeypatch.setattr(db_mod, "execute_query", fake_execute)

    async def fake_get_pool():
        return None
    async def fake_close_pool():
        pass
    monkeypatch.setattr(db_mod, "get_pool", fake_get_pool)
    monkeypatch.setattr(db_mod, "close_pool", fake_close_pool)

    resp = await client.post(
        "/query",
        json={"query": "Quel est le prix du gazoil ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # NL-to-SQL failed (both attempts) → fell back to keyword mapping
    assert data["metadata"]["strategy"] == "mvp_keyword_match"
    assert "12.45" in data["answer"]


# ---------------------------------------------------------------------------
# Retry SQL — non-retryable error (network) → no retry, direct fallback
# ---------------------------------------------------------------------------

async def test_no_retry_on_network_error(client, monkeypatch):
    """Connection error → NOT retryable → skip retry, go to fallback."""
    from app.services import database as db_mod

    async def fake_generate(question):
        return "SELECT nom FROM clients WHERE ville ILIKE '%Casablanca%';"

    monkeypatch.setattr(main_mod, "generate_sql", fake_generate)

    # retry_generate_sql should NOT be called — set it to fail loudly
    async def fake_retry_should_not_be_called(question, previous_sql, pg_error):
        raise AssertionError("retry_generate_sql should not have been called!")

    monkeypatch.setattr(main_mod, "retry_generate_sql", fake_retry_should_not_be_called)

    # DB: connection refused (not a SQL error)
    async def fake_execute(sql):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(db_mod, "execute_query", fake_execute)

    async def fake_get_pool():
        return None
    async def fake_close_pool():
        pass
    monkeypatch.setattr(db_mod, "get_pool", fake_get_pool)
    monkeypatch.setattr(db_mod, "close_pool", fake_close_pool)

    resp = await client.post(
        "/query",
        json={"query": "Quels clients habitent à Casablanca ?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # NL-to-SQL gave up (non-retryable) → unsupported (no keyword match)
    assert data["metadata"]["strategy"] == "unsupported"
