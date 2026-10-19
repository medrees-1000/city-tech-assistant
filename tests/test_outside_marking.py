"""Tester round 1b, item 1a: a named course outside the four departments is marked as such.
No model call. The "before" texts were saved before the change in tests/fixtures/."""

import hashlib
import json
import re

import pytest

from cta.graph import chain as ch
from cta.graph import chain_render as cr
from cta.settings import ROOT
from tests.helpers import MARK, PREFIXES, RECORDS, outside_rewrite

BEFORE = json.loads((ROOT / "tests/fixtures/chain_render_before_outside_marking.json").read_text())




def new_render(code_or_codes) -> str:
    if isinstance(code_or_codes, list):
        return cr.render(ch.combined_chain(code_or_codes), RECORDS)
    return cr.render(ch.prerequisite_chain.invoke({"course_code": code_or_codes}), RECORDS)


def test_the_fixture_is_the_197_single_and_42_multi_renders():
    assert len(BEFORE["single"]) == 197 and len(BEFORE["multi"]) == 42


@pytest.mark.parametrize("code", sorted(BEFORE["single"]))
@pytest.mark.needs_data
def test_single_chain_differs_only_by_the_outside_marking(code):
    assert new_render(code) == outside_rewrite(BEFORE["single"][code])


@pytest.mark.parametrize("key", sorted(BEFORE["multi"]))
@pytest.mark.needs_data
def test_multi_course_render_differs_only_by_the_outside_marking(key):
    item = BEFORE["multi"][key]
    assert new_render(item["codes"]) == outside_rewrite(item["text"])


@pytest.mark.needs_data
def test_catalog_quotes_dates_numbers_and_the_closing_sentence_are_unchanged():
    for code, old in BEFORE["single"].items():
        new = new_render(code)
        for pattern in (
            r'\*\*Catalog says:\*\* ".*"',
            r"\[\d+\]",
            r"No catalog record in the four.*",
        ):
            assert re.findall(pattern, new) == re.findall(pattern, old), (code, pattern)


@pytest.mark.needs_data
def test_the_counts_the_pre_registration_expects():
    marked = [
        c
        for c, t in BEFORE["single"].items()
        if any(m[1] not in PREFIXES for m in MARK.finditer(t))
    ]
    assert len(marked) == 52
    changed = [c for c in BEFORE["single"] if new_render(c) != BEFORE["single"][c]]
    assert sorted(changed) == sorted(marked)  # exactly the renders with an outside mark change
    inside = [
        c for c, t in BEFORE["single"].items() if any(m[1] in PREFIXES for m in MARK.finditer(t))
    ]
    assert len(inside) == 21
    multi = [k for k, v in BEFORE["multi"].items() if new_render(v["codes"]) != v["text"]]
    assert len(multi) == 18


@pytest.mark.needs_data
def test_an_inside_prefix_code_keeps_no_catalog_record_and_an_outside_one_does_not():
    titles = {c: r["title"].strip() for c, r in RECORDS.items()}
    assert cr.named("MAT 1476", titles) == "MAT 1476 (no catalog record)"  # MAT is in the data
    assert cr.named("CST 1202", titles) == "CST 1202 (no catalog record)"
    assert cr.named("ENG 1101", titles) == "ENG 1101 (outside the four departments I cover)"
    assert cr.named("EMT 1111", titles) == "EMT 1111 (outside the four departments I cover)"
    some = next(c for c in titles if titles[c])
    assert cr.named(some, titles) == f"{some} ({titles[some]})"  # a code with a record is unchanged


def test_the_prefix_set_is_derived_from_the_records_not_typed():
    import inspect

    assert PREFIXES == {c.split()[0] for c in RECORDS}
    body = inspect.getsource(cr.named) + inspect.getsource(cr.render_sections)
    assert not re.search(r'"(?:CST|MAT|EET|DEN|ENG)"', body)


@pytest.mark.needs_data
def test_a_multi_course_asked_code_outside_the_data_uses_the_single_course_sentence():
    text = new_render(["CST 1204", "ENG 1101"])
    assert "## Prerequisites for ENG 1101\n\n" + ch.outside_sentence("ENG 1101") in text
    assert "ABSTAIN" not in text  # the marker belongs to a whole-answer abstention only
    text = new_render(["CST 1204", "CST 9999"])  # a known prefix with no record keeps its sentence
    assert "There is no catalog record for CST 9999 in the four departments" in text


@pytest.mark.needs_data
def test_the_regenerated_hash_fixture_matches_the_new_single_renders():
    golden = json.loads((ROOT / "tests/fixtures/chain_single_render_sha256.json").read_text())
    for code in BEFORE["single"]:
        assert hashlib.sha256(new_render(code).encode()).hexdigest() == golden["sha256"][code]
