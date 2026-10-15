"""Step 5 NO ADVICE: the detector, the three-part answer, the checks of the keep rule, the graph
and the API. No network, no database, no paid call. Only the dev questions are read."""

import re

import pytest

from cta.answer import Answer
from cta.eval.questions import load_questions
from cta.graph import advice, build, render, terms
from cta.index.search import Search
from tests.test_api import Client, ask, make_client_app
from tests.test_clarify import CFG, stored_intents
from tests.test_router import TODAY, Script, make_router

DEV = [q for q in load_questions() if q["split"] == "dev"]
ADVICE_IDS = {"q30", "q47", "q91", "q92"}


@pytest.fixture(scope="module")
def events():
    return build.load_events()


# ---- the detector ----


def test_the_four_advice_questions_are_dev_and_the_dev_split_is_63():
    assert len(DEV) == 63 and ADVICE_IDS <= {q["id"] for q in DEV}


def test_fires_on_q30_q47_q91_q92_and_on_no_other_dev_question():
    fired = {q["id"] for q in DEV if advice.needs_advice_rules(q["question"])}
    assert fired == ADVICE_IDS


def test_dev_has_no_question_about_a_payment_plan_or_signing_up():
    assert not [
        q["id"] for q in DEV if re.search(r"payment plan|sign(ing)? up", q["question"], re.I)
    ]


@pytest.mark.parametrize("qid", ["q16", "q18", "q31", "q34", "q65", "q71"])
def test_dev_questions_with_an_action_word_and_no_cue_do_not_fire(qid):
    text = next(q["question"] for q in DEV if q["id"] == qid)
    assert advice.ACTIONS and any(a.words.search(text) for a in advice.ACTIONS)
    assert not advice.needs_advice_rules(text)


@pytest.mark.parametrize(
    "question",
    ["How do I sign up for a payment plan?", "When is the last day to drop?",
     "How do I withdraw from a course?", "What is the payment plan?",
     "How do I audit a class?", "Is the library open?", "Should I eat lunch?"],
)  # fmt: skip
def test_controls_do_not_fire(question):
    assert not advice.needs_advice_rules(question)


@pytest.mark.parametrize(
    ("question", "names"),
    [
        ("Should I withdraw from my biology class?", ["drop_withdraw"]),
        ("Should I take an Incomplete or withdraw from my class?", ["incomplete", "drop_withdraw"]),
        ("Is it a good idea to take an Incomplete?", ["incomplete"]),
        ("Should I sign up for the Nelnet payment plan?", ["payment_plan", "sign_up"]),
        ("Would you recommend auditing a course?", ["audit"]),
        ("Is it better to change my major now?", ["change_major"]),
        ("Should I transfer to another college?", ["transfer"]),
        ("Should I retake a class?", ["take_class"]),
        ("should i take the course again", ["take_class"]),
    ],
)
def test_cue_and_action_fire_and_name_the_actions(question, names):
    assert [a.name for a in advice.matched_actions(question)] == names


def test_no_cue_never_fires_and_no_action_never_fires():
    for a in advice.ACTIONS:
        assert not advice.needs_advice_rules(f"Tell me about {a.name.replace('_', ' ')} drop")
    for cue in advice.CUES:
        assert not advice.needs_advice_rules(f"{cue} go to the library")


def test_a_prerequisite_classification_never_fires():
    q = "Should I take a course before CST 2403?"
    assert advice.needs_advice_rules(q) and not advice.needs_advice_rules(q, "prerequisite")


def test_routing_is_unchanged_for_every_stored_dev_question_that_does_not_fire():
    after = build.make_nodes(build.Deps(None, CFG, None, [], "c"))[1]
    old = {"prerequisite": "chain", "calendar": "calendar"}
    for text, intent in stored_intents():
        route = after({"question": text, "intent": intent})
        if advice.needs_advice_rules(text, intent):
            assert route == "advice"
        elif route != "clarify":
            assert route == old.get(intent, "retrieve")


