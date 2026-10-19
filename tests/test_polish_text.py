"""UI polish, answer-text items 3a, 3b, 3c (docs/decisions.md, "UI polish round ... keep rule").
No model call. The "before" texts were saved before the change in tests/fixtures/."""

import json
import re
from datetime import date

import pytest

from cta.answer import Answer
from cta.graph import advice, render, terms
from cta.graph import chain as ch
from cta.graph import chain_render as cr
from cta.graph.build import load_events
from cta.index.search import Search
from cta.settings import ROOT

RECORDS = ch.load_records()
BEFORE = json.loads((ROOT / "tests/fixtures/chain_render_before_polish.json").read_text())
CLOSING = "No catalog record in the four departments for: "
NAMED = re.compile(r"^\*\*(?:Courses named|Must not have taken[^*]*):\*\* (.*)$", re.M)


def marked_in(text: str) -> set[str]:
    """Codes a rendered text already marks "(no catalog record)" in a named line."""
    return {
        m
        for line in NAMED.findall(text)
        for m in re.findall(r"([A-Z]+ \w+) \(no catalog record\)", line)
    }


def apply_the_three_rewrites(old: str) -> str:
    """What the new render must equal: 3b by replacement, 3a by removing the closing line only when
    every code in it is marked above it. Nothing else."""
    text = re.sub(
        r"^\*\*Courses named:\*\* none$", "**Courses named:** none listed", old, flags=re.M
    )
    for line in text.split("\n"):
        if line.startswith(CLOSING):
            codes = line.removeprefix(CLOSING).removesuffix(".").split(", ")
            if all(c in marked_in(text) for c in codes):
                text = (
                    text.removesuffix("\n\n" + line)
                    if text.endswith("\n\n" + line)
                    else text.replace(line + "\n", "", 1)
                )
    return text


def with_outside_marking(text: str) -> str:
    """Tester round 1b (1a) came after this polish round: it also rewrites the marking of a named
    course whose prefix is in no record (docs/decisions.md)."""
    from tests.helpers import outside_rewrite

    return outside_rewrite(text)


def new_render(code_or_codes) -> str:
    if isinstance(code_or_codes, list):
        return cr.render(ch.combined_chain(code_or_codes), RECORDS)
    return cr.render(ch.prerequisite_chain.invoke({"course_code": code_or_codes}), RECORDS)


def test_the_fixture_is_the_197_single_chains_and_42_multi_renders():
    assert len(BEFORE["single"]) == 197 and len(BEFORE["multi"]) == 42
    assert {"q42", "q93", "q94"} <= set(BEFORE["multi"])


@pytest.mark.parametrize("code", sorted(BEFORE["single"]))
@pytest.mark.needs_data
def test_single_chain_differs_from_before_only_by_the_three_rewrites(code):
    old = BEFORE["single"][code]
    assert new_render(code) == with_outside_marking(apply_the_three_rewrites(old))


@pytest.mark.parametrize("key", sorted(BEFORE["multi"]))
@pytest.mark.needs_data
def test_multi_course_render_differs_from_before_only_by_the_three_rewrites(key):
    item = BEFORE["multi"][key]
    assert new_render(item["codes"]) == with_outside_marking(apply_the_three_rewrites(item["text"]))


@pytest.mark.needs_data
def test_every_verbatim_text_every_date_and_every_citation_number_is_still_there():
    for code, old in BEFORE["single"].items():
        new = new_render(code)
        assert re.findall(r'\*\*Catalog says:\*\* ".*"', new) == re.findall(
            r'\*\*Catalog says:\*\* ".*"', old
        )
        assert re.findall(r"\[\d+\]", new) == re.findall(r"\[\d+\]", old)
        assert re.findall(r"\d{1,2}/\d{1,2}|\b[A-Z][a-z]+ \d{1,2}\b", new) == re.findall(
            r"\d{1,2}/\d{1,2}|\b[A-Z][a-z]+ \d{1,2}\b", old
        )


def test_3a_the_closing_line_stays_exactly_when_a_code_is_not_marked():
    changed = kept = 0
    for old in [*BEFORE["single"].values(), *(m["text"] for m in BEFORE["multi"].values())]:
        had = CLOSING in old
        if not had:
            continue
        codes = (
            [ln for ln in old.split("\n") if ln.startswith(CLOSING)][0]
            .removeprefix(CLOSING)
            .removesuffix(".")
            .split(", ")
        )
        all_marked = all(c in marked_in(old) for c in codes)
        new = apply_the_three_rewrites(old)
        assert (CLOSING in new) == (not all_marked)
        changed += all_marked
        kept += not all_marked
    print("3a: closing line dropped in", changed, "renders, kept in", kept)
    assert changed > 0


