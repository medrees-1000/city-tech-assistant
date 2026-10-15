"""Near-miss helper (docs/decisions.md, "Near-miss helper"). No network, no database, no paid call.
Only dev questions are read."""

import dataclasses
import json
import re
from datetime import date

import pytest

from cta import answer as answer_module
from cta.answer import (
    NEAR_MISS_INTRO,
    THRESHOLD_ABSTAIN,
    Answer,
    closest_pages,
    is_near_miss,
    near_miss_text,
    page_key,
)
from cta.eval import run_answers as ra
from cta.index.search import Search
from cta.settings import ROOT, load_models
from tests.test_api import Client, ask, make_client_app, retrieve_answer

CFG = load_models(env={})
CUTOFF, MARGIN = CFG["answer"]["abstain_threshold"], CFG["answer"]["near_miss_margin"]
TODAY = date(2026, 10, 15)


def chunk(cid, source, heading="A heading", sim=None):
    row = {"id": cid, "kind": "section", "source": source, "heading_path": heading, "text": "t",
           "doc_type": "faq", "term": None, "terms": [], "last_updated": None}  # fmt: skip
    if sim is not None:
        row["similarity"] = sim
    return row


PAGE_A = "https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx"
PAGE_B = "https://www.citytech.cuny.edu/bursar/payment-plan.aspx"
PAGE_C = "https://www.citytech.cuny.edu/registrar/faqs.aspx"


def stub_search(monkeypatch, top, results):
    found = Search(results, False, 0, 0, 0.0, top_vector_similarity=top)
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: found)


class NoModel:
    """A client that fails the test if anything calls the model."""

    def __call__(self):
        raise AssertionError("the near-miss helper must not call a model")


# ---- the settings ----


def test_the_default_margin_is_0_04_and_the_cutoff_is_still_0_59():
    assert (CUTOFF, MARGIN) == (0.59, 0.04)


def test_the_margin_can_be_switched_off_overridden_and_is_checked():
    assert load_models(env={"CTA_NEAR_MISS_MARGIN": "0"})["answer"]["near_miss_margin"] == 0.0
    assert load_models(env={"CTA_NEAR_MISS_MARGIN": "0.02"})["answer"]["near_miss_margin"] == 0.02
    for bad in ("x", "-0.1", "0.59", "1"):
        with pytest.raises(ValueError, match="near_miss_margin"):
            load_models(env={"CTA_NEAR_MISS_MARGIN": bad})


# ---- (c) boundaries ----


def test_exactly_cutoff_minus_margin_is_included_just_below_is_not_and_the_cutoff_is_not():
    low = round(CUTOFF - MARGIN, 10)  # 0.55
    assert is_near_miss(low, CUTOFF, MARGIN) is True  # exactly cutoff - margin
    assert is_near_miss(low - 1e-6, CUTOFF, MARGIN) is False  # just below
    assert is_near_miss(CUTOFF - 1e-6, CUTOFF, MARGIN) is True  # just under the cutoff
    assert (
        is_near_miss(CUTOFF, CFG["answer"]["abstain_threshold"], MARGIN) is False
    )  # exactly the cutoff
    assert is_near_miss(0.8, CUTOFF, MARGIN) is False
    assert is_near_miss(0.55, 0.59, 0.04) is True  # the float case: 0.59 - 0.04 is not exactly 0.55


def test_margin_zero_switches_the_helper_off():
    assert is_near_miss(0.58, CUTOFF, 0) is False


@pytest.mark.parametrize(
    ("top", "expect"),
    [(0.55, True), (0.5499, False), (0.576, True), (0.568, True), (0.549, False), (0.59, False)],
)
def test_the_tester_and_band_review_values(top, expect):
    assert (
        is_near_miss(top, CUTOFF, MARGIN) is expect
    )  # 0.549 is the advisor walk-in: not a near-miss


# ---- the pages ----


