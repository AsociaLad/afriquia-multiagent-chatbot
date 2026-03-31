"""Node 4 — Fuse agent responses into a final answer.

MVP: pick the response with the highest confidence.
Future: LLM-based synthesis when multiple agents respond.
"""

from __future__ import annotations

from loguru import logger

from app.state import OrchestratorState


def fuse_responses(state: OrchestratorState) -> dict:
    """Select the best response by confidence (MVP strategy)."""
    logger.info("Node: fuse_responses")

    responses = state.get("agent_responses", [])
    if not responses:
        return {
            "final_answer": "Aucun agent n'a pu répondre.",
            "final_confidence": 0.0,
        }

    # Pick highest confidence
    best = max(responses, key=lambda r: r.get("confidence", 0.0))
    logger.info(
        f"Fusion: best agent='{best['agent']}' confidence={best['confidence']:.2f}"
    )
    return {
        "final_answer": best.get("answer", ""),
        "final_confidence": best.get("confidence", 0.0),
    }
