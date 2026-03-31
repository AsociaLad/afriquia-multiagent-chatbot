"""OrchestratorState — shared state flowing through the LangGraph pipeline."""

from typing import TypedDict


class OrchestratorState(TypedDict):
    query: str
    chatbot_id: int
    user_id: str
    session_id: str
    agents_config: list[dict]
    selected_agents: list[str]
    routing_confidence: float
    sub_queries: dict[str, str]
    agent_responses: list[dict]
    tried_agents: list[str]
    retry_count: int
    final_answer: str
    final_confidence: float
    needs_clarification: bool
    from_cache: bool
    agents_used: list[str]
    error: str
