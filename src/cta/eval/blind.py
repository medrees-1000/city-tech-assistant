# ruff: noqa: E501  (the sheet header is prose; long lines are fine)
"""The blind A/B grading of the version 2 casual held-out set (docs/decisions.md, version 2
pre-registration): the export of the two answer files, the grading sheet and its parser.

    uv run python -m cta.eval.blind export BASELINE-answers.jsonl FIX-answers.jsonl OUT-PREFIX
    uv run python -m cta.eval.blind make BLIND.jsonl QUESTIONS.jsonl SHEET.md
    uv run python -m cta.eval.blind parse SHEET.md GRADES.json

`export` reads the two answer files written by scripts/export_final_answers.py and writes
OUT-PREFIX-blind.jsonl (one row per question: the two answers as "A" and "B", the configuration
hidden, the A/B assignment random per question) and OUT-PREFIX-key.json (which configuration is
A for each question). Open the key file only after grading. Calls no model and no database.
Fields that would give the configuration away (route, abstain reason) are left out.

`make` writes one Markdown sheet from the blind file, in the blind file's (shuffled) order. It
shows the question as typed, the confirmed expected behavior, and the two answers; nothing that
names the configuration. `parse` reads the filled-in sheet back into JSON (graded_blind true),
rejects any grade word that is not allowed and lists every blank. Neither `make` nor `parse`
reads the key file, calls a model or touches the database.
(This file was blind_export.py and blind_sheet.py.)
"""

import json
import random
import re
import sys
from pathlib import Path

# ---- the blind export (was blind_export.py) ----

SHOWN = ("answer", "citations", "sources_shown")


def load_answers(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["id"]: r for r in rows}


def blind_rows(
    baseline: dict[str, dict], fix: dict[str, dict], rng: random.Random
) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """(rows to grade, key). The same question ids must be in both runs. Rows are shuffled too,
    so the file order does not follow the run order."""
    if baseline.keys() != fix.keys():
        only = sorted(baseline.keys() ^ fix.keys())
        raise ValueError(f"the two runs do not have the same questions: {', '.join(only)}")
    rows, key = [], {}
    for qid in baseline:
        baseline_is_a = rng.random() < 0.5
        a, b = (baseline[qid], fix[qid]) if baseline_is_a else (fix[qid], baseline[qid])
        key[qid] = {
            "A": "baseline" if baseline_is_a else "fix",
            "B": "fix" if baseline_is_a else "baseline",
        }
        rows.append({
            "id": qid, "question": baseline[qid]["question"],
            **{f"{f}_A": a.get(f) for f in SHOWN}, **{f"{f}_B": b.get(f) for f in SHOWN},
        })  # fmt: skip
    rng.shuffle(rows)
    return rows, key


