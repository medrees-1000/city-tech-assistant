"""Show the last API requests: uv run python -m cta.api.logs --last 5 [--since DATE] [--route R]

Reads only what the API stored (already redacted) and redacts it again before printing.
"""

import argparse
import sys
from datetime import date

from cta.index.db import connect
from cta.redact import redact

ROUTES = ("calendar", "chain", "retrieve")


def where(since: date | None, route: str | None) -> tuple[str, list]:
    clauses, params = ["source = 'api'"], []
    if since:
        clauses.append("ts >= %s")
        params.append(since)
    if route:
        clauses.append("route = %s")
        params.append(route)
    return " AND ".join(clauses), params


def fetch(conn, last: int, since: date | None = None, route: str | None = None):
    """(the last `last` rows, number of matching requests, their total cost in USD)."""
    clause, params = where(since, route)
    rows = conn.execute(
        "SELECT ts, question, route, abstained, contact_office, status, latency_ms, "
        "prompt_tokens, completion_tokens, cost_usd FROM request_logs "
        f"WHERE {clause} ORDER BY ts DESC, id DESC LIMIT %s",
        [*params, last],
    ).fetchall()
    total, cost = conn.execute(
        f"SELECT count(*), coalesce(sum(cost_usd), 0) FROM request_logs WHERE {clause}", params
    ).fetchone()
    return rows, total, float(cost)


def line(row) -> str:
    ts, question, route, abstained, office, status, ms, p_tok, c_tok, cost = row
    flag = "-" if abstained is None else ("abstained" if abstained else "answered")
    tokens = "-" if p_tok is None else f"{p_tok}/{c_tok}"
    price = "-" if cost is None else f"${float(cost):.6f}"
    text = " ".join(redact(question or "").split())  # any whitespace or line break -> one space
    text = text if len(text) <= 90 else text[:87] + "..."
    return (
        f"{ts:%Y-%m-%d %H:%M:%S}  {route or '-':8}  {flag:9}  office={office or '-':14} "
        f"{status or '-':15} {ms if ms is not None else '-':>6} ms  tokens {tokens:>9}  {price:>10}"
        f"  | {text}"
    )


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.api.logs")
    p.add_argument("--last", type=int, default=10, help="how many requests to show")
    p.add_argument(
        "--since", type=date.fromisoformat, help="only requests from this date (YYYY-MM-DD)"
    )
    p.add_argument("--route", choices=ROUTES, help="only this route")
    args = p.parse_args(argv[1:])
    with connect() as conn:
        rows, total, cost = fetch(conn, args.last, args.since, args.route)
    for row in rows:
        print(line(row))
    scope = " matching" if args.since or args.route else ""
    print(f"{total} API requests{scope}, total cost ${cost:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
