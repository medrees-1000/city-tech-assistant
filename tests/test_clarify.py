"""Step 4 CLARIFY: the detector, the graph node, the API contract, the log row and the eval rule.
No network, no database, no paid call. The dev questions are read; the test split is not."""

import json

import pytest

from cta.api import convert, requestlog, schema
from cta.eval import run_answers as ra
from cta.eval.questions import load_questions
from cta.graph import advice, build, clarify
from cta.settings import ROOT, load_models
from tests.test_api import Client, ask, make_client_app
from tests.test_router import TODAY, Script, make_router

DEV = [q for q in load_questions() if q["split"] == "dev"]
STATED = {"q88", "q89"}  # the dev questions the detector must fire on
CFG = load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "on", "CTA_ROUTER_CHAIN": "on"})


def stored_intents() -> list[tuple[str, str]]:
    """(question text, intent) for every stored dev answer that carries a router record."""
    text = {q["id"]: q["question"] for q in DEV}
    out = []
    for path in sorted((ROOT / "eval" / "results").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(run, dict) or run.get("split") != "dev":
            continue
        for r in run.get("per_question", []):
            intent = (r.get("router") or {}).get("intent")
            if intent and r["id"] in text:
                out.append((text[r["id"]], intent))
    return out


# ---- the detector ----


def test_dev_set_is_the_90_questions_and_includes_the_three_named_ones():
    # 63 + the tester round's 8 (q96 to q103) + 19 casual rows (q104 to q122)
    assert len(DEV) == 90 and {"q88", "q89", "q90"} <= {q["id"] for q in DEV}


def test_fires_on_q88_and_q89_never_on_q90_and_on_no_other_dev_question():
    fired = {q["id"] for q in DEV if clarify.needs_clarification(q["question"])}
    assert fired == STATED | {"q109"}  # q109 (casual round, "when is it due") is vague itself


def test_the_stored_classifier_outputs_change_nothing():
    pairs = stored_intents()
    assert len(pairs) > 500  # many stored dev runs
    fired = {text for text, intent in pairs if clarify.needs_clarification(text, intent)}
    # q109 ("when is it due", casual round) is in the stored runs since the casual-b0 run
    stated = {q["question"] for q in DEV if q["id"] in STATED | {"q109"}}
    assert fired == stated & {t for t, _ in pairs}


def test_the_routing_function_is_unchanged_for_every_question_that_does_not_fire():
    after_classify = build.make_nodes(build.Deps(None, CFG, None, [], "c"))[1]
    old = {"prerequisite": "chain", "calendar": "calendar"}  # anything else went to retrieve
    for text, intent in stored_intents():
        state = {"question": text, "intent": intent}
        if clarify.needs_clarification(text, intent):
            assert after_classify(state) == "clarify"
        elif advice.needs_advice_rules(text, intent):
            assert after_classify(state) == "advice"  # step 5: the NO ADVICE questions
        else:
            assert after_classify(state) == old.get(intent, "retrieve")


CLEAR = [
    "When is the filing period for February 2027 graduation?",
    "What is the last day to add a course in Fall 2026?",
    "What is the tuition payment deadline?",
    "When is the deadline to drop a class?",
    "When is the SAP appeal deadline?",
    "When is the last day of classes?",
    "What is the registration deadline for Spring 2027?",
    "What is the deadline for CST 1101?",
    "When is the deadline for the Dental Hygiene program?",
    "What is the financial aid deadline?",
    "How do I apply for graduation?",
    "Hello",
    "",
]


@pytest.mark.parametrize("question", CLEAR)
def test_a_clear_question_never_clarifies(question):
    assert clarify.needs_clarification(question) is False


@pytest.mark.parametrize(
    "question",
    ["When is the deadline?", "When is the due date?", "What is the last day?",
     "what's the deadline", "Deadline?", "When is the deadline for Fall 2026?"],
)  # fmt: skip
def test_the_generic_questions_clarify(question):
    assert clarify.needs_clarification(question) is True


def test_a_prerequisite_classification_never_clarifies():
    assert clarify.needs_clarification("What is the last day?", "prerequisite") is False
    assert clarify.needs_clarification("What is the last day?", "calendar") is True


def test_a_long_question_never_clarifies():
    assert not clarify.needs_clarification("When is the deadline for the thing I was told " * 2)


@pytest.mark.parametrize("word", clarify.TOPIC_WORDS)
def test_property_any_topic_word_course_code_or_department_blocks_it(word):
    assert not clarify.needs_clarification(f"When is the {word} deadline?")
    assert not clarify.needs_clarification(f"When is the deadline for {word}?")


@pytest.mark.parametrize(
    "extra", ["CST 1101", "MAT 1475", "EET3672", "Mathematics", "Dental Hygiene"]
)
def test_property_a_course_code_or_department_blocks_it(extra):
    assert not clarify.needs_clarification(f"What is the last day for {extra}?")


def test_the_reply_is_the_fixed_template_with_the_terms_from_the_config():
    text = clarify.reply_text()
    assert text == (
        "I can help with that, but I need a little more detail. Which deadline do you mean: "
        "registration, tuition payment, dropping or withdrawing from a class, applying to "
        "graduate, or financial aid? And for which term (Fall 2026, Winter 2027 or Spring 2027)?"
    )
    assert clarify.calendar_terms() == ["Fall 2026", "Winter 2027", "Spring 2027"]


# ---- the graph ----


def test_a_clarified_request_makes_the_classifier_call_and_nothing_else(monkeypatch):
    script = Script("calendar")
    events = build.load_events()
    router, seen = make_router(script, monkeypatch, events, CFG)
    ans = router.answer("When is the due date?", TODAY, log=False)
    assert script.calls == ["classify"] and seen == []
    assert ans.route == "clarify" and ans.text == clarify.reply_text()
    assert not ans.abstained and ans.sources == [] and ans.citations == []
    assert "contact_office" in ans.router and ans.router["contact_office"] is None


def test_a_clear_question_still_takes_its_old_route(monkeypatch):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])
    router, seen = make_router(script, monkeypatch, build.load_events(), CFG)
    ans = router.answer("When is the filing period for February 2027 graduation?", TODAY, log=False)
    assert ans.route == "calendar" and script.calls == ["classify", "select"]


