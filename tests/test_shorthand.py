"""Item A (batch 2 follow-up): a catalog shorthand token (PRE_CST3500_CST3600) in model-written
answer text is replaced with a plain phrase; the chain renderer's verbatim text is untouched.
No network, no database, no model call."""

from datetime import date

import pytest

from cta import answer as answer_module
from cta.graph import chain as ch
from cta.index.search import Search
from cta.settings import load_models
from tests.helpers import Model

PHRASE = ch.SHORTHAND_REPLACEMENT
assert PHRASE == "a prerequisite code the catalog does not spell out"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("PRE_CST3500_CST3600", PHRASE),  # the token alone
        (
            "the catalog lists prerequisites as “PRE_CST3500_CST3600.” [2]",
            f"the catalog lists prerequisites as “{PHRASE}.” [2]",
        ),  # inside a sentence, quotes and citation kept
        ("PRE_CST1201 and PRE_CST1201_CST1204 apply", f"{PHRASE} and {PHRASE} apply"),  # two tokens
        ("`PRE_CST1101_1204_MST2304_MAT13`", f"`{PHRASE}`"),
        ("It needs CST 1204 and MAT 1375. [1]", "It needs CST 1204 and MAT 1375. [1]"),  # none
        ("", ""),
    ],
)
def test_the_token_is_replaced_and_nothing_else_is_touched(text, expected):
    assert ch.explain_shorthand(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "pre_cst3500_cst3600 is lowercase",
        "Pre_CST3500 is mixed case",
        "XPRE_CST3500 has no word boundary",
        "the PRE: CST 3513 AND CST 2301 form is a normal rule",
        "prerequisite is CST 1204",
    ],
)
def test_lowercase_look_alikes_and_normal_rule_text_are_not_touched(text):
    assert ch.explain_shorthand(text) == text


def test_no_expansion_is_ever_written():
    out = ch.explain_shorthand("PRE_CST3500_CST3600")
    assert "3500" not in out and "3600" not in out and "CST" not in out


def chunk(sim=0.8):
    return {"id": "page/a#1", "kind": "section", "source": "https://www.citytech.cuny.edu/x.aspx",
            "heading_path": "H", "text": "text", "doc_type": "faq", "term": None, "terms": [],
            "last_updated": None, "similarity": sim}  # fmt: skip


def ask(monkeypatch, content):
    found = Search([chunk()], False, 1, 10, 0.0, top_vector_similarity=0.8)
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: found)
    cfg = load_models(env={"CTA_RERANK": "off"})
    return answer_module.answer(
        None, "q", date(2026, 10, 17), cfg=cfg, client_factory=lambda: Model(content), log=False
    )


def test_the_answer_step_replaces_the_token_and_keeps_citations_and_abstain_detection(monkeypatch):
    ans = ask(monkeypatch, "The catalog lists it as PRE_CST3500_CST3600. [1]")
    assert ans.text == f"The catalog lists it as {PHRASE}. [1]"
    assert ans.citations == [1] and ans.abstained is False
    ab = ask(monkeypatch, "ABSTAIN: the sources only give PRE_CST3500_CST3600.")
    assert ab.text.startswith("ABSTAIN:") and PHRASE in ab.text and ab.abstained is True


def test_every_final_text_path_goes_through_the_answer_step():
    """The answer text leaves the server only as the JSON of /ask (no streaming anywhere): the
    API takes ans.text from the router, the router from cta.answer.answer (retrieval, advice,
    calendar fall-through) or from the chain node. The two places a model writes the text call
    explain_shorthand; the renderers that quote the catalog do not."""
    import inspect

    from cta.graph import build

    assert "explain_shorthand(" in inspect.getsource(answer_module.answer)
    assert "chains.explain_shorthand(" in inspect.getsource(build.make_nodes)
    from cta.graph import chain_render

    assert "explain_shorthand" not in inspect.getsource(chain_render)


def _records():
    return ch.load_records()


@pytest.mark.skipif(not _records(), reason="no processed course records")
def test_the_model_written_chain_answer_is_scrubbed_but_the_chain_renderer_is_not(monkeypatch):
    from tests.helpers import CFG_CODE, CFG_MODEL, Client, route

    model_client = Client("prerequisite", answer="It is listed as PRE_CST3500_CST3600. [1]")
    out = route(CFG_MODEL, model_client, monkeypatch)
    assert out.text == f"It is listed as {PHRASE}. [1]"
    records = dict(ch.load_records())
    records["CST 3504"] = {**records["CST 3504"], "prerequisite_text": "PRE_CST3500_CST3600"}
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    rendered = route(CFG_CODE, Client("prerequisite"), monkeypatch)
    assert 'Catalog says:** "PRE_CST3500_CST3600"' in rendered.text  # verbatim, on purpose
    assert PHRASE not in rendered.text
