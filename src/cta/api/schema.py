"""The JSON contract of the API (docs/phase4-plan.md, section 1). Response models only."""

from typing import Any, Literal

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class Citation(BaseModel):
    n: int
    id: str
    title: str
    url: str | None  # only where the data proves it (never invented)
    file: str | None
    doc_type: str | None
    scope: str | None
    term: str | None
    last_updated: str | None
    excerpt: str
    cited: bool


class Contact(BaseModel):
    office: str
    name: str
    emails: list[dict[str, str | None]]  # {"address": ..., "for": ... or null}
    phones: list[str]
    note: str | None


class RetrievedChunk(BaseModel):
    id: str
    first_stage_rank: int
    similarity: float | None
    rerank_score: float | None
    final_rank: int | None
    sent_to_answerer: bool


class HowFound(BaseModel):
    route_detail: str
    intent: str | None
    top_vector_similarity: float | None
    abstain_threshold: float
    retrieved: list[RetrievedChunk]
    calendar: dict[str, Any] | None
    chain: dict[str, Any] | None
    stages_ms: dict[str, float | None]
    tokens: dict[str, int]
    cost_usd: dict[str, float]
    cache_hits: dict[str, bool]


class Meta(BaseModel):
    today: str
    version: str
    model: str


class AskResponse(BaseModel):
    request_id: str
    question: str
    answer: str
    answer_type: Literal["answer", "abstain", "not_announced", "clarify"]
    abstained: bool
    abstain_reason: str | None
    route: Literal["calendar", "chain", "retrieve"]
    citations: list[Citation]
    contact: Contact | None
    how_found: HowFound
    meta: Meta


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str | None = None
