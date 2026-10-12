"""Judge hand-check sheet helpers (no network, no database)."""

from cta.eval import judge_sheet as js

CHECK = """# Judge check

## q01 (lookup)

**My verdict:** correctness partial / faithfulness yes

## q03 (lookup)

**My verdict:** correctness correct / faithfulness partly (a note in brackets)

## q09 (lookup)

(no verdict written)
"""


def rec(qid, correctness, faithfulness, **kw):
    return {"id": qid, "correctness": correctness, "faithfulness": faithfulness,
            "correctness_reason": "c reason", "faithfulness_reason": "f reason"} | kw  # fmt: skip


def test_owner_verdicts_are_read_from_the_my_verdict_lines():
    assert js.owner_verdicts(CHECK) == {"q01": ("partial", "yes"), "q03": ("correct", "partly")}


def test_the_real_check_file_has_the_eight_owner_verdicts():
    text = js.CHECK.read_text(encoding="utf-8")
    owner = js.owner_verdicts(text)
    assert sorted(owner) == ["q01", "q03", "q04", "q05", "q06", "q08", "q12", "q15"]


def test_agreement_counts_and_names_the_disagreements():
    owner = {"q01": ("partial", "yes"), "q03": ("correct", "partly"), "q04": ("correct", "yes")}
    records = [
        rec("q01", "correct", "yes"),
        rec("q03", "correct", "yes"),
        rec("q04", "correct", "yes"),
        rec("q99", "incorrect", "no"),
    ]
    got = js.agreement(records, owner)
    assert (got["n"], got["correctness"], got["faithfulness"]) == (3, 2, 2)
    assert got["disagreements"] == [
        "q01 correctness (correct vs partial)",
        "q03 faithfulness (yes vs partly)",
    ]
    row = js.agreement_row("v9", got)
    assert row.startswith("| v9 | 2 / 3 | 2 / 3 | q01 correctness (correct vs partial), q03")
    assert js.agreement_row(
        "v9", js.agreement([rec("q01", "partial", "yes")], {"q01": ("partial", "yes")})
    ).endswith("| none |")


def test_the_judges_own_sentences_are_listed_only_for_verdicts_that_are_not_correct_yes():
    assert js.named_claims(rec("q", "correct", "yes")) == []
    got = js.named_claims(rec("q", "partial", "no"))
    assert got == ["correctness (partial): c reason", "faithfulness (no): f reason"]
    assert js.named_claims(rec("q", "incorrect", None)) == ["correctness (incorrect): c reason"]


CHUNK = {
    "id": "page/x#1", "kind": "section", "source": "https://x/y.aspx", "heading_path": "A > B",
    "terms": ["Fall 2026"], "last_updated": None, "text": "Body text of the section.",
}  # fmt: skip


def test_a_source_block_shows_the_text_exactly_as_the_answerer_got_it():
    from cta.answer import format_source

    block = js.source_block(1, CHUNK, "1")
    assert block.startswith("<details><summary>[1] https://x/y.aspx | A > B | rank 1</summary>")
    assert format_source(1, CHUNK) in block and block.endswith("</details>")


def test_an_item_has_the_answer_reasons_sources_and_a_blank_verdict_line():
    q = {"id": "q22", "type": "multi_chunk", "question": "Q?", "gold_answer": "G"}
    text = js.render_item(
        q, "run-x", "arm ON", rec("q22", "partial", "no"), "The answer [1].", [CHUNK]
    )
    assert "**Judge, correctness:** partial: c reason" in text
    assert "**Judge, faithfulness:** no: f reason" in text
    assert (
        "**Model's answer:** The answer [1]." in text
        and "**Sources the answerer received (1):**" in text
    )
    assert "<details>" in text and text.rstrip().endswith(
        "**My verdict:** correctness  / faithfulness"
    )
    assert "right" not in text.lower().replace(
        "copyright", ""
    )  # it never says which verdict is right


def test_the_items_are_the_ones_and_the_order_the_owner_asked_for():
    assert [(q, label) for q, label, _ in js.ITEMS] == [
        ("q22", "baseline-dev-60-v3"), ("q22", "on-run1"), ("q40", "baseline-dev-60-v3"),
        ("q40", "on-run1"), ("q52", "baseline-dev-60-v3"), ("q52", "on-run1"),
        ("q15", "on-run1"), ("q15", "baseline-dev-60-v3"),
    ]  # fmt: skip
