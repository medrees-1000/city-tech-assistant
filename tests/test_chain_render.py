"""The chain answer written by plain code: the deterministic checks of the chain-layout plan over
all 197 course chains, the page fixtures, the loud failure on risky catalog text, and the router
switch. No model call anywhere."""

import re

import pytest

from cta.answer import Answer
from cta.graph import build, chain_render
from cta.graph import chain as ch
from cta.graph.build import Router
from cta.index.search import Search
from cta.settings import ROOT, load_models
from tests.test_api import Client

RECORDS = ch.load_records()
pytestmark = pytest.mark.skipif(not RECORDS, reason="no processed course records")
CODES = sorted(RECORDS)
HEADING = re.compile(r"^### (.+?) — (.+?) \[(\d+)\]$", re.M)


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
                items = [f"{x} ({names.get(x) or chain_render.NO_RECORD})" for x in c["codes"]]
                want = "**Courses named:** " + ", ".join(items)
            else:
                want = "**Courses named:** none"
            assert want in blocks[n].splitlines(), (code, c["code"])
            excluded = [ln for ln in blocks[n].splitlines() if ln.startswith("**Must not have")]
            if c["exclusions"]:
                items = [f"{x} ({names.get(x) or chain_render.NO_RECORD})" for x in c["exclusions"]]
                label = "**Must not have taken (as the catalog text says):** "
                assert excluded == [label + ", ".join(items)]
            else:
                assert excluded == []


def test_no_word_or_or_and_is_added_between_codes():
    for code in CODES:
        _, text = rendered(code)
        for ln in text.splitlines():
            if ln.startswith("**Courses named:** ") and chain_render.UNREADABLE not in ln:
                body = ln.removeprefix("**Courses named:** ")
                if body == "none":
                    continue
                pieces = re.split(r"(?<=\)), (?=[A-Z]{2,5} ?\d)", body)
                assert all(
                    re.fullmatch(r"[A-Z]{2,5} \d{3,4}[A-Z]{0,2} \(.+\)", p) for p in pieces
                ), ln


# ---- check 4: the [n] markers are exactly 1..N, each in its own heading only ----


def test_markers_are_one_to_n_each_only_in_its_own_heading():
    for code in CODES:
        result, text = rendered(code)
        markers = re.findall(r"\[(\d+)\]", text)
        assert sorted(map(int, markers)) == list(range(1, result["course_count"] + 1)), code
        for line in text.splitlines():
            if re.search(r"\[\d+\]", line):
                assert line.startswith("### "), line


# ---- check 5: no "Level", deterministic ----


def test_no_level_wording_and_the_same_text_every_time():
    for code in CODES:
        result, text = rendered(code)
        assert "Level" not in text and "level" not in text.replace("(depth limit)", "")
        assert chain_render.render(result, RECORDS) == text


# ---- check 6: truncation and no-record sentences iff the walk reports them ----


def test_truncation_and_no_record_sentences_appear_if_and_only_if_the_walk_reports_them():
    cut = no_rec = 0
    for code in CODES:
        result, text = rendered(code)
        assert ("No catalog record in the four departments for:" in text) == bool(
            result["no_record"]
        )
        if result["no_record"]:
            no_rec += 1
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


def test_the_fixtures_the_page_tests_read_are_what_the_renderer_writes():
    for code, name in (("CST 3504", "chain_cst3504.md"), ("MAT 2440", "chain_mat2440.md")):
        path = ROOT / "web" / "lib" / "testdata" / name
        assert path.read_text(encoding="utf-8") == rendered(code)[1] + "\n"
    several = ch.combined_chain(["CST 1204", "CST 2403"])
    path = ROOT / "web" / "lib" / "testdata" / "chain_cst1204_cst2403.md"
    assert path.read_text(encoding="utf-8") == chain_render.render(several, RECORDS) + "\n"


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


def test_no_catalog_text_today_holds_a_markup_character():
    for code, record in RECORDS.items():
        assert not chain_render.RISKY.search((record["prerequisite_text"] or "").strip()), code


# ---- the router switch ----

CFG_CODE = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "on",
        "CTA_ROUTER_CONTACTS": "off",
        "CTA_ROUTER_CHAIN_RENDER": "code",
    }  # fmt: skip
)
CFG_MODEL = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "on",
        "CTA_ROUTER_CONTACTS": "off",
        "CTA_ROUTER_CHAIN_RENDER": "model",
    }  # fmt: skip
)


def route(cfg, client, monkeypatch, question="What are the prerequisites for CST 3504?"):
    stub = Answer("old path [1]", False, None, [], [1], [], Search([], False, 0, 0, 0.0))
    monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    router = Router(None, cfg, lambda: client, events=[], contact="c")
    return router.answer(question, build.date(2026, 10, 13), log=False)


def test_the_switch_defaults_to_code_since_the_keep_rule_passed_and_is_validated():
    assert load_models(env={})["router"]["chain_render"] == "code"
    assert (
        load_models(env={"CTA_ROUTER_CHAIN_RENDER": "model"})["router"]["chain_render"] == "model"
    )
    with pytest.raises(ValueError, match="chain_render"):
        load_models(env={"CTA_ROUTER_CHAIN_RENDER": "both"})


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


def test_a_catalog_text_that_is_unsafe_as_markdown_falls_back_to_the_model_path(monkeypatch):
    records = dict(RECORDS)
    records["CST 3504"] = {**records["CST 3504"], "prerequisite_text": "PRE: **CST 1204**"}
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    client = Client("prerequisite", answer="model wrote this [1]")
    out = route(CFG_CODE, client, monkeypatch)
    assert client.calls == ["classify", "answer"] and out.text == "model wrote this [1]"
    assert out.router["chain"]["render_fallback"] is True


def test_the_chain_with_no_record_and_the_fall_through_do_not_use_the_renderer(monkeypatch):
    client = Client("prerequisite")
    out = route(CFG_CODE, client, monkeypatch, "What do I need before CST 4999?")
    assert out.abstain_reason == "chain_no_record" and client.calls == ["classify"]
    out = route(CFG_CODE, Client("prerequisite"), monkeypatch, "Tell me about courses.")
    assert out.route == "chain_fallthrough" and out.text == "old path [1]"


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


def test_no_course_answer_shows_the_word_chain_or_level():
    for code in CODES:
        text = rendered(code)[1]
        own_words = re.sub(r'"[^"]*"', "", text)  # the catalog's own text is quoted verbatim
        assert "chain" not in text.lower() and "level" not in own_words.lower(), code


def test_page_strings_do_not_show_the_word_chain():
    import re as _re

    for path in PAGE_STRINGS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = _re.sub(r"[A-Za-z_.]*\bchain[A-Za-z_]*|chain_|\"chain\"|'chain'", "", line)
            assert "chain" not in code.lower(), f"{path.name}:{number}: {line}"
