"""Node 6 — Ask user for clarification when confidence is too low."""

from __future__ import annotations

from loguru import logger

from app.state import OrchestratorState


def ask_clarification(state: OrchestratorState) -> dict:
    """Set the clarification flag and provide a fallback answer."""
    logger.info("Node: ask_clarification")
    return {
        "needs_clarification": True,
        "final_answer": (
            "Je n'ai pas assez d'informations pour répondre avec certitude. "
            "Pourriez-vous préciser votre question ?"
        ),
        "final_confidence": 0.0,
    }
