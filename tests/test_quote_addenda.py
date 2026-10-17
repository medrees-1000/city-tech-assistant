"""Item B (batch 2 follow-up): a sentence the cited chunk holds and the answer left out is appended
as a quote, copied from the chunk text at run time. No network, no database, no model call."""

import inspect
from datetime import date
from types import SimpleNamespace

import pytest

from cta import answer as answer_module
from cta.index.search import Search
from cta.settings import load_models

RULE = {"chunk": "page/x#1", "starts_with": "No portion of the fee"}
SENTENCE = "No portion of the fee is refundable, except in cases where the College cancels it."
CHUNK_TEXT = f"Heading\n\nThe date matters.\n\n- {SENTENCE}\n- Another bullet."


def chunk(cid="page/x#1", text=CHUNK_TEXT):
    return {"id": cid, "kind": "section", "source": "https://www.citytech.cuny.edu/x.aspx",
            "heading_path": "H", "text": text, "doc_type": "faq", "term": None, "terms": [],
            "last_updated": None, "similarity": 0.8}  # fmt: skip


def add(text, sources, citations, rules=(RULE,)):
    return answer_module.add_quoted_sentences(text, sources, citations, list(rules))


def test_the_sentence_is_appended_as_a_quote_with_the_cited_number():
    out = add("Refund is 75%. [2]", [chunk("page/other#1"), chunk()], [2])
    assert out == f"Refund is 75%. [2]\n\nThe source also says: “{SENTENCE}” [2]"
    quoted = out.split("“")[1].split("”")[0]
    assert quoted in CHUNK_TEXT  # a substring of the chunk, nothing written in code


def test_already_said_means_no_duplicate():
    text = "No portion of the fee is refundable. [1]"
    assert add(text, [chunk()], [1]) == text
    again = add("Refund is 75%. [1]", [chunk()], [1])
    assert add(again, [chunk()], [1]) == again


def test_a_chunk_that_is_not_cited_adds_nothing():
    text = "Refund is 75%. [1]"
    assert add(text, [chunk("page/other#1"), chunk()], [1]) == text  # chunk 2 is shown, not cited
    assert add(text, [chunk()], []) == text


def test_a_chunk_without_the_sentence_adds_nothing_and_never_guesses():
    text = "Refund is 75%. [1]"
    assert add(text, [chunk(text="Heading\n\nOnly a date.")], [1]) == text


def test_a_citation_number_outside_the_sources_is_ignored():
    text = "x [3]"
    assert add(text, [chunk()], [3]) == text and add(text, [chunk()], [0]) == text


def test_no_rules_means_off():
    text = "Refund is 75%. [1]"
    assert add(text, [chunk()], [1], rules=()) == text


def test_only_one_sentence_is_added_when_two_configured_chunks_are_cited():
    other = {"chunk": "page/y#1", "starts_with": "No portion of the fee"}
    sources = [chunk(), chunk("page/y#1")]
    out = add("Refund. [1][2]", sources, [1, 2], rules=(RULE, other))
    assert out.count("The source also says") == 1


def test_the_sentence_is_never_written_in_code_or_in_a_test_fixture_of_the_function():
    code = inspect.getsource(answer_module.add_quoted_sentences) + inspect.getsource(
        answer_module.quote_sentence
    )
    assert "student activity fee" not in code and "refundable" not in code


def test_the_config_names_the_two_chunks_and_validates_its_entries(tmp_path):
    rules = load_models(env={})["answer"]["quote_addenda"]
    assert {r["chunk"] for r in rules} == {
        "page/bursar/refund-policy#1",
        "page/admissions/tuition-refund#1",
    }
    assert all(r["starts_with"] == "No portion of the student activity fee" for r in rules)
    c = load_models(env={})
    c["answer"]["quote_addenda"] = [{"chunk": "x"}]
    from cta import settings

    assert settings  # the validation runs in load_models; a bad file is rejected there
    import yaml

    from cta.settings import ROOT

    text = (ROOT / "config" / "models.yaml").read_text()
    bad = text.replace(
        'starts_with: "No portion of the student activity fee"}', "starts_with: 5}", 1
    )
    path = tmp_path / "models.yaml"
    path.write_text(bad)
    with pytest.raises(ValueError, match="quote_addenda"):
        load_models(path, env={})
    assert yaml.safe_load(bad)  # the file is still valid YAML; only the entry is wrong


class Model:
    def __init__(self, content):
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))], usage=usage
        )


def ask(monkeypatch, content, sources):
    found = Search(sources, False, 1, 10, 0.0, top_vector_similarity=0.8)
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: found)
    cfg = load_models(env={"CTA_RERANK": "off"})
    cfg["answer"]["quote_addenda"] = [RULE]
    return answer_module.answer(
        None, "q", date(2026, 10, 17), cfg=cfg, client_factory=lambda: Model(content), log=False
    )


def test_the_answer_step_appends_for_an_answer_and_never_for_an_abstention(monkeypatch):
    sources = [chunk("page/other#1"), chunk()]
    ans = ask(monkeypatch, "Refund is 75%. [2]", sources)
    assert ans.text.endswith(f"“{SENTENCE}” [2]") and ans.citations == [2]
    assert ans.abstained is False
    ab = ask(monkeypatch, "ABSTAIN: I could not find this.", sources)
    assert ab.text == "ABSTAIN: I could not find this." and ab.abstained is True
    plain = ask(monkeypatch, "Refund is 75%. [1]", sources)  # cites the other chunk
    assert plain.text == "Refund is 75%. [1]"
