"""The chain answer written by plain code: the deterministic checks of the chain-layout plan over
all 197 course chains, the page fixtures, the loud failure on risky catalog text and the router
switch; the two-course questions (keep rule K1 to K4 of docs/decisions.md, "Step 2"; only dev
result files are read); a course outside the four departments (tester round 1, item D) and its
marking (tester round 1b, item 1a; the "before" texts were saved in tests/fixtures/). No model
call anywhere.
"""

import hashlib
import json
import re

import pytest
import yaml

from cta.api import convert
from cta.graph import advice, build, chain_render
from cta.graph import chain as ch
from cta.graph import chain_render as cr
from cta.settings import ROOT, load_models
from tests.helpers import (
    CFG_CODE,
    CFG_MODEL,
    HEADING,
    MARK,
    PREFIXES,
    RECORDS,
    TODAY,
    Client,
    Script,
    ask,
    make_client_app,
    make_router,
    outside_rewrite,
    route,
)

needs_records = pytest.mark.skipif(not RECORDS, reason="no processed course records")


# ---- from test_chain_render.py ----
#
# The chain answer written by plain code: the deterministic checks of the chain-layout plan over
# all 197 course chains, the page fixtures, the loud failure on risky catalog text, and the router
# switch. No model call anywhere.

RECORDS = ch.load_records()
CODES = sorted(RECORDS)


def chain_of(code):
    return ch.prerequisite_chain.invoke({"course_code": code})


def rendered(code):
    result = chain_of(code)
    return result, chain_render.render(result, RECORDS)


def blocks_of(text):
    """{n: block text} split at the headings."""
    parts = re.split(r"(?m)^(?=### )", text)
    out = {}
    for part in parts[1:]:
        number = int(HEADING.match(part.splitlines()[0]).group(3))
        out[number] = part
    return out


def titles():
    return {c: r["title"].strip() for c, r in RECORDS.items()}


# ---- check 1: every course once, with code, title and [n]; the sources match ----


@needs_records
def test_every_course_appears_once_with_its_code_title_and_source_number():
    for code in CODES:
        result, text = rendered(code)
        found = HEADING.findall(text)
        assert [(c, t, int(n)) for c, t, n in found] == [
            (c["code"], c["title"], i) for i, c in enumerate(result["courses"], 1)
        ], code
        sources = ch.sources_of(result, RECORDS)
        assert [s["id"] for s in sources] == [f"catalog:{c['code']}" for c in result["courses"]]
        assert len({c for c, _, _ in found}) == len(found)  # no course twice


# ---- check 2: verbatim strings unchanged, empty text has its sentence ----


@needs_records
def test_every_verbatim_rule_string_is_unchanged_and_empty_text_has_its_sentence():
    for code in CODES:
        result, text = rendered(code)
        blocks = blocks_of(text)
        for n, course in enumerate(result["courses"], 1):
            block = blocks[n]
            if course["text"]:
                assert f'**Catalog says:** "{course["text"]}"' in block, (code, course["code"])
            else:
                assert chain_render.NO_PREREQUISITE in block and "Catalog says" not in block


# ---- check 3: "Courses named" equals the walk's codes, joined by commas only ----


def untitled(code):
    """The marking of a named code with no record (tester round 1b, 1a)."""
    outside = code.split()[0] not in ch.known_prefixes(RECORDS)
    return chain_render.OUTSIDE if outside else chain_render.NO_RECORD


@needs_records
def test_courses_named_is_the_walks_list_joined_by_commas_and_exclusions_are_the_walks():
    names = titles()
    for code in CODES:
        result, text = rendered(code)
        blocks = blocks_of(text)
        for n, c in enumerate(result["courses"], 1):
            if not c["text"]:
                continue
            if c["unparsed"]:
                want = f"**Courses named:** {chain_render.UNREADABLE}"
            elif c["codes"]:
                items = [f"{x} ({names.get(x) or untitled(x)})" for x in c["codes"]]
                want = "**Courses named:** " + ", ".join(items)
            else:
                want = "**Courses named:** none listed"  # UI polish 3b: was "none"
            assert want in blocks[n].splitlines(), (code, c["code"])
            excluded = [ln for ln in blocks[n].splitlines() if ln.startswith("**Must not have")]
            if c["exclusions"]:
                items = [f"{x} ({names.get(x) or untitled(x)})" for x in c["exclusions"]]
                label = "**Must not have taken (as the catalog text says):** "
                assert excluded == [label + ", ".join(items)]
            else:
                assert excluded == []


