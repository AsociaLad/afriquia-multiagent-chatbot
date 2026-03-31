"""QueryDecomposer — stub for MVP.

Future: uses LLM to split complex queries into sub-queries per agent.
For now, returns the original query for each selected agent.
"""

from __future__ import annotations

from loguru import logger


def decompose(query: str, selected_agents: list[str]) -> dict[str, str]:
    """Return a sub-query per selected agent.

    MVP: each agent gets the full original query.
    """
    logger.debug(f"Decomposing query for agents: {selected_agents} (MVP: passthrough)")
    return {agent: query for agent in selected_agents}
