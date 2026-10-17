# ruff: noqa: E501  (the sheet header is prose; long lines are fine)
"""The grading sheet for the blind A/B grading (docs/decisions.md, version 2 pre-registration).

    uv run python -m cta.eval.blind_sheet make BLIND.jsonl QUESTIONS.jsonl SHEET.md
    uv run python -m cta.eval.blind_sheet parse SHEET.md GRADES.json

`make` writes one Markdown sheet from the blind file of cta.eval.blind_export, in the blind file's
(shuffled) order. It shows the question as typed, the confirmed expected behavior, and the two
answers; nothing that names the configuration. `parse` reads the filled-in sheet back into JSON
(graded_blind true), rejects any grade word that is not allowed and lists every blank. Neither
command reads the key file, calls a model or touches the database.
"""

import json
import re
import sys
from pathlib import Path

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


def main(argv: list[str]) -> int:
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


if __name__ == "__main__":
    sys.exit(main(sys.argv))
