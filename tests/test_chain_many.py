"""Step 2, two-course questions: the keep rule K1 to K4 of docs/decisions.md ("Step 2 (two-course
questions): the keep rule"). Deterministic; no model call. Only dev result files are read."""

import hashlib
import json
import re

import pytest

from cta.graph import advice
from cta.graph import chain as ch
from cta.graph import chain_render as cr
from cta.settings import ROOT
from tests.test_api import Client
from tests.test_chain_render import CFG_CODE, CFG_MODEL, HEADING, route

RECORDS = ch.load_records()
pytestmark = pytest.mark.skipif(not RECORDS, reason="no processed course records")
CODES = sorted(RECORDS)
SECTION = re.compile(r"^## Prerequisites for (.+)$", re.M)
SHOWN = re.compile(r"^(\S+ \S+) is already shown above\.$", re.M)

SHARES = ["CST 1204", "CST 2403"]  # both need CST 1101
ONE_NAMES_OTHER = ["CST 3504", "CST 1204"]  # CST 3504 names CST 1204
SAME_DESCRIPTION = ["CST 1204", "CST 2304"]  # two records that share a description: never merged
CROSS_LISTED = ["EET 3672", "CET 3672", "MECH 3672"]  # only EET 3672 is in the four departments
CAPPED = ["CST 4702", "CST 4802", "CST 4822"]  # each chain alone reaches the cap of 15
COMBOS = (
    [SHARES, ONE_NAMES_OTHER, ONE_NAMES_OTHER[::-1], SAME_DESCRIPTION, CAPPED]
    + [["CST 3601", "CST 1204"], ["CST 3504", "CST 1204", "CST 1100"], ["MAT 2440", "MAT 1475"]]
    + [[CODES[i], CODES[(i * 7 + 3) % len(CODES)]] for i in range(0, len(CODES), 4)]
    + [[CODES[i], CODES[(i * 5 + 1) % len(CODES)], CODES[(i * 11 + 2) % len(CODES)]]
       for i in range(1, len(CODES), 9)]
)  # fmt: skip


def combined(codes):
    result = ch.combined_chain(codes)
    return result, cr.render(result, RECORDS)


def distinct(codes):
    return list(dict.fromkeys(codes))


def positions(text):
    """{course code: index of the section that shows it}, from the text itself."""
    where, section = {}, -1
    for line in text.splitlines():
        if line.startswith("## Prerequisites for "):
            section += 1
        elif m := re.match(r"### (\S+ \S+) — ", line):
            assert m[1] not in where, f"{m[1]} shown twice"
            where[m[1]] = section
    return where


# ---- K1: the walk and the renderer over the combinations ----


def test_k1_every_course_of_the_union_appears_exactly_once_and_numbers_match_the_sources():
    for codes in COMBOS:
        result, text = combined(codes)
        found = [(c, int(n)) for c, _, n in HEADING.findall(text)]
        assert [c for c, _ in found] == [c["code"] for c in result["courses"]], codes
        assert [n for _, n in found] == list(range(1, len(found) + 1)), codes
        assert len({c for c, _ in found}) == len(found), codes
        sources = ch.sources_of(result, RECORDS)
        assert [s["id"] for s in sources] == [f"catalog:{c}" for c, _ in found], codes
        if not result["dropped"]:  # nothing cut: the union of the single walks, nothing else
            union = {c["code"] for k in codes for c in ch.prerequisite_chain.invoke(
                {"course_code": k})["courses"]}  # fmt: skip
            assert {c for c, _ in found} == union, codes


def test_k1_the_asked_courses_come_in_the_order_asked_each_with_its_heading():
    for codes in COMBOS:
        result, text = combined(codes)
        assert SECTION.findall(text) == distinct(codes), codes
        assert result["asked"] == distinct(codes)
        assert text.startswith(
            "Here are the prerequisites for " + cr.codes_phrase(distinct(codes)) + ", from"
        )


