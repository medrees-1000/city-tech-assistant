"""Near-miss polish and possessive cue, item 2 (docs/decisions.md): a possessive plus an office noun
alone no longer makes a policy abstention a personal-account refusal. The two lists were written
before the code. No network, no database, no paid call. Only dev questions are read."""

import json
import re

import pytest

from cta.answer import THRESHOLD_ABSTAIN
from cta.api import convert
from cta.graph import contact
from cta.settings import ROOT
from tests.test_api import Client, ask, make_client_app, retrieve_answer

TABLE = contact.load_contacts()

MUST_REFUSE = [
    "what is my financial aid status", "do I have a hold on my account", "how much do I owe",
    "did my TAP get approved", "when will my refund be deposited", "what are my grades",
    "why was my financial aid denied", "is my application complete", "wheres my refund at",
    "did my fafsa go thru", "why is my aid so late", "whats my gpa rn",
    "i cant log in to cunyfirst", "what is my balance", "has my tap been approved yet",
    "do i have any holds on my account",
]  # fmt: skip
MUST_NOT = [
    "what happens if i dont accept my financial aid award by the deadline",
    "how does my financial aid get disbursed",
    "what do i need to do to keep my financial aid",
    "how do i accept my loan on cunyfirst",
    "when is my tuition bill due this fall",
    "how does my tuition get refunded if i drop",
    "does my financial aid cover books",
    "what happens to my refund if i withdraw",
    "how is my tuition calculated",
    "do i need to reapply for my tap every year",
    "what is the deadline to renew my fafsa",
    "how do i set up a payment plan for my tuition",
    "can i use my financial aid for summer classes",
    "what is the last day to drop to get my tuition back",
]  # fmt: skip


def code(question, reason="below_threshold"):
    return convert.abstain_code(reason, question, TABLE)


def test_the_lists_have_the_pre_registered_sizes():
    assert (len(MUST_REFUSE), len(MUST_NOT)) == (16, 14)


@pytest.mark.parametrize("question", MUST_REFUSE)
def test_every_must_refuse_question_is_still_a_personal_account_refusal(question):
    assert code(question) == "personal_account"
    assert code(question, "some model sentence") == "personal_account"


@pytest.mark.parametrize("question", MUST_NOT)
def test_no_must_not_question_is_relabelled(question):
    assert code(question) == "below_threshold"
    assert code(question, "some model sentence") == "model"


def test_the_cd9d2a93_question_is_a_plain_abstention_with_the_financial_aid_card_kept():
    q = "what happens if i dont accept my financial aid award by the deadline"
    assert code(q) == "below_threshold"
    assert (
        contact.cue_office(q, TABLE) == "financial-aid"
    )  # the contact logic is untouched (policy v2)
    assert contact.account_cue(q, TABLE) is True  # the old function is unchanged and still says yes


def test_the_two_new_cues_are_the_only_account_only_additions_and_the_new_keys_exist():
    assert {"how much do i owe", "is my application complete"} <= set(TABLE["account_only"])
    assert len(TABLE["account_only"]) == 11
    assert set(TABLE["noun_cues"]) == {
        "my financial aid", "my aid", "my fafsa", "my tap", "my refund", "my tuition", "my bill",
    }  # fmt: skip
    for word in ("status", "approved", "denied", "deposited", "did my", "why is my", "wheres my"):
        assert word in TABLE["account_signals"]
    # every noun cue is one of the existing office cues: nothing new chooses a card
    existing = {w for words in TABLE["cues"].values() for w in words}
    assert set(TABLE["noun_cues"]) <= existing


def test_a_possessive_noun_alone_is_not_enough_but_with_a_signal_it_is():
    assert not contact.personal_account_cue("what is my financial aid", TABLE)
    assert contact.personal_account_cue("what is my financial aid status", TABLE)
    assert not contact.personal_account_cue("how does my tuition work", TABLE)
    assert contact.personal_account_cue("what is my balance", TABLE)  # a data cue by itself
    assert contact.personal_account_cue(
        "Why hasn’t my aid arrived", TABLE
    )  # a curly apostrophe works
    assert not contact.personal_account_cue("what is the status of the registrar line", TABLE)


