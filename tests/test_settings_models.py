import pytest

from cta import answer as ans_mod
from cta.redact import redact
from cta.settings import answer_model, check_answer_model, cost_usd, load_models, secret_status


def test_defaults_load_and_dimensions_follow_model():
    cfg = load_models(env={})
    assert cfg["embedding_model"] == "text-embedding-3-small"
    assert cfg["embedding_dimensions"] == 1536
    assert cfg["judge_model"] != cfg["chat_model"]


def test_env_override_changes_model_and_dimensions():
    cfg = load_models(env={"CTA_EMBEDDING_MODEL": "text-embedding-3-large"})
    assert cfg["embedding_dimensions"] == 3072


def test_unpriced_model_is_refused():
    with pytest.raises(ValueError, match="no price entry"):
        load_models(env={"CTA_CHAT_MODEL": "gpt-unknown"})


def test_wrong_kind_is_refused():
    with pytest.raises(ValueError, match="expected chat"):
        load_models(env={"CTA_CHAT_MODEL": "text-embedding-3-small"})


def test_cost_usd():
    cfg = load_models(env={})
    assert cost_usd(cfg, "gpt-6-luna", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert cost_usd(cfg, "text-embedding-3-small", 1_000_000) == pytest.approx(0.02)
    with pytest.raises(ValueError):
        cost_usd(cfg, "nope", 1)


def test_secret_status_hides_values():
    status = secret_status({"OPENAI_API_KEY": "sk-secret"})
    assert status["OPENAI_API_KEY"] == "set"
    assert status["POSTGRES_PASSWORD"] == "missing"
    assert "sk-secret" not in str(status)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("my id is 23456789 help", "my id is [ID] help"),
        ("mail me at jane.doe@mail.citytech.cuny.edu now", "mail me at [EMAIL] now"),
        ("call 718-260-5000 or (718) 260 5000", "call [PHONE] or [PHONE]"),
        ("ssn 123-45-6789", "ssn [SSN]"),
        ("+1 718.260.5000", "[PHONE]"),
        ("Fall 2026 deadline? CST 1101, 3 credits", "Fall 2026 deadline? CST 1101, 3 credits"),
        ("code 1234567890", "code 1234567890"),
    ],
)
def test_redact(raw, clean):
    assert redact(raw) == clean


def test_answer_model_defaults_to_the_chat_model_and_everything_else_stays():
    cfg = load_models(env={})
    assert cfg["answer"]["model"] is None and answer_model(cfg) == cfg["chat_model"] == "gpt-6-luna"
    cfg = load_models(env={"CTA_ANSWER_MODEL": "gpt-6.1-sol"})
    assert answer_model(cfg) == "gpt-6.1-sol" and cfg["chat_model"] == "gpt-6-luna"
    assert cfg["judge_model"] == "gpt-5.6-terra"


def test_answer_model_must_be_priced_and_a_chat_model():
    with pytest.raises(ValueError, match="no price entry"):
        load_models(
            env={"CTA_ANSWER_MODEL": "gpt-6-astra"}
        )  # not priced here: not an experiment arm
    with pytest.raises(ValueError, match="expected chat"):
        load_models(env={"CTA_ANSWER_MODEL": "text-embedding-3-small"})
    cfg = load_models(env={})
    cfg["answer"]["model"] = "nope"
    with pytest.raises(ValueError, match="no price entry"):
        check_answer_model(cfg)


def test_call_chat_uses_chat_model_unless_told_otherwise():
    seen = []

    class Client:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kw):
                    seen.append(kw["model"])

    cfg = load_models(env={})
    ans_mod.call_chat(Client, cfg, [])
    ans_mod.call_chat(Client, cfg, [], "gpt-6.1-sol")
    assert seen == ["gpt-6-luna", "gpt-6.1-sol"]
