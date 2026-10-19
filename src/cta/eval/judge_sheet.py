# ruff: noqa: E501  (long report strings)
"""Judge hand-check sheet for step 3b (no model call; reads results files, request_logs and chunks).

    uv run python -m cta.eval.judge_sheet           # writes docs/archive/judge-check-v3b.md
    uv run python -m cta.eval.judge_sheet --agreement   # prints the rubric v3 agreement row

Each item shows the question, the gold answer, the model's answer, the judge's verdicts and reasons
copied unedited, the claim the judge names, and the numbered sources exactly as the answerer received
them (full text in a <details> block), with blank lines for the owner's verdicts. It never says which
verdict is right. The rubric v3 agreement row is computed from the stored v3 re-judge against the
owner verdicts already written in docs/judge-check.md.
"""

import json
import re
import sys

from cta.answer import format_source
from cta.eval.questions import load_questions
from cta.eval.run_retrieval import RESULTS
from cta.redact import redact
from cta.settings import ROOT

CHECK = ROOT / "docs" / "judge-check.md"
OUT = ROOT / "docs" / "archive" / "judge-check-v3b.md"
# (question, run label, how to name it) in the order the owner asked for
ITEMS = [
    ("q22", "baseline-dev-60-v3", "stored baseline answer, arm OFF run 1 (rubric v3 verdicts)"),
    ("q22", "on-run1", "arm ON run 1"),
    ("q40", "baseline-dev-60-v3", "stored baseline answer, arm OFF run 1 (rubric v3 verdicts)"),
    ("q40", "on-run1", "arm ON run 1"),
    ("q52", "baseline-dev-60-v3", "stored baseline answer, arm OFF run 1 (rubric v3 verdicts)"),
    ("q52", "on-run1", "arm ON run 1"),
    ("q15", "on-run1", "arm ON run 1"),
    ("q15", "baseline-dev-60-v3", "stored baseline answer, arm OFF run 1 (rubric v3 verdicts)"),
]  # fmt: skip
HEADING = re.compile(r"^## (q\d+) ", re.M)
VERDICT = re.compile(r"\*\*My verdict:\*\* correctness (\w+) / faithfulness (\w+)")


def owner_verdicts(text: str) -> dict[str, tuple[str, str]]:
    """question id -> (correctness, faithfulness) from the '**My verdict:**' lines of judge-check.md."""
    parts = HEADING.split(text)
    out = {}
    for qid, body in zip(parts[1::2], parts[2::2], strict=True):
        found = VERDICT.search(body)
        if found:
            out[qid] = (found.group(1), found.group(2))
    return out


def agreement(records: list[dict], owner: dict[str, tuple[str, str]]) -> dict:
    """Agreement of the judge records with the owner on the owner's items, and the disagreements."""
    by_id = {r["id"]: r for r in records}
    ids = sorted(owner)
    correctness = [i for i in ids if by_id[i]["correctness"] != owner[i][0]]
    faithfulness = [i for i in ids if by_id[i]["faithfulness"] != owner[i][1]]
    notes = [f"{i} correctness ({by_id[i]['correctness']} vs {owner[i][0]})" for i in correctness]
    notes += [
        f"{i} faithfulness ({by_id[i]['faithfulness']} vs {owner[i][1]})" for i in faithfulness
    ]
    return {
        "n": len(ids),
        "correctness": len(ids) - len(correctness),
        "faithfulness": len(ids) - len(faithfulness),
        "disagreements": notes,
    }


def agreement_row(label: str, result: dict) -> str:
    n = result["n"]
    notes = ", ".join(result["disagreements"]) or "none"
    return f"| {label} | {result['correctness']} / {n} | {result['faithfulness']} / {n} | {notes} |"


def named_claims(record: dict) -> list[str]:
    """The judge's own sentences to check, copied unedited: its reason for any verdict that is not
    correct / yes."""
    lines = []
    if record["correctness"] != "correct":
        lines.append(f"correctness ({record['correctness']}): {record['correctness_reason']}")
    if record["faithfulness"] not in ("yes", None):
        lines.append(f"faithfulness ({record['faithfulness']}): {record['faithfulness_reason']}")
    return lines