def export_main(argv: list[str], rng: random.Random | None = None) -> int:
    if len(argv) != 4:
        print("usage: blind export BASELINE-answers.jsonl FIX-answers.jsonl OUT-PREFIX")
        return 2
    baseline, fix = load_answers(Path(argv[1])), load_answers(Path(argv[2]))
    out = Path(argv[3])
    blind, key = out.with_name(out.name + "-blind.jsonl"), out.with_name(out.name + "-key.json")
    if blind.exists() or key.exists():
        print(f"refused: {blind.name} or {key.name} already exists")
        return 2
    try:
        rows, assignment = blind_rows(baseline, fix, rng or random.SystemRandom())
    except ValueError as e:
        print(f"refused: {e}")
        return 2
    blind.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    key.write_text(json.dumps(assignment, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} questions written to {blind.name}; the key is in {key.name} (not yet)")
    return 0



# ---- the grading sheet (was blind_sheet.py) ----

GRADES = ("correct", "partial", "acceptable_abstain", "incorrect", "wrongly_abstained")
PREFIX = "CONFIRMED Oct 17, 2026 by owner. "

HEADER = """# Blind grading sheet: held-out casual set (41 questions)

Fill in the blanks after `Grade A:` and `Grade B:` with one of: {words}.
Where the two answers are identical, only one `Grade:` line is shown. `Notes:` is optional.
Leave nothing you cannot grade blank on purpose: the parser lists every blank.

What the words mean:
- **correct**: matches the confirmed expected behavior, cited, nothing unsupported.
- **partial**: substantive and supported but incomplete (for example one half of a two-part question).
- **acceptable_abstain**: only for questions labeled uncertain/thin-data: a refusal that names the right office. Counts as neither a win nor an error.
- **incorrect**: a confident unsupported claim, a wrong date, or falling for a trap (echoing the insult in #40, confirming "three years" in #19, confirming the $20 fee in #37, presenting penalty fees as "the fees" in #14).
- **wrongly_abstained**: a refusal on a question labeled "answer".

"""


def same(a: str | None, b: str | None) -> bool:
    return " ".join((a or "").split()) == " ".join((b or "").split())


def block(row: dict, question: dict) -> str:
    expected = question["note"].removeprefix(PREFIX)
    gold = question["gold_answer"]
    lines = [
        f"## {row['id']}",
        "",
        f"**Question:** {row['question']}",
        "",
        f"**Label:** {question['tags'][0]}" + (" (trap)" if "trap" in question["tags"] else ""),
        f"**Expected:** {expected}",
    ]
    if gold not in ("TODO", "ABSTAIN"):
        lines.append(f"**Gold answer:** {gold}")
    lines.append("")
    if same(row["answer_A"], row["answer_B"]):
        lines += ["**A and B are identical.**", "", quote(row["answer_A"]), "", "Grade: ____"]
    else:
        lines += ["**Answer A**", "", quote(row["answer_A"]), "", "**Answer B**", ""]
        lines += [quote(row["answer_B"]), "", "Grade A: ____", "Grade B: ____"]
    lines += ["Notes: ____", "", "---", ""]
    return "\n".join(lines)


def quote(text: str | None) -> str:
    return "\n".join("> " + line for line in (text or "(no answer)").splitlines())


def make_sheet(blind_rows: list[dict], questions: dict[str, dict]) -> str:
    body = "".join(block(r, questions[r["id"]]) for r in blind_rows)
    return HEADER.format(words=", ".join(GRADES)) + body


GRADE_LINE = re.compile(r"^(Grade A|Grade B|Grade|Notes):[ \t]*(.*)$")
BLANK = {"", "____"}


def parse_sheet(text: str) -> tuple[dict, list[str], list[str]]:
    """(grades by question id, blanks, bad words). A blank is a Grade line left as ____."""
    grades: dict[str, dict] = {}
    blanks: list[str] = []
    bad: list[str] = []
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            grades[current] = {"identical": False}
            continue
        m = GRADE_LINE.match(line)
        if not m or current is None:
            continue
        label, value = m[1], m[2].strip()
        if label == "Notes":
            grades[current]["notes"] = "" if value in BLANK else value
            continue
        slots = ("A", "B") if label == "Grade" else (label[-1],)
        grades[current]["identical"] = label == "Grade"
        for slot in slots:
            if value in BLANK:
                blanks.append(f"{current} {slot}")
                grades[current][slot] = None
            elif value in GRADES:
                grades[current][slot] = value
            else:
                bad.append(f"{current} {slot}: {value!r}")
    return grades, blanks, bad


def sheet_main(argv: list[str]) -> int:
    if len(argv) == 5 and argv[1] == "make":
        blind = [json.loads(x) for x in Path(argv[2]).read_text(encoding="utf-8").splitlines() if x]
        qs = {}
        for x in Path(argv[3]).read_text(encoding="utf-8").splitlines():
            if x:
                q = json.loads(x)
                qs[q["id"]] = q
        out = Path(argv[4])
        if out.exists():
            print(f"refused: {out} already exists")
            return 2
        out.write_text(make_sheet(blind, qs), encoding="utf-8")
        print(f"{len(blind)} questions written to {out}")
        return 0
    if len(argv) == 4 and argv[1] == "parse":
        out = Path(argv[3])
        if out.exists():
            print(f"refused: {out} already exists")
            return 2
        grades, blanks, bad = parse_sheet(Path(argv[2]).read_text(encoding="utf-8"))
        if bad:
            print("refused: grade words that are not allowed:\n  " + "\n  ".join(bad))
            print("allowed: " + ", ".join(GRADES))
            return 1
        out.write_text(
            json.dumps({"graded_blind": True, "grades": grades}, indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(f"{len(grades)} questions written to {out}")
        if blanks:
            print(f"{len(blanks)} blank grades: " + ", ".join(blanks))
        return 0
    print(__doc__)
    return 2


def main(argv: list[str]) -> int:
    """`blind export ...` writes the blind files; `blind make|parse ...` does the sheet."""
    if len(argv) > 1 and argv[1] == "export":
        return export_main([argv[0], *argv[2:]])
    return sheet_main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
