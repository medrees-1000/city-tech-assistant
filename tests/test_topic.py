"""Topic-aware abstain wording (chat polish): the topic call, the two templates, the fallbacks,
the cost and trace, and that the eval path is untouched. Scripted client only: no paid call."""

import json
import re
from pathlib import Path

import pytest

from cta.answer import THRESHOLD_ABSTAIN
from cta.api import topic
from cta.api.topic import NOT_FOUND, OUT_OF_SCOPE, sanitize_topic, sentence
from cta.index.embed import ApiError
from cta.settings import ROOT
from tests.test_api import Client, ask, make_client_app, retrieve_answer

GENERIC = "I could not find this in the City Tech sources I have."


def reply(topic_text, in_scope):
    return json.dumps({"topic": topic_text, "in_scope": in_scope})


def abstain_app(monkeypatch, topic_reply, chunk="page/MATH-NYT/faqs#12", **client_kw):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    stub.sources[0]["id"] = chunk
    client = Client(topic=topic_reply, **client_kw)
    return make_client_app(client, monkeypatch, stub), client


# ---- the sanitiser ----


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("the weather today", "the weather today"),
        ("  A joke.  ", "A joke"),
        ("**bold** [x](http://evil.example.com/a) topic", "bold x topic"),
        ("see https://evil.example.com now", "see now"),
        ("mail me jane@example.com about fees", "mail me about fees"),
        ("`code` and # heading > quote", "code and heading quote"),
        ("a\x00b\x1fc​d e", "a b c d e"),
        ('holds on "my" account', "holds on my account"),
        (
            "one two three four five six seven eight nine ten",
            "one two three four five six seven eight",
        ),
    ],
)
def test_sanitize_topic_cleans(raw, clean):
    assert sanitize_topic(raw) == clean


@pytest.mark.parametrize(
    "raw",
    [
        None,
        7,
        ["x"],
        "",
        "   ",
        "***",
        "12345",
        "student 23456789",
        "call 718-260-5800",
        "123-45-6789",
    ],
)
def test_sanitize_topic_rejects_the_empty_and_the_suspicious(raw):
    assert sanitize_topic(raw) is None


def test_a_long_topic_is_cut_to_60_characters_at_a_word():
    out = sanitize_topic("extraordinarily " * 3 + "long")
    assert out is not None and len(out) <= 60 and not out.endswith(" ")
    assert len(sanitize_topic("a" * 200)) <= 60


def test_the_templates_are_fixed_sentences():
    assert sentence("the weather today", False) == (
        "I can only help with City Tech questions (registration, deadlines, advising, tuition and "
        "aid, and four departments), so I can't help with the weather today."
    )
    assert sentence("laptop loans", True) == (
        "I couldn't find anything about laptop loans in the City Tech pages and documents I use."
    )
    assert OUT_OF_SCOPE.count("{topic}") == NOT_FOUND.count("{topic}") == 1


# ---- through the API ----


def test_out_of_scope_gets_the_out_of_scope_template(monkeypatch):
    c, client = abstain_app(monkeypatch, reply("the weather today", False))
    body = ask(c, "What's the weather today?").json()
    assert body["answer"] == sentence("the weather today", False)
    assert body["answer_type"] == "abstain" and body["abstained"]  # unchanged
    assert body["abstain_reason"] == "below_threshold" and body["contact"] is None
    assert client.calls[-1] == "topic" and body["how_found"]["abstain_wording"] == "topic"
    assert body["how_found"]["topic_in_scope"] is False


def test_in_scope_but_nothing_found_gets_the_not_found_template(monkeypatch):
    c, _ = abstain_app(monkeypatch, reply("laptop loans", True))
    body = ask(c, "What is the policy on laptop loans?").json()
    assert body["answer"] == sentence("laptop loans", True)
    assert body["how_found"]["topic_in_scope"] is True


def test_a_model_written_abstention_also_gets_the_topic_sentence(monkeypatch):
    stub = retrieve_answer("ABSTAIN: The sources do not list the hours.", True,
                           "The sources do not list the hours.", ())  # fmt: skip
    client = Client(topic=reply("student hours", True))
    c = make_client_app(client, monkeypatch, stub)
    body = ask(c, "What are the EET student hours?").json()
    assert body["abstain_reason"] == "model" and body["answer"] == sentence("student hours", True)
    assert body["contact"]["office"] == "EET-NYT"  # the card is not affected


