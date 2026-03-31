"""Level 3 — LLM fallback routing (stub for MVP).

Future: prompt Ollama to classify the query into one of the agent types.
"""

from __future__ import annotations

from loguru import logger


async def route_by_llm(
    query: str, agents_config: list[dict]
) -> tuple[list[str], float]:
    """Stub: returns empty result so the router uses the default fallback.

    TODO: build prompt with agent descriptions, call ollama.generate, parse.
    """
    logger.debug("LLM fallback routing: stub — skipping")
    return [], 0.0
