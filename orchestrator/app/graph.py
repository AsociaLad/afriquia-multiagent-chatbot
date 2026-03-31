"""LangGraph StateGraph — full pipeline construction with conditional edges."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.config import settings
from app.state import OrchestratorState
from app.nodes.load_config import load_config
from app.nodes.router import route_query
from app.nodes.parallel_calls import call_agents
from app.nodes.fusion import fuse_responses
from app.nodes.retry_router import retry_router
from app.nodes.clarification import ask_clarification


# ---------------------------------------------------------------------------
# Conditional decision functions
# ---------------------------------------------------------------------------

def decide_after_routing(state: OrchestratorState) -> str:
    """After routing, decide whether we have agents to call."""
    selected = state.get("selected_agents", [])
    confidence = state.get("routing_confidence", 0.0)

    if not selected or confidence < settings.routing_confidence_min:
        return "clarification"
    return "call_agents"


def decide_after_fusion(state: OrchestratorState) -> str:
    """After fusion, decide: accept / retry / clarify."""
    confidence = state.get("final_confidence", 0.0)
    retry_count = state.get("retry_count", 0)

    if confidence >= settings.fusion_confidence_min:
        return "end"
    if retry_count < settings.max_retries:
        return "retry"
    return "clarification"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Build and return the compiled LangGraph pipeline."""
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("load_config", load_config)
    graph.add_node("route_query", route_query)
    graph.add_node("call_agents", call_agents)
    graph.add_node("fuse_responses", fuse_responses)
    graph.add_node("retry_router", retry_router)
    graph.add_node("clarification", ask_clarification)

    # Entry point
    graph.set_entry_point("load_config")

    # Linear edges
    graph.add_edge("load_config", "route_query")

    # Conditional: after routing
    graph.add_conditional_edges(
        "route_query",
        decide_after_routing,
        {
            "call_agents": "call_agents",
            "clarification": "clarification",
        },
    )

    # Linear: agents → fusion
    graph.add_edge("call_agents", "fuse_responses")

    # Conditional: after fusion
    graph.add_conditional_edges(
        "fuse_responses",
        decide_after_fusion,
        {
            "end": END,
            "retry": "retry_router",
            "clarification": "clarification",
        },
    )

    # Retry loops back to routing
    graph.add_edge("retry_router", "route_query")

    # Clarification is terminal
    graph.add_edge("clarification", END)

    return graph.compile()


# Compiled pipeline — import this from main.py
pipeline = build_graph()
