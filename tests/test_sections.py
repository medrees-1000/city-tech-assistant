from cta.index.chunks import has_table, merge_tables_into_parents
from tests.helpers import parse


def section(heading, level, markdown, parents=()):
    return {"heading": heading, "level": level, "markdown": markdown, "parents": list(parents)}


TABLE = "| A | B |\n| --- | --- |\n| 1 | 2 |"
H1 = {"level": 1, "heading": "Standard"}


def test_has_table():
    assert has_table(TABLE) and has_table("text\n\n" + TABLE)
    assert not has_table("a | b\nplain text with | a pipe")


def test_sap_tables_are_merged_with_the_intro_text_above_them():
    rec = parse("financial_aid_sap", "/financial-aid/sap.aspx", owner="financial-aid")
    sections = rec["sections"]
    assert "following table" in sections[0]["markdown"].lower()  # the intro is in the parent
    assert [has_table(s["markdown"]) for s in sections[:3]] == [False, True, True]
    units = merge_tables_into_parents(sections)
    assert len(units) == len(sections) - 2
    first = units[0]
    assert first["heading"] == sections[0]["heading"]
    assert first["markdown"].startswith(sections[0]["markdown"])  # intro text first, unchanged
    assert first["merged"] == ["Associate Degrees (Two-Year Programs)",
                               "Baccalaureate Degrees (Four-Year Programs)"]  # fmt: skip
    assert "### Associate Degrees (Two-Year Programs)" in first["markdown"]
    assert first["markdown"].count("\n| --- |") == 2  # both tables, in the same unit
    assert first["markdown"].index("Associate Degrees") < first["markdown"].index("Baccalaureate")
    assert not [u for u in units[1:] if has_table(u["markdown"])]  # no table left on its own
    assert [u["heading"] for u in units[1:]] == [s["heading"] for s in sections[3:]]


def test_sap_table_cells_are_unchanged_by_the_merge():
    rec = parse("financial_aid_sap", "/financial-aid/sap.aspx", owner="financial-aid")
    table_text = rec["sections"][1]["markdown"]
    merged = merge_tables_into_parents(rec["sections"])[0]["markdown"]
    assert table_text in merged


def test_table_without_a_parent_text_stays_alone_and_input_is_not_changed():
    sections = [section("Orphan", 3, TABLE, [H1])]  # no section "Standard" exists (it had no text)
    units = merge_tables_into_parents(sections)
    assert [u["heading"] for u in units] == ["Orphan"] and units[0]["merged"] == []
    assert sections[0]["markdown"] == TABLE and "merged" not in sections[0]


def test_text_only_children_are_not_merged():
    sections = [section("Standard", 1, "intro text"), section("Child", 2, "more", [H1])]
    assert [u["heading"] for u in merge_tables_into_parents(sections)] == ["Standard", "Child"]


def test_table_goes_to_its_own_parent_not_a_sibling_branch():
    h2 = {"level": 2, "heading": "Branch"}
    sections = [
        section("Standard", 1, "intro"),
        section("Branch", 2, "branch intro", [H1]),
        section("Data", 3, TABLE, [H1, h2]),
    ]
    units = merge_tables_into_parents(sections)
    assert [u["heading"] for u in units] == ["Standard", "Branch"]
    assert units[1]["merged"] == ["Data"] and TABLE in units[1]["markdown"]
    assert TABLE not in units[0]["markdown"]