@needs_records
def test_no_word_or_or_and_is_added_between_codes():
    for code in CODES:
        _, text = rendered(code)
        for ln in text.splitlines():
            if ln.startswith("**Courses named:** ") and chain_render.UNREADABLE not in ln:
                body = ln.removeprefix("**Courses named:** ")
                if body == "none listed":  # UI polish 3b: was "none"
                    continue
                pieces = re.split(r"(?<=\)), (?=[A-Z]{2,5} ?\d)", body)
                assert all(
                    re.fullmatch(r"[A-Z]{2,5} \d{3,4}[A-Z]{0,2} \(.+\)", p) for p in pieces
                ), ln


# ---- check 4: the [n] markers are exactly 1..N, each in its own heading only ----


@needs_records
def test_markers_are_one_to_n_each_only_in_its_own_heading():
    for code in CODES:
        result, text = rendered(code)
        markers = re.findall(r"\[(\d+)\]", text)
        assert sorted(map(int, markers)) == list(range(1, result["course_count"] + 1)), code
        for line in text.splitlines():
            if re.search(r"\[\d+\]", line):
                assert line.startswith("### "), line


# ---- check 5: no "Level", deterministic ----


@needs_records
def test_no_level_wording_and_the_same_text_every_time():
    for code in CODES:
        result, text = rendered(code)
        assert "Level" not in text and "level" not in text.replace("(depth limit)", "")
        assert chain_render.render(result, RECORDS) == text


# ---- check 6: truncation and no-record sentences iff the walk reports them ----


@needs_records
def test_truncation_and_no_record_sentences_appear_if_and_only_if_the_walk_reports_them():
    cut = no_rec = 0
    for code in CODES:
        result, text = rendered(code)
        # UI polish 3a: the closing sentence stays unless every code in it is already marked
        # "(no catalog record)" in a block above; then each code is still stated, once
        names = {c: r["title"].strip() for c, r in RECORDS.items()}
        marked = chain_render.marked_codes(result["courses"], names)
        closing = "No catalog record in the four departments for:" in text
        assert closing == (bool(result["no_record"]) and not set(result["no_record"]) <= marked)
        if result["no_record"]:
            no_rec += 1
            assert all(c in text for c in result["no_record"])
            if closing:
                assert f"for: {', '.join(result['no_record'])}." in text
        stops = re.findall(r"The list stops at (\S+ \S+), which names (.+?); prerequisites", text)
        assert [(a, b) for a, b in stops] == [
            (u["code"], ", ".join(u["names"])) for u in result["unexpanded"]
        ]
        dropped = re.findall(r"(\S+ \S+), named by (\S+ \S+), is not shown", text)
        assert dropped == [(d["code"], d["named_by"]) for d in result["dropped"]]
        cut += bool(result["truncated"])
    assert cut > 0 and no_rec > 0  # the data does contain both situations


# ---- check 7: UNPARSED shows its verbatim string and the fixed sentence ----


@needs_records
def test_unparsed_text_shows_the_fixed_sentence_and_the_verbatim_string():
    seen = 0
    for code in CODES:
        result, text = rendered(code)
        for n, c in enumerate(result["courses"], 1):
            if c["unparsed"]:
                seen += 1
                block = blocks_of(text)[n]
                assert "**Courses named:** cannot be read from this text" in block
                assert f'**Catalog says:** "{c["text"]}"' in block
    assert seen > 0


# ---- the page side: the fixtures, and risky text fails loudly ----


