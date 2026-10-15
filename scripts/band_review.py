"""Write docs/band-review.md: every question whose stored top retrieval similarity is between 0.50 and
0.65, from the tester's rows and the dev runs. READ-ONLY: stored data only, no model call, no re-run.
No gold answers and no gold sources are read or printed. Run: uv run python scripts/band_review.py
"""

import json
import re
from collections import OrderedDict
from pathlib import Path

from cta.index.db import connect

ROOT = Path(__file__).resolve().parents[1]
LOW, HIGH, CUTOFF = 0.50, 0.65, 0.59
TESTER_FROM, TESTER_TO = "2026-10-15 17:32:00+00", "2026-10-15 17:57:00+00"  # the tester's session
DEV_RUNS = ("tester1-dev", "tester1-new8")  # the most recent dev runs (63 questions + the 8 new ones)


def chunk_index() -> dict:
    out = {}
    for line in (ROOT / "data/processed/chunks.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        out[d["id"]] = (d.get("heading_path") or "", d.get("source") or "")
    return out


def dev_questions() -> dict[str, str]:
    """id -> question of the dev rows only: a row is selected by its raw text BEFORE it is parsed."""
    out = {}
    for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines():
        if re.search(r'"split": ?"dev"', line):
            row = json.loads(line)
            out[row["id"]] = row["question"]
    return out


def noisy(question: str) -> bool:
    """Non-English or non-ASCII text, markup, a redaction placeholder, or an encoded blob."""
    return (not question.isascii() or bool(re.search(r"[<>]|\[[A-Z]+\]|javascript:", question))
            or bool(re.search(r"\S{30,}", question)))  # fmt: skip


def top3(chunks: list[tuple[str, float]], index: dict) -> list[str]:
    out = []
    for cid, sim in sorted(chunks, key=lambda c: -c[1])[:3]:
        heading, source = index.get(cid, ("(not in the processed chunks)", ""))
        out.append(f"{sim:.3f} · {cid} · {heading or '-'} · {source or '-'}")
    return out


def esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    index = chunk_index()
    rows, missing = [], []
    with connect() as conn:
        tester = conn.execute(
            "select request_id, question, route, abstained, abstain_reason, status, trace "
            "from request_logs where source = 'api' and ts >= %s and ts < %s and status = 'ok' "
            "order by ts", (TESTER_FROM, TESTER_TO)).fetchall()  # fmt: skip
    seen: OrderedDict[str, dict] = OrderedDict()
    for rid, question, route, abstained, reason, status, trace in tester:
        if route == "guardrail" or noisy(question):
            continue
        if question in seen:
            seen[question]["repeats"] += 1
            continue
        top = trace.get("top_vector_similarity")
        pool = [(c["id"], c["similarity"]) for c in trace.get("retrieved", []) if c.get("similarity") is not None]
        seen[question] = {"id": str(rid), "source": "tester", "question": question, "repeats": 1,
                          "outcome": f"abstained ({reason})" if abstained else f"answered ({route})",
                          "top": top, "route": route, "chunks": pool}  # fmt: skip
    for r in seen.values():
        (rows if r["top"] is not None else missing).append(r)

    dev = dev_questions()
    for label in DEV_RUNS:
        run = json.loads((ROOT / f"eval/results/{label}.json").read_text(encoding="utf-8"))
        for r in run["per_question"]:
            if r["id"] not in dev:  # only dev ids are ever used
                continue
            pool = [(c["id"], c["similarity"]) for c in r["retrieved"]]
            item = {"id": r["id"], "source": "dev", "question": dev[r["id"]], "repeats": 1,
                    "outcome": f"abstained ({r['abstain_reason']})" if r["abstained"] else f"answered ({r['route']})",
                    "top": max((s for _, s in pool), default=None), "route": r["route"], "chunks": pool}  # fmt: skip
            (rows if item["top"] is not None else missing).append(item)

    band = sorted((r for r in rows if LOW <= r["top"] <= HIGH), key=lambda r: r["top"])
    below = [r for r in band if r["top"] < CUTOFF]
    lines = [
        "# Band review: questions whose stored top similarity is between 0.50 and 0.65",
        "",
        "Written 2026-10-15 (tester round 1b, follow-up item 2). **Read-only: stored data only, no model "
        "call, no re-run, no config change, no recommendation.** The owner and I decide from this table.",
        "",
        "## Where the rows come from",
        "- **tester**: the tester's rows in `request_logs` (`source = 'api'`, 2026-10-15 17:32 to 17:57 UTC, status ok). "
        "Excluded: guardrail and blocked rows, non-English or non-ASCII text, markup, redaction placeholders and encoded "
        "blobs. Identical questions are listed once with their repeat count. Top similarity is the stored "
        "`top_vector_similarity`, the number the 0.59 cutoff is compared with.",
        "- **dev**: the dev questions only (the file's rows were selected by their `split` before any row was read), "
        "from the two most recent dev runs, `tester1-dev` (63 questions) and `tester1-new8` (the 8 new ones). The dev "
        "runs store only the reranked top ten that the runner retrieves for its own metrics, on the question text as "
        "written (without the noise-cleaning step), so the top similarity of a dev row is the **largest similarity "
        "among those stored chunks**. That is **not necessarily the number the pipeline compared with the cutoff**: "
        "the calendar, chain and advice routes search differently (or not at all), and the pipeline cleans noise "
        "first. Two visible effects below: q98 shows 0.592 but abstained `below_threshold` (its cleaned text scored "
        "lower), and q47 and q85 show a value under 0.59 but were answered (the advice route searches its own fixed "
        "question, the chain route does not search). The noise questions q96 to q98 are included (the noise "
        "exclusion applies to the tester rows only).",
        "- **Chunks**: the three stored chunks with the highest similarity, each as `score · chunk id · heading · "
        "source URL or file`; headings and sources come from `data/processed/chunks.jsonl`. No gold answers and no "
        "gold sources are in this file.",
        "",
        f"## The table ({len(band)} rows, sorted by similarity)",
        "",
        "| id or request_id | source | question as stored | outcome | top similarity | top 3 chunks |",
        "|---|---|---|---|---|---|",
    ]
    for r in band:
        ident = r["id"] if r["source"] == "dev" else f'{r["id"][:8]}' + (f' (×{r["repeats"]})' if r["repeats"] > 1 else "")
        marker = "below 0.59" if r["top"] < CUTOFF else "at or above 0.59"
        lines.append(f'| {ident} | {r["source"]} | {esc(r["question"])} | {r["outcome"]} | {r["top"]:.3f} ({marker}) | '
                     + "<br>".join(esc(c) for c in top3(r["chunks"], index)) + " |")
    lines += ["", "## Missing: no stored similarity (nothing was re-run)", "",
              "These rows were answered without retrieval (the calendar, chain or clarify route) or have no stored chunks.", "",
              "| id or request_id | source | question as stored | route |", "|---|---|---|---|"]
    for r in missing:
        ident = r["id"] if r["source"] == "dev" else r["id"][:8] + (f' (×{r["repeats"]})' if r["repeats"] > 1 else "")
        lines.append(f'| {ident} | {r["source"]} | {esc(r["question"])} | {r["route"]} |')
    t = [r for r in band if r["source"] == "tester"]; d = [r for r in band if r["source"] == "dev"]
    lines += ["", "## Counts", "",
              f"- Rows in the band: **{len(band)}** ({len(t)} tester, {len(d)} dev); missing similarity: {len(missing)}.",
              f"- Below the 0.59 cutoff: **{len(below)}** (tester {sum(r['source']=='tester' for r in below)}, dev {sum(r['source']=='dev' for r in below)}).",
              f"- At or above the cutoff: **{len(band) - len(below)}** (tester {sum(r['source']=='tester' and r['top']>=CUTOFF for r in band)}, dev {sum(r['source']=='dev' and r['top']>=CUTOFF for r in band)}).",
              f"- Of the rows below the cutoff, abstained: {sum(r['outcome'].startswith('abstained') for r in below)}; answered anyway (a calendar or other route took them): {sum(r['outcome'].startswith('answered') for r in below)}.",
              ""]
    (ROOT / "docs/band-review.md").write_text("\n".join(lines), encoding="utf-8")
    print(len(band), "rows;", len(missing), "missing;", len(below), "below the cutoff")


if __name__ == "__main__":
    main()
