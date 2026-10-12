# ruff: noqa: E501
"""Step 4-judge: labels, plant rules, claims derivation, variant settings, selection rule (no network)."""

import json
from types import SimpleNamespace

import pytest

from cta.eval import judge_plants as jp
from cta.eval import judge_variants as jv
from cta.settings import load_models

CFG = load_models(env={})


def chunk(text, heading="Heading", cid="c"):
    return {"id": cid, "kind": "section", "source": "https://x", "heading_path": heading,
            "terms": [], "last_updated": None, "text": text}  # fmt: skip


def item(key="q|run", answer="a", sources=(), label=None, kind="real"):
    q = {"id": "q", "question": "Q?", "gold_answer": "G", "gold_sources": []}
    return jp.Item(key, kind, q, answer, list(sources), label)


# ---- labels ----


def test_the_real_labels_file_has_16_items_8_owner_and_8_second_reader():
    labels = jp.load_labels()
    assert len(labels) == 16
    assert [e["source"] for e in labels].count("owner") == 8
    assert [e["source"] for e in labels].count("second reader") == 8
    assert {(e["question"], e["run"]) for e in labels} >= {("q52", "on-run1"), ("q15", "on-run1")}
    owner = {
        e["question"]: (e["correctness"], e["faithfulness"])
        for e in labels
        if e["source"] == "owner"
    }
    assert owner["q03"] == ("correct", "partly") and owner["q12"] == ("incorrect", "yes")
    assert all(
        set(e) <= {"question", "run", "correctness", "faithfulness", "source", "note"}
        for e in labels
    )


def test_the_label_loader_rejects_bad_files(tmp_path):
    def write(entries):
        path = tmp_path / "l.json"
        path.write_text(json.dumps({"items": entries}))
        return path

    ok = {
        "question": "q1",
        "run": "r",
        "correctness": "correct",
        "faithfulness": "yes",
        "source": "owner",
    }
    assert jp.load_labels(write([ok]))[0]["question"] == "q1"
    for bad, text in (
        (ok | {"faithfulness": "maybe"}, "bad verdict"),
        (ok | {"source": "me"}, "source must be"),
        ({k: v for k, v in ok.items() if k != "run"}, "missing"),
    ):
        with pytest.raises(ValueError, match=text):
            jp.load_labels(write([bad]))
    with pytest.raises(ValueError, match="duplicate"):
        jp.load_labels(write([ok, ok]))


# ---- number plants ----


def test_the_first_shared_number_is_replaced_by_one_absent_from_the_sources():
    sources = [chunk("The program needs 66 credits and 20 liberal arts credits.")]
    text, what = jp.plant_number("It needs 66 credits [1] and 20 more.", sources)
    assert text == "It needs 67 credits [1] and 20 more." and what == "66 -> 67"


def test_the_replacement_skips_values_that_appear_in_the_sources():
    sources = [chunk("You need 66 credits; the old rule was 67; a form has 68 fields.")]
    text, _ = jp.plant_number("You need 66 credits.", sources)
    assert "69" in text


def test_citation_markers_and_numbers_not_in_the_sources_are_ignored():
    sources = [chunk("Fees are 40 dollars.")]
    text, what = jp.plant_number("About 12 weeks [1]; the fee is 40 dollars [1].", sources)
    assert what == "40 -> 41" and text.startswith("About 12 weeks [1]; the fee is 41")
    assert jp.plant_number("Nothing numeric here [1].", sources) is None
    assert jp.plant_number("It is 99 [1].", [chunk("no digits")]) is None


def test_course_codes_keep_their_prefix_space_and_suffix():
    sources = [chunk("MAT 1275CO is required before MAT 1375.")]
    text, what = jp.plant_number("Take MAT 1275CO first.", sources)
    assert (text, what) == ("Take MAT 1276CO first.", "MAT 1275CO -> MAT 1276CO")
    text, _ = jp.plant_number("Take EET3212 first.", [chunk("EET3212 is offered.")])
    assert text == "Take EET3213 first."
    # the same digits elsewhere in the sources (even in a header) rule a replacement out
    sources = [chunk("EET 3212 is offered; see room 3213.")]
    assert jp.plant_number("Take EET 3212.", sources)[0] == "Take EET 3214."


