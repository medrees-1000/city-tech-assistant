"""Show API requests and votes.

    uv run python -m cta.api.logs --last 5 [--since DATE] [--route R] [--feedback up|down|any]
    uv run python -m cta.api.logs --id REQUEST_ID      (the whole stored row of one request)

Reads only what the API stored (already redacted) and redacts it again before printing.
"""

import argparse
import json
import sys
import uuid
from datetime import date

from cta.index.db import connect
from cta.redact import redact

ROUTES = ("calendar", "chain", "retrieve", "clarify")
FEEDBACK = ("up", "down", "any")


def where(since: date | None, route: str | None, feedback: str | None = None) -> tuple[str, list]:
    clauses, params = ["source = 'api'"], []
    if since:
        clauses.append("ts >= %s")
        params.append(since)
    if route:
        clauses.append("route = %s")
        params.append(route)
    if feedback in ("up", "down"):
        clauses.append("feedback = %s")
        params.append(feedback)
    elif feedback == "any":
        clauses.append("feedback IS NOT NULL")
    return " AND ".join(clauses), params


def fetch(conn, last: int, since: date | None = None, route: str | None = None,
          feedback: str | None = None):  # fmt: skip
    """(the last `last` rows, matching requests, their total cost in USD, vote counts)."""
    clause, params = where(since, route, feedback)
    rows = conn.execute(
        "SELECT ts, question, route, abstained, contact_office, status, latency_ms, "
        "prompt_tokens, completion_tokens, cost_usd, feedback, request_id FROM request_logs "
        f"WHERE {clause} ORDER BY ts DESC, id DESC LIMIT %s",
        [*params, last],
    ).fetchall()
    total, cost, up, down = conn.execute(
        "SELECT count(*), coalesce(sum(cost_usd), 0), count(*) FILTER (WHERE feedback = 'up'), "
        f"count(*) FILTER (WHERE feedback = 'down') FROM request_logs WHERE {clause}",
        params,
    ).fetchone()
    return rows, total, float(cost), {"up": up, "down": down, "none": total - up - down}


def line(row) -> str:
    ts, question, route, abstained, office, status, ms, p_tok, c_tok, cost, vote, rid = row
    flag = "-" if abstained is None else ("abstained" if abstained else "answered")
    tokens = "-" if p_tok is None else f"{p_tok}/{c_tok}"
    price = "-" if cost is None else f"${float(cost):.6f}"
    text = " ".join(redact(question or "").split())  # any whitespace or line break -> one space
    text = text if len(text) <= 90 else text[:87] + "..."
    return (
        f"{ts:%Y-%m-%d %H:%M:%S}  {route or '-':8}  {flag:9}  office={office or '-':14} "
        f"{status or '-':15} {ms if ms is not None else '-':>6} ms  tokens {tokens:>9}  {price:>10}"
        f"  vote={vote or '-':4} id={rid.hex if rid else '-'}  | {text}"
    )


COLUMNS = (
    "request_id", "ts", "source", "status", "route", "abstained", "abstain_reason",
    "contact_office", "today", "chat_model", "question", "answer", "retrieved",
    "prompt_tokens", "completion_tokens", "embedding_tokens", "cost_usd", "latency_ms",
    "query_cache_hit", "feedback", "feedback_at", "trace",
)  # fmt: skip


def show(conn, request_id: str) -> str | None:
    """The whole stored row of one API request as text, redacted again; None if there is none."""
    try:
        rid = uuid.UUID(request_id.strip()).hex
    except ValueError:
        return None
    row = conn.execute(
        f"SELECT {', '.join(COLUMNS)} FROM request_logs WHERE request_id = %s AND source = 'api'",
        (rid,),
    ).fetchone()
    if row is None:
        return None
    out = []
    for name, value in zip(COLUMNS, row, strict=True):
        if name in ("retrieved", "trace"):
            text = json.dumps(value, indent=2, ensure_ascii=False)
            out.append(f"{name}:\n" + "\n".join("  " + ln for ln in redact(text).splitlines()))
        else:
            if isinstance(value, uuid.UUID):
                value = value.hex  # the form the API returns
            out.append(f"{name}: {redact(value) if isinstance(value, str) else value}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.api.logs")
    p.add_argument("--last", type=int, default=10, help="how many requests to show")
    p.add_argument("--since", type=date.fromisoformat, help="only requests from this date")
    p.add_argument("--route", choices=ROUTES, help="only this route")
    p.add_argument("--feedback", choices=FEEDBACK, help="only requests with this vote (any: voted)")
    p.add_argument("--id", help="print the whole stored row of this request id")
    args = p.parse_args(argv[1:])
    with connect() as conn:
        if args.id:
            text = show(conn, args.id)
            print(text if text else "no API request with that id")
            return 0 if text else 1
        rows, total, cost, votes = fetch(conn, args.last, args.since, args.route, args.feedback)
    for row in rows:
        print(line(row))
    filtered = args.since or args.route or args.feedback
    scope = " matching" if filtered else ""
    print(
        f"{total} API requests{scope}, total cost ${cost:.6f}; "
        f"votes: {votes['up']} up, {votes['down']} down, {votes['none']} no vote"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
