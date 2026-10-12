"""Load config/sources.yaml and the contact email from .env."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def load_sources(path: Path = ROOT / "config" / "sources.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_user_agent(sources: dict) -> str:
    """User-Agent with the owner's email from the environment (never hard-coded)."""
    load_dotenv(ROOT / ".env")
    crawl = sources["crawl"]
    email = os.environ.get(crawl["contact_email_env"], "").strip()
    if not email:
        raise RuntimeError(f"{crawl['contact_email_env']} is not set; copy .env.example to .env")
    return crawl["user_agent_template"].format(email=email)


RETRIEVAL_MODES = ("vector", "hybrid", "hybrid_bm25")
SECRET_KEYS = ("OPENAI_API_KEY", "POSTGRES_PASSWORD", "DATABASE_URL")
MODEL_OVERRIDES = {
    "embedding_model": "CTA_EMBEDDING_MODEL",
    "chat_model": "CTA_CHAT_MODEL",
    "judge_model": "CTA_JUDGE_MODEL",
}


def load_models(path: Path = ROOT / "config" / "models.yaml", env: dict | None = None) -> dict:
    """Read config/models.yaml, apply CTA_*_MODEL overrides, and refuse unpriced models.

    `env` defaults to .env plus the process environment. Secrets are not part of the result.
    """
    if env is None:
        load_dotenv(ROOT / ".env")
        env = dict(os.environ)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, var in MODEL_OVERRIDES.items():
        if env.get(var, "").strip():
            cfg[key] = env[var].strip()
    expected = {"embedding_model": "embedding", "chat_model": "chat", "judge_model": "chat"}
    for key, kind in expected.items():
        entry = cfg["models"].get(cfg[key])
        if entry is None:
            raise ValueError(f"{key} '{cfg[key]}' has no price entry in {path.name}; add one first")
        if entry["kind"] != kind:
            raise ValueError(f"{key} '{cfg[key]}' is a {entry['kind']} model, expected {kind}")
    cfg["embedding_dimensions"] = cfg["models"][cfg["embedding_model"]]["dimensions"]
    if env.get("CTA_RETRIEVAL_MODE", "").strip():
        cfg["retrieval"]["mode"] = env["CTA_RETRIEVAL_MODE"].strip()
    if env.get("CTA_DEPT_FILTER", "").strip():
        cfg["retrieval"]["dept_filter"] = env["CTA_DEPT_FILTER"].strip()
    if cfg["retrieval"]["dept_filter"] not in ("off", "on"):
        raise ValueError(
            f"retrieval.dept_filter must be off or on, not {cfg['retrieval']['dept_filter']!r}"
        )
    if cfg["retrieval"]["mode"] not in RETRIEVAL_MODES:
        raise ValueError(
            f"retrieval.mode must be one of {RETRIEVAL_MODES}, not {cfg['retrieval']['mode']!r}"
        )
    return cfg


def secret_status(env: dict | None = None) -> dict[str, str]:
    """Which secrets are set, as 'set' / 'missing'. Values are never returned."""
    if env is None:
        load_dotenv(ROOT / ".env")
        env = dict(os.environ)
    return {k: "set" if env.get(k, "").strip() else "missing" for k in SECRET_KEYS}


def cost_usd(cfg: dict, model: str, input_tokens: int, output_tokens: int = 0) -> float:
    """Dollar cost of a call from the price table; unknown models raise."""
    price = cfg["models"].get(model)
    if price is None:
        raise ValueError(f"no price entry for model '{model}'")
    return (input_tokens * price["input"] + output_tokens * price.get("output", 0.0)) / 1_000_000