def test_thousands_separators_and_decimals():
    assert jp.replacement("1,000", "") == "1,001"
    assert jp.replacement("2.0", "") == "3.0"


def test_plants_are_made_only_for_yes_labeled_non_abstain_items_with_a_shared_token():
    src = [chunk("It costs 66 credits.")]
    yes = item("a|r", "It needs 66 credits.", src, {"faithfulness": "yes"})
    partly = item("b|r", "It needs 66 credits.", src, {"faithfulness": "partly"})
    abstain = item("c|r", "ABSTAIN: the sources do not list 66.", src, {"faithfulness": "yes"})
    none = item("d|r", "No numbers.", src, {"faithfulness": "yes"})
    planted = jp.number_plants([yes, partly, abstain, none])
    assert [p.key for p in planted] == ["plant:a|r"] and planted[0].expected_not_yes
    assert planted[0].answer == "It needs 67 credits." and planted[0].sources == src


def test_cross_pairs_use_the_baseline_answer_with_the_on_run_sources():
    base = item("q22|baseline-dev-60-v3", "baseline answer", [chunk("old")], {})
    on = item("q22|on-run1", "on answer", [chunk("new")], {})
    pairs = jp.cross_pairs([base, on, item("q99|on-run1", "x", [], {})])
    assert [p.key for p in pairs] == ["cross:q22"]
    assert pairs[0].answer == "baseline answer" and pairs[0].sources[0]["text"] == "new"
    assert pairs[0].expected_not_yes and pairs[0].kind == "plant_cross"


# ---- claims derivation ----


@pytest.mark.parametrize(
    ("statuses", "faithfulness"),
    [([], "yes"), (["supported", "supported"], "yes"), (["supported", "not_in_sources"], "partly"),
     (["contradicted", "supported"], "no"), (["not_in_sources", "contradicted"], "no")],
)  # fmt: skip
def test_faithfulness_is_derived_from_claim_statuses(statuses, faithfulness):
    assert jv.derive_faithfulness(statuses) == faithfulness


def test_claims_and_status_parsing():
    assert jv.parse_claims('{"claims": ["a", "b"]}') == ["a", "b"]
    assert jv.parse_claims('{"claims": []}') == []
    for bad in ("x", "[]", '{"claims": "a"}', '{"claims": [1]}', '{"claims": [""]}'):
        assert jv.parse_claims(bad) is None
    ok = '{"verdicts": [{"claim": 1, "status": "supported", "reason": "r"}, {"claim": 2, "status": "contradicted"}]}'
    assert jv.parse_statuses(ok, 2) == ["supported", "contradicted"]
    assert jv.parse_statuses(ok, 3) is None  # a missing claim
    assert jv.parse_statuses(ok.replace('"claim": 2', '"claim": 5'), 2) is None
    assert jv.parse_statuses(ok.replace("contradicted", "maybe"), 2) is None


def test_the_claims_prompts_are_general_and_carry_the_pre_registered_rules():
    text = jv.EXTRACT_INSTRUCTIONS + jv.VERIFY_INSTRUCTIONS
    assert "do not state X" in jv.VERIFY_INSTRUCTIONS and "contradicted" in jv.VERIFY_INSTRUCTIONS
    assert (
        'returns {"claims": []}' in jv.EXTRACT_INSTRUCTIONS.replace("return {", "returns {")
        or '{"claims": []}' in jv.EXTRACT_INSTRUCTIONS
    )
    for needle in ("MAT", "CST", "EET", "q22", "q40", "q52", "q15", "Calculus", "Dental"):
        assert needle not in text


# ---- a stub client: variants and settings ----


class Client:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=100,
            prompt_tokens_details=SimpleNamespace(cached_tokens=500),
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))],
            usage=usage,
        )


V3_REPLY = json.dumps(
    {
        "correctness": "partial",
        "correctness_reason": "c",
        "faithfulness": "yes",
        "faithfulness_reason": "f",
    }
)


