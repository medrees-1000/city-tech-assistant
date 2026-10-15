"""The JSON contract of the API (docs/phase4-plan.md, section 1). Response models only."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AskRequest(BaseModel):
    question: str


class FeedbackRequest(BaseModel):
    """A vote on one answer. Nothing else is accepted: no free text, no other field."""

    model_config = ConfigDict(extra="forbid")
    request_id: str
    vote: Literal["up", "down"]


class FeedbackResponse(BaseModel):
    request_id: str
    vote: Literal["up", "down"]


class Citation(BaseModel):
    n: int
    id: str
    title: str
    url: str | None  # only where the data proves it (never invented)
    file: str | None
    doc_type: str | None
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
    title: str | None = None  # the chunk's heading path (the panel shows it instead of the id)
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
    # "topic" (sentence written from the templates) or "generic"; None for other answers
    abstain_wording: str | None = None
    topic_in_scope: bool | None = None  # the topic call's in_scope, when it ran and was usable
    # the language step, when it ran (tester round 1b): the detected language and, for a question
    # that was not English, the redacted English translation every later step worked on
    language: dict[str, str | None] | None = None


class Meta(BaseModel):
    today: str
    version: str
    model: str


class AskResponse(BaseModel):
    request_id: str
    question: str
    answer: str
    answer_type: Literal["answer", "abstain", "not_announced", "clarify", "guardrail"]
    abstained: bool
    abstain_reason: str | None
    route: Literal["calendar", "chain", "retrieve", "clarify", "guardrail"]
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