def test_office_for_and_cue_office_are_unchanged():
    assert contact.cue_office("why is my aid late", TABLE) == "financial-aid"
    assert contact.cue_office("whats my gpa", TABLE) == "registrar"
    assert contact.cue_office("what is my balance", TABLE) == "bursar"
    assert contact.cue_office("do i have a hold on my account", TABLE) is None


# ---- zero changes for the dev questions ----


def dev_questions():
    out = {}
    for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines():
        if re.search(r'"split": ?"dev"', line):  # selected by its raw text before it is parsed
            row = json.loads(line)
            out[row["id"]] = row["question"]
    return out


def old_code(reason, question):
    """The relabel rule before this change: any office cue or account word."""
    if reason is None:
        return None
    if reason.startswith(convert.OWN_CODES):
        return reason
    if contact.account_cue(question, TABLE):
        return "personal_account"
    return reason if reason == "below_threshold" else "model"


# The pre-registered "zero changes" check could not be literally empty: q13 ("When is my tuition
# bill due this fall?") is a dev question AND on the owner's must-not list, so its relabel must
# change if it ever abstained. Checked instead: the exact set of dev questions whose relabel would
# differ, and that only q98 of them actually abstained through retrieval in the stored dev runs.
HYPOTHETICAL_CHANGES = {
    "q13",
    "q14",
    "q53",
    "q59",
    "q96",
    "q97",
    "q98",
}  # all personal_account -> plain


def test_exactly_these_dev_questions_would_be_relabelled_differently_and_none_else():
    dev = dev_questions()
    assert len(dev) == 71
    differ = set()
    for qid, question in dev.items():
        for reason in ("below_threshold", "some model sentence", "calendar_unsupported_term", None):
            if code(question, reason) != old_code(reason, question):
                differ.add(qid)
    assert differ == HYPOTHETICAL_CHANGES
    for qid in (
        differ
    ):  # each is a possessive plus an office noun with no account signal: a policy question
        assert contact.account_cue(dev[qid], TABLE) and not contact.personal_account_cue(
            dev[qid], TABLE
        )
        assert (
            code(dev[qid]) == "below_threshold"
            and old_code("below_threshold", dev[qid]) == "personal_account"
        )


def test_in_the_stored_dev_runs_only_q98_abstained_through_retrieval_among_them():
    dev = dev_questions()
    abstained = set()
    for label in ("tester1-dev", "tester1-new8", "tester1-nearmiss2"):
        run = json.loads((ROOT / f"eval/results/{label}.json").read_text(encoding="utf-8"))
        for r in run["per_question"]:
            if (
                r["id"] in dev
                and r["abstained"]
                and r["route"] in ("other", "calendar_fallthrough")
            ):
                abstained.add(r["id"])
    assert abstained & HYPOTHETICAL_CHANGES == {
        "q98"
    }  # the others were answered: no relabel applies
    # every dev question that abstained and is not q98 gets the same code before and after
    for qid in abstained - {"q98"}:
        assert code(dev[qid]) == old_code("below_threshold", dev[qid]), qid


def test_the_eval_path_never_calls_the_relabel():
    for path in (ROOT / "src" / "cta" / "eval").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "abstain_code" not in text and "personal_account_cue" not in text, path


# ---- through the API ----


def abstain_app(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    return make_client_app(Client(), monkeypatch, stub)


def test_the_cd9d2a93_question_gets_the_plain_abstention_and_the_financial_aid_card(monkeypatch):
    body = ask(
        abstain_app(monkeypatch),
        "what happens if i dont accept my financial aid award by the deadline",
    ).json()
    assert body["abstained"] and body["abstain_reason"] == "below_threshold"
    assert body["contact"]["office"] == "financial-aid"
    assert "personal account" not in body["answer"]


def test_a_must_refuse_question_is_still_refused_through_the_api(monkeypatch):
    body = ask(abstain_app(monkeypatch), "what is my financial aid status").json()
    assert (
        body["abstain_reason"] == "personal_account"
        and body["contact"]["office"] == "financial-aid"
    )
