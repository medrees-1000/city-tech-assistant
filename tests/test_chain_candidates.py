# ruff: noqa: E501
"""scripts/make_chain_candidates.py: expansion rules, gold text, determinism (no network)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "make_chain_candidates", ROOT / "scripts" / "make_chain_candidates.py"
)
mcc = importlib.util.module_from_spec(spec)
sys.modules["make_chain_candidates"] = mcc
spec.loader.exec_module(mcc)


def rec(code, text="", style="text", title=None, dept="CST-NYT", **kw):
    return {"code": code, "title": title or f"Title of {code}", "credits": 3, "description": f"About {code}.",
            "prerequisite_text": text, "prereq_style": style, "rule_id": "000001" if text else None,
            "course_group_id": "0000001", "department": dept} | kw  # fmt: skip


def recs(*records):
    return {r["code"]: r for r in records}


# ---- parsing ----


def test_explicit_codes_and_bare_numbers_inherit_the_prefix_and_are_marked():
    p = mcc.parse_text("PRE: CST 1100 & 1101, C GRADE")
    assert p.codes == ["CST 1100", "CST 1101"] and p.inferred == ["CST 1101"]
    p = mcc.parse_text("PRE: CST1201 & (2405 or 2415)")
    assert p.codes == ["CST 1201", "CST 2405", "CST 2415"] and p.inferred == [
        "CST 2405",
        "CST 2415",
    ]
    assert mcc.parse_text("Prerequisite: MAT1275CO or MAT 1275").codes == ["MAT 1275CO", "MAT 1275"]


def test_level_wording_is_not_a_code():
    p = mcc.parse_text("PRE: TWO 2000-LEVEL COURSES")
    assert p.codes == []
    assert mcc.parse_text("PRE: THREE CST 35XX LEVEL COURSES OR HIGHER").codes == []


def test_codes_after_must_not_or_not_have_are_exclusions_not_prerequisites():
    p = mcc.parse_text("PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675")
    assert (p.codes, p.exclusions) == (["MAT 1475"], ["MAT 2675"])
    p = mcc.parse_text(
        "Prerequisite of MAT 1275CO OR MAT 1275 OR higher. Must not have taken MAT 2572."
    )
    assert p.codes == ["MAT 1275CO", "MAT 1275"] and p.exclusions == ["MAT 2572"] and p.or_branch
    assert mcc.parse_text("P: ENG 1101, MUST NOT BE CIS OR CIB MAJOR").exclusions == []


def test_an_own_code_inside_the_text_is_skipped():
    p = mcc.parse_text("PRE: MAT 1275 OR Meet the Math Placement for MAT 1375", own="MAT 1375")
    assert p.codes == ["MAT 1275"]
    assert any("Placement" in c for c in p.conditions)  # a non-course condition, kept as text


def test_non_course_conditions_are_listed_as_text():
    p = mcc.parse_text(
        "CUNY proficiency in mathematics. High School Math GPA 70 or higher; DEN 1100"
    )
    assert p.codes == ["DEN 1100"]
    assert p.conditions == ["CUNY proficiency in mathematics", "High School Math GPA 70 or higher"]


@pytest.mark.parametrize(
    ("text", "style", "why"),
    [("PRE_CST1100_CST1101", "shorthand", "shorthand"), ("PRE_CST1101_1204_MST2304_MAT13", "text", "shorthand"),
     ("Prerequisite: CST1201 and MAT13", "text", "truncated"), ("anything", "shorthand", "shorthand")],
)  # fmt: skip
def test_shorthand_and_truncated_text_is_unparsed_and_nothing_is_guessed(text, style, why):
    p = mcc.parse_text(text, style)
    assert p.unparsed and why in p.unparsed and p.codes == [] and p.exclusions == []


def test_corequisite_and_or_wording_is_flagged_not_interpreted():
    p = mcc.parse_text("Prerequisites: DEN 1100; Corequisite: DEN 1112")
    assert p.coreq and p.codes == ["DEN 1100", "DEN 1112"] and not p.or_branch


# ---- expansion ----


def test_breadth_first_order_levels_and_sources():
    records = recs(
        rec("AA 1001", "PRE: BB 1001 & CC 1001"),
        rec("BB 1001", "PRE: DD 1001"),
        rec("CC 1001"),
        rec("DD 1001"),
    )
    nodes = mcc.expand("AA 1001", records)
    assert [(n.code, n.level) for n in nodes] == [
        ("AA 1001", 0),
        ("BB 1001", 1),
        ("CC 1001", 1),
        ("DD 1001", 2),
    ]
    assert mcc.chain_depth(nodes) == 2
    assert mcc.gold_sources(nodes) == [
        f"catalog:{c}" for c in ("AA 1001", "BB 1001", "CC 1001", "DD 1001")
    ]


def test_a_cycle_ends_and_each_course_appears_once():
    records = recs(
        rec("DEN 1100", "Corequisite: DEN 1112"), rec("DEN 1112", "Corequisite of DEN 1100.")
    )
    nodes = mcc.expand("DEN 1100", records)
    assert [n.code for n in nodes] == ["DEN 1100", "DEN 1112"]


def test_an_exclusion_is_listed_but_never_expanded_or_a_source():
    records = recs(
        rec("AA 1001", "PRE: BB 1001. MUST NOT HAVE TAKEN XX 1001"),
        rec("BB 1001"),
        rec("XX 1001", "PRE: YY 1001"),
        rec("YY 1001"),
    )
    nodes = mcc.expand("AA 1001", records)
    assert [n.code for n in nodes] == ["AA 1001", "BB 1001"]
    assert nodes[0].parsed.exclusions == ["XX 1001"]
    assert "catalog:XX 1001" not in mcc.gold_sources(nodes)
    assert "exclusion, not a prerequisite: XX 1001" in mcc.node_line(nodes[0])


def test_an_or_text_names_every_alternative_and_flags_the_branch():
    records = recs(rec("AA 1001", "PRE: BB 1001 OR CC 1001"), rec("BB 1001"), rec("CC 1001"))
    nodes = mcc.expand("AA 1001", records)
    assert [n.code for n in nodes] == ["AA 1001", "BB 1001", "CC 1001"] and nodes[
        0
    ].parsed.or_branch


def test_the_depth_limit_stops_expansion_and_says_so():
    chain = [rec(f"CC 100{i}", f"PRE: CC 100{i + 1}") for i in range(7)] + [rec("CC 1007")]
    nodes = mcc.expand("CC 1000", recs(*chain))
    assert [n.level for n in nodes] == [0, 1, 2, 3, 4]  # nothing beyond level 4
    assert nodes[-1].depth_limit and not nodes[0].depth_limit
    assert "the chain continues beyond level 4" in mcc.node_line(nodes[-1])


def test_an_unparsed_course_is_shown_verbatim_and_not_expanded():
    records = recs(
        rec("AA 1001", "PRE: BB 1001"),
        rec("BB 1001", "PRE_C1001_D1001", "shorthand"),
        rec("CC 1001"),
    )
    nodes = mcc.expand("AA 1001", records)
    assert [n.code for n in nodes] == ["AA 1001", "BB 1001"]
    line = mcc.node_line(nodes[1])
    assert (
        'catalog text "PRE_C1001_D1001"' in line
        and "UNPARSED (shorthand text); not expanded" in line
    )


def test_a_code_with_no_record_is_marked_and_not_expanded():
    nodes = mcc.expand("AA 1001", recs(rec("AA 1001", "PRE: ENG 1101")))
    assert nodes[1].record is None and "no record in the catalog data" in mcc.node_line(nodes[1])
    assert mcc.gold_sources(nodes) == ["catalog:AA 1001"]


# ---- gold text ----


def test_gold_text_is_built_from_the_record_in_a_fixed_format():
    records = recs(
        rec("AA 1001", "PRE: BB 1001\nPRE: CC 1001", title=" Root Course "),
        rec("BB 1001"),
        rec("CC 1001", title="Third"),
    )
    gold = mcc.chain_gold(mcc.expand("AA 1001", records))
    assert gold.splitlines() == [
        "Draft chain for AA 1001 (Root Course), built from the catalog records:",
        'Level 0 - AA 1001 (Root Course): catalog text "PRE: BB 1001 / PRE: CC 1001"; course codes named: BB 1001, CC 1001.',
        "Level 1 - BB 1001 (Title of BB 1001): no prerequisite is listed in the catalog.",
        "Level 1 - CC 1001 (Third): no prerequisite is listed in the catalog.",
    ]


def test_unparsed_gold_gives_the_verbatim_text_and_the_department_contact(tmp_path):
    (tmp_path / "CST-NYT.json").write_text(json.dumps({"emails": ["d@x.edu"], "phones": ["718-1"]}))
    node = mcc.expand("AA 1001", recs(rec("AA 1001", "PRE_X", "shorthand")))[0]
    gold = mcc.unparsed_gold(node, mcc.contact_line("CST-NYT", tmp_path))
    assert gold == ('AA 1001 (Title of AA 1001): the catalog text is "PRE_X". The prerequisites cannot be determined '
                    "from the catalog text; contact the department: d@x.edu, 718-1.")  # fmt: skip
    assert mcc.contact_line("DENT-NYT", tmp_path) == "TODO"


def test_control_gold_is_the_description_and_credits():
    node = mcc.expand("AA 1001", recs(rec("AA 1001")))[0]
    assert mcc.control_gold(node) == "AA 1001 (Title of AA 1001, 3 credits): About AA 1001."


# ---- the file ----


def test_output_is_deterministic_and_lists_the_owner_checklist(tmp_path):
    existing = {"q39": {"MAT 1275"}}
    records = mcc.load_records()
    rules = json.loads(mcc.RULES.read_text())
    first = mcc.render(records, rules, 76, existing)
    assert first == mcc.render(records, rules, 76, existing)
    assert (
        "## Checklist for the owner" in first
        and "| q76 | | | |" in first
        and "| q87 | | | |" in first
    )


def test_the_real_candidates_cover_the_categories_and_ids_continue_after_the_highest():
    assert mcc.highest_question_number() == 75
    items = mcc.build(mcc.load_records(), 76)
    assert [c["id"] for c in items] == [f"q{n}" for n in range(76, 88)] and len(items) == 12
    assert (
        sum(c["split"] == "dev" for c in items) == 7
        and sum(c["split"] == "test" for c in items) == 5
    )
    by_kind = {c["spec"]["kind"] for c in items}
    assert by_kind == {"chain", "unparsed", "abstain", "control"}
    control = next(c for c in items if c["spec"]["kind"] == "control")
    assert control["tags"] == [] and all("chain" in c["tags"] for c in items if c is not control)
    assert {c["spec"]["root"].split(" ")[0] for c in items} >= {"CST", "MAT", "EET", "DEN"}
    records = mcc.load_records()
    for c in items:
        for source in c["sources"]:
            assert source.removeprefix("catalog:") in records


def test_the_unknown_code_is_really_absent_and_the_abstain_golds_are_plain_abstain():
    records = mcc.load_records()
    items = {c["spec"]["root"]: c for c in mcc.build(records, 76)}
    assert "CST 4999" not in records and "ENG 1101" not in records
    assert items["CST 4999"]["gold"] == items["ENG 1101"]["gold"] == "ABSTAIN"
    assert items["CST 4999"]["sources"] == []


def test_the_script_never_writes_the_questions_file():
    source = (ROOT / "scripts" / "make_chain_candidates.py").read_text()
    assert "QUESTIONS.write" not in source and "open(QUESTIONS" not in source


def test_the_control_uses_one_record_only_as_gold_source():
    items = mcc.build(mcc.load_records(), 76)
    control = next(c for c in items if c["spec"]["kind"] == "control")
    assert control["sources"] == ["catalog:MAT 2440"] and len(control["nodes"]) == 1
