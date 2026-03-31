"""Pydantic schemas for the RAG Agent API.

Response contract is aligned with the orchestrator's AgentResponse:
  answer, confidence, agent, sources, data, metadata
"""

from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    query: str
    top_k: int = 4


class RAGResponse(BaseModel):
    answer: str
    confidence: float
    agent: str = "rag"
    sources: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
