import shutil

from cta.parse.pages import record_for
from cta.parse.terms import (
    covered_terms,
    resolve_refund_seasons,
    seasons_without_year,
    section_terms,
    set_terms,
    tag_terms,
    terms_in,
)
from tests.helpers import PAGES, entry


def sec(heading, markdown="body", parents=()):
    return {
        "heading": heading,
        "level": len(parents) + 1,
        "parents": [{"level": i + 1, "heading": p} for i, p in enumerate(parents)],
        "markdown": markdown,
    }


def test_terms_are_season_names_with_a_year_in_the_stored_form():
    assert terms_in("Fall 2026 Refund Policy") == ["Fall 2026"]
    assert terms_in("Summer Session I 2026 Payment Due Dates") == ["Summer I 2026"]
    assert terms_in("Summer Session II 2026") == ["Summer II 2026"]
    assert terms_in("Summer I 2026") == ["Summer I 2026"]
    assert terms_in("Summer 2026 Payment Plan") == ["Summer 2026"]
    assert terms_in("SPRING 2027 CALENDAR") == ["Spring 2027"]
    assert terms_in("Winter 2027") == ["Winter 2027"]
    assert terms_in("Summer 2026, Fall 2026, and Spring 2027 Refund Schedule") == [
        "Summer 2026", "Fall 2026", "Spring 2027",
    ]  # fmt: skip
    assert terms_in("Fall 2026 and again Fall 2026") == ["Fall 2026"]


def test_names_without_a_year_and_dates_are_not_terms():
    texts = [
        "Year 1 Fall (11 credits)", "Fall and Spring, 100%", "Fall Refund Date: 10/05/2026",
        "Dropping a Class On or Before September 3, 2026", "2026 Fall Term",
        "Summer semester", "Fall 15 - 18 credits", "Fallacy 2026",
    ]  # fmt: skip
    for text in texts:
        assert terms_in(text) == [], text


def test_seasons_without_a_year_are_reported_separately():
    assert seasons_without_year("Fall and Spring, 100% Summer Session, 100%") == [
        "Fall", "Spring", "Summer Session",
    ]  # fmt: skip
    assert seasons_without_year("Fall 2026 Refund Policy, Summer Session I 2026") == []


def test_terms_come_from_the_heading_path_and_the_table_header_not_the_body():
    parent = sec("Bill Payment Deadlines")
    assert section_terms(
        sec("Fall 2026 Payment Due Dates", parents=("Bill Payment Deadlines",))
    ) == ["Fall 2026"]
    under = sec("Dropping Classes", parents=("Fall 2026 Important Information",))
    assert section_terms(under) == ["Fall 2026"]  # the heading path includes the parents
    body_only = sec("Refunds", "Summer 2026 refunds begin July 17, 2026. Fall 2027 too.")
    assert section_terms(body_only) == []
    table = "| Summer 2026 Advisement Schedule<br>Please email | Email |\n| --- | --- |\n| A | b |"
    assert section_terms(sec("Advisement", table)) == ["Summer 2026"]
    data_row = "|  |  |\n| --- | --- |\n| Fall 2027 | x |"
    assert section_terms(sec("Advisement", data_row)) == []  # only the header row is a title
    assert parent["heading"] == "Bill Payment Deadlines"


def test_term_is_the_single_entry_else_null():
    s = sec("x")
    set_terms(s, ["Fall 2026"])
    assert (s["terms"], s["term"]) == (["Fall 2026"], "Fall 2026")
    set_terms(s, ["Fall 2026", "Spring 2027"])
    assert s["term"] is None
    set_terms(s, [])
    assert (s["terms"], s["term"]) == ([], None)


def test_tag_terms_sets_every_section():
    record = {"sections": [sec("Fall 2026 Plan"), sec("About")]}
    tag_terms(record)
    assert [s["terms"] for s in record["sections"]] == [["Fall 2026"], []]


def refund_record():
    return {
        "sections": [
            sec("Attendance", parents=("AWARD YEAR",)),
            sec(
                "Summer 2026, Fall 2026, and Spring 2027 Refund Schedule",
                "|  |\n| --- |\n| 7/24/2026 |",
            ),
            sec("Fall Book Advance Refund Dates (25%):"),
            sec("Fall Refund Date: 10/05/2026"),
            sec("Spring Book Advance Refund Dates (25%):"),
            sec("Spring Refund Date: 3/05/2027"),
            sec("Summer Refund Date: July"),
            sec("Winter Break Notes"),
        ]
    }


def test_refund_rule_resolves_unyeared_seasons_from_the_schedule_heading():
    record = resolve_refund_seasons(tag_terms(refund_record()))
    got = [(s["heading"][:12], s["terms"], s["term"]) for s in record["sections"]]
    assert got == [
        ("Attendance", [], None),
        ("Summer 2026,", ["Summer 2026", "Fall 2026", "Spring 2027"], None),
        ("Fall Book Ad", ["Fall 2026"], "Fall 2026"),
        ("Fall Refund ", ["Fall 2026"], "Fall 2026"),
        ("Spring Book ", ["Spring 2027"], "Spring 2027"),
        ("Spring Refun", ["Spring 2027"], "Spring 2027"),
        ("Summer Refun", ["Summer 2026"], "Summer 2026"),
        ("Winter Break", [], None),  # the schedule names no Winter term: nothing is guessed
    ]
    assert record["sections"][2]["terms_source"].startswith("season in the heading")
    assert "terms_source" not in record["sections"][1]


