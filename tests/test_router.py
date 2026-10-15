"""Step 4a: terms, link rows, selector parsing, renderer, scoring, graph wiring, the off path."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from cta.answer import Answer
from cta.eval import run_answers as ra
from cta.graph import build, classify, render, select, terms
from cta.graph.build import Router, answer_question, build_graph
from cta.graph.state import RoutedAnswer
from cta.index.search import Search
from cta.settings import load_models

CFG = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_SELECTOR": "1",
        "CTA_ROUTER_CHAIN": "off",
        "CTA_ROUTER_CONTACTS": "off",
    }
)
OFF = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "off",
        "CTA_ROUTER_CHAIN": "off",
        "CTA_ROUTER_CONTACTS": "off",
    }
)
TODAY = date(2026, 10, 11)


@pytest.fixture(scope="module")
def events():
    return build.load_events()


def row(rid="fall-2026-040", **kw):
    base = {
        "id": rid, "term": "Fall 2026", "event": "Last day to withdraw.",
        "date_start": "2026-11-06", "date_end": None, "date_raw": "November 06",
        "weekday_raw": "Friday", "applies_to": None, "source_pdf": "data/pdfs/fall_2026.pdf",
        "source_page": 1, "pdf_last_updated": "2026-09-15", "verified": True,
    }  # fmt: skip
    return base | kw


# ---- term resolution ----


@pytest.mark.parametrize(
    ("mention", "status", "term"),
    [
        ("Fall 2026", "explicit", "Fall 2026"),
        ("FALL 2026", "explicit", "Fall 2026"),
        ("winter 2027", "explicit", "Winter 2027"),
        ("Spring 2027", "explicit", "Spring 2027"),
        ("spring semester 2027", "explicit", "Spring 2027"),
        ("this fall", "season", "Fall 2026"),
        ("fall semester", "season", "Fall 2026"),
        ("autumn", "season", "Fall 2026"),
        ("next spring", "season", "Spring 2027"),
        ("this spring", "season", "Spring 2027"),
        ("the winter session", "season", "Winter 2027"),
        (None, "assumed", "Fall 2026"),
        ("", "assumed", "Fall 2026"),
        ("next semester", "assumed", "Fall 2026"),  # a known limitation: the current term
        ("2026", "assumed", "Fall 2026"),
    ],
)
def test_term_resolution_on_the_eval_date(events, mention, status, term):
    got = terms.resolve_term(mention, TODAY, events)
    assert (got.status, got.term) == (status, term)


@pytest.mark.parametrize(
    ("mention", "label"),
    [("Summer 2027", "Summer 2027"), ("Fall 2027", "Fall 2027"), ("summer", "Summer"),
     ("Spring 2028", "Spring 2028"), ("2028", "2028"), ("SUMMER 2027", "Summer 2027")],
)  # fmt: skip
def test_terms_without_a_calendar_are_unsupported(events, mention, label):
    got = terms.resolve_term(mention, TODAY, events)
    assert got.status == "unsupported" and got.label == label and got.term is None


def test_seasons_resolve_against_today(events):
    on = lambda d, m: terms.resolve_term(m, d, events)  # noqa: E731
    assert on(date(2026, 8, 1), "fall").term == "Fall 2026"
    assert on(date(2026, 12, 30), "winter").term == "Winter 2027"
    assert on(date(2027, 2, 1), "spring").term == "Spring 2027"
    assert on(date(2027, 2, 1), "fall").status == "unsupported"  # no Fall term is left
    assert on(date(2027, 2, 1), "winter").status == "unsupported"  # Winter 2027 has ended


def test_the_current_term_is_the_one_in_session(events):
    assert terms.current_term(events, date(2026, 10, 11)) == "Fall 2026"
    assert terms.current_term(events, date(2027, 1, 10)) == "Winter 2027"
    assert terms.current_term(events, date(2026, 7, 1)) == "Fall 2026"  # next to start
    assert terms.current_term(events, date(2027, 6, 30)) == "Spring 2027"  # last to end


def test_supported_terms_come_from_the_calendar_file(events):
    assert terms.supported_terms(events) == ["Fall 2026", "Winter 2027", "Spring 2027"]
    assert terms.supported_terms([row(term="Autumn 2030")]) == ["Autumn 2030"]


def test_the_q73_pattern_an_unsupported_term_found_in_another_calendars_rows(events):
    got = terms.resolve_term("Fall 2027", TODAY, events)
    assert got.status == "unsupported"
    ids = {r["id"] for r in got.pool}
    assert "spring-2027-040" in ids and "spring-2027-038" in ids  # registration for Fall 2027
    assert all("fall 2027" in r["event"].lower() for r in got.pool)
    assert not any(
        r["id"].startswith("fall-2026") for r in got.pool
    )  # no Fall 2027 calendar exists


def test_an_unsupported_label_that_no_row_mentions_has_an_empty_pool(events):
    assert terms.resolve_term("Spring 2028", TODAY, events).pool == []


def test_link_rows_are_excluded_from_the_pool(events):
    link = row("x", event="For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx")
    appeals = row("y", event="Deadline for Course and Standards Appeals Submission (students ...).")
    assert terms.link_row(link) and not terms.link_row(appeals)
    assert terms.link_row(row(event="For more info: https://example.edu/a"))
    assert not terms.link_row(row(event="For more information about aid, call the office."))
    pool = terms.term_pool([link, appeals, row()], "Fall 2026")
    assert [r["id"] for r in pool] == ["y", "fall-2026-040"]
    real = terms.term_pool(events, "Fall 2026")
    assert len(real) == 53 and not any(terms.link_row(r) for r in real)  # 55 rows, 2 link rows


# ---- classifier and selector ----


def test_classification_parsing():
    assert classify.parse_classification({"intent": "calendar", "term_mention": " this fall "}) == (
        "calendar", "this fall")  # fmt: skip
    assert classify.parse_classification({"intent": "other", "term_mention": None}) == (
        "other",
        None,
    )
    assert classify.parse_classification({"intent": "other"}) == ("other", None)
    for bad in (None, {}, {"intent": "maybe"}, {"intent": "calendar", "term_mention": 5}):
        assert classify.parse_classification(bad) is None


def test_selection_reading_valid_empty_invalid_and_malformed():
    pool = {"a", "b"}
    assert select.read_selection({"row_ids": ["b", "a"]}, pool).row_ids == ["b", "a"]
    assert select.read_selection({"row_ids": []}, pool).status == "empty"
    partial = select.read_selection({"row_ids": ["a", "zzz", "a"]}, pool)
    assert (partial.status, partial.row_ids, partial.invalid_ids) == ("ok", ["a"], ["zzz"])
    allbad = select.read_selection({"row_ids": ["zzz"]}, pool)
    assert allbad.status == "failed" and allbad.invalid_ids == ["zzz"]
    for bad in (None, {}, {"row_ids": "a"}, {"row_ids": [1]}, {"ids": ["a"]}):
        assert select.read_selection(bad, pool).status == "failed"


def test_the_selector_sees_the_pool_as_lines_and_no_dates_are_asked_for():
    msgs = select.build_messages("When?", TODAY, "Fall 2026", [row(applies_to="all students")])
    assert (
        "fall-2026-040 | Last day to withdraw. | November 06 | Friday | all students"
        in msgs[1]["content"]
    )
    assert (
        "Today's date: 2026-10-11" in msgs[1]["content"] and "Term: Fall 2026" in msgs[1]["content"]
    )
    assert "Never write dates" in msgs[0]["content"]


# ---- renderer ----


def text(r):
    return render.date_in_words(r)[0]


def test_single_date_range_and_cross_month_and_cross_year():
    assert text(row()) == "Friday, November 6, 2026"
    rng = row(date_start="2026-12-15", date_end="2026-12-21", weekday_raw="Tuesday-Monday")
    assert text(rng) == "December 15-21, 2026 (Tuesday-Monday)"
    months = row(date_start="2027-05-28", date_end="2027-06-02", weekday_raw="Friday-Wednesday")
    assert text(months) == "May 28 - June 2, 2027 (Friday-Wednesday)"
    years = row(date_start="2026-12-30", date_end="2027-01-02", weekday_raw="Wednesday-Saturday")
    assert text(years) == "December 30, 2026 - January 2, 2027 (Wednesday-Saturday)"


def test_winter_december_is_2026_and_january_is_2027():
    dec = row("winter-2027-001", term="Winter 2027", date_start="2026-12-28", weekday_raw="Monday")
    jan = row("winter-2027-004", term="Winter 2027", date_start="2027-01-04", weekday_raw="Monday")
    assert text(dec) == "Monday, December 28, 2026" and text(jan) == "Monday, January 4, 2027"


def test_a_weekday_that_disagrees_renders_the_printed_one_and_is_counted():
    wrong = row(weekday_raw="Monday")  # 2026-11-06 is a Friday
    out = render.render_rows(
        [wrong, row("b", date_start="2026-11-07", weekday_raw="Saturday")], "c"
    )
    assert out.weekday_mismatches == 1 and "Monday, November 6, 2026" in out.text
    assert render.render_rows([row()], "c").weekday_mismatches == 0


def test_the_answer_text_has_event_source_line_and_applies_to():
    r = row(applies_to="all students")
    out = render.render_rows([r], "c")
    assert out.text == (
        "**Friday, November 6, 2026**: Last day to withdraw. [1] (applies to: all students)\n\n"
        "From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). "
        "The calendar can change."
    )
    assert out.row_ids == ["fall-2026-040"] and out.sources[0]["id"] == "fall-2026-040"
    assert out.sources[0]["kind"] == "calendar" and out.sources[0]["heading_path"].startswith(
        "Fall 2026"
    )


def test_rows_are_sorted_by_date_and_numbered_in_that_order():
    a, b = row("a", date_start="2026-12-01", weekday_raw="Tuesday"), row("b")
    c = row("c", date_start=None, weekday_raw="TBA")
    out = render.render_rows([c, a, b], "contact")
    assert out.row_ids == ["b", "a", "c"]
    bullets = [line for line in out.text.splitlines() if line.startswith("- ")]
    assert [line.split("[")[1][0] for line in bullets] == ["1", "2", "3"]


def test_assumed_term_is_stated():
    out = render.render_rows([row()], "c", assumed_term="Fall 2026")
    assert out.text.startswith(
        "Assuming the current term, Fall 2026.\n\n**Friday, November 6, 2026**"
    )


def test_the_tba_rule_a_null_date_is_not_announced_yet_plus_the_registrar_contact():
    tba = row("spring-2027-055", term="Spring 2027", event="87th Commencement Ceremony",
              date_start=None, weekday_raw="TBA", date_raw="TBA",
              source_pdf="data/pdfs/spring_2027.pdf",
              pdf_last_updated="2026-07-27")  # fmt: skip
    out = render.render_rows([tba], "registrar@x.edu, 718-000-0000")
    assert out.text.startswith("87th Commencement Ceremony: not announced yet [1]")
    assert "Contact the Registrar: registrar@x.edu, 718-000-0000." in out.text.splitlines()[0]
    assert out.tba_rows == ["spring-2027-055"] and "2027" not in out.text.splitlines()[0]


def test_registrar_contact_from_the_contacts_file(tmp_path):
    path = tmp_path / "registrar.json"
    path.write_text(json.dumps({"emails": ["r@x.edu"], "phones": ["718-1"]}))
    assert render.registrar_contact(path) == "r@x.edu, 718-1"
    assert render.registrar_contact(tmp_path / "missing.json") == render.NO_CONTACT


def test_abstain_text_starts_with_the_marker_the_runner_recognises():
    assert render.abstain_text("Nothing.", "c").startswith(
        "ABSTAIN: Nothing. Contact the Registrar: c"
    )


# ---- scoring of calendar-only gold ----


def gold_q(*ids):
    return {"id": "q", "gold_sources": [{"id": i} for i in ids]}


def routed_ans(rows=(), route="calendar", abstained=False):
    ans = RoutedAnswer("t", abstained, None, [], search=Search([], False, 0, 0, 0.0))
    ans.row_ids, ans.route = list(rows), route
    return ans


@pytest.mark.parametrize(
    ("rows", "route", "grade", "label"),
    [
        (["a", "b"], "calendar", "correct", None),
        (["b", "a"], "calendar", "correct", None),
        (["a"], "calendar", "partial", "calendar missed"),
        (["a", "x"], "calendar", "incorrect", "calendar wrong row"),
        (["x"], "calendar", "incorrect", "calendar wrong row"),
        ([], "abstain", "incorrect", "calendar abstained"),
        ([], "calendar_fallthrough", "incorrect", "calendar missed"),
        ([], "other", "incorrect", "calendar missed"),
    ],
)
def test_calendar_scoring(rows, route, grade, label):
    verdict, got_label, _ = ra.calendar_result(gold_q("a", "b"), routed_ans(rows, route))
    assert (verdict["correctness"], got_label) == (grade, label)
    assert verdict["judge_status"] == "rule" and verdict["faithfulness"] is None


def test_an_answer_from_the_old_path_has_no_rows_and_scores_incorrect_missed():
    old = Answer("text", False, None, [], search=Search([], False, 0, 0, 0.0))
    verdict, label, _ = ra.calendar_result(gold_q("a"), old)
    assert (verdict["correctness"], label) == ("incorrect", "calendar missed")


def test_evaluate_question_uses_the_calendar_rule_only_when_asked():
    q = {"id": "q", "question": "?", "gold_answer": "d", "type": "time_sensitive",
         "department": None, "gold_sources": [{"id": "fall-2026-040"}]}  # fmt: skip
    ans = routed_ans(["fall-2026-040"])
    on = ra.evaluate_question(q, ans, [], lambda m: pytest.fail("no judge call"), True)
    assert (
        on["correctness"] == "correct"
        and on["route"] == "calendar"
        and on["returned_rows"] == ["fall-2026-040"]
    )
    verdict = json.dumps({"correctness": "incorrect", "correctness_reason": "r",
                          "faithfulness": "yes", "faithfulness_reason": "f"})  # fmt: skip
    off = ra.evaluate_question(q, ans, [], lambda m: (verdict, 0.0), False)
    assert off["judge_status"] == "ok" and off["label"] == "not supported yet"  # the old behaviour


# ---- graph wiring (a scripted client, no network) ----


class Script:
    """A chat client with fixed replies for the classifier, the selector and the answerer."""

    def __init__(
        self, intent="calendar", mention=None, row_ids=(), selector_text=None, answer="ok [1]"
    ):
        self.intent, self.mention, self.row_ids = intent, mention, list(row_ids)
        self.selector_text, self.answer_text, self.calls = selector_text, answer, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        system = kw["messages"][0]["content"]
        which = "classify" if system.startswith("You route") else "select" if system.startswith(
            "You choose") else "answer"  # fmt: skip
        self.calls.append(which)
        reply = {
            "classify": json.dumps({"intent": self.intent, "term_mention": self.mention}),
            "select": self.selector_text or json.dumps({"row_ids": self.row_ids}),
            "answer": self.answer_text,
        }[which]
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=usage
        )


def make_router(script, monkeypatch, events, cfg=CFG):
    stub = Answer(
        "old path [1]", False, None, [{"id": "c1"}], [1], [], Search([], False, 0, 0, 0.0)
    )
    seen = []
    monkeypatch.setattr(build, "answer", lambda *a, **k: seen.append((a, k)) or stub)
    return Router(None, cfg, lambda: script, events=events, contact="registrar@x.edu"), seen


def test_calendar_route_answers_from_the_rows_and_never_calls_retrieve(monkeypatch, events):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])
    router, seen = make_router(script, monkeypatch, events)
    ans = router.answer("Last day to withdraw in Fall 2026?", TODAY, log=False)
    assert script.calls == ["classify", "select"] and seen == []
    assert ans.route == "calendar" and ans.row_ids == ["fall-2026-040"] and not ans.abstained
    assert ans.text.startswith("**Friday, November 6, 2026**: Last day to withdraw from a course")
    assert ans.citations == [1] and ans.sources[0]["id"] == "fall-2026-040"
    assert (
        ans.prompt_tokens == 200 and ans.chat_cost > 0 and ans.router["term_status"] == "explicit"
    )
    assert ans.router["classify"]["prompt_tokens"] == 100 and ans.router["select"]["status"] == "ok"


def test_other_route_calls_the_existing_pipeline_after_the_classifier(monkeypatch, events):
    script = Script("other")
    router, seen = make_router(script, monkeypatch, events)
    ans = router.answer("How do I apply for graduation?", TODAY, log=False)
    assert script.calls == ["classify"] and len(seen) == 1 and seen[0][1]["log"] is False
    assert ans.route == "other" and ans.text == "old path [1]" and ans.row_ids == []
    assert ans.chat_cost > 0 and ans.router["intent"] == "other"


def test_a_valid_empty_selection_falls_through_to_retrieve(monkeypatch, events):
    script = Script("calendar", "this fall", [])
    router, seen = make_router(script, monkeypatch, events)
    ans = router.answer("When is my tuition bill due this fall?", TODAY, log=False)
    assert script.calls == ["classify", "select"] and len(seen) == 1
    assert ans.route == "calendar_fallthrough" and ans.router["fallthrough"] is True
    assert ans.text == "old path [1]" and ans.row_ids == []
    assert ans.router["select"]["status"] == "empty"


@pytest.mark.parametrize("reply", ["not json", '{"row_ids": "x"}', '{"row_ids": ["nope"]}', "[]"])
def test_a_failed_or_malformed_selector_abstains_and_does_not_fall_through(
    monkeypatch, events, reply
):
    router, seen = make_router(Script("calendar", None, selector_text=reply), monkeypatch, events)
    ans = router.answer("Last day to add?", TODAY, log=False)
    assert seen == [] and ans.route == "abstain" and ans.abstained
    assert ans.text.startswith("ABSTAIN: I could not find that in the Fall 2026 calendar.")
    assert ans.text.endswith("Contact the Registrar: registrar@x.edu.")
    assert ans.abstain_reason == "calendar_selector_failed"


def test_invalid_ids_are_dropped_and_counted_but_valid_ones_are_used(monkeypatch, events):
    script = Script("calendar", None, ["fall-2026-040", "winter-2027-004", "zzz"])
    router, _ = make_router(script, monkeypatch, events)
    ans = router.answer("Last day to withdraw?", TODAY, log=False)
    # winter-2027-004 exists but is not in the Fall pool: it is invalid here
    assert ans.row_ids == ["fall-2026-040"] and ans.router["invalid_ids"] == 2


def test_no_term_mention_states_the_assumed_term(monkeypatch, events):
    router, _ = make_router(Script("calendar", None, ["fall-2026-040"]), monkeypatch, events)
    ans = router.answer("What is the last day to withdraw?", TODAY, log=False)
    assert ans.text.startswith("Assuming the current term, Fall 2026.")
    assert ans.router["term_status"] == "assumed"


def test_unsupported_term_with_no_row_abstains_without_a_selector_call(monkeypatch, events):
    script = Script("calendar", "Spring 2028")
    router, seen = make_router(script, monkeypatch, events)
    ans = router.answer("When do classes begin in Spring 2028?", TODAY, log=False)
    assert script.calls == ["classify"] and seen == [] and ans.route == "abstain"
    assert ans.abstain_reason == "calendar_unsupported_term" and "Spring 2028" in ans.text


def test_unsupported_term_found_in_other_rows_goes_to_the_selector(monkeypatch, events):
    script = Script("calendar", "Fall 2027", ["spring-2027-040"])
    router, _ = make_router(script, monkeypatch, events)
    ans = router.answer("When does registration for Fall 2027 begin?", TODAY, log=False)
    assert ans.route == "calendar" and ans.row_ids == ["spring-2027-040"]
    assert "**Monday, March 22, 2027**: Online registration for Fall 2027" in ans.text


def test_unsupported_term_with_a_valid_empty_selection_abstains_not_falls_through(
    monkeypatch, events
):
    router, seen = make_router(Script("calendar", "Summer 2027", []), monkeypatch, events)
    ans = router.answer("Last day to drop for a 100% refund in Summer 2027?", TODAY, log=False)
    assert seen == [] and ans.route == "abstain" and ans.abstained


def test_a_failed_classifier_sends_the_question_to_the_old_pipeline(monkeypatch, events):
    class Down(Script):
        def create(self, **kw):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="garbage"))],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=1),
            )

    router, seen = make_router(Down(), monkeypatch, events)
    ans = router.answer("When is the last day to add?", TODAY, log=False)
    assert ans.route == "other" and len(seen) == 1 and ans.router["classify"]["failed"] is True


def test_the_graph_has_the_pre_registered_nodes_and_edges():
    graph = build_graph(build.Deps(None, CFG, None, [], "c")).get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert set(graph.nodes) == {
        "__start__", "classify", "clarify", "calendar", "chain", "retrieve", "__end__"
    }  # fmt: skip
    assert edges == {
        ("__start__", "classify"), ("classify", "calendar"), ("classify", "chain"),
        ("classify", "retrieve"), ("classify", "clarify"), ("clarify", "__end__"),
        ("calendar", "retrieve"), ("calendar", "__end__"),
        ("chain", "retrieve"), ("chain", "__end__"), ("retrieve", "__end__"),
    }  # fmt: skip


def test_the_architecture_doc_shows_the_current_graph():
    from pathlib import Path

    mermaid = build_graph(build.Deps(None, CFG, None, [], "c")).get_graph().draw_mermaid()
    doc = (Path(__file__).resolve().parents[1] / "docs" / "architecture.md").read_text()
    assert mermaid in doc


# ---- the switch and the off path ----


def test_router_defaults_are_on_and_selector_2_since_step_4a2_and_validated():
    default = load_models(env={})["router"]
    assert (default["mode"], default["selector"]) == ("on", 2)  # kept by the 4a-2 rule
    assert OFF["router"]["mode"] == "off"
    assert load_models(env={"CTA_ROUTER_MODE": "off"})["router"]["mode"] == "off"
    with pytest.raises(ValueError, match="router.mode"):
        load_models(env={"CTA_ROUTER_MODE": "maybe"})


def test_router_off_is_exactly_the_old_path(monkeypatch):
    stub = Answer("old", False, None, [], [], [], Search([], False, 0, 0, 0.0))
    calls = []
    monkeypatch.setattr(build, "answer", lambda *a, **k: calls.append((a, k)) or stub)
    monkeypatch.setattr(build, "Router", lambda *a, **k: pytest.fail("the graph must not be built"))
    got = answer_question("conn", "Q?", TODAY, cfg=OFF, client_factory="cf", run_id=7)
    assert got is stub  # the very object `answer` returned, not a copy
    assert calls == [(("conn", "Q?", TODAY), {"cfg": OFF, "client_factory": "cf", "run_id": 7})]


def test_run_answers_off_calls_answer_and_never_the_router(monkeypatch):
    seen = []
    ans = Answer("a", False, None, [], [], [], Search([], False, 0, 0, 0.0))
    monkeypatch.setattr(ra, "answer", lambda *a, **k: seen.append(k) or ans)
    monkeypatch.setattr(ra, "Router", lambda *a, **k: pytest.fail("no router when off"))
    monkeypatch.setattr(ra, "search", lambda *a, **k: SimpleNamespace(results=[]))
    monkeypatch.setattr(ra, "start_run", lambda *a, **k: 1)
    monkeypatch.setattr(ra, "make_judge_call", lambda *a, **k: None)
    monkeypatch.setattr(ra, "finish_run", lambda *a, **k: None)
    monkeypatch.setattr(ra, "RESULTS", __import__("pathlib").Path("/tmp"))
    q = {
        "id": "q70x", "question": "Q?", "gold_answer": "ABSTAIN", "gold_sources": [],
        "type": "unanswerable", "department": None, "split": "dev",
    }  # fmt: skip
    summary = ra.run(
        None, [q], "zz-off-test", "dev", OFF, client_factory=lambda: None, out=lambda *_: None
    )
    assert len(seen) == 1 and summary["per_question"][0]["route"] is None
    assert summary["per_question"][0]["returned_rows"] == []
    import os

    os.remove("/tmp/zz-off-test.json")


# ---- logging ----


@pytest.mark.integration
def test_request_log_row_carries_route_and_router_numbers_and_is_redacted(conn):
    ans = routed_ans(["fall-2026-040"])
    ans.text, ans.today, ans.prompt_tokens, ans.router = (
        "call me at 718-260-5800",
        TODAY,
        200,
        {"x": 1},
    )
    ans.sources = [{"id": "fall-2026-040"}]
    build.log_request(conn, "my email is a@b.edu, when?", ans, CFG, None)
    q, a, route, router = conn.execute(
        "SELECT question, answer, route, router FROM request_logs"
    ).fetchone()
    assert "a@b.edu" not in q and "718-260-5800" not in a
    assert route == "calendar" and router == {"x": 1}


# ---- selector v2 (step 4a-2) ----

CFG2 = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_SELECTOR": "2",
        "CTA_ROUTER_CHAIN": "off",
        "CTA_ROUTER_CONTACTS": "off",
    }
)


def test_selector_switch_values_and_validation():
    assert CFG["router"]["selector"] == 1 and load_models(env={})["router"]["selector"] == 2
    assert CFG2["router"]["selector"] == 2
    with pytest.raises(ValueError, match="router.selector"):
        load_models(env={"CTA_ROUTER_SELECTOR": "3"})


def test_the_all_calendar_pool_has_every_term_and_no_link_rows(events):
    pool = terms.all_rows_pool(events)
    assert {r["term"] for r in pool} == {"Fall 2026", "Winter 2027", "Spring 2027"}
    assert not any(terms.link_row(r) for r in pool)
    assert len(pool) == 136 - sum(terms.link_row(r) for r in events)


def test_v2_lines_show_the_term_and_the_prompt_is_the_stricter_one():
    msgs = select.build_messages_v2("When?", TODAY, "Fall 2026", [row(applies_to="all students")])
    assert (
        "fall-2026-040 | Fall 2026 | Last day to withdraw. | November 06 | Friday | all"
        in msgs[1]["content"]
    )
    assert "Assumed term: Fall 2026" in msgs[1]["content"]
    assert "Return a row only if its event is what the student asked about" in msgs[0]["content"]
    assert 'Reply {"row_ids": []} if the listed rows are about something else' in msgs[0]["content"]
    assert (
        "Prefer rows from the assumed term" in msgs[0]["content"]
        and "Never write dates" in msgs[0]["content"]
    )
    assert select.build_messages("When?", TODAY, "Fall 2026", [row()])[0]["content"].startswith(
        "You choose rows from a City Tech"
    )


class Spy(Script):
    def create(self, **kw):
        if kw["messages"][0]["content"].startswith(
            "You choose rows from City Tech academic calendars"
        ):
            self.calls.append("select_v2")
            self.v2_user = kw["messages"][1]["content"]
            usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
            reply = json.dumps({"row_ids": self.row_ids})
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=usage
            )
        return super().create(**kw)


def test_selector_v2_sees_all_calendars_and_a_row_of_another_term_can_be_chosen(
    monkeypatch, events
):
    script = Spy("calendar", "next spring", ["fall-2026-039", "fall-2026-038"])
    router, _ = make_router(script, monkeypatch, events, CFG2)
    ans = router.answer("When can I register for classes next spring?", TODAY, log=False)
    assert script.calls == ["classify", "select_v2"]
    for term in ("Fall 2026", "Winter 2027", "Spring 2027"):
        assert f"| {term} |" in script.v2_user
    assert "For more info" not in script.v2_user and "Assumed term: Spring 2027" in script.v2_user
    assert ans.route == "calendar" and ans.row_ids == ["fall-2026-038", "fall-2026-039"]
    assert ans.router["selector_version"] == 2 and ans.router["pool_size"] > 100
    # each row names its own calendar, although the question resolved to Spring 2027
    assert (
        ans.text.count("From the Fall 2026 calendar (fall_2026.pdf") == 1
        and "Spring 2027 calendar" not in ans.text
    )


def test_selector_v1_is_unchanged_when_the_switch_is_1(monkeypatch, events):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])
    router, _ = make_router(script, monkeypatch, events, CFG)
    ans = router.answer("Last day to withdraw in Fall 2026?", TODAY, log=False)
    assert script.calls == ["classify", "select"]
    assert ans.router["selector_version"] == 1 and ans.router["pool_size"] == 53


def test_the_unsupported_term_path_keeps_selector_v1_even_when_v2_is_on(monkeypatch, events):
    script = Script("calendar", "Fall 2027", ["spring-2027-040"])
    router, _ = make_router(script, monkeypatch, events, CFG2)
    ans = router.answer("When does registration for Fall 2027 begin?", TODAY, log=False)
    assert script.calls == ["classify", "select"] and ans.router["selector_version"] == 1
    assert ans.row_ids == ["spring-2027-040"]


def test_a_valid_empty_v2_selection_still_falls_through(monkeypatch, events):
    script = Script("calendar", "this fall", [])
    router, seen = make_router(script, monkeypatch, events, CFG2)
    ans = router.answer("When is my tuition bill due this fall?", TODAY, log=False)
    assert ans.route == "calendar_fallthrough" and len(seen) == 1


def test_the_renderer_names_each_rows_own_calendar_and_sorts_across_terms():
    fall = row("fall-2026-039", date_start="2026-11-02", weekday_raw="Monday")
    spring = row(
        "spring-2027-040", term="Spring 2027", date_start="2027-03-22", weekday_raw="Monday",
        source_pdf="data/pdfs/spring_2027.pdf", pdf_last_updated="2026-07-27",
    )  # fmt: skip
    out = render.render_rows([spring, fall], "c", assumed_term="Fall 2026")
    paragraphs = out.text.split("\n\n")
    assert out.row_ids == ["fall-2026-039", "spring-2027-040"]
    assert paragraphs[1].startswith("- ") and paragraphs[3].startswith("- ")
    assert paragraphs[2] == (
        "From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). "
        "The calendar can change."
    )
    assert paragraphs[4] == (
        "From the Spring 2027 calendar (spring_2027.pdf, last updated 2026-07-27). "
        "The calendar can change."
    )