@needs_records
def test_the_fixtures_the_page_tests_read_are_what_the_renderer_writes():
    for code, name in (("CST 3504", "chain_cst3504.md"), ("MAT 2440", "chain_mat2440.md")):
        path = ROOT / "web" / "lib" / "testdata" / name
        assert path.read_text(encoding="utf-8") == rendered(code)[1] + "\n"
    several = ch.combined_chain(["CST 1204", "CST 2403"])
    path = ROOT / "web" / "lib" / "testdata" / "chain_cst1204_cst2403.md"
    assert path.read_text(encoding="utf-8") == chain_render.render(several, RECORDS) + "\n"


@needs_records
@pytest.mark.parametrize(
    "text",
    [
        "PRE: **MAT 1275**",
        "see [1] first",
        "line\n# heading",
        "a\n- item",
        "say <b>x</b>",
        'the "quoted" word',
    ],
)
def test_catalog_text_with_markup_characters_fails_loudly(text):
    result = chain_of("CST 3504")
    result["courses"][0]["text"] = text
    with pytest.raises(chain_render.ChainRenderError, match="CST 3504"):
        chain_render.render(result, RECORDS)


@needs_records
def test_no_catalog_text_today_holds_a_markup_character():
    for code, record in RECORDS.items():
        assert not chain_render.RISKY.search((record["prerequisite_text"] or "").strip()), code


# ---- the router switch ----


@needs_records
def test_the_switch_defaults_to_code_since_the_keep_rule_passed_and_is_validated():
    assert load_models(env={})["router"]["chain_render"] == "code"
    assert (
        load_models(env={"CTA_ROUTER_CHAIN_RENDER": "model"})["router"]["chain_render"] == "model"
    )
    with pytest.raises(ValueError, match="chain_render"):
        load_models(env={"CTA_ROUTER_CHAIN_RENDER": "both"})


@needs_records
def test_with_code_only_the_classifier_is_called_and_route_sources_and_citations_match(monkeypatch):
    model_client = Client("prerequisite", answer="x [1][2][3][4]")
    old = route(CFG_MODEL, model_client, monkeypatch)
    assert model_client.calls == ["classify", "answer"]
    code_client = Client("prerequisite")
    new = route(CFG_CODE, code_client, monkeypatch)
    assert code_client.calls == ["classify"]  # no model call after the classifier
    assert new.route == old.route == "chain" and not new.abstained
    assert [s["id"] for s in new.sources] == [s["id"] for s in old.sources]
    assert new.citations == [1, 2, 3, 4] and new.invalid_citations == []
    assert new.router["chain"]["rendered_by"] == "code"
    assert new.text.startswith("Here are the prerequisites for CST 3504, from the catalog:")
    assert (
        new.chat_cost == old.chat_cost - old.router["chain"].get("x", 0)
        or new.chat_cost < old.chat_cost
    )


@needs_records
def test_a_catalog_text_that_is_unsafe_as_markdown_falls_back_to_the_model_path(monkeypatch):
    records = dict(RECORDS)
    records["CST 3504"] = {**records["CST 3504"], "prerequisite_text": "PRE: **CST 1204**"}
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    client = Client("prerequisite", answer="model wrote this [1]")
    out = route(CFG_CODE, client, monkeypatch)
    assert client.calls == ["classify", "answer"] and out.text == "model wrote this [1]"
    assert out.router["chain"]["render_fallback"] is True


@needs_records
def test_the_chain_with_no_record_and_the_fall_through_do_not_use_the_renderer(monkeypatch):
    client = Client("prerequisite")
    out = route(CFG_CODE, client, monkeypatch, "What do I need before CST 4999?")
    assert out.abstain_reason == "chain_no_record" and client.calls == ["classify"]
    out = route(CFG_CODE, Client("prerequisite"), monkeypatch, "Tell me about courses.")
    assert out.route == "chain_fallthrough" and out.text == "old path [1]"


@needs_records
def test_the_cost_of_a_code_rendered_chain_is_only_the_classifier(monkeypatch):
    out = route(CFG_CODE, Client("prerequisite"), monkeypatch)
    assert out.chat_cost == out.router["classify"]["cost"] and out.prompt_tokens == 100


# ---- the word "chain" is internal: no student sees it (C1 of the round of 2026-10-13) ----

