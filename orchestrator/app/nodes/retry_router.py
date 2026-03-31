"""Node 5 — Retry logic: re-route if confidence is too low.

MVP: increment retry counter. The decision to actually retry is in graph.py
via the conditional edge decide_after_fusion.
"""

from __future__ import annotations

from loguru import logger

from app.state import OrchestratorState


def retry_router(state: OrchestratorState) -> dict:
    """Increment retry counter and clear previous responses."""
    retry_count = state.get("retry_count", 0) + 1
    logger.info(f"Node: retry_router (attempt #{retry_count})")
    return {
        "retry_count": retry_count,
        "agent_responses": [],
        "final_answer": "",
        "final_confidence": 0.0,
    }
