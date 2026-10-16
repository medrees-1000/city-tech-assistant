"""Step 3b: answer.format_rule (off | on) and the detectors F1 to F3. No model call."""

import hashlib
import json
from datetime import date

import pytest

from cta import answer as ans_mod
from cta.eval import format_check as fc
from cta.graph import build
from cta.settings import ROOT, load_models
from tests.test_router import Script, make_router

TODAY = date(2026, 10, 11)
CHUNKS = [
    {"id": "page/x#1", "kind": "section", "source": "https://example.edu/p", "heading_path": "H",
     "terms": ["Fall 2026"], "last_updated": None, "text": "some text"}
]  # fmt: skip
STORED = json.loads((ROOT / "tests/fixtures/format_rule_answers.json").read_text(encoding="utf-8"))
# SHA-256 of cta.answer.INSTRUCTIONS as it stood before step 3b (git 9e72079)
INSTRUCTIONS_SHA256 = "639e1e2dbbc8a42416fb4a631f9355ee8143f6912120f2fdaa02738bfeed85c6"
TIERS = """For Fall 2026, the due date depends on when you first registered [1]:
- March 19 to July 19: August 3 [1]
- July 20 to August 7: August 14 [1]
- August 8 to 27: August 27 [1]
- August 28 or later: immediately upon registration [1]"""


# ---- the switch ----


def test_the_default_is_off_and_off_is_todays_prompt_byte_for_byte():
    cfg = load_models(env={})
    assert cfg["answer"]["format_rule"] == "off"
    off = ans_mod.build_messages(CHUNKS, TODAY, "Q?")
    assert hashlib.sha256(ans_mod.INSTRUCTIONS.encode()).hexdigest() == INSTRUCTIONS_SHA256
    assert off[0]["content"] == ans_mod.INSTRUCTIONS
    assert ans_mod.build_messages(CHUNKS, TODAY, "Q?", "off") == off


def test_on_changes_only_the_system_prompt_and_only_by_the_one_rule():
    off = ans_mod.build_messages(CHUNKS, TODAY, "Q?")
    on = ans_mod.build_messages(CHUNKS, TODAY, "Q?", "on")
    assert on[1] == off[1] and on[0]["role"] == "system"
    assert on[0]["content"] == off[0]["content"] + ans_mod.FORMAT_RULE
    assert ans_mod.FORMAT_RULE == (
        "7. When the sources give several dates or tiers that depend on a condition "
        "(for example, when you first registered), write a short bullet list, one per line, "
        "each tier with its date; keep the sentence before the list to one line and state the "
        "condition in it. Otherwise answer in sentences, as before.\n"
    )


def test_the_setting_is_validated_and_the_env_override_works():
    assert load_models(env={"CTA_ANSWER_FORMAT_RULE": "on"})["answer"]["format_rule"] == "on"
    with pytest.raises(ValueError, match="format_rule"):
        load_models(env={"CTA_ANSWER_FORMAT_RULE": "maybe"})


def test_calendar_answers_are_identical_with_the_rule_on(monkeypatch):
    events = build.load_events()
    texts = []
    for rule in ("off", "on"):
        env = {"CTA_RERANK": "off", "CTA_ROUTER_MODE": "on", "CTA_ROUTER_SELECTOR": "1",
               "CTA_ROUTER_CHAIN": "off", "CTA_ANSWER_FORMAT_RULE": rule}  # fmt: skip
        cfg = load_models(env=env)
        script = Script("calendar", "Fall 2026", ["fall-2026-040"])
        router, _ = make_router(script, monkeypatch, events, cfg)
        question = "Last day to withdraw with a W in Fall 2026?"
        texts.append(router.answer(question, TODAY, log=False).text)
    assert texts[0] == texts[1] and texts[0].startswith("**Friday, November 6, 2026**")


# ---- the detectors on made-up answers ----


def test_dates_are_found_and_normalised():
    assert fc.dates_in("March 19-July 19: August 3; 10/09, 11/27/2026") == {
        (3, 19), (7, 19), (8, 3), (10, 9), (11, 27)}  # fmt: skip
    assert fc.dates_in("Sept. 3 and Sep 4 but not 2026 or 12 students") == {(9, 3), (9, 4)}
    assert fc.dates_in("no dates here") == set()


def test_f1_needs_three_dated_bullets_and_no_lost_date():
    before = [STORED["q13"]["luna_run1"]]
    ok, why = fc.f1(TIERS, before)
    assert ok, why
    assert not fc.f1(STORED["q13"]["luna_run1"], before)[0]  # the run-on sentence: no bullets
    two = "\n".join(TIERS.splitlines()[:3])
    assert not fc.f1(two, before)[0]  # two bullets only
    lost = TIERS.replace("August 3", "early August")
    ok, why = fc.f1(lost, before)
    assert not ok and "lost" in why


def test_f2_a_one_fact_answer_is_not_a_list():
    assert fc.f2("The deadline is October 5, 2026. [1]")[0]
    assert fc.f2("- only one bullet [1]")[0]
    assert not fc.f2("- first [1]\n- second [1]")[0]


def test_f3_the_condition_is_still_stated():
    assert fc.f3(TIERS)[0]
    assert fc.f3("Due date depends on when you   first registered.")[0]
    assert not fc.f3("March 19 to July 19: August 3")[0]


def test_the_trigger_chunk_has_three_dated_rows():
    table = (
        "| Registered | Due |\n|---|---|\n| March 19-July 19 | August 3 |\n"
        "| July 20-August 7 | August 14 |\n| August 8-27 | August 27 |"
    )
    assert fc.has_date_rows(table)
    prose = "A paragraph with August 3 and August 14 and August 27 in prose."
    assert not fc.has_date_rows(prose)
    assert not fc.has_date_rows("- one list item August 3\n- another without a date")


def test_f2_prime_fails_only_where_every_before_answer_was_not_a_list():
    one_fact = "The deadline is October 5, 2026. [1]"
    listed = "- first [1]\n- second [1]"
    assert fc.f2_prime(one_fact, [one_fact])[0]
    assert not fc.f2_prime(listed, [one_fact, one_fact, one_fact])[0]
    assert fc.f2_prime("- only one [1]", [one_fact])[0]
    # one before answer was already a list: a list now is not a new failure
    assert fc.f2_prime(listed, [one_fact, listed, one_fact])[0]
    q13 = STORED["q13"]["luna_run1"]
    assert not fc.f2_prime(TIERS, [q13])[0]  # a list after run-on answers: q13 is outside F2'


# ---- the detectors on stored answers (luna, modelexp-luna-run1) ----


def test_stored_answers_the_run_on_q13_fails_f1_and_the_one_fact_answers_pass_f2():
    q13 = STORED["q13"]["luna_run1"]
    assert fc.f3(q13)[0] and fc.f2(q13)[0] and not fc.f1(q13, [q13])[0]
    assert len(fc.dates_in(q13)) == 9
    for qid in ("q14", "q54", "q59"):
        assert fc.f2(STORED[qid]["luna_run1"])[0], qid
