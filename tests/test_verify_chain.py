# ruff: noqa: E501
"""scripts/verify_chain_candidates.py: the independent check, on hand-made raw data (no network)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_chain_candidates", ROOT / "scripts" / "verify_chain_candidates.py"
)
vcc = importlib.util.module_from_spec(spec)
sys.modules["verify_chain_candidates"] = vcc
spec.loader.exec_module(vcc)


def raw_rec(code, rule=None, name=None, dept="CST-NYT", **kw):
    return {"_id": f"id-{code}", "code": code, "name": name or f"Title {code}", "courseGroupId": f"g{code[-4:]}",
            "requirementGroup": rule, "departments": [{"id": dept}], "status": "Active", "description": "About it.",
            "alternativeCode": None} | kw  # fmt: skip


def world(tmp_path, records, rules):
    """A raw directory with one page of courses and one file per rule; returns (raw, cache, raw_rules)."""
    page = {"listLength": len(records), "data": records}
    (tmp_path / "api-v1-cm-nyt01-courses-search-x.json").write_text(json.dumps(page))
    for rid, text in rules.items():
        body = {"data": {rid: {"descriptionLong": text, "catalogDisplayName": text}}}
        (tmp_path / f"api-v1-nyt01-requirementGroups-{rid}-x.json").write_text(json.dumps(body))
    cache = {rid: {"code": rid, "text": text} for rid, text in rules.items()}
    return vcc.load_raw_courses(tmp_path), cache, vcc.load_raw_rules(tmp_path)


def md(rows, sources, tags="chain", kind="multi_chunk", extra=""):
    table = "\n".join(f"| {lv} | {c} | {t} | {x} | {r} | {g} |" for lv, c, t, x, r, g in rows)
    src = ", ".join(f"`catalog:{s}`" for s in sources) or "(none)"
    return f"## q1 — x\n\n- **Type:** {kind}  |  **Tags:** {tags}  |  **Proposed split:** dev\n- **Gold sources:** {src}\n{extra}\n| level | code | title | prerequisite text | requirementGroup id | courseGroupId |\n|---|---|---|---|---|---|\n{table}\n"


RECORDS = [raw_rec("AA 1001", "000001"), raw_rec("BB 1001", "000002"), raw_rec("CC 1001")]
RULES = {"000001": "PRE: BB 1001", "000002": "PRE: CC 1001"}
GOOD = [(0, "AA 1001", "Title AA 1001", "PRE: BB 1001", "000001", "g1001"), (1, "BB 1001", "Title BB 1001", "PRE: CC 1001", "000002", "g1001"),
        (2, "CC 1001", "Title CC 1001", "-", "-", "g1001")]  # fmt: skip


def run_one(tmp_path, rows, sources=("AA 1001", "BB 1001", "CC 1001"), **kw):
    raw, cache, rules = world(tmp_path, RECORDS, RULES)
    sec = vcc.parse_candidates(md(rows, list(sources), **kw))["q1"]
    return vcc.check_candidate("q1", sec, raw, cache, rules)


def failed(res):
    return sorted(c for c, ok in res.passed.items() if ok is False)


# ---- reading texts ----


def test_read_text_codes_bare_numbers_stop_words_exclusions_and_unparsed():
    assert vcc.read_text("PRE: CST 1100 & 1101, C GRADE", "X 1") == (
        ["CST 1100", "CST 1101"],
        [],
        None,
    )
    assert vcc.read_text("PRE: CST1201 & (2405 or 2415)", "X 1")[0] == [
        "CST 1201",
        "CST 2405",
        "CST 2415",
    ]
    assert vcc.read_text("PRE: TWO 2000-LEVEL COURSES", "X 1")[0] == []
    assert vcc.read_text("PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675", "X 1")[:2] == (
        ["MAT 1475"],
        ["MAT 2675"],
    )
    assert vcc.read_text("Meet the Placement for MAT 1375 or MAT 1275", "MAT 1375")[0] == [
        "MAT 1275"
    ]
    assert vcc.read_text("PRE_CST1100_CST1101", "X 1") == ([], [], "shorthand")
    assert vcc.read_text("PRE_CST1101_1204_MST2304_MAT13", "X 1")[2] == "shorthand"
    assert vcc.read_text("Prerequisite: CST1201 and MAT13", "X 1")[2] == "truncated"
    assert vcc.read_text("", "X 1") == ([], [], None)


def test_my_chain_levels_and_the_level_limit():
    texts = {f"C {i}": f"PRE: C {i + 1}" for i in range(1000, 1008)} | {"C 1008": ""}
    texts = {k.replace("C ", "CC "): v.replace("C 1", "CC 1") for k, v in texts.items()}
    levels, _ = vcc.my_chain("CC 1000", {"CC 1000": "PRE: CC 1001"} | texts)
    assert max(levels.values()) == 4 and len(levels) == 5


# ---- checks a, b, c ----


def test_a_matching_candidate_passes(tmp_path):
    res = run_one(tmp_path, GOOD)
    assert failed(res) == [] and res.notes == []


def test_a_title_text_rule_or_group_difference_fails_a(tmp_path):
    for bad in (GOOD[:1] + [(1, "BB 1001", "A different title", "PRE: CC 1001", "000002", "g1001")] + GOOD[2:],
                [GOOD[0], (1, "BB 1001", "Title BB 1001", "PRE: ZZ 9999", "000002", "g1001"), GOOD[2]],
                [GOOD[0], (1, "BB 1001", "Title BB 1001", "PRE: CC 1001", "000009", "g1001"), GOOD[2]],
                [GOOD[0], (1, "BB 1001", "Title BB 1001", "PRE: CC 1001", "000002", "g9999"), GOOD[2]]):  # fmt: skip
        assert "a" in failed(run_one(tmp_path, bad))


def test_a_rule_whose_cache_and_raw_file_disagree_fails_a(tmp_path):
    raw, cache, rules = world(tmp_path, RECORDS, RULES)
    cache["000001"]["text"] = "PRE: something else"
    sec = vcc.parse_candidates(md(GOOD, ["AA 1001", "BB 1001", "CC 1001"]))["q1"]
    assert "a" in failed(vcc.check_candidate("q1", sec, raw, cache, rules))


def test_a_no_record_row_for_a_course_the_raw_data_has_fails_a(tmp_path):
    rows = GOOD[:2] + [
        (2, "CC 1001", "-", "no record in the catalog data of the four departments", "-", "-")
    ]
    assert "a" in failed(run_one(tmp_path, rows, ("AA 1001", "BB 1001")))


def test_an_extra_or_a_missing_chain_course_fails_b(tmp_path):
    extra = GOOD + [(2, "DD 1001", "Title DD 1001", "-", "-", "g1001")]
    assert "b" in failed(run_one(tmp_path, extra))
    assert "b" in failed(run_one(tmp_path, GOOD[:2], ("AA 1001", "BB 1001")))


def test_an_exclusion_in_the_chain_fails_b(tmp_path):
    records = [raw_rec("AA 1001", "000001"), raw_rec("BB 1001")]
    raw, cache, rules = world(
        tmp_path, records, {"000001": "PRE: BB 1001. MUST NOT HAVE TAKEN CC 1001"} | {}
    )
    rows = [(0, "AA 1001", "Title AA 1001", "PRE: BB 1001. MUST NOT HAVE TAKEN CC 1001", "000001", "g1001"), (1, "BB 1001", "Title BB 1001", "-", "-", "g1001"),
            (1, "CC 1001", "-", "no record", "-", "-")]  # fmt: skip
    sec = vcc.parse_candidates(md(rows, ["AA 1001", "BB 1001"]))["q1"]
    assert "b" in failed(vcc.check_candidate("q1", sec, raw, cache, rules))


def test_gold_sources_must_equal_the_chain_records(tmp_path):
    assert "c" in failed(run_one(tmp_path, GOOD, ("AA 1001", "BB 1001")))
    assert "c" in failed(run_one(tmp_path, GOOD, ("BB 1001", "AA 1001", "CC 1001")))  # order too


def test_a_control_without_the_chain_tag_is_checked_as_one_record(tmp_path):
    res = run_one(tmp_path, GOOD[:1], ("AA 1001",), tags="(none)", kind="lookup")
    assert res.passed["b"] is None and failed(res) == []
    assert "c" in failed(
        run_one(tmp_path, GOOD[:1], ("AA 1001", "BB 1001"), tags="(none)", kind="lookup")
    )


def test_an_unanswerable_candidate_lists_no_gold_sources_and_names_its_reference(tmp_path):
    ok = run_one(
        tmp_path,
        GOOD[:1],
        (),
        kind="unanswerable",
        extra="- **Note:** Reference record: catalog:AA 1001.",
    )
    assert "c" not in failed(ok)
    bad = run_one(
        tmp_path,
        GOOD[:1],
        ("AA 1001",),
        kind="unanswerable",
        extra="- **Note:** Reference record: catalog:AA 1001.",
    )
    assert "c" in failed(bad)


# ---- checks d to h ----


def test_d_a_record_with_a_requirement_group_or_prerequisite_wording_fails(tmp_path):
    ok = {"AA 1001": [raw_rec("AA 1001", None, description="The students must know algebra.")]}
    res = vcc.Result("q79")
    vcc.lost_field_check(res, "AA 1001", ok, {})
    assert res.passed["d"] is True and any("fields checked" in n for n in res.notes)
    for kw in ({"requirementGroup": "000001"}, {"customFields": {"note": "Prerequisite: BB 1001"}}):
        res = vcc.Result("q79")
        vcc.lost_field_check(res, "AA 1001", {"AA 1001": [raw_rec("AA 1001", None, **kw)]}, {})
        assert res.passed["d"] is False
    res = vcc.Result("q79")
    vcc.lost_field_check(
        res,
        "AA 1001",
        {"AA 1001": [raw_rec("AA 1001", None, description="Prerequisite: none.")]},
        {},
    )
    assert res.passed["d"] is True and any(
        "description" in n and "mentions" in n for n in res.notes
    )


def test_e_a_code_anywhere_in_the_raw_list_fails(tmp_path):
    raw, _, _ = world(tmp_path, RECORDS, RULES)
    res = vcc.Result("q83")
    vcc.absent_check(res, "CST 4999", tmp_path, raw)
    assert res.passed["e"] is True and any(
        "1 distinct records" in n or "3 distinct records" in n for n in res.notes
    )
    for where in ({"alternativeCode": "CST 4999"}, {"description": "see CST4999"}):
        raw2, _, _ = world(tmp_path, [raw_rec("ZZ 1001", None, **where)], {})
        res = vcc.Result("q83")
        vcc.absent_check(res, "CST 4999", tmp_path, raw2)
        assert res.passed["e"] is False


def test_f_reports_whether_the_course_exists_either_answer_passes(tmp_path):
    raw, _, _ = world(tmp_path, [raw_rec("ENG 1101", None, dept="ENGL-NYT")], {})
    res = vcc.Result("q84")
    vcc.exists_check(res, "ENG 1101", raw)
    assert res.passed["f"] is True and "exists in the full raw list" in res.notes[0]
    res = vcc.Result("q84")
    vcc.exists_check(res, "ENG 9999", raw)
    assert res.passed["f"] is True and "is not in the full raw list" in res.notes[0]


def test_g_the_title_must_belong_to_exactly_one_record_of_the_four_departments(tmp_path):
    raw, _, _ = world(tmp_path, [raw_rec("CST 3504", None, name="Database Design"), raw_rec("CST 3999", None, name="Advanced Database Design II"),
                                 raw_rec("ENG 3504", None, name="Database Design", dept="ENGL-NYT")], {})  # fmt: skip
    res = vcc.Result("q85")
    vcc.title_check(res, "Database Design", raw)
    assert (
        res.passed["g"] is True
        and "other titles containing the phrase: ['CST 3999']" in res.notes[0]
    )
    raw2, _, _ = world(
        tmp_path,
        [
            raw_rec("CST 3504", None, name="Database Design"),
            raw_rec("CST 3505", None, name=" database design "),
        ],
        {},
    )
    res = vcc.Result("q85")
    vcc.title_check(res, "Database Design", raw2)
    assert res.passed["g"] is False


CHUNKS = {
    "contact:CST-NYT": "CONTACT US\nEmail: compsystech@citytech.cuny.edu\n\nPhone: 718-260-5170"
}


def test_h_contact_line_must_equal_the_chunk_with_no_stray_spaces():
    ok = 'text\n> X: the catalog text is "P". The prerequisites cannot be determined from the catalog text; contact the department: compsystech@citytech.cuny.edu, 718-260-5170.\n'
    res = vcc.Result("q82")
    vcc.contact_check(res, ok, CHUNKS, "contact:CST-NYT")
    assert res.passed["h"] is True
    for line in (
        "compsystech@citytech.cuny.edu, 718-260-5171",
        "compsystech @citytech.cuny.edu, 718-260-5170",
        "other@citytech.cuny.edu, 718-260-5170",
    ):
        res = vcc.Result("q82")
        vcc.contact_check(res, f"contact the department: {line}.\n", CHUNKS, "contact:CST-NYT")
        assert res.passed["h"] is False
    res = vcc.Result("q82")
    vcc.contact_check(res, "no contact here", CHUNKS, "contact:CST-NYT")
    assert res.passed["h"] is False


def test_table_marks_pass_fail_and_not_applicable():
    res = vcc.Result("q1", {"a": True, "b": None, "c": False}, ["c: bad"])
    text = vcc.table([res])
    assert "| q1 | pass | - | FAIL | - | - | - | - | - | c: bad |" in text


# ---- the real files ----


def test_the_candidate_file_parses_into_12_sections_and_q87_is_not_a_chain():
    sections = vcc.parse_candidates(vcc.CANDIDATES.read_text(encoding="utf-8"))
    assert list(sections) == [f"q{n}" for n in range(76, 88)]
    assert sections["q87"]["chain"] is False and sections["q76"]["chain"] is True
    assert sections["q82"]["type"] == "unanswerable" and sections["q82"]["gold_sources"] == []


@pytest.mark.skipif(
    not vcc.RAW.exists() or not vcc.CHUNKS.exists(), reason="no raw or processed data"
)
def test_the_real_candidates_pass_the_independent_check(capsys):
    assert vcc.main() == 0
    out = capsys.readouterr().out
    assert "failed: none" in out and "| q87 | pass | - | pass |" in out
