"""Step 3b: comparing runs (no database, no network), the rerank fields, the step budget."""

from types import SimpleNamespace

import pytest

from cta.eval import answer_compare as ac
from cta.eval import run_answers as ra
from cta.index.rerank import Rerank
from cta.settings import load_models
from tests.helpers import ans, question, top


def record(qid, correctness="correct", faithfulness="yes", **kw):
    base = {"id": qid, "type": "lookup", "correctness": correctness, "faithfulness": faithfulness,
            "answer_cost": 0.001, "judge_cost": 0.004, "rerank_cost": 0.0, "rerank_ms": 0.0,
            "latency_ms": 1000, "chat_ms": 900, "retrieval_ms": 20.0}  # fmt: skip
    return base | kw


def agg(correct, partial, incorrect, yes, abstain=1.0, wrongly=0, cites=1.0, invalid=0):
    n = 26
    return {
        "correctness": {"correct": correct, "partial": partial, "incorrect": incorrect},
        "faithfulness": {"yes": yes},
        "abstention_accuracy": {"share": abstain},
        "wrongly_abstained": {"n": 30, "share": wrongly / 30},
        "citation_rate": {"share": cites, "invalid_citations": invalid},
        "no_advice_correct": {"correct": 1.0, "n": n},
    }


def run(label="r", a=None, rows=None):
    return {
        "label": label,
        "answers": a or agg(0.6, 0.3, 0.1, 0.9),
        "per_question": rows or [record("q1")],
        "failure_labels": {},
    }


# ---- the rule ----


def arm(**kw):
    return ac.arm_summary([run(a=agg(0.6, 0.3, 0.1, 0.9, **kw))] * 3)


def test_rule_passes_when_nothing_gets_worse():
    checks = ac.apply_rule(arm(), arm())
    assert all(ok for _, ok, _ in checks)


def test_rule_a_allows_a_fall_of_one_question_but_not_more():
    off = ac.arm_summary([run(a=agg(0.60, 0.3, 0.1, 0.9))] * 3)
    one = ac.arm_summary([run(a=agg(0.60 - 1 / 26, 0.3, 0.1, 0.9))] * 3)
    two = ac.arm_summary([run(a=agg(0.60 - 2 / 26, 0.3, 0.1, 0.9))] * 3)
    assert ac.apply_rule(off, one)[0][1] and not ac.apply_rule(off, two)[0][1]


def test_rule_b_any_fall_in_faithfulness_fails():
    on = ac.arm_summary([run(a=agg(0.6, 0.3, 0.1, 0.9 - 0.01))] * 3)
    assert not ac.apply_rule(arm(), on)[1][1]


def test_rule_c_abstention_accuracy_and_wrongly_abstained():
    assert not ac.apply_rule(arm(), arm(abstain=0.75))[2][1]
    assert not ac.apply_rule(arm(), arm(wrongly=1))[2][1]
    assert ac.apply_rule(arm(wrongly=1), arm(wrongly=0))[2][1]


def test_rule_d_citations():
    assert not ac.apply_rule(arm(), arm(cites=0.95))[3][1]
    assert not ac.apply_rule(arm(), arm(invalid=1))[3][1]


# ---- noise ----


def test_stable_arms_that_differ_are_a_real_change():
    assert ac.classify(["correct"] * 3, ["partial"] * 3, ac.CORRECTNESS) == "real worse"
    assert ac.classify(["partial"] * 3, ["correct"] * 3, ac.CORRECTNESS) == "real better"
    assert ac.classify(["correct"] * 3, ["correct"] * 3, ac.CORRECTNESS) == "same"


def test_any_variation_inside_an_arm_is_unstable_and_may_lean():
    got = ac.classify(["partial", "partial", "correct"], ["correct"] * 3, ac.CORRECTNESS)
    assert got == "unstable (leaning better)"
    assert ac.classify(["correct"] * 3, ["partial", "correct", "partial"], ac.CORRECTNESS) == (
        "unstable (leaning worse)"
    )
    assert ac.classify(["correct", "partial", "correct"], ["partial", "correct", "correct"],
                       ac.CORRECTNESS) == "unstable"  # fmt: skip


def test_a_question_with_no_verdict_is_not_compared():
    assert ac.classify([None] * 3, [None] * 3, ac.FAITHFULNESS) == "same"


def test_judge_noise_lists_the_differing_verdicts():
    one = run(rows=[record("q1"), record("q2")])
    two = run(rows=[record("q1"), record("q2", faithfulness="partly")])
    assert ac.judge_noise(one, two) == ["q2 faithfulness: yes -> partly"]