def test_k1_a_shared_course_is_shown_once_in_the_first_section_and_the_later_one_says_so():
    result, text = combined(SHARES)
    where = positions(text)
    assert where["CST 1101"] == 0 and where["CST 1204"] == 0 and where["CST 2403"] == 1
    sections = {s["root"]: s for s in result["sections"]}
    assert sections["CST 2403"]["shared"] == ["CST 1101"]
    assert text.count("CST 1101 is already shown above.") == 1
    later = text.split("## Prerequisites for CST 2403")[1]
    assert "CST 1101 is already shown above." in later


def test_k1_an_asked_course_inside_another_asked_chain_gets_only_the_sentence():
    result, text = combined(ONE_NAMES_OTHER)  # CST 1204 is walked inside CST 3504's section
    by_asked = {s["root"]: s for s in result["sections"]}
    assert by_asked["CST 1204"]["already_shown"] and by_asked["CST 1204"]["courses"] == []
    assert (
        text.split("## Prerequisites for CST 1204")[1].strip() == "CST 1204 is already shown above."
    )
    assert positions(text)["CST 1204"] == 0 and text.count("### CST 1204 — ") == 1
    result, text = combined(ONE_NAMES_OTHER[::-1])  # asked first, then named by CST 3504
    assert {s["root"]: s for s in result["sections"]}["CST 3504"]["shared"] == ["CST 1204"]
    assert positions(text)["CST 1204"] == 0 and text.count("### CST 1204 — ") == 1


def test_k1_at_most_15_courses_and_everything_cut_is_named_exactly_as_the_walk_reports():
    cut = 0
    for codes in COMBOS:
        result, text = combined(codes)
        assert len(result["courses"]) <= ch.MAX_COURSES and result["course_count"] <= 15
        for d in result["dropped"]:
            cut += 1
            sentence = (
                f"{d['code']}, named by {d['named_by']}, is not shown because the list is "
                f"limited to {ch.MAX_COURSES} courses."
            )
            assert sentence in text
        for u in result["unexpanded"]:
            assert f"The list stops at {u['code']}, which names {', '.join(u['names'])};" in text
        if result["no_record"]:
            asked_unknown = {s["root"] for s in result["sections"] if not s["found"]}
            left = [c for c in result["no_record"] if c not in asked_unknown]
            # UI polish 3a: the closing sentence is left out when every such code is already marked
            # "(no catalog record)" in a "Courses named" line above; either way each is stated once
            closing_has = "No catalog record in the four departments for:" in text
            marked = {
                c
                for c in left
                if f"{c} (no catalog record)" in text or f"{c} ({cr.OUTSIDE})" in text
            }
            assert closing_has == (bool(left) and marked != set(left))
            assert all(c in text for c in left)
    assert cut > 0  # the capped combination does cut


def test_k1_the_asked_courses_are_never_the_ones_cut():
    result, text = combined(CAPPED)
    assert all(s["found"] and (s["courses"] or s["already_shown"]) for s in result["sections"])
    assert [c for c in CAPPED if f"### {c} — " not in text] == []  # all three are shown


def test_k1_verbatim_strings_no_chain_no_level_and_the_same_text_twice():
    for codes in COMBOS:
        result, text = combined(codes)
        assert cr.render(ch.combined_chain(codes), RECORDS) == text  # deterministic
        for c in result["courses"]:
            if c["text"]:
                assert f'**Catalog says:** "{c["text"]}"' in text, (codes, c["code"])
        own = re.sub(r'"[^"]*"', "", text)
        assert "chain" not in text.lower() and "level" not in own.lower(), codes


def test_k1_four_codes_fall_through_and_titles_alone_never_take_the_several_course_path():
    four = ch.extract_course("CST 1204, CST 2403, CST 3601 and CST 3504?", RECORDS)
    assert four.status == "many"
    title = RECORDS["CST 1204"]["title"].strip()
    assert ch.extract_course(f"What do I need for {title}?", RECORDS).status in (
        "title",
        "ambiguous",
    )
    mixed = ch.extract_course(f"What do I need for CST 3504 and {title}?", RECORDS)
    assert mixed.status == "code" and mixed.code == "CST 3504"  # the title is not mixed in
    two_titles = ch.extract_course(
        f"{title} and {RECORDS['CST 3601']['title'].strip()}: what do I need?", RECORDS
    )
    assert two_titles.status in ("ambiguous", "none")


