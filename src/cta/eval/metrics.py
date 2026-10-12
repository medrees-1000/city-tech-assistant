"""Retrieval metrics. Pure functions: no database, no network.

Definitions (all per question, then averaged over the scored questions):
- relevant chunk: chunk.source_id equals a gold source id, or a gold source id is in
  chunk.merged_section_ids (a table merged into its parent still counts for the table's id).
- scorable gold sources: the gold sources that are not calendar event ids (fall-2026-044 and so on;
  the calendar table answers those, not vector search).
- recall@k    = distinct scorable gold sources matched in the top k / scorable gold sources
- precision@k = relevant chunks in the top k / k
- hit rate@k  = 1 if any relevant chunk is in the top k, else 0
- MRR         = 1 / rank of the first relevant chunk within the top 10, else 0
A question with no scorable gold source (abstain, advice, calendar-only, clarify without a section
source) is excluded from retrieval metrics: question_metrics returns None for it.
"""

import re
from statistics import mean

CALENDAR_ID = re.compile(r"^(fall|winter|spring|summer)-\d{4}-\d+$")
KS = (1, 3, 5, 10)


def scorable_gold(question: dict) -> list[str]:
    """The distinct gold source ids that retrieval is scored on, in order."""
    ids = [g["id"] for g in question["gold_sources"] if not CALENDAR_ID.match(g["id"])]
    return list(dict.fromkeys(ids))


def matched_gold(chunk: dict, gold: list[str]) -> set[str]:
    """The gold ids this chunk stands for (empty when the chunk is not relevant)."""
    own = {chunk["source_id"], *chunk.get("merged_section_ids", [])}
    return own & set(gold)


def question_metrics(chunks: list[dict], gold: list[str], ks: tuple[int, ...] = KS) -> dict | None:
    """Metrics for one question from its ranked chunks (best first). None if nothing is scorable."""
    if not gold:
        return None
    hits = [matched_gold(c, gold) for c in chunks]
    first = next((i for i, h in enumerate(hits, 1) if h), None)
    out: dict = {"first_rank": first, "mrr": 1 / first if first and first <= 10 else 0.0}
    for k in ks:
        found = set().union(*hits[:k]) if hits[:k] else set()
        relevant = sum(1 for h in hits[:k] if h)
        out[f"recall@{k}"] = len(found) / len(gold)
        out[f"precision@{k}"] = relevant / k
        out[f"hit@{k}"] = 1.0 if relevant else 0.0
    return out


def average(per_question: list[dict], ks: tuple[int, ...] = KS) -> dict:
    """Mean of each metric over the scored questions, with n."""
    names = [f"{m}@{k}" for k in ks for m in ("recall", "precision", "hit")] + ["mrr"]
    return {"n": len(per_question)} | {
        name: mean(q[name] for q in per_question) if per_question else None for name in names
    }