def test_3a_made_up_cases():
    result = {"no_record": ["XXX 1"], "unexpanded": [], "dropped": []}
    assert cr.closing(result, marked=set()) == CLOSING + "XXX 1."  # not marked: stays
    assert cr.closing(result, marked={"XXX 1"}) == ""  # marked above: said once
    two = {"no_record": ["XXX 1", "YYY 2"], "unexpanded": [], "dropped": []}
    assert cr.closing(two, marked={"XXX 1"}) == CLOSING + "XXX 1, YYY 2."  # one unmarked: both kept
    cut = {"no_record": ["XXX 1"], "unexpanded": [{"code": "A 1", "names": ["B 2"]}], "dropped": []}
    assert "The list stops at A 1" in cr.closing(cut, marked={"XXX 1"})  # other sentences unchanged
    assert CLOSING not in cr.closing(cut, marked={"XXX 1"})


def test_3a_a_block_with_unreadable_text_or_no_text_marks_nothing():
    titles = {}
    blocks = [
        {"text": "", "unparsed": False, "codes": ["XXX 1"], "exclusions": []},
        {"text": "x", "unparsed": True, "codes": ["YYY 2"], "exclusions": []},
        {"text": "x", "unparsed": False, "codes": ["ZZZ 3"], "exclusions": ["WWW 4"]},
    ]
    assert cr.marked_codes(blocks, titles) == {"ZZZ 3", "WWW 4"}
    assert cr.marked_codes(blocks, {"ZZZ 3": "Has a title"}) == {"WWW 4"}


@pytest.mark.needs_data
def test_3b_none_listed_replaces_none_everywhere_and_nowhere_else():
    news = [new_render(c) for c in BEFORE["single"]]
    assert all(not re.search(r"^\*\*Courses named:\*\* none$", t, re.M) for t in news)
    olds = sum(
        len(re.findall(r"^\*\*Courses named:\*\* none$", t, re.M))
        for t in BEFORE["single"].values()
    )
    assert olds > 0 and sum(t.count("**Courses named:** none listed") for t in news) == olds


# ---- 3c: advice answers ----


def policy():
    sources = [
        {"id": "pdf/drop#1", "kind": "section", "source": "x", "text": "Drop by September 3."}
    ]
    return Answer("Rules [1].", False, None, sources, [1], [], Search([], False, 0, 0, 0.0))


@pytest.fixture(scope="module")
def rows():
    events = load_events()
    return advice.calendar_rows(terms.term_pool(events, "Fall 2026"), [advice.ACTIONS[1]])


def test_3c_the_assumed_term_is_at_the_end_of_the_provenance_line_once(rows):
    rendered = render.render_rows(rows, "r@x.edu")
    ans = advice.compose(policy(), rendered, "Fall 2026")
    last = ans.text.split("\n\n")[-1]
    assert last.startswith("From the Fall 2026 calendar (fall_2026.pdf")
    assert last.endswith("The calendar can change. Assuming the current term, Fall 2026.")
    assert ans.text.count("Assuming the current term") == 1
    assert not any(p.startswith("Assuming") for p in ans.text.split("\n\n"))


def test_3c_when_the_term_was_named_nothing_is_added(rows):
    ans = advice.compose(policy(), render.render_rows(rows, "r@x.edu"), None)
    assert "Assuming" not in ans.text and ans.text.endswith("The calendar can change.")


def test_3c_only_that_sentence_moved_numbers_sources_and_rows_are_identical(rows):
    old = advice.compose(policy(), render.render_rows(rows, "r@x.edu", "Fall 2026"))
    new = advice.compose(policy(), render.render_rows(rows, "r@x.edu"), "Fall 2026")
    expected = (
        old.text.replace("Assuming the current term, Fall 2026.\n\n", "")
        + " Assuming the current term, Fall 2026."
    )
    assert new.text == expected
    assert (new.citations, new.sources, new.row_ids) == (old.citations, old.sources, old.row_ids)


def test_3c_the_calendar_route_keeps_its_line_at_the_top(rows):
    text = render.render_rows(rows, "r@x.edu", "Fall 2026").text
    assert text.startswith("Assuming the current term, Fall 2026.\n\n")


def test_3c_the_graph_passes_the_assumed_term_to_the_end(monkeypatch):
    from tests.helpers import CLARIFY_CFG as CFG
    from tests.helpers import TODAY, Script, make_router

    router, _ = make_router(Script("other"), monkeypatch, load_events(), CFG)
    ans = router.answer("Should I withdraw from my biology class?", TODAY, log=False)
    assert ans.text.split("\n\n")[-1].endswith(
        "The calendar can change. Assuming the current term, Fall 2026."
    )
    assert ans.text.count("Assuming") == 1 and date  # a term-less question assumes the current term
