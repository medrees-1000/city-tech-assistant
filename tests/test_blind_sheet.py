"""The blind grading sheet and its parser (synthetic data; no model, no database)."""

import json

import pytest

from cta.eval import blind_sheet as bs

QUESTIONS = {
    "cv2-01": {"id": "cv2-01", "gold_answer": "TODO", "tags": ["answer"],
               "note": bs.PREFIX + "ANSWER. Calendar rows."},
    "cv2-02": {"id": "cv2-02", "gold_answer": "ABSTAIN", "tags": ["refuse", "trap"],
               "note": bs.PREFIX + "ABSTAIN (trap)."},
}  # fmt: skip
ROWS = [
    {
        "id": "cv2-02",
        "question": "q two  typed",
        "answer_A": "Same  text.",
        "answer_B": "Same text.",
    },
    {"id": "cv2-01", "question": "q one", "answer_A": "First.\nLine two.", "answer_B": "Other."},
]


def sheet():
    return bs.make_sheet(ROWS, QUESTIONS)


def test_the_sheet_keeps_the_order_shows_the_question_as_typed_and_has_grade_lines():
    text = sheet()
    assert text.index("## cv2-02") < text.index("## cv2-01")  # the blind file's shuffled order
    assert "**Question:** q two  typed" in text
    assert "**Expected:** ABSTAIN (trap)." in text and "CONFIRMED" not in text
    assert "(trap)" in text and "Grade A: ____" in text and "Grade B: ____" in text
    assert "> First.\n> Line two." in text
    for word in bs.GRADES:
        assert word in text.split("## cv2-02")[0]  # the definitions are at the top


def test_identical_answers_are_shown_once_with_a_single_grade_line():
    text = sheet()
    second, first = (
        text[text.index("## cv2-02") : text.index("## cv2-01")],
        text.split("## cv2-01")[1],
    )
    assert "A and B are identical" in second and "Grade: ____" in second
    assert "Grade A:" not in second and second.count("Same") == 1
    assert "A and B are identical" not in first


def test_the_sheet_names_no_configuration():
    text = sheet().lower()
    for hint in ("baseline", "rescue", "route", "abstain_reason", "similarity", "score"):
        assert hint not in text


def fill(text, a="correct", b="partial", both="acceptable_abstain"):
    out = text.replace("Grade A: ____", f"Grade A: {a}").replace("Grade B: ____", f"Grade B: {b}")
    return out.replace("Grade: ____", f"Grade: {both}").replace("Notes: ____", "Notes: ok", 1)


def test_a_filled_sheet_parses_with_both_slots_for_an_identical_pair():
    grades, blanks, bad = bs.parse_sheet(fill(sheet()))
    assert blanks == [] and bad == []
    assert grades["cv2-02"]["A"] == grades["cv2-02"]["B"] == "acceptable_abstain"
    assert grades["cv2-02"]["identical"] is True and grades["cv2-02"]["notes"] == "ok"
    assert grades["cv2-01"]["A"] == "correct" and grades["cv2-01"]["B"] == "partial"
    assert grades["cv2-01"]["notes"] == ""


def test_blanks_are_listed_and_bad_words_are_rejected():
    grades, blanks, bad = bs.parse_sheet(sheet())
    assert blanks == ["cv2-02 A", "cv2-02 B", "cv2-01 A", "cv2-01 B"] and bad == []
    _, _, bad = bs.parse_sheet(fill(sheet(), a="Correct!", b="partial"))
    assert bad == ["cv2-01 A: 'Correct!'"]


def test_the_commands_write_the_files_and_refuse_to_overwrite_or_to_save_bad_grades(
    tmp_path, capsys
):
    (tmp_path / "blind.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    (tmp_path / "q.jsonl").write_text("".join(json.dumps(q) + "\n" for q in QUESTIONS.values()))
    md = tmp_path / "sheet.md"
    assert (
        bs.main(["x", "make", str(tmp_path / "blind.jsonl"), str(tmp_path / "q.jsonl"), str(md)])
        == 0
    )
    assert (
        bs.main(["x", "make", str(tmp_path / "blind.jsonl"), str(tmp_path / "q.jsonl"), str(md)])
        == 2
    )
    out = tmp_path / "grades.json"
    md.write_text(fill(sheet(), a="great"))
    assert bs.main(["x", "parse", str(md), str(out)]) == 1 and not out.exists()
    assert "not allowed" in capsys.readouterr().out
    md.write_text(fill(sheet()))
    assert bs.main(["x", "parse", str(md), str(out)]) == 0
    saved = json.loads(out.read_text())
    assert saved["graded_blind"] is True and set(saved["grades"]) == {"cv2-01", "cv2-02"}
    assert bs.main(["x", "parse", str(md), str(out)]) == 2


@pytest.mark.parametrize(
    "a,b,expected", [("x  y", " x y ", True), ("x", "y", False), (None, "", True)]
)
def test_same_ignores_whitespace(a, b, expected):
    assert bs.same(a, b) is expected