# ---- the answer ----


def policy_answer(text="You may drop until the deadline [1]. A WD is recorded [2].", **kw):
    sources = [
        {"id": "pdf/drop#1", "kind": "section", "source": "x", "text": "Drop by September 3."},
        {"id": "pdf/drop#2", "kind": "section", "source": "x", "text": "A WD grade is given."},
    ]
    return Answer(text, False, None, sources, [1, 2], [], Search([], False, 0, 0, 0.0), **kw)


def rows(events, pattern="drop|withdraw|grade of W"):
    pool = terms.term_pool(events, "Fall 2026")
    return advice.calendar_rows(pool, [advice.ACTIONS[1]])


def test_the_fixed_sentence_is_in_the_answer_once_and_first(events):
    rendered = render.render_rows(rows(events), "r@x.edu", "Fall 2026")
    ans = advice.compose(policy_answer(), rendered)
    assert ans.text.count(advice.SENTENCE) == 1 and ans.text.startswith(advice.SENTENCE)
    assert not ans.abstained and ans.row_ids == rendered.row_ids


def test_no_advice_phrase_in_the_code_written_parts(events):
    rendered = render.render_rows(rows(events), "r@x.edu", "Fall 2026")
    assert advice.advice_phrases(advice.SENTENCE) == []  # the refusal itself is not advice
    assert advice.advice_phrases(f"{advice.SENTENCE} You should drop.") == ["you should"]
    assert advice.advice_phrases(rendered.text) == []
    assert advice.advice_phrases("I recommend it. You should drop. It's best.") == [
        "i recommend", "you should", "it's best"
    ]  # fmt: skip


def test_citations_are_policy_sources_first_then_calendar_rows(events):
    rendered = render.render_rows(rows(events), "r@x.edu", "Fall 2026")
    ans = advice.compose(policy_answer(), rendered)
    n = len(ans.sources)
    assert n == 2 + len(rendered.sources) and ans.citations == list(range(1, n + 1))
    assert [s["id"] for s in ans.sources[:2]] == ["pdf/drop#1", "pdf/drop#2"]
    assert ans.sources[2]["id"] == rendered.row_ids[0] or ans.sources[2]["kind"] == "calendar"
    used = {int(x) for x in re.findall(r"\[(\d+)\]", ans.text)}
    assert used == set(range(1, n + 1))  # every number in the text is a source, none is missing
    assert f"[{3}]" in ans.sources[2]["text"]  # the row's own text carries its new number


def test_every_date_is_traceable_to_a_cited_source(events):
    rendered = render.render_rows(rows(events), "r@x.edu", "Fall 2026")
    ans = advice.compose(policy_answer("Drop by September 3 [1]."), rendered)
    assert advice.untraceable_dates(ans) == set()
    bad = advice.compose(policy_answer("Drop by October 31 [1]."), rendered)
    assert advice.untraceable_dates(bad) == {(10, 31)}


def test_no_calendar_rows_gives_the_sentence_and_the_policy_only():
    ans = advice.compose(policy_answer(), None)
    assert (
        ans.text
        == f"{advice.SENTENCE}\n\nYou may drop until the deadline [1]. A WD is recorded [2]."
    )
    assert ans.citations == [1, 2] and ans.row_ids == []


def test_the_fixed_query_is_code_text_and_never_the_students(events):
    actions = advice.matched_actions("Should I drop my biology class zzqx?")
    query = advice.rule_query(actions)
    assert query == actions[0].query and "zzqx" not in query and "biology" not in query


def test_calendar_rows_by_action_come_from_the_term_only(events):
    got = rows(events)
    assert got and all(r["term"] == "Fall 2026" for r in got)
    assert any(r["id"] == "fall-2026-040" for r in got)
    assert advice.calendar_rows(terms.term_pool(events, "Fall 2026"), [advice.ACTIONS[2]]) == []