def test_variant_settings_v3_unchanged_v4_reason_low_effort_without_temperature():
    sp = jv.specs(CFG)
    assert (sp["v3"].reasoning, sp["v3"].temperature) == ("none", 0)
    assert (sp["v4-reason"].reasoning, sp["v4-reason"].temperature) == ("low", None)
    client = Client([V3_REPLY, V3_REPLY])
    it = item(sources=[chunk("t")])
    jv.judge_item(client, CFG, "v3", it)
    jv.judge_item(client, CFG, "v4-reason", it)
    first, second = client.calls
    assert first["temperature"] == 0 and first["reasoning_effort"] == "none"
    assert "temperature" not in second and second["reasoning_effort"] == "low"
    assert first["messages"] == second["messages"]  # the same rubric text, the same input
    assert first["messages"][0]["content"].startswith(
        "You grade answers given by a student-help assistant"
    )


def test_v4_claims_takes_correctness_from_v3_and_derives_faithfulness():
    client = Client(
        [
            '{"claims": ["a claim"]}',
            '{"verdicts": [{"claim": 1, "status": "contradicted", "reason": "r"}]}',
        ]
    )
    out = jv.judge_item(
        client, CFG, "v4-claims", item(sources=[chunk("t")]), {"correctness": "partial"}
    )
    assert (
        out["correctness"] == "partial"
        and out["faithfulness"] == "no"
        and out["claims"] == ["a claim"]
    )
    assert (
        len(client.calls) == 2 and "Numbered sources" in client.calls[1]["messages"][1]["content"]
    )
    none = Client(['{"claims": []}'])
    out = jv.judge_item(none, CFG, "v4-claims", item(), {"correctness": "incorrect"})
    assert (out["faithfulness"], len(none.calls)) == ("yes", 1)  # no claim, no verification call
    bad = Client(["not json"])
    assert (
        jv.judge_item(bad, CFG, "v4-claims", item(), {"correctness": "correct"})["faithfulness"]
        is None
    )


def test_cached_prompt_tokens_are_charged_at_the_cached_price():
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=100,
        prompt_tokens_details=SimpleNamespace(cached_tokens=500),
    )
    price = CFG["models"][CFG["judge_model"]]
    expected = (500 * price["input"] + 500 * price["cached_input"] + 100 * price["output"]) / 1e6
    assert jv.call_cost(CFG, usage) == pytest.approx(expected)
    plain = SimpleNamespace(prompt_tokens=1000, completion_tokens=0)
    assert jv.call_cost(CFG, plain) == pytest.approx(1000 * price["input"] / 1e6)


# ---- the selection rule ----


def make_results(v3, v4r, v4c, keys):
    """Each argument: a function (run, key) -> (correctness, faithfulness)."""
    out = {}
    for name, fn in (("v3", v3), ("v4-reason", v4r), ("v4-claims", v4c)):
        out[name] = [
            {
                k: dict(zip(("correctness", "faithfulness"), fn(r, k), strict=True)) | {"cost": 0.0}
                for k in keys
            }
            for r in (0, 1)
        ]
    return out


def labeled(n=16):
    return [
        item(f"r{i}|run", label={"correctness": "partial", "faithfulness": "yes"}) for i in range(n)
    ]


def test_a_variant_qualifies_only_if_all_four_criteria_hold_and_v3_is_the_control():
    real = labeled()
    plants = [item(f"p{i}", kind="plant_number") for i in range(10)]
    keys = [i.key for i in real + plants]

    def perfect(run, k):
        return ("partial", "no") if k.startswith("p") else ("partial", "yes")

    def v3(run, k):  # the control misses two planted errors and one real item
        if k == "r0|run":
            return ("partial", "no")
        return ("partial", "yes") if k in ("p0", "p1", "p2") else perfect(run, k)

    results = make_results(v3, perfect, perfect, keys)
    ev = jv.evaluate(results, real, plants)
    assert ev["v3"]["planted_caught"] == [7, 7] and ev["v3"]["faithfulness_wrong"] == [
        ["r0|run"],
        ["r0|run"],
    ]
    assert ev["v4-reason"]["qualifies"] and ev["v4-claims"]["qualifies"]
    assert jv.choose(ev, results, real) == "v4-reason"  # equal agreement: the simpler one