PAGE_STRINGS = [
    ROOT / "web" / "lib" / "howfound.ts",
    ROOT / "web" / "app" / "chat" / "page.tsx",
    ROOT / "web" / "lib" / "testdata" / "chain_cst3504.md",
    ROOT / "web" / "lib" / "testdata" / "chain_mat2440.md",
    ROOT / "web" / "lib" / "testdata" / "chain_cst1204_cst2403.md",
]


@needs_records
def test_no_course_answer_shows_the_word_chain_or_level():
    for code in CODES:
        text = rendered(code)[1]
        own_words = re.sub(r'"[^"]*"', "", text)  # the catalog's own text is quoted verbatim
        assert "chain" not in text.lower() and "level" not in own_words.lower(), code


@needs_records
def test_page_strings_do_not_show_the_word_chain():
    import re as _re

    for path in PAGE_STRINGS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = _re.sub(r"[A-Za-z_.]*\bchain[A-Za-z_]*|chain_|\"chain\"|'chain'", "", line)
            assert "chain" not in code.lower(), f"{path.name}:{number}: {line}"


# ---- from test_chain_many.py ----
#
# Step 2, two-course questions: the keep rule K1 to K4 of docs/decisions.md ("Step 2 (two-course
# questions): the keep rule"). Deterministic; no model call. Only dev result files are read.

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


@needs_records
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


@needs_records
def test_k1_the_asked_courses_come_in_the_order_asked_each_with_its_heading():
    for codes in COMBOS:
        result, text = combined(codes)
        assert SECTION.findall(text) == distinct(codes), codes
        assert result["asked"] == distinct(codes)
        assert text.startswith(
            "Here are the prerequisites for " + cr.codes_phrase(distinct(codes)) + ", from"
        )


@needs_records
def test_k1_a_shared_course_is_shown_once_in_the_first_section_and_the_later_one_says_so():
    result, text = combined(SHARES)
    where = positions(text)
    assert where["CST 1101"] == 0 and where["CST 1204"] == 0 and where["CST 2403"] == 1
    sections = {s["root"]: s for s in result["sections"]}
    assert sections["CST 2403"]["shared"] == ["CST 1101"]
    assert text.count("CST 1101 is already shown above.") == 1
    later = text.split("## Prerequisites for CST 2403")[1]
    assert "CST 1101 is already shown above." in later


@needs_records
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


@needs_records
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


@needs_records
def test_k1_the_asked_courses_are_never_the_ones_cut():
    result, text = combined(CAPPED)
    assert all(s["found"] and (s["courses"] or s["already_shown"]) for s in result["sections"])
    assert [c for c in CAPPED if f"### {c} — " not in text] == []  # all three are shown


@needs_records
def test_k1_verbatim_strings_no_chain_no_level_and_the_same_text_twice():
    for codes in COMBOS:
        result, text = combined(codes)
        assert cr.render(ch.combined_chain(codes), RECORDS) == text  # deterministic
        for c in result["courses"]:
            if c["text"]:
                assert f'**Catalog says:** "{c["text"]}"' in text, (codes, c["code"])
        own = re.sub(r'"[^"]*"', "", text)
        assert "chain" not in text.lower() and "level" not in own.lower(), codes


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
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


@needs_records
def test_the_router_dict_names_the_asked_codes(monkeypatch):
    out = route(
        CFG_CODE, Client("prerequisite"), monkeypatch, "Prerequisites of CST 1204 and CST 2403?"
    )
    info = out.router["chain"]
    assert info["extraction"] == "codes" and info["detail"] == SHARES and info["code"] == "CST 1204"
    assert info["rendered_by"] == "code"


@needs_records
def test_a_catalog_text_that_is_unsafe_as_markdown_sends_several_courses_to_retrieval(monkeypatch):
    records = dict(RECORDS)
    records["CST 1204"] = {**records["CST 1204"], "prerequisite_text": "PRE: **CST 1100**"}
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    client = Client("prerequisite")
    out = route(CFG_CODE, client, monkeypatch, "Prerequisites of CST 1204 and CST 2403?")
    assert client.calls == ["classify"] and out.route == "chain_fallthrough"
    assert out.router["chain"]["render_fallback"] is True


@needs_records
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


# ---- from test_chain_outside.py ----
#
# Tester round 1, item D: a course outside the four departments. No network, no model.

