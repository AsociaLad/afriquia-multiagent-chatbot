"""Tests for the RAG Agent — endpoint + retriever + generator unit tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Patch retriever and generator on the app module to avoid real I/O."""
    import app.main as main_mod
    from app.services.retriever import Retriever
    from app.services.generator import Generator

    FAKE_CHUNKS = [
        {
            "text": "La norme EN 590 définit les spécifications du diesel.",
            "source": "norme_EN590.txt",
            "doc_type": "norme",
            "chunk_index": 0,
            "title": "Norme En590",
            "score": 0.82,
        }
    ]

    class FakeRetriever:
        async def retrieve(self, query):
            return FAKE_CHUNKS

    class FakeGenerator:
        async def generate(self, query, chunks):
            if not chunks:
                from app.services.generator import NO_CONTEXT_ANSWER
                return {"answer": NO_CONTEXT_ANSWER, "sources": [], "confidence": 0.0}
            return {
                "answer": "La norme EN 590 fixe les specs du diesel.",
                "sources": ["norme_EN590.txt"],
                "confidence": 0.88,
            }

    monkeypatch.setattr(main_mod, "_retriever", FakeRetriever())
    monkeypatch.setattr(main_mod, "_generator", FakeGenerator())


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /query — endpoint tests (pipeline mocked)
# ---------------------------------------------------------------------------

async def test_query_returns_valid_schema(client, mock_pipeline):
    """Nominal case: endpoint returns a complete, valid RAGResponse."""
    resp = await client.post("/query", json={"query": "Quelle est la norme EN590 ?"})
    assert resp.status_code == 200
    data = resp.json()

    # Schema fields
    assert "answer" in data
    assert "confidence" in data
    assert "agent" in data
    assert "sources" in data
    assert "data" in data
    assert "metadata" in data

    # Values
    assert data["agent"] == "rag"
    assert data["confidence"] == 0.88
    assert "norme_EN590.txt" in data["sources"]
    assert data["data"]["chunks_used"] == 1


async def test_query_no_chunks_returns_fallback(client, monkeypatch):
    """When retriever returns no chunks, endpoint returns the no-context answer."""
    import app.main as main_mod
    from app.services.generator import NO_CONTEXT_ANSWER

    class EmptyRetriever:
        async def retrieve(self, query):
            return []

    class FallbackGenerator:
        async def generate(self, query, chunks):
            return {"answer": NO_CONTEXT_ANSWER, "sources": [], "confidence": 0.0}

    monkeypatch.setattr(main_mod, "_retriever", EmptyRetriever())
    monkeypatch.setattr(main_mod, "_generator", FallbackGenerator())

    resp = await client.post("/query", json={"query": "question sans réponse"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == NO_CONTEXT_ANSWER
    assert data["confidence"] == 0.0
    assert data["sources"] == []


async def test_smoke_without_mock(client):
    """Smoke test with no mock — endpoint must not crash (stub or real)."""
    resp = await client.post("/query", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "agent" in data
    assert data["agent"] == "rag"


# ---------------------------------------------------------------------------
# Retriever unit tests (mocked — no real Qdrant/model)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_retriever_deps(monkeypatch):
    import app.services.embedder as emb
    import app.services.qdrant_client as qc

    monkeypatch.setattr(emb, "encode", lambda text: [0.1] * 384)

    def fake_search(query_vector, top_k=4, score_threshold=0.35):
        return [
            {
                "text": "La norme EN 590 définit les spécifications du diesel.",
                "source": "norme_EN590.txt",
                "doc_type": "norme",
                "chunk_index": 0,
                "title": "Norme En590",
                "score": 0.82,
            },
            {
                "text": "Indice de cétane minimum : 51.",
                "source": "norme_EN590.txt",
                "doc_type": "norme",
                "chunk_index": 1,
                "title": "Norme En590",
                "score": 0.71,
            },
        ]
    monkeypatch.setattr(qc, "search", fake_search)


async def test_retriever_returns_chunks(mock_retriever_deps):
    from app.services.retriever import Retriever
    r = Retriever()
    chunks = await r.retrieve("Quelle est la norme EN590 ?")
    assert len(chunks) == 2
    assert chunks[0]["score"] >= chunks[1]["score"]
    assert chunks[0]["source"] == "norme_EN590.txt"


async def test_retriever_returns_empty_on_failed_encode(monkeypatch):
    import app.services.embedder as emb
    monkeypatch.setattr(emb, "encode", lambda text: [])
    from app.services.retriever import Retriever
    chunks = await Retriever().retrieve("n'importe quoi")
    assert chunks == []


# ---------------------------------------------------------------------------
# Generator unit tests (mocked — no real Ollama call)
# ---------------------------------------------------------------------------

SAMPLE_CHUNKS = [
    {
        "text": "La norme EN 590 définit les spécifications du carburant diesel.",
        "source": "norme_EN590.txt",
        "doc_type": "norme",
        "chunk_index": 0,
        "title": "Norme En590",
        "score": 0.82,
    },
]


async def test_generator_with_chunks(monkeypatch):
    import app.services.ollama as ollama_mod

    async def fake_generate(prompt, model=None):
        return "La norme EN 590 fixe les spécifications du diesel (cétane ≥ 51)."
    monkeypatch.setattr(ollama_mod, "generate", fake_generate)

    from app.services.generator import Generator
    result = await Generator().generate("Quelle est la norme EN590 ?", SAMPLE_CHUNKS)
    assert result["confidence"] > 0.0
    assert "norme_EN590.txt" in result["sources"]
    assert len(result["answer"]) > 10


async def test_generator_no_chunks_returns_fallback():
    from app.services.generator import Generator, NO_CONTEXT_ANSWER
    result = await Generator().generate("question sans contexte", [])
    assert result["answer"] == NO_CONTEXT_ANSWER
    assert result["confidence"] == 0.0
    assert result["sources"] == []


# ---------------------------------------------------------------------------
# Tests to activate when Ollama + Qdrant are fully wired (integration)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Integration test — requires Qdrant + Ollama running")
async def test_rag_retrieves_norme_EN590(client):
    resp = await client.post("/query", json={"query": "Quelle est la norme EN590 ?"})
    data = resp.json()
    assert data["confidence"] >= 0.5
    assert "EN 590" in data["answer"]


@pytest.mark.skip(reason="Integration test — requires Qdrant + Ollama running")
async def test_rag_retrieves_securite(client):
    resp = await client.post("/query", json={"query": "règles de sécurité stockage gaz"})
    data = resp.json()
    assert data["confidence"] >= 0.5
