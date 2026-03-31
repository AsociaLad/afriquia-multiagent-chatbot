"""Retriever — encodes a query and fetches the top-k relevant chunks from Qdrant."""

from __future__ import annotations

from loguru import logger

from app.config import settings
from app.services import embedder
from app.services import qdrant_client as qclient


class Retriever:
    """Retrieves the most relevant document chunks for a query.

    Usage:
        r = Retriever()
        chunks = await r.retrieve("Quelle est la norme EN590 ?")
    """

    def __init__(
        self,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> None:
        self.top_k           = top_k or settings.top_k              # default 4 (via config)
        self.score_threshold = score_threshold or settings.min_score # default 0.35

    async def retrieve(self, query: str) -> list[dict]:
        """Return a list of relevant chunks sorted by score (descending).

        Each chunk dict: {text, source, doc_type, chunk_index, title, score}
        Returns [] if embedding fails or no chunk reaches the threshold.
        """
        logger.info(f"Retriever: query='{query[:80]}…'" if len(query) > 80 else f"Retriever: query='{query}'")

        # 1. Encode query
        vector = embedder.encode(query)
        if not vector:
            logger.warning("Retriever: empty vector — aborting search")
            return []

        # 2. Search Qdrant
        hits = qclient.search(
            query_vector=vector,
            top_k=self.top_k,
            score_threshold=self.score_threshold,
        )

        # 3. Sort by score descending (Qdrant already does this, but be explicit)
        hits.sort(key=lambda h: h["score"], reverse=True)

        # 4. Log retained chunks
        if hits:
            logger.info(f"Retriever: {len(hits)} chunk(s) retained (threshold={self.score_threshold})")
            for i, h in enumerate(hits):
                logger.debug(
                    f"  [{i+1}] score={h['score']:.4f} | "
                    f"source={h['source']} | chunk={h['chunk_index']} | "
                    f"title={h['title']}"
                )
        else:
            logger.info("Retriever: no chunk above threshold")

        return hits