def test_report_names_the_real_and_unstable_questions_and_the_verdict():
    off = [run(rows=[record("q1"), record("q2")]) for _ in range(3)]
    on = [run(rows=[record("q1", "partial"), record("q2", "correct" if i else "partial")])
          for i in range(3)]  # fmt: skip
    text = ac.report(off, on, run(rows=[record("q1"), record("q2")]), on[0])
    assert "Real changes: ['q1']" in text and "Unstable (not counted): ['q2']" in text
    assert "KEEP pool_a" in text and "Judge noise" in text


def test_metrics_split_the_rerank_cost_out_of_the_answer_cost():
    rows = [
        record("q1", answer_cost=0.003, rerank_cost=0.002, rerank_ms=1500.0, retrieval_ms=1600.0)
    ]
    m = ac.run_metrics(run(rows=rows))
    assert m["answer_usd_per_request"] == pytest.approx(0.001)
    assert m["rerank_usd_per_request"] == pytest.approx(0.002)
    lat = ac.latency_metrics(run(rows=rows))
    assert lat["search_median"] == pytest.approx(100.0) and lat["rerank_median"] == 1500.0


def test_the_v3_check_lists_only_changed_verdicts_with_both_reasons():
    why = {"correctness_reason": "a", "faithfulness_reason": "b"}
    old = run(rows=[record("q1", **why), record("q2", faithfulness="no", **why)])
    new = run(rows=[record("q1", **why), record("q2", **why | {"faithfulness_reason": "e"})])
    q = {i: {"type": "lookup", "question": f"Q{i}?", "gold_answer": f"G{i}"} for i in ("q1", "q2")}
    text = ac.verdict_diff_markdown(old, new, q)
    assert "## q2" in text and "## q1" not in text and "| faithfulness | no | yes |" in text
    assert "| faithfulness reason | b | e |" in text and "Gq2" in text


# ---- the run: rerank fields and the budget ----


def test_a_record_carries_the_rerank_cost_time_and_failure():
    a = ans()
    a.search.rerank = Rerank([0], failed=True, cost=0.0007, ms=1234.5)
    r = ra.evaluate_question(question(), a, top("g"), lambda m: ('{"x":1}', 0.0))
    assert (r["rerank_cost"], r["rerank_ms"], r["rerank_failed"]) == (0.0007, 1234.5, True)
    plain = ra.evaluate_question(question(), ans(), top("g"), lambda m: ('{"x":1}', 0.0))
    assert (plain["rerank_cost"], plain["rerank_failed"]) == (0.0, False)


def test_a_stored_run_is_read_back_with_the_reranker_it_had(tmp_path):
    cfg = load_models(env={})  # default pool_a
    off = ra.stored_config(cfg, {"retrieval": {"rerank": "off"}}, "x")
    old = ra.stored_config(cfg, {"retrieval": {"mode": "vector"}}, "x")  # made before the switch
    on = ra.stored_config(cfg, {"retrieval": {"rerank": "pool_a"}}, "on-run1")
    assert off["retrieval"]["rerank"] == old["retrieval"]["rerank"] == "off"
    assert on["retrieval"]["rerank"] == "pool_a"
    assert on["rerank"]["cache_path"].endswith("rerank-on-run1.json")
    assert "cache_path" not in cfg["rerank"] and "cache_path" not in off["rerank"]


@pytest.mark.integration
def test_spent_so_far_adds_up_the_listed_runs_only(conn):
    for label, usd in (("on-run1", 0.2), ("off-run2", 0.1), ("other", 5.0)):
        conn.execute(
            "INSERT INTO eval_runs (label, git_commit, split, config, cost) "
            "VALUES (%s, 'x', 'dev', '{}', %s)",
            (label, f'{{"usd": {usd}}}'),
        )
    conn.commit()
    assert ra.spent_so_far(conn) == pytest.approx(0.3)


def test_a_run_stops_before_the_question_that_would_pass_the_budget(monkeypatch):
    class Conn:
        def execute(self, *a, **k):
            return SimpleNamespace(fetchone=lambda: (1,))

        def commit(self):
            pass

    cfg = load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"})
    monkeypatch.setattr(ra, "start_run", lambda *a, **k: 1)
    monkeypatch.setattr(ra, "make_judge_call", lambda *a, **k: None)
    monkeypatch.setattr(ra, "answer", lambda *a, **k: ans())
    monkeypatch.setattr(ra, "search", lambda *a, **k: SimpleNamespace(results=top("g")))
    monkeypatch.setattr(
        ra, "evaluate_question",
        lambda *a: {"answer_cost": 0.01, "judge_cost": 0.01, "correctness": None, "label": None},
    )  # fmt: skip
    qs = [question(f"q{i}") for i in range(5)]
    with pytest.raises(ra.BudgetStop, match="stopped before q1"):
        ra.run(
            Conn(),
            qs,
            "x",
            "dev",
            cfg,
            client_factory=lambda: None,
            out=lambda *_: None,
            budget=0.035,
        )