def test_two_chunks_of_the_same_page_show_one_page_and_the_order_is_the_pipelines():
    results = [chunk("page/bursar/payment-deadlines#1", PAGE_A, "Bill Payment Deadlines"),
               chunk("page/bursar/payment-deadlines#4", PAGE_A, "Fall 2026 Payment Due Dates"),
               chunk("page/bursar/payment-plan#1", PAGE_B, "Nelnet Tuition Payment Plan"),
               chunk("page/registrar/faqs#2", PAGE_C)]  # fmt: skip
    pages = closest_pages(results)
    assert [p["id"] for p in pages] == [
        "page/bursar/payment-deadlines#1",
        "page/bursar/payment-plan#1",
    ]


def test_fewer_than_two_distinct_pages_show_one_and_pdf_files_and_courses_are_their_own_page():
    assert len(closest_pages([chunk("page/x#1", PAGE_A), chunk("page/x#2", PAGE_A)])) == 1
    pdf1 = chunk("pdf/refund#1", "data/pdfs/Award_Year_2026.pdf")
    pdf2 = chunk("pdf/refund#2", "data/pdfs/Award_Year_2026.pdf")
    assert page_key(pdf1) == page_key(pdf2) and len(closest_pages([pdf1, pdf2])) == 1
    c1 = chunk("catalog:MAT 1475", "catalog_course", "MAT 1475 - Calculus I")
    c2 = chunk("catalog:MAT 1575", "catalog_course", "MAT 1575 - Calculus II")
    assert [p["id"] for p in closest_pages([c1, c2])] == ["catalog:MAT 1475", "catalog:MAT 1575"]
    assert closest_pages([]) == []


def test_the_text_is_the_fixed_template_with_the_headings_and_markers_and_no_claim():
    pages = [chunk("a#1", PAGE_A, "Bill Payment Deadlines"), chunk("b#1", PAGE_B, "Nelnet Plan")]
    assert near_miss_text(pages) == (
        f"{NEAR_MISS_INTRO}\n\n- Bill Payment Deadlines [1]\n- Nelnet Plan [2]"
    )
    assert NEAR_MISS_INTRO.startswith(
        "ABSTAIN: I'm not sure my sources answer that, so I won't guess."
    )
    assert not any(
        ch.isdigit() for ch in NEAR_MISS_INTRO
    )  # no date, number or contact in the template


# ---- (a) answered questions are untouched, (c) no model call ----


def results():
    # similarities of the pages: payment-deadlines 0.576 (best chunk), payment-plan 0.562
    return [chunk("page/bursar/payment-deadlines#1", PAGE_A, "Bill Payment Deadlines", 0.576),
            chunk("page/bursar/payment-deadlines#4", PAGE_A, "Dues", 0.571),
            chunk("page/bursar/payment-plan#1", PAGE_B, "Nelnet Plan", 0.562)]  # fmt: skip


def run(monkeypatch, top, cfg=CFG, **kw):
    stub_search(monkeypatch, top, results())
    return answer_module.answer(None, "whats the tuition deadline", TODAY, cfg=cfg,
                                client_factory=NoModel(), log=False, **kw)  # fmt: skip


def test_a_near_miss_lists_the_two_closest_pages_and_is_still_an_abstention(monkeypatch):
    ans = run(monkeypatch, 0.576)
    assert ans.abstained and ans.abstain_reason == "below_threshold" and ans.near_miss
    assert ans.text.startswith("ABSTAIN:") and ans.text.startswith(NEAR_MISS_INTRO)
    assert ans.citations == [1, 2] and [s["id"] for s in ans.sources] == [
        "page/bursar/payment-deadlines#1", "page/bursar/payment-plan#1"]  # fmt: skip
    assert ans.prompt == [] and ans.chat_cost == 0.0  # no model call


def test_below_the_band_the_old_text_stays(monkeypatch):
    ans = run(monkeypatch, 0.549)
    assert (
        ans.text == THRESHOLD_ABSTAIN
        and not ans.near_miss
        and ans.abstain_reason == "below_threshold"
    )
    assert ans.citations == [] and len(ans.sources) == 3  # as before


def test_at_the_cutoff_it_answers_and_the_prompt_is_the_normal_one(monkeypatch):
    ans = run(monkeypatch, CUTOFF, dry_run=True)
    assert not ans.abstained and not ans.near_miss and ans.text == ""
    expected = answer_module.build_messages(results(), TODAY, "whats the tuition deadline", "off")
    assert ans.prompt == expected  # the answered path is exactly what it was