def test_each_criterion_can_fail():
    real, plants = labeled(), [item(f"p{i}", kind="plant_number") for i in range(10)]
    keys = [i.key for i in real + plants]
    good = lambda run, k: ("partial", "no") if k.startswith("p") else ("partial", "yes")  # noqa: E731

    def two_wrong(run, k):
        return (
            ("partial", "no")
            if k in ("r0|run", "r1|run") or k.startswith("p")
            else ("partial", "yes")
        )

    def two_missed(run, k):
        return ("partial", "yes") if k in ("p0", "p1") else good(run, k)

    def worse_correctness(run, k):
        return ("correct", good(run, k)[1]) if k == "r3|run" else good(run, k)

    def flip(run, k):
        if k in ("r0|run", "r1|run") and run == 1:
            return ("partial", "no")  # differs from run 0 (yes)
        return good(run, k)

    ev = jv.evaluate(make_results(good, two_wrong, good, keys), real, plants)
    assert ev["v4-reason"]["criteria"][1] is False and ev["v4-claims"]["qualifies"]
    ev = jv.evaluate(make_results(good, two_missed, good, keys), real, plants)
    assert ev["v4-reason"]["criteria"][2] is False
    ev = jv.evaluate(make_results(good, worse_correctness, good, keys), real, plants)
    assert ev["v4-reason"]["criteria"][3] is False and ev["v4-reason"]["qualifies"] is False
    ev = jv.evaluate(make_results(good, flip, good, keys), real, plants)
    assert ev["v4-reason"]["flips"] == 2 and ev["v4-reason"]["criteria"][4] is False


def test_the_excluding_q15_count_and_the_no_qualifier_default():
    real = labeled(3) + [
        item("q15|on-run1", label={"correctness": "partial", "faithfulness": "yes"})
    ]
    plants = [item(f"p{n}", kind="plant_number") for n in range(3)]
    keys = [i.key for i in real + plants]

    def bad_q15(run, k):
        return ("partial", "no") if k.startswith("p") or k == "q15|on-run1" else ("partial", "yes")

    results = make_results(bad_q15, bad_q15, bad_q15, keys)
    ev = jv.evaluate(results, real, plants)
    assert ev["v4-reason"]["faithfulness_wrong"] == [["q15|on-run1"]] * 2
    assert ev["v4-reason"]["faithfulness_wrong_excluding_q15_on"] == [0, 0]
    broken = make_results(
        bad_q15, lambda run, k: ("partial", "yes"), lambda run, k: ("partial", "yes"), keys
    )
    assert jv.choose(jv.evaluate(broken, real, plants), broken, real) == "v3"


def test_a_run_stops_before_the_budget_saves_what_it_finished_and_resumes(tmp_path):
    items = [item(f"i{n}|run", sources=[chunk("t")]) for n in range(3)]
    triple = [V3_REPLY, V3_REPLY, '{"claims": []}']
    partial = tmp_path / "partial.json"
    with pytest.raises(jv.BudgetStop, match="rerun with a bigger --budget"):
        jv.run(Client(triple * 3), CFG, items, 0.04, out=lambda *_: None, partial=partial)
    saved = json.loads(partial.read_text())
    assert sorted(saved) == sorted(f"{v}|0|i{n}|run" for n in (0, 1) for v in jv.VARIANTS)
    client = Client(
        triple * 10
    )  # a bigger budget continues: item i2 of run 1, then the whole second run
    results, spent = jv.run(client, CFG, items, 1.0, out=lambda *_: None, partial=partial)
    assert len(client.calls) == 3 + 9 and all(
        len(results[v][r]) == 3 for v in jv.VARIANTS for r in (0, 1)
    )
    assert spent == pytest.approx(sum(r["cost"] for r in json.loads(partial.read_text()).values()))