def test_k1_cross_listed_codes_stay_separate_never_merged():
    result, text = combined(SAME_DESCRIPTION)  # same description, two records, two sections
    for code in SAME_DESCRIPTION:
        assert text.count(f"### {code} — ") == 1 and f"## Prerequisites for {code}" in text
    texts = {c["code"]: c["text"] for c in result["courses"] if c["code"] in SAME_DESCRIPTION}
    assert texts == {c: (RECORDS[c]["prerequisite_text"] or "").strip() for c in SAME_DESCRIPTION}
    # EET 3672 / CET 3672 / MECH 3672: only the first has a record here; the others are not
    # mapped onto it
    result, text = combined(CROSS_LISTED)
    assert [s["found"] for s in result["sections"]] == [True, False, False]
    assert text.count("### EET 3672 — ") == 1 and "### CET 3672" not in text
    # tester round 1b (1a): CET and MECH are subjects of no record we hold, so their sections use
    # the sentence of item D ("I only have catalog records for ...") not "no catalog record"
    assert text.count("so I can't tell you about CET 3672.") == 1
    assert text.count("so I can't tell you about MECH 3672.") == 1
    assert text.count("There is no catalog record for") == 0


def test_k1_an_unknown_code_among_several_has_its_own_section_and_the_others_are_walked():
    result, text = combined(["CST 1204", "XYZ 1000", "CST 3504"])
    assert result["found"] and [s["found"] for s in result["sections"]] == [True, False, True]
    # XYZ is a subject of no record we hold: the asked-code section uses the item D sentence (1a)
    assert (
        text.count("## Prerequisites for XYZ 1000\n\nI only have catalog records for Computer") == 1
    )
    assert text.count("There is no catalog record for") == 0
    assert "### CST 1204 — " in text and "### CST 3504 — " in text
    assert "No catalog record in the four departments for: XYZ 1000" not in text  # said once
    only = ch.combined_chain(["XYZ 1000", "ABC 2000"])
    assert only == {"found": False, "code": "XYZ 1000, ABC 2000"}


# ---- K2: one code is byte-identical to the renderer at the end of C1 and C2 (f6cdbdc) ----


def test_k2_all_197_single_course_answers_are_byte_identical_to_f6cdbdc():
    golden = json.loads((ROOT / "tests/fixtures/chain_single_render_sha256.json").read_text())
    assert sorted(golden["sha256"]) == CODES and len(CODES) == 197
    for code in CODES:
        text = cr.render(ch.prerequisite_chain.invoke({"course_code": code}), RECORDS)
        assert hashlib.sha256(text.encode()).hexdigest() == golden["sha256"][code], code


DEV_RUNS = ["4b-run1", "4b-run2", "4b-run3", "chain-code-run1", "chain-code-run2"]


def stored_dev_questions():
    """(id, question, stored route, stored intent) from the dev result files only."""
    questions = {
        q["id"]: q["question"]
        for q in map(json.loads, (ROOT / "eval/questions.jsonl").read_text().splitlines())
        if q["split"] == "dev"
    }
    rows = []
    for label in DEV_RUNS:
        data = json.loads((ROOT / f"eval/results/{label}.json").read_text())
        assert data["split"] == "dev"
        for r in data["per_question"]:
            rows.append((r["id"], questions[r["id"]], r["route"], r["router"]["intent"]))
    return rows


def test_k2_every_stored_one_code_chain_question_gives_the_same_text_as_at_f6cdbdc(monkeypatch):
    golden = json.loads((ROOT / "tests/fixtures/chain_single_render_sha256.json").read_text())
    seen = {}
    for qid, question, stored, _ in stored_dev_questions():
        codes = ch.question_codes(question)
        if stored == "chain" and len(codes) == 1:
            out = route(CFG_CODE, Client("prerequisite"), monkeypatch, question)
            assert out.route == "chain" and out.router["chain"]["extraction"] == "code"
            code = out.router["chain"]["code"]
            assert hashlib.sha256(out.text.encode()).hexdigest() == golden["sha256"][code], qid
            seen[qid] = code
    print("K2 stored one-code chain questions:", seen)
    assert len(seen) >= 6


# ---- K3: routing from the stored classifier outputs (no new model call) ----


