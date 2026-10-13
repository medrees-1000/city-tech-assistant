# ruff: noqa: E501
"""Step 4b: the chain walk, the extraction, the tool, the chain node and the switch (no network)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from cta.answer import Answer
from cta.eval import run_answers as ra
from cta.graph import build, classify
from cta.graph import chain as ch
from cta.graph.build import Router
from cta.index.search import Search
from cta.settings import load_models

CFG = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "on",
        "CTA_ROUTER_CONTACTS": "off",
        "CTA_ROUTER_CHAIN_RENDER": "model",  # these tests are about the model-written answer
    }
)
OFF = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "off",
        "CTA_ROUTER_CONTACTS": "off",
    }
)
TODAY = date(2026, 10, 11)


def rec(code, text="", style=None, title=None, dept="CST-NYT"):
    return {"code": code, "title": title or f"Title of {code}", "credits": 3, "description": f"About {code}.",
            "prerequisite_text": text, "prereq_style": style or ("text" if text else "none"), "rule_id": None,
            "course_group_id": "1", "department": dept, "department_name": "Dept", "fetched_at": "x", "programs": []}  # fmt: skip


def recs(*records):
    return {r["code"]: r for r in records}


# ---- the walk ----


def test_breadth_first_order_levels_and_course_count_are_deterministic():
    records = recs(
        rec("AA 1001", "PRE: BB 1001 & CC 1001"),
        rec("BB 1001", "PRE: DD 1001"),
        rec("CC 1001"),
        rec("DD 1001"),
    )
    first = ch.walk("AA 1001", records)
    assert [(n.code, n.level) for n in first.nodes] == [
        ("AA 1001", 0),
        ("BB 1001", 1),
        ("CC 1001", 1),
        ("DD 1001", 2),
    ]
    assert first.course_count == 4 and not first.truncated
    assert [n.code for n in ch.walk("AA 1001", records).nodes] == [n.code for n in first.nodes]


def test_a_cycle_ends():
    records = recs(
        rec("DEN 1100", "Corequisite: DEN 1112"), rec("DEN 1112", "Corequisite of DEN 1100.")
    )
    assert [n.code for n in ch.walk("DEN 1100", records).nodes] == ["DEN 1100", "DEN 1112"]


def test_the_depth_limit_is_4_and_is_recorded_exactly():
    chain = [rec(f"CC 100{i}", f"PRE: CC 100{i + 1}") for i in range(7)] + [rec("CC 1007")]
    result = ch.walk("CC 1000", recs(*chain))
    assert [n.level for n in result.nodes] == [0, 1, 2, 3, 4]
    assert result.truncated and result.unexpanded == [
        {"code": "CC 1004", "level": 4, "names": ["CC 1005"], "reason": "depth limit"}
    ]
    assert result.dropped == []


def test_the_course_cap_is_15_records_and_the_dropped_codes_are_recorded():
    kids = [f"KK {1000 + i}" for i in range(20)]
    records = recs(rec("AA 1001", "PRE: " + ", ".join(kids)), *[rec(k) for k in kids])
    result = ch.walk("AA 1001", records)
    assert result.course_count == 15 and result.truncated
    assert [d["code"] for d in result.dropped] == kids[14:] and all(
        d["named_by"] == "AA 1001" and d["reason"] == "course cap" for d in result.dropped
    )
    assert result.unexpanded == []


def test_no_record_codes_are_shown_but_do_not_count_toward_the_cap():
    result = ch.walk("AA 1001", recs(rec("AA 1001", "PRE: ENG 1101, PHYS 1433")))
    assert [(n.code, n.record is None) for n in result.nodes] == [
        ("AA 1001", False),
        ("ENG 1101", True),
        ("PHYS 1433", True),
    ]
    assert result.course_count == 1 and ch.chain_to_dict(result)["no_record"] == [
        "ENG 1101",
        "PHYS 1433",
    ]


def test_an_exclusion_is_listed_and_never_followed():
    records = recs(
        rec("AA 1001", "PRE: BB 1001. MUST NOT HAVE TAKEN XX 1001"),
        rec("BB 1001"),
        rec("XX 1001", "PRE: YY 1001"),
        rec("YY 1001"),
    )
    result = ch.walk("AA 1001", records)
    assert [n.code for n in result.nodes] == ["AA 1001", "BB 1001"]
    assert ch.chain_to_dict(result)["courses"][0]["exclusions"] == ["XX 1001"]


def test_unparsed_text_is_verbatim_and_nothing_is_expanded():
    records = recs(
        rec("AA 1001", "PRE: BB 1001"),
        rec("BB 1001", "PRE_CC1001_DD1001", "shorthand"),
        rec("CC 1001"),
    )
    data = ch.chain_to_dict(ch.walk("AA 1001", records))
    assert [c["code"] for c in data["courses"]] == ["AA 1001", "BB 1001"]
    assert (
        data["courses"][1]["unparsed"] == "shorthand text"
        and data["courses"][1]["text"] == "PRE_CC1001_DD1001"
    )
    truncated = ch.chain_to_dict(ch.walk("BB 1001", records))
    assert truncated["truncated"] is False  # UNPARSED is not a truncation


def test_or_text_conditions_and_bare_numbers_are_kept_as_written():
    records = recs(
        rec("AA 1001", "PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for AA 1001"),
        rec("MAT 1275"),
        rec("MAT 1275CO"),
    )
    data = ch.chain_to_dict(ch.walk("AA 1001", records))
    top = data["courses"][0]
    assert top["text"] == "PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for AA 1001"
    assert (
        top["codes"] == ["MAT 1275", "MAT 1275CO"]
        and top["or_wording"]
        and any("Placement" in c for c in top["conditions"])
    )
    bare = ch.parse_text("PRE: CST 1100 & 1101, C GRADE")
    assert bare.codes == ["CST 1100", "CST 1101"] and bare.inferred == ["CST 1101"]
    assert ch.parse_text("PRE: CST1201 & (2405 or 2415)").codes == [
        "CST 1201",
        "CST 2405",
        "CST 2415",
    ]


# ---- extraction ----

RECORDS = recs(rec("CST 2412", title="Data Security, Privacy, Ethics"), rec("CST 1204", title="Database Systems Fundamentals"),
               rec("CST 2304", title="Database Systems Fundamentals"), rec("CST 3504", title="Database Design"),
               rec("MAT 1475", title="Calculus I"), rec("MAT 2675", title="Calculus III"))  # fmt: skip


@pytest.mark.parametrize(
    "question",
    [
        "What do I need before CST 2412?",
        "what do i need before cst2412",
        "prerequisites for CST  2412?".replace("  ", " "),
        "CST 2412 and then CST2412 again?",
    ],
)
def test_code_forms_are_normalised_and_a_repeat_counts_once(question):
    got = ch.extract_course(question, RECORDS)
    assert (got.status, got.code) == ("code", "CST 2412")


def test_two_or_three_codes_are_asked_four_fall_through_and_seasons_are_not_codes():
    got = ch.extract_course(
        "What are the prerequisites for MAT 1190CO and how do they differ from MAT 1190?", RECORDS
    )
    assert got.status == "codes" and got.detail == ["MAT 1190CO", "MAT 1190"]
    assert got.code == "MAT 1190CO"
    three = ch.extract_course("Prerequisites of CST 1204, CST 2403 and CST 3601?", RECORDS)
    assert three.status == "codes" and three.detail == ["CST 1204", "CST 2403", "CST 3601"]
    four = ch.extract_course("CST 1204, CST 2403, CST 3601 and CST 3504?", RECORDS)
    assert four.status == "many" and four.code is None and len(four.detail) == 4
    assert (
        ch.extract_course("What do I need before CST 2412 in Fall 2026?", RECORDS).code
        == "CST 2412"
    )
    assert ch.extract_course("Is MAT 2675 offered in spring 2027?", RECORDS).status == "code"


def test_an_unknown_code_is_still_a_code_for_the_abstain_path():
    assert ch.extract_course("What do I need before ENG 1101?", RECORDS) == ch.Extraction(
        "code", "ENG 1101", []
    )


def test_a_unique_exact_title_is_found_case_insensitively():
    got = ch.extract_course("what do i need to take before database design?", RECORDS)
    assert (got.status, got.code) == ("title", "CST 3504")


def test_an_ambiguous_title_two_titles_or_none_do_not_extract():
    assert (
        ch.extract_course("What do I need before Database Systems Fundamentals?", RECORDS).status
        == "ambiguous"
    )
    assert (
        ch.extract_course("Compare Database Design and Calculus I please", RECORDS).status
        == "ambiguous"
    )
    assert ch.extract_course("What is the registrar's phone number?", RECORDS).status == "none"
    assert (
        ch.extract_course("Tell me about Calculus I", RECORDS).code == "MAT 1475"
    )  # 'Calculus I' is not inside 'Calculus III'
    assert ch.extract_course("Tell me about Calculus III", RECORDS).code == "MAT 2675"


def test_a_code_wins_over_a_title():
    assert (
        ch.extract_course("Calculus III (MAT 2675): what comes first?", RECORDS).code == "MAT 2675"
    )


# ---- the tool ----


def test_the_tool_has_a_name_a_description_and_an_argument_schema(monkeypatch):
    assert (
        ch.prerequisite_chain.name == "prerequisite_chain"
        and "prerequisite" in ch.prerequisite_chain.description
    )
    assert list(ch.prerequisite_chain.args) == ["course_code"]
    monkeypatch.setattr(
        ch, "load_records", lambda *a, **k: recs(rec("AA 1001", "PRE: BB 1001"), rec("BB 1001"))
    )
    out = ch.prerequisite_chain.invoke({"course_code": "aa1001"})
    assert (
        out["found"]
        and out["root"] == "AA 1001"
        and [c["code"] for c in out["courses"]] == ["AA 1001", "BB 1001"]
    )
    assert ch.prerequisite_chain.invoke({"course_code": "ZZ 9999"}) == {
        "found": False,
        "code": "ZZ 9999",
    }


def test_messages_have_numbered_course_sources_a_truncation_note_outside_them_and_unparsed_flags():
    records = recs(rec("AA 1001", "PRE: BB 1001"), rec("BB 1001", "PRE_X", "shorthand"))
    result = ch.chain_to_dict(ch.walk("AA 1001", records))
    sources = ch.sources_of(result, records)
    assert [s["id"] for s in sources] == ["catalog:AA 1001", "catalog:BB 1001"]
    text = ch.build_messages("Q?", TODAY, result, sources)[1]["content"]
    assert (
        "UNPARSED (shorthand text)" in text
        and "Truncation note" not in text
        and "Question: Q?" in text
    )
    cut = ch.chain_to_dict(
        ch.walk(
            "CC 1000",
            recs(
                *([rec(f"CC 100{i}", f"PRE: CC 100{i + 1}") for i in range(7)] + [rec("CC 1007")])
            ),
        )
    )
    note = ch.describe(cut)
    assert (
        "Truncation note: the chain was cut. CC 1004 (level 4) names CC 1005, not followed (depth limit)."
        in note
    )
    assert all(
        "Truncation" not in s["text"]
        for s in ch.sources_of(cut, recs(*[rec(f"CC 100{i}") for i in range(5)]))
    )


def test_the_chain_prompt_is_the_committed_file():
    text = ch.instructions()
    assert text.startswith(
        "You answer a City Tech (CUNY) student's question about which courses come before"
    )
    for needle in ("UNPARSED", "must not have", 'Report "and" and "or" exactly', "truncation note"):
        assert needle in text


# ---- the classifier switch ----


def test_the_classifier_text_is_the_4a_one_with_chain_off_and_v2_with_it_on():
    assert (
        classify.instructions(OFF) == classify.INSTRUCTIONS
        and '"prerequisite"' not in classify.INSTRUCTIONS
    )
    v2 = classify.instructions(CFG)
    assert (
        v2 == classify.CLASSIFY_V2.read_text() and '"calendar" or "prerequisite" or "other"' in v2
    )
    assert "description, credits, schedule, who teaches" in v2


def test_prerequisite_is_a_valid_intent_only_with_chain_on():
    data = {"intent": "prerequisite", "term_mention": None}
    assert classify.parse_classification(data) is None
    assert classify.parse_classification(data, ("calendar", "prerequisite", "other")) == (
        "prerequisite",
        None,
    )


def test_chain_switch_default_is_on_and_the_flag_and_env_turn_it_off():
    assert load_models(env={})["router"]["chain"] == "on"  # on by default since step 4b-final
    assert (
        load_models(env={"CTA_ROUTER_CHAIN": "off", "CTA_ROUTER_CONTACTS": "off"})["router"][
            "chain"
        ]
        == "off"
    )
    assert (
        load_models(env={"CTA_ROUTER_CHAIN": "on", "CTA_ROUTER_CONTACTS": "off"})["router"]["chain"]
        == "on"
    )
    with pytest.raises(ValueError, match="router.chain"):
        load_models(env={"CTA_ROUTER_CHAIN": "maybe"})
    assert 'chain: "on"' in (ra.ROOT / "config" / "models.yaml").read_text()


def test_the_runner_flag_sets_the_switch(monkeypatch):
    from contextlib import nullcontext

    seen = {}
    monkeypatch.setattr(ra, "connect", lambda: nullcontext(None))
    monkeypatch.setattr(
        ra, "estimate_run", lambda conn, qs, cfg, *a: seen.update(cfg["router"]) or (5.0, [])
    )
    monkeypatch.setattr(ra, "RESULTS", __import__("pathlib").Path("/tmp/none-4b"))
    ra.main(["x", "--split", "dev", "--label", "zz-chain-flag", "--chain", "on"])
    assert seen["chain"] == "on"
    ra.main(["x", "--split", "dev", "--label", "zz-chain-flag", "--chain", "off"])
    assert seen["chain"] == "off"


# ---- the graph ----


class Client:
    def __init__(self, intent="prerequisite", answer="Chain answer [1]."):
        self.intent, self.answer_text, self.calls = intent, answer, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        system = kw["messages"][0]["content"]
        which = (
            "classify"
            if system.startswith("You route")
            else "chain"
            if system.startswith(
                "You answer a City Tech (CUNY) student's question about which courses"
            )
            else "other"
        )
        self.calls.append(which)
        reply = (
            json.dumps({"intent": self.intent, "term_mention": None})
            if which == "classify"
            else self.answer_text
        )
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=usage
        )


def make_router(client, monkeypatch, records, cfg=CFG):
    monkeypatch.setattr(ch, "load_records", lambda *a, **k: records)
    stub = Answer(
        "old path [1]", False, None, [{"id": "c1"}], [1], [], Search([], False, 0, 0, 0.0)
    )
    seen = []
    monkeypatch.setattr(build, "answer", lambda *a, **k: seen.append(k) or stub)
    return Router(None, cfg, lambda: client, events=[], contact="c"), seen


WORLD = recs(
    rec("AA 1001", "PRE: BB 1001"),
    rec("BB 1001", "PRE: ENG 1101"),
    rec("DD 1001", "PRE_X", "shorthand"),
)


def test_a_prerequisite_question_is_answered_by_the_chain_node(monkeypatch):
    client = Client()
    router, seen = make_router(client, monkeypatch, WORLD)
    ans = router.answer("What do I need before AA 1001?", TODAY, log=False)
    assert client.calls == ["classify", "chain"] and seen == []
    assert (
        ans.route == "chain"
        and ans.text == "Chain answer [1]."
        and ans.citations == [1]
        and not ans.abstained
    )
    assert [s["id"] for s in ans.sources] == ["catalog:AA 1001", "catalog:BB 1001"]
    info = ans.router["chain"]
    assert (
        info["course_count"] == 2
        and info["truncated"] is False
        and info["no_record_codes"] == ["ENG 1101"]
    )
    assert (
        info["source_ids"] == ["catalog:AA 1001", "catalog:BB 1001"]
        and ans.router["chain_fallthrough"] is False
    )
    assert ans.prompt_tokens == 200 and ans.chat_cost > 0


def test_the_chain_answer_step_uses_the_answer_settings(monkeypatch):
    seen = {}
    client = Client()
    orig = client.create

    def spy(**kw):
        if kw["messages"][0]["content"].startswith("You answer"):
            seen.update(kw)
        return orig(**kw)

    client.chat.completions.create = spy
    router, _ = make_router(client, monkeypatch, WORLD)
    router.answer("What do I need before AA 1001?", TODAY, log=False)
    a = CFG["answer"]
    assert (seen["temperature"], seen["top_p"], seen["model"]) == (
        a["temperature"],
        a["top_p"],
        CFG["chat_model"],
    )


@pytest.mark.parametrize(
    "question", ["What do I need before CST 4999?", "What do I need before ENG 1101?"]
)
def test_a_code_with_no_record_abstains_without_a_model_answer_and_without_contact(
    monkeypatch, question
):
    client = Client()
    router, seen = make_router(client, monkeypatch, WORLD)
    ans = router.answer(question, TODAY, log=False)
    code = question.split(" before ")[1].rstrip("?")
    assert client.calls == ["classify"] and seen == [] and ans.route == "abstain" and ans.abstained
    assert (
        ans.text
        == f"ABSTAIN: No record exists in the catalog data for {code} in the four departments (CST, Math, EET, Dental Hygiene)."
    )
    assert (
        "@" not in ans.text
        and "Contact" not in ans.text
        and ans.router["chain"]["no_record"] is True
    )


@pytest.mark.parametrize(
    "question",
    [
        "What are the prerequisites for AA 1001 and BB 1001?",
        "What do I need to take before the calculus course?",
    ],
)
def test_two_codes_or_no_course_fall_through_to_retrieve(monkeypatch, question):
    client = Client()
    router, seen = make_router(client, monkeypatch, WORLD)
    ans = router.answer(question, TODAY, log=False)
    assert client.calls == ["classify"] and len(seen) == 1 and seen[0]["log"] is False
    assert (
        ans.route == "chain_fallthrough"
        and ans.text == "old path [1]"
        and ans.router["chain_fallthrough"] is True
    )
    assert ans.router["chain"]["fallthrough"] is True


def test_other_and_calendar_routes_are_unchanged_with_chain_on(monkeypatch):
    router, seen = make_router(Client("other"), monkeypatch, WORLD)
    ans = router.answer("How do I apply for graduation?", TODAY, log=False)
    assert ans.route == "other" and len(seen) == 1 and "chain" not in ans.router


def test_with_chain_off_the_classifier_cannot_reach_the_chain_node(monkeypatch):
    client = Client("prerequisite")  # a model that ignores the 4a text and says prerequisite
    router, seen = make_router(client, monkeypatch, WORLD, OFF)
    ans = router.answer("What do I need before AA 1001?", TODAY, log=False)
    assert ans.route == "other" and ans.router["classify"]["failed"] is True and len(seen) == 1


def test_a_truncated_chain_tells_the_answerer_in_the_prompt_not_in_the_sources(monkeypatch):
    chain = [rec(f"CC 100{i}", f"PRE: CC 100{i + 1}") for i in range(7)] + [rec("CC 1007")]
    client = Client()
    seen_user = {}
    orig = client.create

    def spy(**kw):
        if kw["messages"][0]["content"].startswith("You answer"):
            seen_user["text"] = kw["messages"][1]["content"]
        return orig(**kw)

    client.chat.completions.create = spy
    router, _ = make_router(client, monkeypatch, recs(*chain))
    ans = router.answer("What do I need before CC 1000?", TODAY, log=False)
    assert ans.router["chain"]["truncated"] is True and len(ans.sources) == 5
    assert "Truncation note: the chain was cut." in seen_user["text"]
    assert not any("Truncation" in s["text"] for s in ans.sources)


def test_the_real_unknown_and_out_of_scope_codes_abstain():
    records = ch.load_records()
    if not records:
        pytest.skip("no processed course data")
    assert "CST 4999" not in records and "ENG 1101" not in records
    assert ch.prerequisite_chain.invoke({"course_code": "CST 4999"})["found"] is False
    assert ch.prerequisite_chain.invoke({"course_code": "ENG 1101"})["found"] is False
    assert ch.prerequisite_chain.invoke({"course_code": "cst2412"})["found"] is True


def test_the_router_dict_and_log_carry_the_chain_fields(monkeypatch):
    router, _ = make_router(Client(), monkeypatch, WORLD)
    ans = router.answer("What do I need before AA 1001?", TODAY, log=False)
    assert {"route", "intent", "classify", "chain_fallthrough", "chain"} <= set(ans.router)
    assert ans.router["intent"] == "prerequisite" and ans.router["chain"]["extraction"] == "code"
