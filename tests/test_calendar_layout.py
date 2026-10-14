"""Step 3a: the calendar layout (docs/decisions.md, "Step 3a ... keep rule", checks 1 to 8).
Real rows from data/calendar/calendar_events.json; no model call."""

import hashlib
import json
from pathlib import Path

import pytest

from cta.eval import run_answers as ra
from cta.eval.questions import load_questions
from cta.graph import render
from cta.settings import ROOT

EVENTS = json.loads((ROOT / "data/calendar/calendar_events.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in EVENTS}
CONTACT = "registrar@x.edu, 718-000-0000"
STORED_RUNS = ["4b-run1", "4b-run2", "4b-run3", "router-run1", "router-run2", "router-run3",
               "router2-run1", "router2-run2", "router2-run3"]  # fmt: skip
TESTDATA = ROOT / "web" / "lib" / "testdata"


def rows(*ids):
    return [BY_ID[i] for i in ids]


def bullets(text):
    return [line for line in text.splitlines() if line.startswith("- ")]


def test_1_the_date_text_is_date_in_words_and_the_rows_are_the_same_in_the_same_order():
    chosen = rows("winter-2027-023", "fall-2026-040", "winter-2027-004", "spring-2027-055")
    out = render.render_rows(chosen, CONTACT)
    # same rows, by calendar group (earliest first), by date inside a group
    assert out.row_ids == ["fall-2026-040", "winter-2027-004", "winter-2027-023", "spring-2027-055"]
    for row in chosen:
        if row["date_start"]:
            assert f"**{render.date_in_words(row)[0]}**: {row['event']}" in out.text


def test_1_every_one_of_the_136_rows_renders_its_old_date_text():
    for row in EVENTS:
        out = render.render_rows([row], CONTACT)
        if row["date_start"]:
            assert out.text.startswith(f"**{render.date_in_words(row)[0]}**: {row['event']} [1]")
        assert out.row_ids == [row["id"]]


def test_2_numbers_are_unique_and_map_to_the_row_at_that_position():
    out = render.render_rows(rows("fall-2026-040", "winter-2027-004", "winter-2027-023",
                                  "spring-2027-055"), CONTACT)  # fmt: skip
    lines = bullets(out.text)
    assert len(lines) == 4
    for position, (line, source, row_id) in enumerate(
        zip(lines, out.sources, out.row_ids, strict=True), 1
    ):
        assert f" [{position}]" in line
        assert source["id"] == row_id
        assert f"[{position}] (" in source["text"]  # the judge's source keeps the full sentence
    assert [line.count("[") for line in lines] == [1, 1, 1, 1]


def test_3_one_provenance_line_per_calendar_with_the_rows_own_fields():
    out = render.render_rows(rows("winter-2027-004", "winter-2027-023"), CONTACT)
    assert out.text.count("From the ") == 1
    row = BY_ID["winter-2027-004"]
    expected = (
        f"From the {row['term']} calendar ({Path(row['source_pdf']).name}, "
        f"last updated {row['pdf_last_updated']}). The calendar can change."
    )
    assert out.text.endswith("\n\n" + expected)
    assert "calendar, " not in out.text  # the old clause is gone from the answer


def test_4_a_tba_row_says_not_announced_yet_and_keeps_the_registrar_line():
    tba = BY_ID["spring-2027-055"]
    assert tba["date_start"] is None
    out = render.render_rows([tba], CONTACT)
    first = out.text.splitlines()[0]
    assert first == f"{tba['event']}: not announced yet [1] Contact the Registrar: {CONTACT}."
    assert "**" not in first and out.tba_rows == ["spring-2027-055"]


def test_5_one_row_keeps_its_provenance_and_two_terms_get_two_lines_after_their_rows():
    one = render.render_rows(rows("fall-2026-040"), CONTACT)
    assert one.text.count("\n\n") == 1 and not bullets(one.text)
    assert one.text.splitlines()[-1].startswith("From the Fall 2026 calendar (fall_2026.pdf")
    two = render.render_rows(rows("spring-2027-040", "fall-2026-039", "fall-2026-040"), CONTACT)
    parts = two.text.split("\n\n")
    assert [p.startswith("- ") for p in parts] == [True, False, True, False]
    assert parts[1].startswith("From the Fall 2026 calendar")
    assert parts[3].startswith("From the Spring 2027 calendar")
    assert two.row_ids == ["fall-2026-039", "fall-2026-040", "spring-2027-040"]


def test_the_assumed_term_line_is_its_own_paragraph():
    out = render.render_rows(rows("fall-2026-040"), CONTACT, "Fall 2026")
    assert out.text.split("\n\n")[0] == "Assuming the current term, Fall 2026."


def test_no_forbidden_words_in_any_row_or_group():
    for row in EVENTS:
        text = render.render_rows([row], CONTACT, "Fall 2026").text
        assert "chain" not in text.lower() and "Level" not in text


def stored_calendar_questions():
    questions = {q["id"]: q for q in load_questions()}
    for label in STORED_RUNS:
        run = json.loads((ROOT / "eval" / "results" / f"{label}.json").read_text())
        for r in run["per_question"]:
            if r["route"] == "calendar" and r.get("returned_rows"):
                yield label, r, questions[r["id"]]


def test_6_stored_dev_runs_return_the_same_row_ids_and_the_same_calendar_scoring():
    seen = 0
    for label, r, q in stored_calendar_questions():
        out = render.render_rows([BY_ID[i] for i in r["returned_rows"]], CONTACT)
        assert out.row_ids == r["returned_rows"], (label, r["id"])
        if ra.gold_kind(q) == "calendar_only":
            for version in (1, 2):
                stored = type("S", (), {"row_ids": r["returned_rows"], "route": r["route"]})()
                new = type("S", (), {"row_ids": out.row_ids, "route": "calendar"})()
                assert ra.calendar_result(q, new, version) == ra.calendar_result(q, stored, version)
        seen += 1
    assert seen >= 100


def test_7_other_answers_are_untouched_the_abstention_text_hash():
    text = render.abstain_text("I could not find that in the Fall 2026 calendar.", "r@x.edu, 718-1")
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "4171735baf30f8bb152e33de8ef0a574a1446c3f9e7383a54bf45e9f8cbd8896"
    )


@pytest.mark.parametrize(
    ("name", "ids", "assumed"),
    [
        ("calendar_winter_start_end.md", ("winter-2027-004", "winter-2027-023"), None),
        ("calendar_one_row.md", ("fall-2026-040",), "Fall 2026"),
        (
            "calendar_two_terms_tba.md",
            ("fall-2026-039", "spring-2027-040", "spring-2027-055"),
            None,
        ),
    ],
)
def test_8_the_fixtures_the_page_tests_read_are_what_the_renderer_writes(name, ids, assumed):
    text = render.render_rows(rows(*ids), CONTACT, assumed).text
    assert (TESTDATA / name).read_text(encoding="utf-8") == text + "\n"
