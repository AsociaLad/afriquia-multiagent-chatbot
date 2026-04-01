"""Tests for the routing layers (Level 1 rules + Level 2 embeddings)."""

from __future__ import annotations

import numpy as np
import pytest

from app.router.rules import route_by_rules


AGENT_TYPES = ["sql", "rag", "location"]

AGENTS_CONFIG = [
    {"agent_type": "sql",      "description": "Données structurées : prix, commandes, livraisons, stocks, factures"},
    {"agent_type": "rag",      "description": "Documentation technique : normes, fiches carburant, FAQ, procédures"},
    {"agent_type": "location", "description": "Géolocalisation : stations proches, itinéraires, adresses"},
]


# ---------------------------------------------------------------------------
# Level 1 — rule-based
# ---------------------------------------------------------------------------

def test_sql_prix_gasoil():
    agents, conf = route_by_rules("Quel est le prix du gasoil ?", AGENT_TYPES)
    assert "sql" in agents
    assert conf >= 0.6


def test_rag_norme():
    agents, conf = route_by_rules("Quelle est la norme EN590 ?", AGENT_TYPES)
    assert "rag" in agents
    assert conf >= 0.8


def test_location_station_casablanca():
    agents, conf = route_by_rules("Où est la station à Casablanca ?", AGENT_TYPES)
    assert "location" in agents
    assert conf >= 0.5


def test_sql_reclamation_sans_accent():
    agents, conf = route_by_rules("Quelles sont les reclamations ouvertes ?", AGENT_TYPES)
    assert "sql" in agents
    assert conf >= 0.8


def test_sql_reclamation_avec_accent():
    agents, conf = route_by_rules("Affiche les réclamations en cours", AGENT_TYPES)
    assert "sql" in agents
    assert conf >= 0.8


def test_sql_clients_ville():
    """'clients habitent à Casablanca' must route to SQL, not Location."""
    agents, conf = route_by_rules("Quels clients habitent à Casablanca ?", AGENT_TYPES)
    assert agents == ["sql"]
    assert conf >= 0.80


def test_sql_clients_ville_courte():
    """'Clients à Rabat' must route to SQL."""
    agents, conf = route_by_rules("Clients à Rabat", AGENT_TYPES)
    assert "sql" in agents
    assert conf >= 0.80


def test_location_station_ville_still_works():
    """'Station proche de Casablanca' must still route to Location."""
    agents, conf = route_by_rules("Station Afriquia proche de Casablanca", AGENT_TYPES)
    assert agents == ["location"]
    assert conf >= 0.80


def test_unknown_query():
    agents, conf = route_by_rules("Bonjour, comment ça va ?", AGENT_TYPES)
    assert conf < 0.5


# ---------------------------------------------------------------------------
# Level 2 — embeddings (monkeypatched — no real model download)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_model(monkeypatch):
    """Inject a fake SentenceTransformer that returns predictable vectors."""

    class FakeModel:
        def encode(self, texts, **kwargs):
            # texts order: [query, sql_desc, rag_desc, location_desc]
            # Assign orthogonal unit vectors by position.
            # query (index 0) → same axis as sql → cosine=1.0 with sql, 0 with others.
            axis = [
                np.array([1.0, 0.0, 0.0]),  # query  → points to sql
                np.array([1.0, 0.0, 0.0]),  # sql desc
                np.array([0.0, 1.0, 0.0]),  # rag desc
                np.array([0.0, 0.0, 1.0]),  # location desc
            ]
            return np.array([axis[i] if i < len(axis) else axis[-1]
                             for i in range(len(texts))])

    import app.router.embeddings as emb_module
    monkeypatch.setattr(emb_module, "_model", FakeModel())
    monkeypatch.setattr(emb_module, "_model_failed", False)


@pytest.mark.asyncio
async def test_embeddings_routes_sql(mock_model):
    """Query mentioning 'sql' should be routed to sql agent."""
    from app.router.embeddings import route_by_embeddings
    agents, conf = await route_by_embeddings("sql query about prices", AGENTS_CONFIG)
    assert agents == ["sql"]
    assert conf >= 0.65


@pytest.mark.asyncio
async def test_embeddings_returns_empty_when_model_unavailable(monkeypatch):
    """If model failed to load, L2 must return [] gracefully."""
    import app.router.embeddings as emb_module
    monkeypatch.setattr(emb_module, "_model", None)
    monkeypatch.setattr(emb_module, "_model_failed", True)

    from app.router.embeddings import route_by_embeddings
    agents, conf = await route_by_embeddings("n'importe quoi", AGENTS_CONFIG)
    assert agents == []
    assert conf == 0.0
