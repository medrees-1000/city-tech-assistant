"""One request_logs row per API request (docs/phase4-plan.md, "What is stored").

Stored: the redacted question and answer, route, abstain flag and code, chunk ids and scores, stage
latencies, tokens, cost, the contact office key, a request id, the date used. Not stored: IP
address, user agent, cookies, headers, or any other identifier. `cta.redact` removes emails, phone
numbers, SSN-like numbers and 8-digit CUNY EMPLIDs; it does NOT remove names or free text.
"""

import json
import logging

from cta.redact import redact

log = logging.getLogger("cta.api")
WARNING = "request log write failed"  # fixed text: never any question text


def success_record(resp) -> dict:
    """The row for an answered request (an answer, an abstention or a not-announced row)."""
    hf = resp.how_found
    sent = [
        {"id": c.id, "similarity": None if c.similarity is None else round(c.similarity, 4)}
        for c in sorted(
            (c for c in hf.retrieved if c.sent_to_answerer), key=lambda c: c.final_rank or 0
        )
    ] or [{"id": c.id} for c in resp.citations]
    trace = hf.model_dump() | {"answer_type": resp.answer_type, "route": resp.route}
    return {
        "request_id": resp.request_id, "status": "ok", "question": redact(resp.question),
        "today": resp.meta.today, "retrieved": sent, "answer": redact(resp.answer),
        "abstained": resp.abstained, "abstain_reason": resp.abstain_reason,
        "chat_model": resp.meta.model, "prompt_tokens": hf.tokens["prompt"],
        "completion_tokens": hf.tokens["completion"], "embedding_tokens": hf.tokens["embedding"],
        "cost_usd": hf.cost_usd["total"], "latency_ms": round(hf.stages_ms["total"] or 0),
        "query_cache_hit": hf.cache_hits["embedding"], "route": resp.route, "trace": trace,
        "contact_office": resp.contact.office if resp.contact else None,
    }  # fmt: skip


def blocked_record(resp, reason: str, status: str | None = None, text_blocked: bool = False,
                   chars: int | None = None, cost: float | None = 0.0) -> dict:  # fmt: skip
    """The row for a request a guardrail answered. `text_blocked`: the reason is about what the
    student typed (Stage 2), so no question text is stored, only the length; otherwise the question
    is stored in its redacted form like any other. A fixed reply holds no student text."""
    trace = resp.how_found.model_dump() | {"answer_type": "guardrail", "route": "guardrail",
                                           "reason": reason}  # fmt: skip
    if chars is not None:
        trace["chars"] = chars
    return {
        "request_id": resp.request_id, "status": status or f"blocked_{reason}",
        "question": "" if text_blocked else redact(resp.question), "today": resp.meta.today,
        "retrieved": [], "answer": redact(resp.answer), "abstained": False,
        "abstain_reason": None, "chat_model": resp.meta.model, "prompt_tokens": 0,
        "completion_tokens": 0, "embedding_tokens": 0, "cost_usd": cost,
        "latency_ms": round(resp.how_found.stages_ms["total"] or 0), "query_cache_hit": False,
        "route": "guardrail", "trace": trace, "contact_office": None,
    }  # fmt: skip


def error_record(request_id: str, status: str, question: str, today, model: str, ms: float,
                 question_chars: int | None = None) -> dict:  # fmt: skip
    """The row for a request that failed after it was understood (status is the error code)."""
    return {
        "request_id": request_id, "status": status, "question": redact(question),
        "today": today.isoformat(), "retrieved": [], "answer": None, "abstained": None,
        "abstain_reason": None, "chat_model": model, "prompt_tokens": None,
        "completion_tokens": None, "embedding_tokens": None, "cost_usd": None,
        "latency_ms": round(ms), "query_cache_hit": None, "route": None,
        "trace": {"error": status, **({} if question_chars is None else {"chars": question_chars})},
        "contact_office": None,
    }  # fmt: skip


COLUMNS = (
    "request_id", "source", "status", "question", "today", "retrieved", "answer", "abstained",
    "abstain_reason", "chat_model", "prompt_tokens", "completion_tokens", "embedding_tokens",
    "cost_usd", "latency_ms", "query_cache_hit", "route", "trace", "contact_office",
)  # fmt: skip
JSON_COLUMNS = {"retrieved", "trace"}


def write(conn, record: dict) -> None:
    """Insert one API row. Raises on failure; the caller decides what a failure means."""
    row = {"source": "api", **record}
    values = [json.dumps(row[c]) if c in JSON_COLUMNS else row[c] for c in COLUMNS]
    marks = ", ".join("%s::jsonb" if c in JSON_COLUMNS else "%s" for c in COLUMNS)
    conn.execute(f"INSERT INTO request_logs ({', '.join(COLUMNS)}) VALUES ({marks})", values)
    conn.commit()


def write_feedback(conn, request_id: str, vote: str) -> bool:
    """Save a vote on an API row: only `feedback` and `feedback_at` change, the latest vote wins.
    False when no API row has this id (an unknown id, or an eval-run row)."""
    done = conn.execute(
        "UPDATE request_logs SET feedback = %s, feedback_at = now() "
        "WHERE request_id = %s AND source = 'api'",
        (vote, request_id),
    )
    conn.commit()
    return done.rowcount == 1


class Logger:
    """Writes records and counts failures; a failed write never fails a request."""

    def __init__(self, writer=write):
        self.writer = writer
        self.failures = 0

    def __call__(self, conn, record: dict) -> None:
        try:
            self.writer(conn, record)
        except Exception:  # noqa: BLE001 - any failure: count it, say so without any question text
            self.failures += 1
            log.warning(WARNING)
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