def test_k3_two_or_three_codes_go_to_the_chain_node_iff_the_stored_intent_is_prerequisite(
    monkeypatch,
):
    changed, counted = set(), 0
    for qid, question, stored, intent in stored_dev_questions():
        n = len(ch.question_codes(question))
        if intent == "calendar":
            continue  # the calendar node needs the calendar table; its routing is not touched
        if advice.needs_advice_rules(question, intent):
            continue  # step 5: the four NO ADVICE questions take the advice route on purpose
        out = route(CFG_CODE, Client(intent), monkeypatch, question)
        chain_family = out.route == "chain" or out.abstain_reason == "chain_no_record"
        if intent != "prerequisite":
            assert not chain_family, (qid, intent)
        elif 2 <= n <= 3:
            counted += 1
            assert chain_family, qid
        elif n > 3:
            assert out.route == "chain_fallthrough", qid
        stored_chain = stored in ("chain",) or stored == "abstain" and intent == "prerequisite"
        if n <= 1 and intent == "prerequisite":
            assert chain_family == stored_chain or stored == "chain_fallthrough", qid
        if chain_family != stored_chain and intent == "prerequisite":
            changed.add(qid)
    print("K3 changed route:", sorted(changed), "two- or three-code prerequisite rows:", counted)
    assert changed == {"q42"}


def test_k3_without_the_code_renderer_several_courses_fall_through_as_in_4b(monkeypatch):
    out = route(
        CFG_MODEL, Client("prerequisite"), monkeypatch, "Prerequisites of CST 1204 and CST 2403?"
    )
    assert out.route == "chain_fallthrough" and out.text == "old path [1]"
    off = load_off()
    assert off["router"]["chain"] == "off"


def load_off():
    from cta.settings import load_models

    return load_models(env={"CTA_ROUTER_CHAIN": "off"})


# ---- K4: q42, q93 and q94 ----


def test_k4_q42_q93_q94_go_to_the_chain_node_and_receive_every_gold_source(monkeypatch):
    rows = {
        q["id"]: q
        for q in map(json.loads, (ROOT / "eval/questions.jsonl").read_text().splitlines())
    }
    for qid in ("q42", "q93", "q94"):
        assert rows[qid]["split"] == "dev"
        out = route(CFG_CODE, Client("prerequisite"), monkeypatch, rows[qid]["question"])
        assert out.route == "chain" and not out.abstained, qid
        received = {s["id"] for s in out.sources}
        gold = {g["id"] for g in rows[qid]["gold_sources"]}
        assert gold <= received, (qid, gold - received)
        assert out.citations == list(range(1, len(out.sources) + 1))


def test_the_router_dict_names_the_asked_codes(monkeypatch):
    out = route(
        CFG_CODE, Client("prerequisite"), monkeypatch, "Prerequisites of CST 1204 and CST 2403?"
    )
    info = out.router["chain"]
    assert info["extraction"] == "codes" and info["detail"] == SHARES and info["code"] == "CST 1204"
    assert info["rendered_by"] == "code"


def test_a_catalog_text_that_is_unsafe_as_markdown_sends_several_courses_to_retrieval(monkeypatch):
    records = dict(RECORDS)
    records["CST 1204"] = {**records["CST 1204"], "prerequisite_text": "PRE: **CST 1100**"}
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    client = Client("prerequisite")
    out = route(CFG_CODE, client, monkeypatch, "Prerequisites of CST 1204 and CST 2403?")
    assert client.calls == ["classify"] and out.route == "chain_fallthrough"
    assert out.router["chain"]["render_fallback"] is True


def test_all_unknown_codes_abstain_for_all_of_them_and_a_known_one_is_answered(monkeypatch):
    out = route(
        CFG_CODE, Client("prerequisite"), monkeypatch, "What do I need for XYZ 1000 and ABC 2000?"
    )
    assert out.abstain_reason == "chain_no_record"
    assert "XYZ 1000, ABC 2000" in out.text
    out = route(
        CFG_CODE, Client("prerequisite"), monkeypatch, "What do I need for XYZ 1000 and CST 1204?"
    )
    assert out.route == "chain" and "## Prerequisites for XYZ 1000" in out.text