def test_margin_zero_gives_the_old_text(monkeypatch):
    cfg = load_models(env={"CTA_NEAR_MISS_MARGIN": "0"})
    ans = run(monkeypatch, 0.576, cfg=cfg)
    assert ans.text == THRESHOLD_ABSTAIN and not ans.near_miss


def test_other_abstain_reasons_are_never_near_misses():
    ans = Answer("ABSTAIN: nothing.", True, "model", [chunk("a#1", PAGE_A)], [], [], None)
    assert ans.near_miss is False and Answer.__dataclass_fields__["near_miss"].default is False


def test_every_dev_question_that_answered_through_retrieval_was_not_near_the_cutoff():
    # (a) in the stored runs a question answered through retrieval had a best similarity at or
    # above the cutoff, so the predicate is false for all of them
    dev_ids = set()
    for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines():
        if re.search(r'"split": ?"dev"', line):
            dev_ids.add(json.loads(line)["id"])
    checked = 0
    for label in ("tester1-dev", "tester1-new8"):
        run_data = json.loads((ROOT / f"eval/results/{label}.json").read_text(encoding="utf-8"))
        for r in run_data["per_question"]:
            if (
                r["id"] in dev_ids
                and not r["abstained"]
                and r["route"] in ("other", "calendar_fallthrough")
            ):
                top = max(c["similarity"] for c in r["retrieved"])
                assert not is_near_miss(top, CUTOFF, MARGIN), r["id"]
                checked += 1
    assert checked >= 20


# ---- the API: citations, flags, no topic call, contact logic ----


def near_miss_stub():
    pages = closest_pages(results())
    base = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    return dataclasses.replace(base, text=near_miss_text(pages), sources=pages,
                               citations=[1, 2], near_miss=True)  # fmt: skip


def test_the_api_returns_the_two_pages_as_citations_with_the_flags_and_no_topic_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, near_miss_stub())
    body = ask(c, "whats the tuition deadline").json()
    assert body["abstained"] is True and body["abstain_reason"] == "below_threshold"
    assert body["answer_type"] == "abstain" and body["how_found"]["near_miss"] is True
    assert body["answer"].startswith("I'm not sure my sources answer that, so I won't guess.")
    assert "- Bill Payment Deadlines [1]" in body["answer"] and "[2]" in body["answer"]
    assert [x["n"] for x in body["citations"]] == [1, 2] and all(
        x["cited"] for x in body["citations"]
    )
    assert body["citations"][0]["url"] == PAGE_A and body["citations"][1]["url"] == PAGE_B
    assert "topic" not in client.calls  # the topic sentence would have replaced the text
    assert body["contact"] is None  # contact policy v2: no office clearly applies here
    row = c.logs[0]
    assert row["abstained"] is True and row["abstain_reason"] == "below_threshold"
    assert row["trace"]["near_miss"] is True  # countable in the log


