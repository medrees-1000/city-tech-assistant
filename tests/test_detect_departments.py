"""Department detection by alias and code (used by the contact, clarify and screen steps)."""

import pytest

from cta.index import departments as deps


def found(question: str) -> set[str]:
    return deps.detect_departments(question)


# ---- detection (no database) ----


def test_aliases_match_whole_words_and_ignore_case():
    assert found("What does the Electrical Engineering Technology department offer?") == {"EET-NYT"}
    assert found("what does the eet department offer") == {"EET-NYT"}
    assert found("Is there a Computer Systems Technology internship?") == {"CST-NYT"}
    assert found("How do I join the dental hygiene program?") == {"DENT-NYT"}
    assert found("What is my math placement?") == {"MATH-NYT"}
    assert found("Electrical & Telecommunications Engineering Technology degrees") == {"EET-NYT"}
    assert found("Electrical and Telecommunications Engineering Technology degrees") == {"EET-NYT"}


def test_aliases_do_not_match_inside_other_words():
    assert found("Meet the chair of the college") == set()  # "meet" is not "EET"
    assert found("How many feet is it?") == set()
    assert found("Is mathematical logic offered?") == set()  # "Math" is not "mathematical"
    assert found("What is the CSTA award?") == set()


def test_etet_and_eet_both_mean_the_electrical_department():
    assert found("ETET office hours") == {"EET-NYT"} == found("EET office hours")
    assert found("etet student hours") == {"EET-NYT"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are the prerequisites for EET 3672?", {"EET-NYT"}),
        ("What are the prerequisites for EET3672?", {"EET-NYT"}),
        ("prerequisites for eet 3672", {"EET-NYT"}),
        ("What do I need before MAT 1275CO?", {"MATH-NYT"}),
        ("Can I take TCET 4102?", {"EET-NYT"}),  # a second EET-department prefix
        ("Is MEDU 4000 offered?", {"MATH-NYT"}),
        ("What is DEN 2400?", {"DENT-NYT"}),
        ("What is MST 1101?", {"CST-NYT"}),  # legacy prefix the catalog lists under CST
        ("What is CET 3672?", set()),  # a cross-listed prefix of another department: not mapped
        ("What is MECH 3672?", set()),
        ("What is the deadline for Fall 2026?", set()),  # "Fall 2026" looks like a code and is not
    ],
)
def test_course_codes_map_through_their_prefix(question, expected):
    assert found(question) == expected


def test_two_departments_in_one_question():
    assert found("Compare MAT 2675 with CST 1101") == {"MATH-NYT", "CST-NYT"}
    assert found("Do Dental Hygiene students take math?") == {"DENT-NYT", "MATH-NYT"}


def test_no_department_detected():
    assert found("How do I apply for graduation at City Tech?") == set()
    assert found("") == set()


def test_every_prefix_belongs_to_one_department_in_the_config():
    seen: dict[str, str] = {}
    for dept_id, info in deps.load_departments().items():
        for prefix in info["prefixes"]:
            assert seen.setdefault(prefix, dept_id) == dept_id
    assert set(deps.load_departments()) == {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"}
