"""Fallback query rewrite (experiment E1; docs/decisions.md, "Casual round").

Used only when the first retrieval of a plain question scores under the cutoff: one small model call
turns the cleaned question into a short search query, and retrieval runs once more with it. The
answer step still gets the student's own words. A failed or slow call returns no query (the caller
then behaves exactly as without the rewrite). Written once and committed before any E1 run.
"""

import re
import time
from dataclasses import dataclass

from cta.redact import redact
from cta.settings import cost_usd

TIMEOUT_S = 15
MAX_OUTPUT_TOKENS = 60
MAX_WORDS = 20

INSTRUCTIONS = """\
You rewrite a student's short, informal question into a short search query for the help pages and
documents of City Tech (CUNY): registration, deadlines, advising, tuition and payment, financial
aid, and four departments.

Rules:
1. Expand abbreviations and student shorthand (for example fafsa to FAFSA financial aid
   application, cst to Computer Systems Technology, dept to department, chair or head to
   department chair, dl to deadline, prereq to prerequisite).
2. Drop emotional filler, jokes and idioms; keep what the student wants to know.
3. Keep every course code, number and term name (for example Fall 2026) exactly as written.
4. Add no fact, date, number, office or name that is not in the question.
5. Reply with only the query: at most 20 words, one line, no quotes, no explanation.
"""


@dataclass
class Rewrite:
    query: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    ms: float = 0.0
    error: str | None = None


def clean_query(text: str, original: str) -> str | None:
    """One line of at most MAX_WORDS words, or None when it is empty, has no letter, or is the
    original again."""
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    line = re.sub(r"\s+", " ", line).strip(" \"'`")
    words = line.split()[:MAX_WORDS]
    line = " ".join(words)
    if not line or not re.search(r"[A-Za-z]", line):
        return None
    if line.lower() == re.sub(r"\s+", " ", original).strip().lower():
        return None
    return redact(line)


def rewrite_query(client, cfg: dict, question: str) -> Rewrite:
    """Never raises. temperature 0, no reasoning, tiny output, 15 s timeout, no retries."""
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=cfg["chat_model"],
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"Question: {question}"},
            ],
            temperature=0,
            reasoning_effort=cfg["router"]["reasoning_effort"],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            timeout=TIMEOUT_S,
        )
    except Exception as e:  # noqa: BLE001 - any failure: the caller falls back to today's behaviour
        return Rewrite(ms=(time.perf_counter() - started) * 1000, error=type(e).__name__)
    ms = (time.perf_counter() - started) * 1000
    usage = response.usage
    spent = cost_usd(cfg, cfg["chat_model"], usage.prompt_tokens, usage.completion_tokens)
    result = Rewrite(None, usage.prompt_tokens, usage.completion_tokens, spent, ms)
    result.query = clean_query(response.choices[0].message.content or "", question)
    if result.query is None:
        result.error = "unusable reply"
    return result