def test_a_plain_below_threshold_abstention_is_unchanged_through_the_api(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    body = ask(make_client_app(Client(), monkeypatch, stub), "whats the tuition deadline").json()
    assert body["citations"] == [] and body["how_found"]["near_miss"] is False
    assert not body["answer"].startswith("I'm not sure my sources answer that")


def test_the_eval_runner_still_reads_the_near_miss_text_as_an_abstention():
    from tests.test_run_answers import ans as stored_answer

    text = near_miss_text(closest_pages(results()))
    q = {"id": "q45", "question": "x", "gold_answer": "ABSTAIN", "gold_sources": [],
         "type": "unanswerable", "department": None, "split": "dev"}  # fmt: skip
    r = ra.evaluate_question(q, stored_answer(text, abstained=True), [], lambda m: ("", 0.0))
    assert r["correctness"] == "correct" and r["abstained"] is True


def test_guardrails_language_and_distress_are_untouched_by_the_flag():
    from cta.api import screen

    assert screen.screen("I want to kill myself", CFG["guardrails"]).reason == "distress"
    assert "near_miss" not in json.dumps(CFG["guardrails"])


# ---- tester round 1b, near-miss polish, item 1: a second page needs its own similarity ----

FLOOR = round(CUTOFF - MARGIN, 10)  # 0.55


def two(second_sim, third=None):
    out = [chunk("a#1", PAGE_A, "First", 0.576), chunk("b#1", PAGE_B, "Second", second_sim)]
    return out + ([third] if third else [])


def test_the_first_page_is_always_listed_even_with_a_low_similarity():
    assert [p["id"] for p in closest_pages([chunk("a#1", PAGE_A, "First", 0.40)], floor=FLOOR)] == [
        "a#1"
    ]


def test_a_second_page_exactly_at_cutoff_minus_margin_is_included_and_just_below_is_not():
    assert [p["id"] for p in closest_pages(two(0.55), floor=FLOOR)] == [
        "a#1",
        "b#1",
    ]  # exactly 0.55
    assert [p["id"] for p in closest_pages(two(0.5499), floor=FLOOR)] == ["a#1"]  # just below
    assert [p["id"] for p in closest_pages(two(round(0.59 - 0.04, 10)), floor=FLOOR)] == [
        "a#1",
        "b#1",
    ]


def test_a_second_page_with_no_stored_similarity_never_qualifies():
    results_ = [chunk("a#1", PAGE_A, "First", 0.576), chunk("b#1", PAGE_B, "Second")]
    assert [p["id"] for p in closest_pages(results_, floor=FLOOR)] == ["a#1"]


def test_a_pages_own_similarity_is_the_best_of_its_chunks():
    results_ = [chunk("a#1", PAGE_A, "First", 0.576), chunk("b#2", PAGE_B, "Weak chunk", 0.51),
                chunk("b#1", PAGE_B, "Strong chunk", 0.552)]  # fmt: skip
    pages = closest_pages(results_, floor=FLOOR)
    assert [p["id"] for p in pages] == ["a#1", "b#2"]  # the page shows its first chunk in order


def test_the_next_page_in_order_that_qualifies_is_the_second():
    third = chunk("c#1", PAGE_C, "Third", 0.553)
    assert [p["id"] for p in closest_pages(two(0.50, third), floor=FLOOR)] == ["a#1", "c#1"]


def test_without_a_floor_two_distinct_pages_are_listed_as_before_and_dedupe_is_unchanged():
    assert len(closest_pages(two(0.30))) == 2
    results_ = [chunk("a#1", PAGE_A, "x", 0.57), chunk("a#2", PAGE_A, "y", 0.56)]
    assert len(closest_pages(results_, floor=FLOOR)) == 1


def test_through_answer_a_low_second_page_is_dropped_and_a_good_one_is_kept(monkeypatch):
    stub_search(monkeypatch, 0.576, two(0.54))
    ans = answer_module.answer(None, "q", TODAY, cfg=CFG, client_factory=NoModel(), log=False)
    assert ans.near_miss and [s["id"] for s in ans.sources] == ["a#1"] and ans.citations == [1]
    assert ans.text.endswith("- First [1]") and "[2]" not in ans.text
    stub_search(monkeypatch, 0.576, two(0.551))
    ans = answer_module.answer(None, "q", TODAY, cfg=CFG, client_factory=NoModel(), log=False)
    assert ans.citations == [1, 2] and ans.text.endswith("- Second [2]")


# ---- a near-miss never applies to a personal-account refusal (found in the cue round) ----


def test_a_personal_account_refusal_carries_no_near_miss_pages_or_citations(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, near_miss_stub())
    body = ask(c, "what is my financial aid status").json()  # the API relabels this abstention
    assert body["abstain_reason"] == "personal_account"
    assert body["citations"] == [] and body["how_found"]["near_miss"] is False
    assert body["answer"] == "I could not find this in the City Tech sources I have."
    assert "closest pages" not in body["answer"]
    assert c.logs[0]["trace"]["near_miss"] is False  # not counted as a near-miss in the log


def test_a_plain_near_miss_is_unchanged_by_that_rule(monkeypatch):
    body = ask(
        make_client_app(Client(), monkeypatch, near_miss_stub()), "whats the tuition deadline"
    ).json()
    assert body["abstain_reason"] == "below_threshold" and body["how_found"]["near_miss"] is True
    assert [x["n"] for x in body["citations"]] == [1, 2]
