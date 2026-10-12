import pytest

from cta.redact import redact
from cta.settings import cost_usd, load_models, secret_status


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
