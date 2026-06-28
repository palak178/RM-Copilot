"""Request/response envelopes for the HTTP API (thin wrappers over agent models)."""

from pydantic import BaseModel

from rm_copilot.agent.models import AgentResult


class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None


class QueryResponse(BaseModel):
    session_id: str
    result: AgentResult


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    seeded: bool


class ProductsResponse(BaseModel):
    products: list[str]
