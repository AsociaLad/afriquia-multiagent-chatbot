"""FastAPI application — POST /query, GET /health."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from loguru import logger

from app.models.schemas import QueryRequest, QueryResponse
from app.services.redis_cache import get_cached, set_cached
from app.graph import pipeline

app = FastAPI(title="Afriquia Orchestrator", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    logger.info(f"Received query: {req.query!r}")

    session_id = req.session_id or str(uuid.uuid4())

    # --- Cache check ---
    cached = await get_cached(req.query, req.chatbot_id)
    if cached:
        return QueryResponse(**cached, from_cache=True)

    # --- Run LangGraph pipeline ---
    initial_state = {
        "query": req.query,
        "chatbot_id": req.chatbot_id,
        "user_id": req.user_id,
        "session_id": session_id,
        "agents_config": [],
        "selected_agents": [],
        "routing_confidence": 0.0,
        "sub_queries": {},
        "agent_responses": [],
        "tried_agents": [],
        "retry_count": 0,
        "final_answer": "",
        "final_confidence": 0.0,
        "needs_clarification": False,
        "from_cache": False,
        "agents_used": [],
        "error": "",
    }

    result = await pipeline.ainvoke(initial_state)

    response = QueryResponse(
        answer=result.get("final_answer", ""),
        agents_used=result.get("agents_used", []),
        confidence=result.get("final_confidence", 0.0),
        needs_clarification=result.get("needs_clarification", False),
        from_cache=False,
    )

    # --- Cache the result ---
    await set_cached(
        req.query,
        req.chatbot_id,
        {
            "answer": response.answer,
            "agents_used": response.agents_used,
            "confidence": response.confidence,
            "needs_clarification": response.needs_clarification,
        },
    )

    return response
