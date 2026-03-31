"""HybridRouter — 3-level routing: rules → embeddings → LLM fallback."""

from __future__ import annotations

from loguru import logger

from app.config import settings
from app.router.rules import route_by_rules
from app.router.embeddings import route_by_embeddings
from app.router.llm_fallback import route_by_llm


class HybridRouter:
    """Route a query to the best agent(s) using a 3-level cascade."""

    async def route(
        self, query: str, agents_config: list[dict]
    ) -> tuple[list[str], float]:
        """Return (selected_agents, confidence).

        Level 1: keyword/regex rules
        Level 2: embedding similarity (stub)
        Level 3: LLM fallback (stub)
        """
        enabled = [a for a in agents_config if a.get("enabled", True)]
        agent_types = [a["agent_type"] for a in enabled]

        # --- Level 1: Rules ---
        agents, confidence = route_by_rules(query, agent_types)
        if confidence >= settings.rules_threshold:
            logger.info(f"L1 rules → {agents} (conf={confidence:.2f})")
            return agents, confidence

        # --- Level 2: Embeddings ---
        agents, confidence = await route_by_embeddings(query, enabled)
        if confidence >= settings.embed_threshold:
            logger.info(f"L2 embeddings → {agents} (conf={confidence:.2f})")
            return agents, confidence

        # --- Level 3: LLM fallback ---
        agents, confidence = await route_by_llm(query, enabled)
        if confidence >= settings.routing_confidence_min:
            logger.info(f"L3 LLM → {agents} (conf={confidence:.2f})")
            return agents, confidence

        # No level reached threshold — return best guess from rules
        logger.warning("All routing levels below threshold, defaulting to rag")
        return ["rag"], 0.30
