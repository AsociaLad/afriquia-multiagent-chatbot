"""Qdrant client — singleton connection and vector search."""

from __future__ import annotations

from loguru import logger

from app.config import settings

COLLECTION_NAME = settings.qdrant_collection  # "afriquia_docs"

_client = None


def get_client():
    """Return a shared QdrantClient instance (lazy init)."""
    global _client
    if _client is not None:
        return _client

    try:
        from qdrant_client import QdrantClient  # lazy import
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        logger.info(
            f"Qdrant client connected to {settings.qdrant_host}:{settings.qdrant_port}"
        )
        return _client
    except Exception as exc:
        logger.error(f"Could not connect to Qdrant: {exc}")
        return None


def search(
    query_vector: list[float],
    top_k: int = 4,
    score_threshold: float = 0.35,
) -> list[dict]:
    """Search for similar vectors in the Qdrant collection.

    Returns a list of dicts:
        {text, source, doc_type, chunk_index, title, score}
    """
    client = get_client()
    if client is None:
        logger.warning("Qdrant search skipped — client unavailable")
        return []

    if not query_vector:
        logger.warning("Qdrant search skipped — empty query vector")
        return []

    logger.debug(
        f"Qdrant search: collection='{COLLECTION_NAME}' "
        f"top_k={top_k} threshold={score_threshold}"
    )

    try:
        from qdrant_client.models import ScoredPoint  # type check only

        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        hits = []
        for r in results:
            payload = r.payload or {}
            hits.append({
                "text":        payload.get("text", ""),
                "source":      payload.get("source", ""),
                "doc_type":    payload.get("doc_type", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "title":       payload.get("title", ""),
                "score":       round(r.score, 4),
            })

        logger.debug(
            f"Qdrant returned {len(results)} result(s), "
            f"scores: {[h['score'] for h in hits]}"
        )
        return hits

    except Exception as exc:
        logger.error(f"Qdrant search failed: {exc}")
        return []
