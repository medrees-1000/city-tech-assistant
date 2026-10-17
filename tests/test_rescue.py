"""Version 2 rescue rule (docs/decisions.md, "Version 2, casual wording: pre-registration").
No network, no database, no paid call: the search and the chat model are stubs with synthetic
scores. No real question is used."""

import json
import random
from datetime import date
from types import SimpleNamespace

import pytest

from cta import answer as answer_module
from cta.eval import blind_export
from cta.eval import questions as q_module
from cta.eval.run_answers import main as run_answers_main
from cta.index.rerank import Rerank
from cta.index.search import Search
from cta.settings import load_models

TODAY = date(2026, 10, 17)
CUTOFF = 0.59


def cfg(rescue="on", **over):
    c = load_models(env={"CTA_RERANK": "off"})
    c["answer"]["rescue"] = rescue
    c["answer"].update(over)
    return c


def chunk(cid="page/a#1", sim=0.5):
    return {"id": cid, "kind": "section", "source": "https://www.citytech.cuny.edu/x.aspx",
            "heading_path": "H", "text": "text", "doc_type": "faq", "term": None, "terms": [],
            "last_updated": None, "similarity": sim}  # fmt: skip


class Model:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls += 1
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        msg = SimpleNamespace(content="The answer. [1]")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def run(monkeypatch, top, rerank_scores, rescue="on", failed=False):
    rerank = None if rerank_scores is None else Rerank([0], failed=failed, scores=rerank_scores)
    found = Search([chunk(sim=top)], False, 1, 10, 0.0, top_vector_similarity=top, rerank=rerank)
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: found)
    model = Model()
    ans = answer_module.answer(
        None, "q", TODAY, cfg=cfg(rescue), client_factory=lambda: model, log=False
    )
    return ans, model


def test_the_rescue_is_off_by_default_and_checked():
    a = load_models(env={})["answer"]
    assert a["rescue"] == "off" and a["rescue_similarity_floor"] == 0.45
    assert a["rescue_reranker_min"] == 8


def test_load_models_rejects_bad_rescue_values(tmp_path):
    base = (load_models.__globals__["ROOT"] / "config" / "models.yaml").read_text()
    for old, new, key in (
        ('rescue: "off"', 'rescue: "maybe"', "answer.rescue must be"),
        (
            "rescue_similarity_floor: 0.45",
            "rescue_similarity_floor: 0.7",
            "rescue_similarity_floor",
        ),
        ("rescue_reranker_min: 8", "rescue_reranker_min: 11", "rescue_reranker_min"),
    ):
        assert old in base
        path = tmp_path / "models.yaml"
        path.write_text(base.replace(old, new))
        with pytest.raises(ValueError, match=key):
            load_models(path, env={})


def test_above_the_cutoff_is_answered_whatever_the_flag(monkeypatch):
    for flag in ("on", "off"):
        ans, model = run(monkeypatch, 0.62, [3], rescue=flag)
        assert not ans.abstained and model.calls == 1 and not ans.rescued


@pytest.mark.parametrize("score,answered", [(10, True), (8, True), (7, False)])
def test_between_the_floor_and_the_cutoff_the_reranker_top_score_decides(
    monkeypatch, score, answered
):
    ans, model = run(monkeypatch, 0.52, [2, score, 1])
    assert (model.calls == 1) is answered and ans.rescued is answered
    assert ans.abstained is (not answered)
    if not answered:
        assert ans.abstain_reason == "below_threshold"


def test_exactly_at_the_floor_counts_and_just_under_it_does_not(monkeypatch):
    ans, model = run(monkeypatch, 0.45, [9])
    assert ans.rescued and model.calls == 1
    ans, model = run(monkeypatch, 0.449, [10])
    assert ans.abstained and not ans.rescued and model.calls == 0


def test_below_the_floor_is_refused_even_with_a_perfect_reranker_score(monkeypatch):
    ans, model = run(monkeypatch, 0.30, [10])
    assert ans.abstained and ans.abstain_reason == "below_threshold" and model.calls == 0


def test_flag_off_keeps_todays_behaviour(monkeypatch):
    ans, model = run(monkeypatch, 0.52, [10], rescue="off")
    assert ans.abstained and not ans.rescued and model.calls == 0


@pytest.mark.parametrize("rerank_scores,failed", [(None, False), ([], False), ([10], True)])
def test_no_usable_reranker_means_no_rescue(monkeypatch, rerank_scores, failed):
    ans, model = run(monkeypatch, 0.52, rerank_scores, failed=failed)
    assert ans.abstained and not ans.rescued and model.calls == 0


def test_the_numbers_come_from_config_not_from_code():
    top, rr = 0.50, Rerank([0], scores=[6])
    assert not answer_module.rescue_applies(cfg(), top, rr)
    assert answer_module.rescue_applies(cfg(rescue_reranker_min=6), top, rr)
    assert not answer_module.rescue_applies(cfg(rescue_similarity_floor=0.55), top, rr)


# ---- the held-out split and the runner ----


def test_heldout_is_only_accepted_when_asked_for():
    row = {"split": "heldout"}
    assert any("split" in p for p in q_module.row_problems(row))  # dev/test file: still refused
    assert not any("split" in p for p in q_module.row_problems(row, (q_module.HELDOUT,)))
    assert any("split" in p for p in q_module.row_problems({"split": "dev"}, (q_module.HELDOUT,)))


def test_split_files_dev_and_test_unchanged_and_heldout_has_its_own():
    assert q_module.SPLITS == ("dev", "test")
    assert q_module.questions_path("dev") == q_module.QUESTIONS
    assert q_module.questions_path("test") == q_module.QUESTIONS
    assert q_module.questions_path("heldout") == q_module.HELDOUT_QUESTIONS


