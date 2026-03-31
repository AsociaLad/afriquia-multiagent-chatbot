"""RAG Agent — FastAPI application.

Endpoint : POST /query
Pipeline : query → Retriever → Generator → RAGResponse
"""

from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from app.models.schemas import RAGRequest, RAGResponse
from app.services.retriever import Retriever
from app.services.generator import Generator, NO_CONTEXT_ANSWER

app = FastAPI(title="Afriquia RAG Agent", version="0.1.0")

_retriever = Retriever()
_generator = Generator()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=RAGResponse)
async def query(req: RAGRequest) -> RAGResponse:
    """RAG pipeline : retrieve relevant chunks then generate an answer."""
    logger.info(f"RAG Agent | query='{req.query!r}'")

    # --- 1. Retrieve ---
    try:
        chunks = await _retriever.retrieve(req.query)
    except Exception as exc:
        logger.error(f"Retriever error: {exc}")
        return RAGResponse(
            answer=NO_CONTEXT_ANSWER,
            confidence=0.0,
            metadata={"error": "retriever_failed", "detail": str(exc)},
        )

    # --- 2. Generate ---
    try:
        result = await _generator.generate(req.query, chunks)
    except Exception as exc:
        logger.error(f"Generator error: {exc}")
        return RAGResponse(
            answer=NO_CONTEXT_ANSWER,
            confidence=0.0,
            metadata={"error": "generator_failed", "detail": str(exc)},
        )

    # --- 3. Build response ---
    return RAGResponse(
        answer=result["answer"],
        confidence=result["confidence"],
        sources=result["sources"],
        data={"chunks_used": len(chunks)},
        metadata={"top_k": req.top_k, "chunks_retrieved": len(chunks)},
    )