CFG = load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_CHAIN": "on", "CTA_ROUTER_CONTACTS": "on"})
URL = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["catalog_api"]["origin"]
NEW = (
    "ABSTAIN: I only have catalog records for Computer Systems Technology, Mathematics, "
    "Electrical and Telecommunications Engineering Technology, and Dental Hygiene, so I can't "
    "tell you about {code}. The City Tech catalog is at {url}."
)


@pytest.mark.needs_data
def test_the_prefix_set_is_read_from_the_records_and_has_no_eng():
    prefixes = ch.known_prefixes(RECORDS)
    assert prefixes == {code.split()[0] for code in RECORDS}
    assert {"CST", "MAT"} <= prefixes and "ENG" not in prefixes and "BIO" not in prefixes
    assert any(p.startswith(("EET", "ELET", "DEN")) for p in prefixes) or len(prefixes) >= 4
    # no hand-typed list: the function holds no prefix literal
    import inspect

    body = inspect.getsource(ch.known_prefixes).split('"""')[2]  # after the docstring
    assert "CST" not in body and "MAT" not in body


def test_the_catalog_url_is_the_one_in_the_config():
    assert ch.catalog_url() == URL == "https://citytech.catalog.cuny.edu"


def test_eng_1101_gets_the_new_text_and_no_contact(monkeypatch):
    router, _ = make_router(Script("prerequisite"), monkeypatch, build.load_events(), CFG)
    ans = router.answer("prereq for ENG 1101", TODAY, log=False)
    assert ans.text == NEW.format(code="ENG 1101", url=URL)
    assert ans.route == "abstain" and ans.abstain_reason == "chain_outside_departments"
    assert ans.router.get("contact_office") is None and "Contact" not in ans.text


@pytest.mark.needs_data
def test_cst_9999_keeps_todays_no_record_text(monkeypatch):
    router, _ = make_router(Script("prerequisite"), monkeypatch, build.load_events(), CFG)
    ans = router.answer("prereq for CST 9999", TODAY, log=False)
    assert ans.text.startswith(
        "ABSTAIN: No record exists in the catalog data for CST 9999 in the four"
    )
    assert ans.abstain_reason == "chain_no_record"
    assert ans.router["contact_office"] == "CST-NYT"  # the department's card, as before


@pytest.mark.needs_data
def test_a_code_with_a_known_prefix_but_no_record_is_not_outside():
    assert not ch.outside_departments("MAT 9999", RECORDS)
    assert ch.outside_departments("ENG 1101", RECORDS) and ch.outside_departments(
        "BIO 1101", RECORDS
    )


def test_through_the_api_it_is_a_chain_abstention_with_its_own_code_and_no_card(monkeypatch):
    c = make_client_app(Client("prerequisite"), monkeypatch)
    body = ask(c, "prereq for ENG 1101").json()
    assert body["abstained"] and body["route"] == "chain" and body["contact"] is None
    assert body["abstain_reason"] == "chain_outside_departments"
    assert body["answer"] == NEW.format(code="ENG 1101", url=URL).removeprefix("ABSTAIN: ")


@pytest.mark.needs_data
def test_named_courses_and_the_chain_renderer_are_untouched():
    # a course named inside prerequisite text keeps "(no catalog record)", and the asked-course
    # sentence of a multi-course answer is the same one as before
    titles = {c: r["title"].strip() for c, r in RECORDS.items()}
    # MAT is in the data, so MAT 1476 keeps "(no catalog record)"
    assert chain_render.named("MAT 1476", titles) == "MAT 1476 (no catalog record)"
    assert "There is no catalog record for {code} " in chain_render.NO_RECORD_ASKED
    assert convert.abstain_code("chain_outside_departments") == "chain_outside_departments"
    assert (
        convert.public_route(
            build.RoutedAnswer("t", True, "chain_outside_departments", [], route="abstain")
        )
        == "chain"
    )


# ---- from test_outside_marking.py ----
#
# Tester round 1b, item 1a: a named course outside the four departments is marked as such.
# No model call. The "before" texts were saved before the change in tests/fixtures/.

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
