"""Replay check of contact policy v2 (docs/step4c-plan.md, "v2"). No model or embedding call.

    uv run python -m cta.eval.contact_replay [--write docs/step4c-replay-v2.md]

Takes the dev answers stored in request_logs for 4b-run1..3, rebuilds each real answer (the log
replaces emails and phones by [EMAIL] and [PHONE]; the rebuild is checked by redacting it again),
and compares the policy of cta.graph.contact (v2) with the frozen policy v1 (kept below only for the
comparison). Only dev questions are read.
"""

import argparse
import json
import re
import subprocess
import sys
from types import SimpleNamespace

from cta.eval.questions import load_questions
from cta.graph import contact, render
from cta.index.db import connect
from cta.redact import redact
from cta.settings import ROOT

RUNS = ["4b-run1", "4b-run2", "4b-run3"]
PREDICTED_LOST = {"q47", "q49"}  # pre-registered: their only match was the chunk map
KEPT_RULES = ("calendar", "chain (department prefix)", "department", "account cue")


# ---- the frozen policy v1 (what the 4b runs were replayed with), for comparison only ----


def v1_chunk_office(chunk: dict, table: dict) -> str | None:
    offices, cid = table["offices"], chunk["id"]
    if cid.startswith("catalog:"):
        owner = chunk.get("department")
    elif cid.startswith("contact:"):
        owner = cid.removeprefix("contact:")
    elif cid.startswith("pdf/"):
        owner = table["pdf_offices"].get(cid.split("/")[1].split("#")[0])
    else:
        owner = cid.split("/")[1] if cid.count("/") >= 2 else None
    return owner if owner in offices else None


def v1_office_and_rule(question: str, ans, table: dict) -> tuple[str, str]:
    reason = ans.abstain_reason or ""
    if reason.startswith("calendar_"):
        return "registrar", "calendar"
    dept = contact.named_department(question)
    if reason == "chain_no_record":
        return (dept, "chain (department prefix)") if dept else ("advisement", "chain default")
    if dept:
        return dept, "department"
    if key := contact.cue_office(question, table):
        return key, "account cue"
    if ans.sources and (key := v1_chunk_office(ans.sources[0], table)):
        return key, "chunk map"
    return table["fallback"], "fallback"


# ---- the replay ----


def rebuild(logged: str) -> str:
    """The real answer text: the only redacted contact in these logs is the Registrar line."""
    text = logged.replace("[EMAIL], [PHONE]", render.registrar_contact())
    if redact(text) != logged:
        raise ValueError("cannot rebuild the answer from the log: " + logged[:80])
    return text


def load_rows(conn, chunk_dept: dict) -> list[dict]:
    dev = {redact(q["question"]): q for q in load_questions() if q["split"] == "dev"}
    out = []
    for label in RUNS:
        run_id = conn.execute("SELECT id FROM eval_runs WHERE label = %s", (label,)).fetchone()[0]
        sql = "SELECT question, answer, abstained, abstain_reason, retrieved FROM request_logs "
        for question, text, abstained, reason, retrieved in conn.execute(
            sql + "WHERE run_id = %s", (run_id,)
        ):
            q = dev[question]
            sources = [{"id": r["id"], "department": chunk_dept.get(r["id"])} for r in retrieved]
            out.append({
                "run": label, "id": q["id"], "question": q["question"], "text": rebuild(text),
                "abstained": abstained, "reason": reason, "sources": sources,
            })  # fmt: skip
    return out


def fresh(r: dict, text: str | None = None):
    """The stored answer as the object add_contact works on."""
    return SimpleNamespace(
        text=r["text"] if text is None else text, abstained=r["abstained"],
        abstain_reason=r["reason"], sources=r["sources"],
    )  # fmt: skip


def replay(rows: list[dict]) -> None:
    table = contact.load_contacts()
    for r in rows:
        r["old_office"] = r["old_rule"] = r["old_text"] = None
        if r["abstained"]:
            r["old_office"], r["old_rule"] = v1_office_and_rule(r["question"], fresh(r), table)
            line = contact.contact_line(r["old_office"], table)
            r["old_line"] = line
            r["old_text"] = r["text"] if line in r["text"] else f"{r['text']} {line}"
        a = fresh(r)
        r["new_office"] = contact.add_contact(a, r["question"])
        r["new"] = a.text
        twice = fresh(r, a.text)
        contact.add_contact(twice, r["question"])
        r["twice"] = twice.text


