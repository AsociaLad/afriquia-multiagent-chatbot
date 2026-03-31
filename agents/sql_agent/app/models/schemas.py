"""Pydantic schemas for the SQL Agent API.

Response contract aligned with the orchestrator's AgentResponse:
  answer, confidence, agent, sources, data, metadata
"""

from pydantic import BaseModel, Field


class SQLRequest(BaseModel):
    query: str


class SQLResponse(BaseModel):
    answer: str
    confidence: float
    agent: str = "sql"
    sources: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
