"""Pydantic schemas for the orchestrator API."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming user query."""

    query: str
    chatbot_id: int = 1
    user_id: str = "anonymous"
    session_id: str = ""


class QueryResponse(BaseModel):
    """Response returned to the user."""

    answer: str
    agents_used: list[str]
    confidence: float
    needs_clarification: bool = False
    from_cache: bool = False


class AgentResponse(BaseModel):
    """Response from a single agent."""

    answer: str
    confidence: float
    agent: str
    sources: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
