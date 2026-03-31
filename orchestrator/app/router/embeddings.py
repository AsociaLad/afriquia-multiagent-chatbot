"""Level 2 — Embedding-based routing via sentence-transformers.

Uses a multilingual MiniLM model (CPU-friendly, ~118MB) to compute cosine
similarity between the query and each agent's description.

Falls back gracefully (returns []) if the model cannot be loaded.
"""

from __future__ import annotations

import numpy as np
from loguru import logger

from app.config import settings

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model = None          # singleton — loaded once on first call
_model_failed = False  # avoid retrying after a load failure


def _get_model():
    """Return the singleton SentenceTransformer model, or None on failure."""
    global _model, _model_failed

    if _model is not None:
        return _model
    if _model_failed:
        return None

    try:
        from sentence_transformers import SentenceTransformer  # lazy import
        logger.info(f"Loading embedding model '{_MODEL_NAME}' (first call)…")
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded.")
        return _model
    except Exception as exc:
        _model_failed = True
        logger.warning(f"Could not load embedding model — L2 disabled: {exc}")
        return None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity between two 1-D vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


async def route_by_embeddings(
    query: str, agents_config: list[dict]
) -> tuple[list[str], float]:
    """Encode query + agent descriptions, return best match above threshold.

    Returns ([], 0.0) if model unavailable or no agent exceeds the threshold.
    """
    model = _get_model()
    if model is None:
        return [], 0.0

    descriptions = [a.get("description", "") for a in agents_config]
    agent_types  = [a["agent_type"] for a in agents_config]

    if not descriptions:
        return [], 0.0

    try:
        # Encode all texts in one batch (faster than one-by-one)
        texts   = [query] + descriptions
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        query_vec = vectors[0]
        desc_vecs = vectors[1:]

        scores = {
            agent_type: _cosine_similarity(query_vec, desc_vec)
            for agent_type, desc_vec in zip(agent_types, desc_vecs)
        }
        logger.debug(f"L2 embedding scores: {scores}")

        best_agent = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_agent]

        if best_score >= settings.embed_threshold:
            logger.info(f"L2 embeddings → [{best_agent}] (score={best_score:.3f})")
            return [best_agent], best_score

        logger.debug(
            f"L2 best score {best_score:.3f} < threshold {settings.embed_threshold}"
        )
        return [], 0.0

    except Exception as exc:
        logger.warning(f"Embedding inference failed (non-fatal): {exc}")
        return [], 0.0