def source_block(n: int, chunk: dict, rank_note: str) -> str:
    """One numbered source exactly as the answerer received it, inside <details>."""
    summary = f"[{n}] {chunk['source']} | {chunk['heading_path']} | rank {rank_note}"
    return f"<details><summary>{summary}</summary>\n\n```\n{format_source(n, chunk)}\n```\n\n</details>"


def render_item(
    q: dict, run_label: str, how: str, record: dict, answer: str, chunks: list[dict]
) -> str:
    out = [
        f"## {q['id']} ({q['type']}): {how}, run `{run_label}`",
        "",
        f"**Question:** {q['question']}",
        "",
        f"**Gold answer:** {q['gold_answer']}",
        "",
        f"**Model's answer:** {answer}",
        "",
        f"**Judge, correctness:** {record['correctness']}: {record['correctness_reason']}",
        "",
        f"**Judge, faithfulness:** {record['faithfulness']}: {record['faithfulness_reason']}",
        "",
    ]
    claims = named_claims(record)
    if claims:
        out += ["**What the judge names, copied from its reasons:**", ""]
        out += [f"- {line}" for line in claims] + [""]
    out += [f"**Sources the answerer received ({len(chunks)}):**", ""]
    out += [source_block(n, c, str(n)) + "\n" for n, c in enumerate(chunks, 1)]
    out += ["**My verdict:** correctness  / faithfulness ", ""]
    return "\n".join(out)


# ---- the parts that read the database ----


def stored_answer(conn, run_label: str, question: str) -> tuple[str, list[str]]:
    """(answer text, retrieved chunk ids in the order the answerer saw them) from request_logs."""
    old = json.loads((RESULTS / f"{run_label}.json").read_text(encoding="utf-8"))
    log_label = old.get("rejudge_of") or run_label  # a re-judge reuses the original run's logs
    run_id = conn.execute(
        "SELECT id FROM eval_runs WHERE label = %s ORDER BY id DESC LIMIT 1", (log_label,)
    ).fetchone()[0]
    text, retrieved = conn.execute(
        "SELECT answer, retrieved FROM request_logs WHERE run_id = %s AND question = %s "
        "ORDER BY id DESC LIMIT 1",
        (run_id, redact(question)),
    ).fetchone()
    return text, [r["id"] for r in retrieved]


def load_chunks(conn, ids: list[str]) -> list[dict]:
    columns = "id, kind, source, heading_path, terms, last_updated, text"
    rows = {r[0]: dict(zip(columns.split(", "), r, strict=True)) for r in conn.execute(
        f"SELECT {columns} FROM chunks WHERE id = ANY(%s)", (ids,))}  # fmt: skip
    return [rows[i] for i in ids]


def build(conn) -> str:
    questions = {q["id"]: q for q in load_questions()}
    head = [
        "# Judge hand-check sheet for the step 3b answers (rubric v3)",
        "",
        "Items in the order requested: q22 and q40 (the stored baseline answer, arm OFF run 1, with its rubric v3 verdicts, and `on-run1`), q52 (same two), q15 (`on-run1`, then the stored baseline answer). "
        "Answers come from `request_logs` (stored with personal data redacted, none here); sources are the chunks the answerer received, in the order it received them, with their full text. "
        "The judge's reasons are copied unedited. This sheet does not say which verdict is right. Fill the blank verdict lines.",
        "",
    ]
    items = []
    for qid, label, how in ITEMS:
        records = {
            r["id"]: r for r in json.loads((RESULTS / f"{label}.json").read_text())["per_question"]
        }
        text, ids = stored_answer(conn, label, questions[qid]["question"])
        items.append(
            render_item(questions[qid], label, how, records[qid], text, load_chunks(conn, ids))
        )
    return "\n".join(head + items)


def v3_agreement_row() -> str:
    owner = owner_verdicts(CHECK.read_text(encoding="utf-8"))
    records = json.loads((RESULTS / "baseline-dev-60-v3.json").read_text())["per_question"]
    return agreement_row(
        "v3, run `baseline-dev-60-v3` (re-judged from the stored answers)",
        agreement(records, owner),
    )


def main(argv: list[str]) -> int:
    if "--agreement" in argv:
        print(v3_agreement_row())
        return 0
    from cta.index.db import connect

    with connect() as conn:
        OUT.write_text(build(conn), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