def test_the_log_function_stores_the_route(conn):
    router_ans = build.RoutedAnswer(clarify.reply_text(), False, None, [], [], [],
                                    build.Search([], False, 0, 0, 0.0))  # fmt: skip
    router_ans.route, router_ans.today = "clarify", TODAY
    router_ans.router = {"route": "clarify"}
    build.log_request(conn, "When is the due date?", router_ans, CFG, None)
    (route,) = conn.execute("SELECT route FROM request_logs").fetchone()
    assert route == "clarify"


# ---- the API ----


def test_the_api_returns_a_clarify_answer_with_no_sources_and_no_contact(monkeypatch):
    client = Client("calendar")
    c = make_client_app(client, monkeypatch)
    r = ask(c, "When is the due date?")
    body = r.json()
    schema.AskResponse.model_validate(body)
    assert body["answer_type"] == "clarify" and body["route"] == "clarify"
    assert body["answer"] == clarify.reply_text()
    assert body["abstained"] is False and body["abstain_reason"] is None
    assert body["citations"] == [] and body["contact"] is None
    assert client.calls == ["classify"]  # no topic call, no selector, no answer call
    assert body["how_found"]["route_detail"] == "clarify"
    assert body["how_found"]["abstain_wording"] is None
    (row,) = c.logs
    assert row["route"] == "clarify" and row["trace"]["answer_type"] == "clarify"
    assert row["abstained"] is False and row["contact_office"] is None


def test_the_request_log_row_goes_through_redact(monkeypatch):
    c = make_client_app(Client("calendar"), monkeypatch)
    ask(c, "When is the due date? mail me at a@b.edu")
    assert "a@b.edu" not in c.logs[0]["question"]


def test_the_clarify_reply_contains_no_text_the_student_typed(monkeypatch):
    c = make_client_app(Client("calendar"), monkeypatch)
    body = ask(c, "When is the deadline? zzqx plum").json()
    assert "zzqx" not in body["answer"] and "plum" not in body["answer"]


def test_a_clarify_answer_is_not_a_public_abstain_route():
    assert convert.public_route(build.RoutedAnswer("t", False, None, [], route="clarify")) == (
        "clarify"
    )
    assert requestlog.COLUMNS  # the row has a route column, which stores "clarify"


# ---- the eval rule ----


def question(qtype, qid="q1", gold="CLARIFY: which?"):
    return {"id": qid, "question": "When is the due date?", "gold_answer": gold, "type": qtype,
            "department": None, "gold_sources": []}  # fmt: skip


def clarify_answer():
    a = build.RoutedAnswer(clarify.reply_text(), False, None, [], [], [],
                           build.Search([], False, 0, 0, 0.0))  # fmt: skip
    a.route = "clarify"
    return a


def no_judge(messages):
    raise AssertionError("the CLARIFY rule must not call the judge")


def test_a_clarify_reply_passes_on_an_ambiguous_question_with_no_judge_call():
    r = ra.evaluate_question(question("ambiguous"), clarify_answer(), [], no_judge)
    assert r["correctness"] == "correct" and r["judge_status"] == "rule" and r["label"] is None
    assert r["judge_cost"] == 0.0


@pytest.mark.parametrize("qtype", ["lookup", "multi_chunk", "time_sensitive", "unanswerable"])
def test_a_clarify_reply_on_any_other_question_is_a_failure(qtype):
    q = question(qtype, gold="Nov 6")
    r = ra.evaluate_question(q, clarify_answer(), [], no_judge)
    assert r["correctness"] == "incorrect" and r["label"] == "clarify error"
    assert "not ambiguous" in r["correctness_reason"]


def test_an_ambiguous_question_that_is_not_clarified_is_scored_as_before():
    from cta.answer import Answer
    from tests.test_run_answers import ans, top

    r = ra.evaluate_question(question("ambiguous"), ans(), top("g"), no_judge)
    assert r["label"] == "not supported yet" and r["correctness"] is None
    assert isinstance(ans(), Answer)


def test_a_clarify_reply_is_not_part_of_the_citation_rate():
    records = [
        ra.evaluate_question(question("ambiguous"), clarify_answer(), [], no_judge),
        ra.evaluate_question(question("ambiguous", "q2"), clarify_answer(), [], no_judge),
    ]
    for r in records:
        r["route"] = "clarify"
    assert ra.aggregate(records)["citation_rate"]["n"] == 0
