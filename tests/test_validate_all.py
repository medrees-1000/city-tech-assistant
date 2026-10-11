from cta.validate.__main__ import Area, details, table
from cta.validate.findings import Finding


def test_area_result_is_fail_only_for_unaccepted_failures():
    ok = Area("a", "3 things", [Finding("w", "warning", "careful")])
    assert (ok.result, len(ok.warnings), len(ok.failed)) == ("PASS", 1, 0)
    accepted = Finding("x", "fail", "known", accepted="owner knows")
    assert Area("b", "1", [accepted]).result == "PASS"
    assert Area("b", "1", [accepted]).accepted == [accepted]
    assert Area("c", "1", [Finding("x", "fail", "bad")]).result == "FAIL"


def test_a_skipped_area_is_never_a_pass():
    area = Area("pdfs", skipped="PDFs missing")
    assert area.result == "SKIPPED"
    assert "skipped: PDFs missing" in table([area]) and "SKIPPED" in table([area])


def test_table_has_one_row_per_area_with_counts():
    areas = [
        Area("courses", "197 courses", [Finding("w", "warning", "m")]),
        Area("pages", "63 pages", [Finding("f", "fail", "m")]),
    ]
    lines = table(areas).split("\n")
    assert lines[2] == "| courses | 197 courses | 0 | 0 | 1 | PASS |"
    assert lines[3] == "| pages | 63 pages | 1 | 0 | 0 | FAIL |"


def test_details_lists_every_finding_with_its_area_and_accepted_reason():
    areas = [Area("pages", "1", [Finding("k", "fail", "404", "u", accepted="known")])]
    assert details(areas) == ["[ACCEPTED] pages: k u: 404 (known)"]
