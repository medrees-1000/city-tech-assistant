"""The judge-only second pass (cta.eval.rejudge_stored): rebuilt sources, skips, no other calls."""

import json
from types import SimpleNamespace

import pytest

from cta.eval import rejudge_stored as rs
from cta.eval.run_answers import judge_messages

Q = {"id": "q1", "question": "What is X?", "gold_answer": "X is Y.", "gold_sources": [{"id": "s"}]}
CHUNK = {
    "id": "page/a#1", "kind": "section", "source": "https://www.citytech.cuny.edu/a.aspx",
    "heading_path": "A", "terms": [], "last_updated": None, "text": "X is Y.",
}  # fmt: skip
VERDICT = json.dumps({
    "correctness": "correct", "correctness_reason": "ok", "faithfulness": "yes",
    "faithfulness_reason": "ok",
})  # fmt: skip


def row(i="q1", route="other"):
    pass1 = {"correctness": "partial", "faithfulness": "yes"}
    return {"id": i, "q": Q, "route": route, "answer": "X is Y. [1]", "sources_shown": ["page/a#1"],
            "router": {}, "pass1": pass1}  # fmt: skip


def test_the_judge_gets_the_stored_answer_and_the_rebuilt_sources(monkeypatch):
    seen = []
    monkeypatch.setattr(rs, "rebuild", lambda conn, r, events: [CHUNK])

    def call(messages):
        seen.append(messages)
        return VERDICT, 0.001

    results, skipped = rs.judge_rows(None, [row()], [], call)
    want = judge_messages("normal", Q, SimpleNamespace(text="X is Y. [1]", sources=[CHUNK]))
    assert seen == [want] and skipped == []
    assert results[0]["pass1"]["correctness"] == "partial"
    assert results[0]["pass2"] == {"correctness": "correct", "faithfulness": "yes"}


def test_a_question_that_cannot_be_rebuilt_is_skipped_and_never_judged(monkeypatch):
    def refuse(conn, r, events):
        raise rs.CannotRebuild("differs")

    monkeypatch.setattr(rs, "rebuild", refuse)

    def call(messages):
        raise AssertionError("the judge must not be called for a skipped question")

    results, skipped = rs.judge_rows(None, [row()], [], call)
    assert results == [] and skipped == [{"id": "q1", "reason": "differs"}]


def test_the_estimate_makes_no_judge_call(monkeypatch):
    monkeypatch.setattr(rs, "rebuild", lambda conn, r, events: [CHUNK])
    total, skipped = rs.judge_rows(None, [row()], [], None, estimate_only=lambda m, kind: 0.01)
    assert total == pytest.approx(0.01) and skipped == []


def test_same_text_compares_after_the_log_redaction():
    assert rs.same_text("Mail a@b.com now", "Mail [EMAIL] now ")
    assert not rs.same_text("one", "two")


def test_the_advice_route_needs_no_sources():
    assert rs.rebuild(None, row(route="advice"), []) == []


def test_an_unknown_route_is_refused():
    with pytest.raises(rs.CannotRebuild):
        rs.rebuild(None, row(route="clarify"), [])


def test_the_module_imports_no_search_embedding_or_answer_call():
    names = vars(rs)
    assert "search" not in names and "answer" not in names and "embed" not in names
