"""The calendar answer: a term with no calendar says so (tester round 1, item C) and the calendar
layout (step 3a, checks 1 to 8; real rows from data/calendar/calendar_events.json). No network,
no database, no model call.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from cta.eval import run_answers as ra
from cta.eval.questions import load_questions
from cta.graph import build, render, terms
from cta.settings import ROOT, load_models
from tests.helpers import TODAY, Client, Script, ask, make_client_app, make_router

# ---- from test_calendar_no_term.py ----
#
# Tester round 1, item C: a term with no calendar says so. No network, no database, no model.

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_CHAIN": "off", "CTA_ROUTER_CONTACTS": "off"}
)
EVENTS = build.load_events()
LISTED = "Fall 2026, Winter 2027 and Spring 2027"
# the stored tester questions (5aa6e0dd, 4a7e826e) and the term the classifier gave
TESTER = [
    ("when does summer 2027 semester start", "summer 2027", "Summer 2027"),
    ("fall 2027 add/drop deadline?", "fall 2027", "Fall 2027"),
]


def wording(label: str) -> str:
    return f"No calendar has been published for {label} yet. The calendars I have cover {LISTED}."


@pytest.mark.parametrize(("question", "mention", "label"), TESTER)
def test_the_tester_questions_get_the_new_wording_and_keep_the_registrar_contact(
    monkeypatch, question, mention, label
):
    router, seen = make_router(Script("calendar", mention, []), monkeypatch, EVENTS, CFG)
    ans = router.answer(question, TODAY, log=False)
    assert ans.abstained and ans.route == "abstain" and seen == []
    assert ans.text.startswith("ABSTAIN: " + wording(label) + " Contact the Registrar: ")
    assert ans.abstain_reason == "calendar_unsupported_term"  # not calendar_no_row
    assert "I could not find that in the" not in ans.text


def test_the_listed_terms_are_read_from_the_calendar_data():
    assert terms.supported_terms(EVENTS) == ["Fall 2026", "Winter 2027", "Spring 2027"]
    assert build.no_term_text("Summer 2027", EVENTS) == wording("Summer 2027")
    assert build.no_term_text("Spring 2029", EVENTS) == wording("Spring 2029")  # any term outside


@pytest.mark.needs_data
def test_the_contact_is_the_existing_registrar_one_not_a_new_one(monkeypatch):
    script = Script("calendar", "Summer 2027", [])
    router = build.Router(None, CFG, lambda: script, events=EVENTS)  # the real registrar contact
    text = router.answer("when does summer 2027 start", TODAY, log=False).text
    registrar = build.render.registrar_contact()
    assert text.endswith(f"Contact the Registrar: {registrar}.")
    record = json.loads((ROOT / "data/processed/contacts/registrar.json").read_text())
    assert all(item in text for item in [*record["emails"], *record["phones"]])


def test_an_unsupported_term_with_a_failed_selector_keeps_the_failure_code_but_the_true_wording(
    monkeypatch,
):
    script = Script("calendar", "Fall 2027", selector_text="not json")
    router, _ = make_router(script, monkeypatch, EVENTS, CFG)
    ans = router.answer("fall 2027 add/drop deadline?", TODAY, log=False)
    assert ans.abstain_reason == "calendar_selector_failed" and wording("Fall 2027") in ans.text


def test_a_published_term_with_no_matching_row_still_falls_through_to_retrieval(monkeypatch):
    router, seen = make_router(Script("calendar", "Fall 2026", []), monkeypatch, EVENTS, CFG)
    ans = router.answer("when is the faculty picnic in Fall 2026?", TODAY, log=False)
    assert len(seen) == 1 and ans.route == "calendar_fallthrough"  # unchanged: retrieval answers


def test_a_row_of_another_calendar_that_answers_is_still_used(monkeypatch):
    script = Script("calendar", "Fall 2027", ["spring-2027-040"])
    router, _ = make_router(script, monkeypatch, EVENTS, CFG)
    ans = router.answer("When does registration for Fall 2027 begin?", TODAY, log=False)
    assert ans.route == "calendar" and "No calendar has been published" not in ans.text


@pytest.mark.needs_data
def test_through_the_api_it_is_a_calendar_abstention_with_the_registrar_card(monkeypatch):
    c = make_client_app(Client("calendar", "summer 2027", []), monkeypatch)
    body = ask(c, "when does summer 2027 semester start").json()
    assert body["abstained"] and body["route"] == "calendar"
    assert body["abstain_reason"] == "calendar_unsupported_term"
    assert body["contact"] and body["contact"]["office"] == "registrar"
    assert body["answer"] == wording("Summer 2027")  # the contact sentence moves to the card


def dev_term_changes() -> list[tuple[str, str, str]]:
    """Stored dev records whose classifier term resolves to an unpublished term (dev runs only)."""
    text = {q["id"]: q["question"] for q in load_questions() if q["split"] == "dev"}
    found = {}
    for path in sorted((ROOT / "eval" / "results").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(run, dict) or run.get("split") != "dev":
            continue
        for r in run.get("per_question", []):
            mention = (r.get("router") or {}).get("term_mention")
            if r["id"] in text and mention:
                got = terms.resolve_term(mention, TODAY, EVENTS)
                if got.status == "unsupported":
                    found[r["id"]] = (text[r["id"]], mention, r.get("abstain_reason"))
    return [(k, *v[:2]) for k, v in sorted(found.items())]


def test_the_dev_questions_whose_answer_text_can_change_are_those_about_unpublished_terms():
    changed = dev_term_changes()
    print("dev questions with an unpublished term:", changed)
    # q34 ("... Summer 2027", gold ABSTAIN) and, since the tester round, q100 and q101 (Summer and
    # Fall 2027), which are about unpublished terms by design
    assert [c[0] for c in changed] == ["q100", "q101", "q34"]
    assert re.search(r"Summer 2027", {c[0]: c[1] for c in changed}["q34"])


# ---- from test_calendar_layout.py ----
#
# Step 3a: the calendar layout (docs/decisions.md, "Step 3a ... keep rule", checks 1 to 8).
# Real rows from data/calendar/calendar_events.json; no model call.

LAYOUT_EVENTS = json.loads(
    (ROOT / "data/calendar/calendar_events.json").read_text(encoding="utf-8")
)
BY_ID = {e["id"]: e for e in LAYOUT_EVENTS}
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
    for row in LAYOUT_EVENTS:
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
    for row in LAYOUT_EVENTS:
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
