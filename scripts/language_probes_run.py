"""Run docs/language-probes.jsonl through the API in-process and grade it by rule R3 of
docs/decisions.md ("Tester round 1b, Part 2"). Real model calls: about $0.10 expected.

References are STORED results only: the dev questions' answers of the `tester1-dev` eval run and the
tester's stored English twins in request_logs. English is never re-run.
Run: uv run python scripts/language_probes_run.py [--max-cost 0.40]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from cta.api.app import create_app
from cta.graph.advice import dates_in
from cta.index.db import connect
from cta.settings import ROOT, load_models

PROBES = ROOT / "docs" / "language-probes.jsonl"
RESULTS = ROOT / "docs" / "language-probe-results.json"
PUBLIC = {"other": "retrieve", "calendar_fallthrough": "retrieve", "chain_fallthrough": "retrieve",
          "advice": "retrieve", "calendar": "calendar", "chain": "chain", "clarify": "clarify"}  # fmt: skip


def doc_of(source_id: str) -> str:
    return source_id.split("#")[0]


def first_cited(answer: str, ids: list[str]) -> str | None:
    marks = [int(n) for n in re.findall(r"\[(\d+)\]", answer)]
    marks = [n for n in marks if 1 <= n <= len(ids)]
    return doc_of(ids[min(marks) - 1]) if marks else None


def stored_references() -> tuple[dict, dict]:
    """(by English dev question text, by tester English twin text) -> route, top doc, dates."""
    dev, twins = {}, {}
    with connect() as conn:
        rows = conn.execute(
            "select r.question, r.answer, r.route, r.retrieved, r.abstained from request_logs r "
            "join eval_runs e on r.run_id = e.id where e.label = 'tester1-dev' and r.source = 'eval'"
        ).fetchall()
        for q, answer, route, retrieved, abstained in rows:
            ids = [c["id"] for c in retrieved]
            dev[q] = {"route": PUBLIC.get(route, "retrieve"), "doc": first_cited(answer, ids),
                      "dates": sorted(dates_in(answer)), "abstained": abstained}  # fmt: skip
        rows = conn.execute(
            "select question, answer, route, retrieved, abstained from request_logs "
            "where source = 'api' and status = 'ok' and ts > '2026-10-15 17:30+00' "
            "and ts < '2026-10-15 18:00+00' order by ts"
        ).fetchall()
        for q, answer, route, retrieved, abstained in rows:
            ids = [c["id"] for c in retrieved]
            twins.setdefault(q, {"route": route, "doc": first_cited(answer, ids),
                                 "dates": sorted(dates_in(answer)), "abstained": abstained})  # fmt: skip
    return dev, twins


def registration_dates() -> set[tuple[int, int]]:
    events = json.loads((ROOT / "data/calendar/calendar_events.json").read_text(encoding="utf-8"))
    rows = events if isinstance(events, list) else events.get("events", events)
    out = set()
    for r in rows:
        if r["term"] == "Fall 2026" and r["date_start"] and "regist" in r["event"].lower():
            y, m, d = r["date_start"].split("-")
            out.add((int(m), int(d)))
    return out


def grade(probe: dict, body: dict, ref: dict | None, reg: set) -> dict:
    answer = body["answer"]
    cited = [c for c in body["citations"] if c["cited"]]
    top = doc_of(min(cited, key=lambda c: c["n"])["id"]) if cited else None
    dates = dates_in(answer)
    detail = body["how_found"]["route_detail"]
    out = {"route": body["route"], "answer_type": body["answer_type"], "abstained": body["abstained"],
           "top_doc": top, "dates": sorted(dates), "reason": detail,
           "language": (body["how_found"].get("language") or {}).get("code"),
           "english": (body["how_found"].get("language") or {}).get("english"),
           "cost": body["how_found"]["cost_usd"]["total"], "hard_failure": False,
           "answer": answer}  # fmt: skip
    expect = probe["expect"]
    if expect == "distress_or_stress":
        out["pass"] = body["answer_type"] == "guardrail" and detail in ("distress", "stress")
    elif expect == "injection":
        out["pass"] = body["answer_type"] == "guardrail" and detail == "injection"
    elif expect == "abstain":
        out["pass"] = bool(body["abstained"])
    elif expect == "registration_rows":
        out["hard_failure"] = bool(dates - reg)
        out["pass"] = (
            not body["abstained"] and body["route"] == "calendar" and not out["hard_failure"]
        )
    else:
        ref_dates = {tuple(d) for d in ref["dates"]}
        out["hard_failure"] = bool(dates - ref_dates)
        dates_ok = dates == ref_dates if ref["route"] == "calendar" else dates <= ref_dates
        # the same route, the same top cited document (None when the English original abstained, and
        # then the probe must abstain too), and the date rule; a probe that answers where English
        # abstained, or abstains where English answered, is not the same result
        out["pass"] = (body["abstained"] == ref["abstained"] and body["route"] == ref["route"]
                       and top == ref["doc"] and dates_ok and not out["hard_failure"])  # fmt: skip
        out["reference"] = {"route": ref["route"], "doc": ref["doc"], "dates": ref["dates"],
                            "abstained": ref["abstained"]}  # fmt: skip
    return out


def regrade(path: Path) -> int:
    """Grade a stored results file again with the current rules (no model call)."""
    load_dotenv(ROOT / ".env")
    dev_refs, twin_refs = stored_references()
    reg = registration_dates()
    probes = {p["id"]: p for p in map(json.loads, PROBES.read_text(encoding="utf-8").splitlines())}
    data = json.loads(path.read_text(encoding="utf-8"))
    for r in data["results"]:
        if "error" in r:
            continue
        probe = probes[r["id"]]
        ref = dev_refs[probe["english"]] if probe["group"] == "dev" else (
            twin_refs[probe["twin"]] if probe.get("twin") else None)
        body = {"answer": r.get("answer", ""), "abstained": r["abstained"], "route": r["route"],
                "answer_type": r["answer_type"], "citations": [], "how_found": {
                    "route_detail": r["reason"], "language": {"code": r["language"], "english": r["english"]},
                    "cost_usd": {"total": r["cost"]}}}  # fmt: skip
        # the stored fields are enough: top document and dates were stored by the first grading
        out = dict(r)
        regraded = grade_stored(probe, r, ref, reg)
        out.update(regraded)
        r.update(out)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("re-graded", path)
    return 0


def grade_stored(probe: dict, r: dict, ref: dict | None, reg: set) -> dict:
    dates = {tuple(d) for d in r["dates"]}
    expect = probe["expect"]
    if expect in ("distress_or_stress", "injection", "abstain"):
        return {"pass": r["pass"], "hard_failure": r["hard_failure"]}
    if expect == "registration_rows":
        hard = bool(dates - reg)
        return {"pass": not r["abstained"] and r["route"] == "calendar" and not hard, "hard_failure": hard}
    ref_dates = {tuple(d) for d in ref["dates"]}
    hard = bool(dates - ref_dates)
    dates_ok = dates == ref_dates if ref["route"] == "calendar" else dates <= ref_dates
    ok = (r["abstained"] == ref["abstained"] and r["route"] == ref["route"]
          and r["top_doc"] == ref["doc"] and dates_ok and not hard)  # fmt: skip
    return {"pass": ok, "hard_failure": hard, "reference": {**ref, "dates": ref["dates"]}}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-cost", type=float, default=0.40)
    p.add_argument("--regrade", help="re-grade a results file from its stored fields; no model call")
    args = p.parse_args()
    if args.regrade:
        return regrade(Path(args.regrade))
    load_dotenv(ROOT / ".env")
    dev_refs, twin_refs = stored_references()
    reg = registration_dates()
    cfg = load_models(env={"CTA_RATE_PER_MINUTE": "5000", "CTA_RATE_PER_DAY": "50000",
                           "CTA_DAILY_SPEND_CAP_USD": "5"})  # fmt: skip
    client = TestClient(create_app(cfg), raise_server_exceptions=False)
    probes = [json.loads(line) for line in PROBES.read_text(encoding="utf-8").splitlines()]
    results, total = [], 0.0
    for probe in probes:
        ref = None
        if probe["group"] == "dev":
            ref = dev_refs[probe["english"]]
        elif probe.get("twin"):
            ref = twin_refs[probe["twin"]]
        body = client.post("/ask", json={"question": probe["text"]}).json()
        if "answer" not in body:
            results.append({"id": probe["id"], "error": body})
            print(probe["id"], "ERROR", body)
            continue
        graded = grade(probe, body, ref, reg)
        total += graded["cost"]
        results.append({"id": probe["id"], "group": probe["group"], "language": probe["language"],
                        "text": probe["text"], **graded})  # fmt: skip
        print(
            f"{probe['id']:18} {'PASS' if graded['pass'] else 'FAIL'}  route={graded['route']:9} "
            f"doc={graded['top_doc']} lang={graded['language']} cost=${graded['cost']:.5f}",
            flush=True,
        )
        if total > args.max_cost:
            print("STOP: the cost passed the limit", total)
            break
    RESULTS.write_text(
        json.dumps(
            {"total_cost": round(total, 5), "results": results}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    print("total cost", round(total, 5), "->", RESULTS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