def test_the_main_file_has_no_heldout_rows_and_the_heldout_file_only_heldout_rows():
    main_rows = q_module.load_questions(q_module.QUESTIONS)
    held = q_module.load_questions(q_module.HELDOUT_QUESTIONS)
    assert {r["split"] for r in main_rows} == {"dev", "test"}
    assert [r["id"] for r in held] == [f"cv2-{n:02d}" for n in range(1, 42)]
    assert {r["split"] for r in held} == {"heldout"}
    assert not {r["id"] for r in held} & {r["id"] for r in main_rows}


def test_select_questions_never_mixes_the_heldout_set_into_dev_or_test():
    held = q_module.load_questions(q_module.HELDOUT_QUESTIONS)
    assert q_module.select_questions(held, "dev") == []
    assert len(q_module.select_questions(held, "heldout")) == 41
    with pytest.raises(ValueError, match="not in the dev split"):
        q_module.select_questions(held, "dev", ["cv2-01"])


def test_check_all_lets_a_todo_gold_answer_pass_only_when_told_to():
    row = {"id": "x", "question": "q", "gold_answer": "TODO", "gold_sources": [],
           "type": "unanswerable", "department": None, "split": "heldout", "note": ""}  # fmt: skip
    data = q_module.GoldData()
    assert q_module.check_all([row], data, (q_module.HELDOUT,), require_answers=False) == {"x": []}
    assert q_module.check_all([row], data, (q_module.HELDOUT,))["x"]  # TODO answer is a problem
    assert q_module.check_all([row], data)["x"]  # and 'heldout' is not a dev/test split


def test_the_test_split_still_needs_final(capsys):
    assert run_answers_main(["x", "--split", "test", "--label", "never-used-label-1"]) == 2
    assert "--final" in capsys.readouterr().out


def test_heldout_needs_no_final_flag_and_unknown_split_ids_are_refused(capsys):
    from cta.eval.run_retrieval import check_split

    assert check_split("heldout", False) is None
    assert check_split("test", False) and check_split("dev", False) is None


# ---- the blind export ----


def answers(prefix):
    return {
        f"cv2-{n:02d}": {"id": f"cv2-{n:02d}", "question": f"question {n}", "route": "retrieve",
                         "abstain_reason": prefix, "answer": f"{prefix} answer {n}",
                         "citations": [1], "sources_shown": ["page/a#1"]}
        for n in range(1, 21)
    }  # fmt: skip


def test_blind_rows_hide_the_configuration_and_the_key_maps_it_back():
    base, fix = answers("baseline"), answers("fix")
    rows, key = blind_export.blind_rows(base, fix, random.Random(7))
    assert sorted(r["id"] for r in rows) == sorted(base)
    text = json.dumps(rows)
    assert "abstain_reason" not in text and "route" not in text
    for r in rows:
        n = r["id"][-2:]
        a_config = key[r["id"]]["A"]
        assert key[r["id"]]["B"] != a_config
        assert r["answer_A"] == f"{a_config} answer {int(n)}"
        assert r["answer_B"] == f"{key[r['id']]['B']} answer {int(n)}"
    assert {k["A"] for k in key.values()} == {"baseline", "fix"}  # random per question, not fixed
    assert [r["id"] for r in rows] != sorted(base)  # shuffled


def test_blind_rows_refuse_runs_with_different_questions():
    base, fix = answers("b"), answers("f")
    del fix["cv2-03"]
    with pytest.raises(ValueError, match="cv2-03"):
        blind_export.blind_rows(base, fix, random.Random(1))


def test_blind_export_writes_two_files_and_never_overwrites(tmp_path, capsys):
    for name, prefix in (("b.jsonl", "baseline"), ("f.jsonl", "fix")):
        rows = answers(prefix).values()
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    args = ["x", str(tmp_path / "b.jsonl"), str(tmp_path / "f.jsonl"), str(tmp_path / "out")]
    assert blind_export.main(args, random.Random(3)) == 0
    blind = (tmp_path / "out-blind.jsonl").read_text().splitlines()
    key = json.loads((tmp_path / "out-key.json").read_text())
    assert len(blind) == 20 and len(key) == 20
    allowed = {"id", "question"} | {f"{f}_{s}" for f in blind_export.SHOWN for s in "AB"}
    assert all(set(json.loads(line)) == allowed for line in blind)  # no field names the config
    assert blind_export.main(args, random.Random(3)) == 2  # refuses to overwrite
    assert "already exists" in capsys.readouterr().out


def test_the_real_heldout_rows_are_well_formed_with_the_confirmed_label_counts():
    rows = q_module.load_questions(q_module.HELDOUT_QUESTIONS)
    assert all(q_module.row_problems(r, (q_module.HELDOUT,)) == [] for r in rows)
    assert q_module.duplicate_ids(rows) == set()
    counts = {}
    for r in rows:
        counts[r["tags"][0]] = counts.get(r["tags"][0], 0) + 1
        assert r["note"].startswith("CONFIRMED Oct 17, 2026 by owner")
    assert counts == {"answer": 7, "uncertain": 12, "refuse": 22}
    assert sum("trap" in r["tags"] for r in rows) == 11


@pytest.mark.skipif(
    not (q_module.ROOT / "data" / "processed" / "pages").exists(), reason="no processed data"
)
def test_every_heldout_gold_source_resolves():
    rows = q_module.load_questions(q_module.HELDOUT_QUESTIONS)
    results = q_module.check_all(
        rows, q_module.load_gold_data(), (q_module.HELDOUT,), require_answers=False
    )
    assert {q: p for q, p in results.items() if p} == {}