def verdicts(rows: list[dict], validator_ok: bool, tools_ok: bool) -> dict[str, tuple[bool, str]]:
    abst = [r for r in rows if r["abstained"]]
    keep = [r for r in rows if not r["abstained"]]
    kept = [r for r in abst if r["old_rule"] in KEPT_RULES]
    lost = [r for r in abst if r["old_rule"] not in KEPT_RULES]
    v1_bad = [r for r in kept if r["new_office"] != r["old_office"] or r["new"] != r["old_text"]]
    v2_bad = [r for r in lost if r["new_office"] is not None or r["new"] != r["text"]]
    lost_ids = {r["id"] for r in lost}
    per_run = {run: {r["id"] for r in lost if r["run"] == run} for run in RUNS}
    v3_bad = [r for r in keep if r["new"] != r["text"]]
    double = [r for r in rows if len(re.findall(r"Contact (the |Advisement)", r["new"])) > 1]
    idem = [r for r in rows if r["twice"] != r["new"]]
    kept_msg = f"{len(kept)} abstentions from the rules that stay keep the identical line"
    lost_msg = f"lost the line: {sorted(lost_ids)} (predicted {sorted(PREDICTED_LOST)})"
    same_msg = f"{len(keep)} non-abstaining answers byte-identical; no double lines; idempotent"
    predicted = all(ids == PREDICTED_LOST for ids in per_run.values())
    return {
        "V1": (not v1_bad, kept_msg),
        "V2": (not v2_bad and predicted, lost_msg + ", the same in each of the three runs"),
        "V3": (not v3_bad and not double and not idem, same_msg),
        "V4": (validator_ok, "contacts validator passes"),
        "V5": (tools_ok, "ruff and pytest pass"),
    }


def validator_check() -> bool:
    import yaml

    from cta.index.departments import load_departments
    from cta.validate.contacts import run_contact_checks

    cfg = yaml.safe_load(contact.CONFIG.read_text(encoding="utf-8"))
    _, found = run_contact_checks(cfg, ROOT, list(load_departments()))
    return not found


def tools_check() -> bool:
    run = lambda *cmd: subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 0  # noqa: E731
    return run("uv", "run", "ruff", "check", "src", "tests") and run("uv", "run", "pytest", "-q")


def render_report(rows: list[dict], result: dict) -> str:
    lines = ["| id | run | old office and rule (v1) | new result (v2) |", "|---|---|---|---|"]
    for r in sorted((r for r in rows if r["abstained"]), key=lambda r: (r["id"], r["run"])):
        old = f"{r['old_office']} ({r['old_rule']})"
        if r["new_office"] is None:
            new = f"**line removed**; old line: {r['old_line']}"
        elif r["new"] == r["old_text"]:
            new = f"same line ({r['new_office']})"
        else:
            new = f"CHANGED to {r['new_office']}"
        lines.append(f"| {r['id']} | {r['run']} | {old} | {new} |")
    lines += ["", "| rule | verdict | detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {why} |" for k, (ok, why) in result.items()]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.contact_replay")
    p.add_argument("--write", help="also write the report to this file")
    p.add_argument("--skip-tools", action="store_true", help="do not run ruff and pytest (V5)")
    args = p.parse_args(argv[1:])
    chunk_dept = {}
    for line in (ROOT / "data/processed/chunks.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        chunk_dept[c["id"]] = c["department"]
    with connect() as conn:
        rows = load_rows(conn, chunk_dept)
    replay(rows)
    result = verdicts(rows, validator_check(), True if args.skip_tools else tools_check())
    report = render_report(rows, result)
    print(report)
    if args.write:
        (ROOT / args.write).write_text(report + "\n", encoding="utf-8")
    return 0 if all(ok for ok, _ in result.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
