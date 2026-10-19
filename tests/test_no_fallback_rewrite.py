"""The fallback query rewrite (experiment E1) is gone: the /ask response keeps every other key, and
nothing in the production configuration could ever have turned it on."""

import importlib.util
import inspect
from pathlib import Path

from cta import answer
from cta.settings import load_models
from tests.test_api import Client, ask, make_client_app, retrieve_answer

ROOT = Path(__file__).resolve().parents[1]

# the keys of a normal answer before the removal, minus how_found.rewrite (it was always null)
TOP_KEYS = ["abstain_reason", "abstained", "answer", "answer_type", "citations", "contact",
            "how_found", "meta", "question", "request_id", "route"]  # fmt: skip
HOW_FOUND_KEYS = ["abstain_threshold", "abstain_wording", "cache_hits", "calendar", "chain",
                  "cost_usd", "intent", "language", "near_miss", "retrieved", "route_detail",
                  "stages_ms", "tokens", "top_vector_similarity", "topic_in_scope"]  # fmt: skip


def test_a_normal_answer_has_the_same_keys_as_before_minus_how_found_rewrite(monkeypatch):
    body = ask(make_client_app(Client(), monkeypatch, retrieve_answer())).json()
    assert sorted(body) == TOP_KEYS
    assert sorted(body["how_found"]) == HOW_FOUND_KEYS
    assert sorted(body["meta"]) == ["model", "today", "version"]


def test_the_production_configuration_never_enabled_the_rewrite_and_no_path_is_left():
    # it was "off" in config/models.yaml and no deploy file set CTA_FALLBACK_REWRITE
    for name in ("config/models.yaml", ".env.production.example", "docker-compose.prod.yml",
                 "Dockerfile", ".github/workflows/ci.yml"):  # fmt: skip
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "fallback_rewrite" not in text, name
    assert "fallback_rewrite" not in load_models(env={"CTA_FALLBACK_REWRITE": "on"})["retrieval"]
    assert "rewrite" not in inspect.signature(answer.answer).parameters
    assert not hasattr(answer, "fallback_search")
    assert importlib.util.find_spec("cta.index.rewrite") is None
