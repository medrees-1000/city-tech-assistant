import json
from pathlib import Path

import pytest

from cta.parse.html import clean_heading, to_sections
from cta.validate.pages import check_heading_markup, run_heading_checks

LINKED = "[Computer Information Systems/AAS](https://citytech.catalog.cuny.edu/programs/CIS-AAS)"


def test_clean_heading_keeps_the_text_and_the_first_url():
    assert clean_heading(LINKED) == (
        "Computer Information Systems/AAS", "https://citytech.catalog.cuny.edu/programs/CIS-AAS",
    )  # fmt: skip
    assert clean_heading("Plain heading") == ("Plain heading", None)
    assert clean_heading(None) == (None, None)
    assert clean_heading("See [A](http://a) and [B](http://b)") == ("See A and B", "http://a")
    assert clean_heading("Fees [not a link] (really)") == ("Fees [not a link] (really)", None)


def test_to_sections_cleans_headings_parents_and_keeps_the_url_without_changing_order():
    blocks = [
        ("h", 1, "Degrees"),
        ("p", 0, "intro"),
        ("h", 2, LINKED),
        ("p", 0, "about it"),
        ("h", 3, "[Sub](https://x/y)"),
        ("p", 0, "deeper"),
        ("h", 2, "Plain"),
        ("p", 0, "text"),
    ]
    sections = to_sections(blocks)
    assert [s["heading"] for s in sections] == [
        "Degrees",
        "Computer Information Systems/AAS",
        "Sub",
        "Plain",
    ]
    assert [s["heading_url"] for s in sections] == [
        None, "https://citytech.catalog.cuny.edu/programs/CIS-AAS", "https://x/y", None,
    ]  # fmt: skip
    assert [p["heading"] for p in sections[2]["parents"]] == [
        "Degrees",
        "Computer Information Systems/AAS",
    ]
    assert all("](" not in s["heading"] for s in sections)



def record(*headings, parents=()):
    sections = [
        {"heading": h, "level": 2, "markdown": "t", "heading_url": None,
         "parents": [{"level": 1, "heading": p} for p in parents]}
        for h in headings
    ]  # fmt: skip
    return {"source_url": "https://x/p", "sections": sections}


def test_the_check_fails_for_link_markup_in_a_heading_or_a_parent():
    assert check_heading_markup(record("Plain", "Also plain")) == []
    found = check_heading_markup(record("[A](https://x)"))
    assert [f.check for f in found] == ["heading_markup"] and "section 1" in found[0].message
    found = check_heading_markup(record("Child", parents=("[Parent](https://x)",)))
    assert [f.check for f in found] == ["heading_markup"]
    assert len(run_heading_checks([record("[A](u)"), record("ok"), record("[B](u)")])) == 2


ROOT = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.mark.skipif(not (ROOT / "pages").exists(), reason="no processed data")
def test_no_real_record_has_link_markup_and_linked_headings_keep_their_url():
    records = [
        json.loads(p.read_text("utf-8"))
        for g in ("pages/*/*.json", "pdfs/*.json", "departments/*/*.json")
        for p in sorted(ROOT.glob(g))
    ]
    assert run_heading_checks(records) == []
    linked = [s for r in records for s in r["sections"] if s["heading_url"]]
    assert len(linked) == 11 and all(s["heading_url"].startswith("https://") for s in linked)
    assert all("heading_url" in s for r in records for s in r["sections"])