@pytest.mark.parametrize(
    "bad",
    [
        None,  # the scripted client answers with text that is not JSON
        "[1, 2]",
        json.dumps({"topic": "", "in_scope": True}),
        json.dumps({"topic": "weather", "in_scope": "yes"}),
        json.dumps({"in_scope": False}),
        json.dumps({"topic": "student 23456789", "in_scope": True}),
    ],
)
def test_an_unusable_reply_keeps_the_generic_sentence(monkeypatch, bad):
    c, _ = abstain_app(monkeypatch, bad)
    body = ask(c, "something").json()
    assert body["answer"] == GENERIC and body["how_found"]["abstain_wording"] == "generic"
    assert body["how_found"]["stages_ms"]["topic"] is not None  # the call still ran and is logged


def test_a_failed_call_keeps_the_generic_sentence_and_the_request_succeeds(monkeypatch):
    c, client = abstain_app(monkeypatch, None)
    real = client.create

    def create(**kw):
        if kw["messages"][0]["content"].startswith("You label"):
            raise ApiError("provider down sk-secret")
        return real(**kw)

    client.chat.completions.create = create
    r = ask(c, "something")
    assert r.status_code == 200 and r.json()["answer"] == GENERIC
    assert "sk-secret" not in r.text


def test_a_topic_with_a_link_or_markdown_is_sanitised_in_the_sentence(monkeypatch):
    c, _ = abstain_app(
        monkeypatch, reply("**free** [money](http://evil.example.com) https://x.org", False)
    )
    answer = ask(c, "q").json()["answer"]
    assert answer == sentence("free money", False)
    assert "http" not in answer and "*" not in answer and "[" not in answer


def test_a_very_long_topic_is_cut(monkeypatch):
    c, _ = abstain_app(monkeypatch, reply("word " * 40, True))
    answer = ask(c, "q").json()["answer"]
    topic_part = re.search(r"about (.*) in the City Tech", answer).group(1)
    assert len(topic_part) <= 60 and len(topic_part.split()) <= 8


def test_specific_messages_are_not_changed_and_make_no_topic_call(monkeypatch):
    # calendar abstain
    client = Client("calendar", "Summer 2027", [], topic=reply("x", False))
    body = ask(make_client_app(client, monkeypatch), "When does Summer 2027 start?").json()
    assert body["abstain_reason"].startswith("calendar_") and "topic" not in client.calls
    assert not body["answer"].startswith("I can only help")
    # chain no-record
    client = Client("prerequisite", topic=reply("x", False))
    body = ask(make_client_app(client, monkeypatch), "What do I need before CST 4999?").json()
    assert body["abstain_reason"] == "chain_no_record" and "topic" not in client.calls
    assert body["answer"].startswith("No record exists in the catalog data for CST 4999")
    # personal account
    c, client = abstain_app(monkeypatch, reply("x", False))
    body = ask(c, "What is my GPA this semester?").json()
    assert body["abstain_reason"] == "personal_account" and "topic" not in client.calls
    assert body["answer"] == GENERIC  # the page shows its own fixed personal-account sentence


def test_an_answer_makes_no_topic_call(monkeypatch):
    client = Client(topic=reply("x", False))
    c = make_client_app(client, monkeypatch, retrieve_answer())
    body = ask(c, "How do I apply?").json()
    assert "topic" not in client.calls and body["how_found"]["abstain_wording"] is None
    assert (
        body["how_found"]["stages_ms"]["topic"] is None
        and body["how_found"]["cost_usd"]["topic"] == 0.0
    )


def test_the_topic_call_is_in_the_cost_the_tokens_the_trace_and_the_log(monkeypatch):
    c, _ = abstain_app(monkeypatch, reply("the weather today", False))
    body = ask(c, "What's the weather today?").json()
    hf = body["how_found"]
    assert hf["stages_ms"]["topic"] is not None and hf["cost_usd"]["topic"] > 0
    assert hf["tokens"]["topic_prompt"] == 100 and hf["tokens"]["topic_completion"] == 10
    parts = ("classify", "select", "embedding", "rerank", "answer", "topic")
    assert hf["cost_usd"]["total"] == pytest.approx(sum(hf["cost_usd"][p] for p in parts), abs=1e-7)
    row = c.logs[0]
    assert row["trace"]["stages_ms"]["topic"] == hf["stages_ms"]["topic"]
    assert (
        row["cost_usd"] == hf["cost_usd"]["total"]
        and row["prompt_tokens"] == hf["tokens"]["prompt"]
    )
    assert row["answer"] == sentence("the weather today", False)
    assert row["trace"]["abstain_wording"] == "topic"


# ---- the eval path is untouched ----


def test_nothing_in_the_pipeline_or_the_eval_path_imports_the_api():
    for rel in ("graph", "eval", "index", "parse", "crawl", "validate"):
        for path in (ROOT / "src" / "cta" / rel).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import) cta\.api", text, re.M), path
    assert not re.search(r"cta\.api", (ROOT / "src" / "cta" / "answer.py").read_text())
    assert not Path(topic.__file__).samefile(ROOT / "src" / "cta" / "answer.py")
