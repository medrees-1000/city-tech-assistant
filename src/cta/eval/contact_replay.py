"""Replay check of step 4c (docs/step4c-plan.md, rules D1 to D8). No model call, no embedding call.

    uv run python -m cta.eval.contact_replay [--write docs/step4c-replay.md]

Takes the dev answers stored in request_logs for 4b-run1..3, rebuilds each real answer (the log
replaces emails and phones by [EMAIL] and [PHONE]; the rebuild is checked by redacting it again),
runs add_contact on it and checks the rules D1 to D8. Only dev questions are read.
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
# The owner-approved table of docs/step4c-plan.md (decisions of 2026-10-13); not adjusted.
APPROVED = {
    "q15": "EET-NYT", "q27": "CST-NYT", "q28": "MATH-NYT", "q34": "registrar", "q44": "registrar",
    "q45": "MATH-NYT", "q47": "registrar", "q49": "registrar", "q83": "CST-NYT",
}  # fmt: skip
CONTACT_LIKE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b\d{3}-\d{3}-\d{4}\b")


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


def replay(rows: list[dict]) -> None:
    for r in rows:
        a = SimpleNamespace(text=r["text"], abstained=r["abstained"], abstain_reason=r["reason"],
                            sources=r["sources"])  # fmt: skip
        r["office"] = contact.add_contact(a, r["question"])
        r["new"] = a.text
        twice = SimpleNamespace(text=a.text, abstained=a.abstained, abstain_reason=a.abstain_reason,
                                sources=a.sources)  # fmt: skip
        contact.add_contact(twice, r["question"])
        r["twice"] = twice.text


def verdicts(rows: list[dict], d6: bool, d8: bool) -> dict[str, tuple[bool, str]]:
    table = contact.load_contacts()
    abst = [r for r in rows if r["abstained"]]
    keep = [r for r in rows if not r["abstained"]]
    line = {r["id"]: contact.contact_line(r["office"], table) for r in abst}
    known = {x for o in table["offices"].values() for x in CONTACT_LIKE.findall(json.dumps(o))}
    d1 = [
        r
        for r in abst
        if not (r["new"].endswith(line[r["id"]]) and r["new"].count(line[r["id"]]) == 1)
    ]
    d2 = [r for r in abst if APPROVED.get(r["id"]) != r["office"]]
    d2_ids = {r["id"] for r in abst} ^ set(APPROVED)
    d3 = [r for r in keep if r["new"] != r["text"]]
    d4 = [r for r in abst if r["new"] not in (r["text"], f"{r['text']} {line[r['id']]}")]
    d5 = [
        r
        for r in rows
        if set(CONTACT_LIKE.findall(r["new"])) - known - set(CONTACT_LIKE.findall(r["text"]))
    ]
    d7 = [r for r in rows if r["twice"] != r["new"]] + [
        r for r in abst if r["id"] == "q34" and r["new"] != r["text"]
    ]  # fmt: skip
    return {
        "D1": (not d1, f"{len(abst)} abstentions end with exactly one table line"),
        "D2": (not d2 and not d2_ids, f"office = approved table; id differences {sorted(d2_ids)}"),
        "D3": (not d3, f"{len(keep)} non-abstaining answers byte-identical"),
        "D4": (not d4, "text before the contact line unchanged"),
        "D5": (not d5, "no email or phone outside the table or the original"),
        "D6": (d6, "validator PASS and a fax-only number is refused"),
        "D7": (not d7, "idempotent; q34 byte-identical"),
        "D8": (d8, "ruff and pytest pass"),
    }  # fmt: skip


def d6_check() -> bool:
    import yaml

    from cta.validate.contacts import check_entry, run_contact_checks

    cfg = yaml.safe_load(contact.CONFIG.read_text(encoding="utf-8"))
    from cta.index.departments import load_departments

    _, found = run_contact_checks(cfg, ROOT, list(load_departments()))
    record = json.loads((ROOT / "data/processed/contacts/EET-NYT.json").read_text(encoding="utf-8"))
    fax = record["fax"][0]  # the panel prints it after Fax:
    refused = check_entry("EET-NYT", cfg["offices"]["EET-NYT"] | {"phones": [fax]}, record)
    return not found and any("only a fax" in f.message for f in refused)


def d8_check() -> bool:
    run = lambda *cmd: subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 0  # noqa: E731
    return run("uv", "run", "ruff", "check", "src", "tests") and run("uv", "run", "pytest", "-q")


def render_report(rows: list[dict], result: dict) -> str:
    lines = ["| id | run | path | office | line appended |", "|---|---|---|---|---|"]
    for r in sorted((r for r in rows if r["abstained"]), key=lambda r: (r["id"], r["run"])):
        path = r["reason"] if len(r["reason"]) < 30 else "model"
        added = r["new"][len(r["text"]) :].strip() or "(already present, unchanged)"
        lines.append(f"| {r['id']} | {r['run']} | {path} | {r['office']} | {added} |")
    lines += ["", "| rule | verdict | detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {why} |" for k, (ok, why) in result.items()]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.contact_replay")
    p.add_argument("--write", help="also write the report to this file")
    args = p.parse_args(argv[1:])
    chunk_dept = {}
    for line in (ROOT / "data/processed/chunks.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        chunk_dept[c["id"]] = c["department"]
    with connect() as conn:
        rows = load_rows(conn, chunk_dept)
    replay(rows)
    result = verdicts(rows, d6_check(), d8_check())
    report = render_report(rows, result)
    print(report)
    if args.write:
        (ROOT / args.write).write_text(report + "\n", encoding="utf-8")
    return 0 if all(ok for ok, _ in result.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