# ---- the graph ----


class AdviceScript(Script):
    pass


def test_a_fired_question_runs_the_classifier_and_one_retrieval_answer(monkeypatch, events):
    script = Script("other")
    router, seen = make_router(script, monkeypatch, events, CFG)
    ans = router.answer("Should I withdraw from my biology class?", TODAY, log=False)
    assert script.calls == ["classify"] and len(seen) == 1  # the one retrieval call, no selector
    args, _ = seen[0]
    assert args[1] == advice.ACTIONS[1].query  # the fixed question, not the student's
    assert ans.route == "advice" and ans.text.startswith(advice.SENTENCE)
    assert ans.text.count(advice.SENTENCE) == 1 and not ans.abstained
    assert ans.router["advice"]["actions"] == ["drop_withdraw"]
    assert "fall-2026-040" in ans.row_ids and ans.router["advice"]["term"] == "Fall 2026"
    assert ans.router.get("contact_office") is None  # no contact for an answered advice question


def test_an_unsupported_term_gets_the_policy_part_only(monkeypatch, events):
    router, seen = make_router(Script("other", "Summer 2027"), monkeypatch, events, CFG)
    ans = router.answer("Should I drop my class in Summer 2027?", TODAY, log=False)
    assert ans.route == "advice" and ans.row_ids == [] and not ans.abstained


def test_when_retrieval_abstains_the_answer_is_the_usual_abstention(monkeypatch, events):
    router, seen = make_router(Script("other"), monkeypatch, events, CFG)
    stub = Answer(
        "ABSTAIN: nothing found.", True, "model", [], [], [], Search([], False, 0, 0, 0.0)
    )
    monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    ans = router.answer("Should I withdraw from my biology class?", TODAY, log=False)
    assert ans.abstained and advice.SENTENCE not in ans.text and ans.route == "advice"


def test_a_clear_non_advice_question_keeps_its_route(monkeypatch, events):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])
    router, seen = make_router(script, monkeypatch, events, CFG)
    ans = router.answer("What is the last day to withdraw in Fall 2026?", TODAY, log=False)
    assert ans.route == "calendar" and script.calls == ["classify", "select"]


# ---- the API ----


def test_the_api_answer_is_a_normal_answer_with_no_card(monkeypatch):
    stub = policy_answer()
    c = make_client_app(Client("other"), monkeypatch, stub)
    body = ask(c, "Should I withdraw from my biology class?").json()
    assert body["answer_type"] == "answer" and body["route"] == "retrieve"
    assert body["contact"] is None and body["abstained"] is False
    assert body["answer"].startswith(advice.SENTENCE)
    assert len(body["citations"]) >= 2 and body["how_found"]["route_detail"] == "advice"
    (row,) = c.logs
    assert row["trace"]["route"] == "retrieve" and row["abstained"] is False


# ---- the advice route's output limit (docs/decisions.md) ----


def test_the_advice_limit_is_1000_and_the_shared_limit_stays_600():
    assert CFG["answer"]["advice_max_output_tokens"] == 1000
    assert CFG["answer"]["max_output_tokens"] == 600


def test_only_the_advice_call_gets_the_larger_limit(monkeypatch, events):
    router, seen = make_router(Script("other"), monkeypatch, events, CFG)
    router.answer("Should I withdraw from my biology class?", TODAY, log=False)
    router.answer("How do I apply for graduation?", TODAY, log=False)
    advice_cfg, other_cfg = seen[0][1]["cfg"], seen[1][1]["cfg"]
    assert advice_cfg["answer"]["max_output_tokens"] == 1000
    assert other_cfg["answer"]["max_output_tokens"] == 600
    assert CFG["answer"]["max_output_tokens"] == 600  # the shared config is not changed
    assert {k: v for k, v in advice_cfg["answer"].items() if k != "max_output_tokens"} == {
        k: v for k, v in other_cfg["answer"].items() if k != "max_output_tokens"
    }
