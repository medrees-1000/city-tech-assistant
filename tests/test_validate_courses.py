from cta.validate.courses import (
    check_counts,
    check_no_duplicates,
    check_prereq_codes_exist,
    check_required_fields,
    check_rules_resolved,
    check_totals,
    run_course_checks,
)


def rec(**over) -> dict:
    base = {
        "code": "CST 1101", "title": "T", "description": "D", "credits": 3,
        "department": "CST-NYT", "status": "Active", "rule_id": "100001",
        "prerequisite_text": "Prerequisite: CST 1101.",
    }  # fmt: skip
    return {**base, **over}


def test_totals_pass_when_equal():
    s = {"downloaded": 1445, "total_before": 1445, "total_after": 1445}
    assert check_totals(s, 1445) == []


def test_totals_fail_when_download_short():
    s = {"downloaded": 1440, "total_before": 1445, "total_after": 1445}
    assert [f.severity for f in check_totals(s, 1445)] == ["fail"]


def test_total_differs_from_expected_is_review_not_fail():
    s = {"downloaded": 1450, "total_before": 1450, "total_after": 1450}
    assert [f.severity for f in check_totals(s, 1445)] == ["warning"]


def test_required_fields_flags_missing_and_inactive():
    found = check_required_fields([rec(description=""), rec(code="X 1", status="Inactive")])
    assert [f.severity for f in found] == ["fail", "fail"]
    assert check_required_fields([rec()]) == []


def test_zero_credits_is_not_missing():
    assert check_required_fields([rec(credits=0)]) == []


def test_rule_id_kept_as_text_fails():
    assert len(check_rules_resolved([rec(prerequisite_text="017007")])) == 1


def test_unresolved_rule_fails():
    assert len(check_rules_resolved([rec(prerequisite_text=None)])) == 1


def test_no_rule_and_no_text_is_fine():
    assert check_rules_resolved([rec(rule_id=None, prerequisite_text=None)]) == []


CATALOG = {"CST 1101", "CST 1201", "MAT 1475", "ENG 1101CO", "CET 3510L"}


def codes_flagged(text: str) -> list[str]:
    found = check_prereq_codes_exist([rec(prerequisite_text=text)], CATALOG)
    return [" ".join(f.message.split()[2:4]).rstrip(",") for f in found]


def test_prereq_code_missing_from_catalog_is_a_warning():
    found = check_prereq_codes_exist([rec(prerequisite_text="CST 1101 and CST 9999")], CATALOG)
    assert [(f.severity, f.course) for f in found] == [("warning", "CST 1101")]
    assert "CST 9999" in found[0].message


def test_prereq_code_without_space_is_normalized():
    assert codes_flagged("CST1201") == []
    assert codes_flagged("CST1999") == ["CST 1999"]


def test_suffix_letters_match_with_or_without_suffix():
    assert codes_flagged("MAT 1475H") == []  # base MAT 1475 exists
    assert codes_flagged("ENG 1101CO") == []  # exact code exists
    assert codes_flagged("CET 3510L") == []


def test_words_that_are_not_subjects_are_ignored():
    assert codes_flagged("OR 3513 or TWO 2000") == []


def test_codes_inside_shorthand_are_checked():
    assert codes_flagged("PRE_CST1101_CST9999") == ["CST 9999"]


def test_duplicate_code_in_department_fails_but_cross_listing_does_not():
    dup = [rec(), rec()]
    cross = [rec(code="EET 3672", department="EET-NYT"), rec(code="CET 3672", department="CET-NYT")]
    assert len(check_no_duplicates(dup)) == 1
    assert check_no_duplicates(cross) == []


def test_count_change_beyond_a_few_is_flagged():
    assert check_counts({"CST-NYT": 60}, {"CST-NYT": 50})[0].check == "counts"
    assert check_counts({"CST-NYT": 52}, {"CST-NYT": 50}) == []
    assert check_counts({"CST-NYT": 52}, {}) == []  # first run: nothing to compare


def test_run_course_checks_clean_data_has_no_findings():
    s = {"downloaded": 1, "total_before": 1, "total_after": 1}
    assert run_course_checks([rec()], s, {"CST 1101"}, expected_total=1) == []