def test_refund_rule_leaves_other_documents_alone():
    record = tag_terms({"sections": [sec("Fall Notes"), sec("Spring Notes")]})
    assert resolve_refund_seasons(record)["sections"][0]["terms"] == []


def test_covered_terms_lists_terms_named_in_headings_and_tables_and_the_bare_seasons():
    record = {
        "sections": [
            sec("Fall 2026 Refund", "text"),
            sec("Table", "|  |  |\n| --- | --- |\n| Fall and Spring | 100% |"),
        ]
    }
    assert covered_terms(record) == {
        "covered_terms": ["Fall 2026"], "seasons_without_year": ["Fall", "Spring"],
    }  # fmt: skip


def test_the_real_refund_pages_report_what_they_name(tmp_path):
    raw = tmp_path / "raw_root" / "raw"
    raw.mkdir(parents=True)
    for name, fixture in (
        ("a", "bursar_refund_policy.html"),
        ("b", "admissions_tuition_refund.html"),
    ):
        shutil.copy(PAGES / fixture, raw / f"{name}.html")
    bursar = entry("/bursar/refund-policy.aspx", "a")
    admissions = entry("/admissions/tuition-refund.aspx", "b")
    bursar["saved_as"], admissions["saved_as"] = "raw/a.html", "raw/b.html"
    urls = [bursar["url"], admissions["url"]]
    b = record_for(bursar, tmp_path / "raw_root", None, None, None, urls)
    a = record_for(admissions, tmp_path / "raw_root", None, None, None, urls)
    assert b["covered_terms"] == ["Summer I 2026", "Summer II 2026", "Fall 2026"]
    assert [s["term"] for s in b["sections"]] == [
        None,
        "Summer I 2026",
        "Summer II 2026",
        "Fall 2026",
    ]
    assert a["covered_terms"] == [] and a["seasons_without_year"] == [
        "Fall",
        "Spring",
        "Summer Session",
    ]
    assert all(s["terms"] == [] and s["term"] is None for s in a["sections"])
    other = record_for(bursar, tmp_path / "raw_root")
    assert "covered_terms" not in other


# ---- the checks ---------------------------------------------------------------------------------


def tagged(*sections, **extra):
    record = {"source_url": "https://x/r.aspx", "sections": list(sections), **extra}
    return tag_terms(record)


def checks(record, refund_pages=()):
    from cta.validate.terms import run_term_checks

    return sorted({f.check for f in run_term_checks([record], list(refund_pages))})


def test_a_correctly_tagged_record_passes():
    record = tagged(sec("Fall 2026 Refund Policy"), sec("About"), sec("Summer Session I 2026 Dues"))
    assert checks(record) == []
    assert checks(resolve_refund_seasons(tagged(*refund_record()["sections"]))) == []


def test_a_deliberately_broken_record_is_caught_by_each_check():
    def broken(mutate):
        record = tagged(sec("Fall 2026 Refund Policy"))
        mutate(record["sections"][0])
        return record

    assert checks(broken(lambda s: s.pop("terms"))) == ["terms_not_list"]
    assert checks(broken(lambda s: s.update(terms="Fall 2026"))) == ["terms_not_list"]
    assert checks(broken(lambda s: s.update(terms=["Fall"]))) == ["term_form"]
    assert checks(broken(lambda s: s.update(terms=["Autumn 2026"]))) == ["term_form"]
    assert checks(broken(lambda s: s.update(terms=[]))) == ["term_missing", "term_value"]
    assert checks(broken(lambda s: s.update(term=None))) == ["term_value"]
    assert checks(broken(lambda s: s.update(terms=["Fall 2026", "Spring 2027"], term=None))) == [
        "term_invented"
    ]
    assert checks(broken(lambda s: s.update(terms=["Spring 2027"], term="Spring 2027"))) == [
        "term_invented", "term_missing",
    ]  # fmt: skip


def test_a_term_in_no_heading_is_allowed_only_with_a_stated_source():
    record = tagged(sec("Fall Refund Date: 10/05/2026"))
    set_terms(record["sections"][0], ["Fall 2026"])
    assert checks(record) == ["term_invented"]
    record["sections"][0]["terms_source"] = "season in the heading, year from the refund schedule"
    assert checks(record) == []


def test_covered_terms_must_exist_on_a_refund_page_and_cover_the_section_terms():
    url = "https://x/r.aspx"
    record = tagged(sec("Fall 2026 Refund Policy"))
    assert checks(record, [url]) == ["covered_terms"]
    record["covered_terms"] = ["Fall 2026"]
    assert checks(record, [url]) == []
    record["covered_terms"] = []
    assert checks(record, [url]) == ["covered_terms"]
    record["covered_terms"] = ["Fall"]
    assert checks(record, [url]) == ["covered_terms"]
    assert checks(tagged(sec("About")), [url]) == ["covered_terms"]
    assert checks(record, []) == []  # not a refund page
