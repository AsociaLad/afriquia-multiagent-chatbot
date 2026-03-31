"""Node 2 — Route the query to the best agent(s) via HybridRouter."""

from __future__ import annotations

from loguru import logger

from app.router import HybridRouter
from app.state import OrchestratorState
from app.services.decomposer import decompose

_router = HybridRouter()


async def route_query(state: OrchestratorState) -> dict:
    """Run the hybrid router and decompose into sub-queries."""
    logger.info("Node: route_query")

    agents_config = state.get("agents_config", [])
    query = state["query"]

    selected_agents, confidence = await _router.route(query, agents_config)
    sub_queries = decompose(query, selected_agents)

    logger.info(f"Routing → agents={selected_agents}, confidence={confidence:.2f}")
    return {
        "selected_agents": selected_agents,
        "routing_confidence": confidence,
        "sub_queries": sub_queries,
    }
