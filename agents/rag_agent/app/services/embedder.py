"""Embedder — singleton SentenceTransformer for query and chunk encoding."""

from __future__ import annotations

from loguru import logger

MODEL_NAME   = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE  = 384

_model       = None
_model_failed = False


def get_model():
    """Return the singleton SentenceTransformer, or None on failure."""
    global _model, _model_failed

    if _model is not None:
        return _model
    if _model_failed:
        return None

    try:
        from sentence_transformers import SentenceTransformer  # lazy import
        logger.info(f"Loading embedding model '{MODEL_NAME}'…")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded.")
        return _model
    except Exception as exc:
        _model_failed = True
        logger.error(f"Could not load embedding model: {exc}")
        return None


def encode(text: str) -> list[float]:
    """Encode a text string into a 384-dimensional float vector.

    Returns an empty list if the model is unavailable.
    """
    model = get_model()
    if model is None:
        logger.warning("Embedder: model unavailable — returning empty vector")
        return []

    vector = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
    logger.debug(f"Embedder: encoded {len(text)} chars → vector dim={len(vector)}")
    return vector.tolist()
