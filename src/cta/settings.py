"""Load config/sources.yaml and the contact email from .env."""

import hashlib
import json
import os
from datetime import date
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
RERANK_MODES = ("off", "pool_a", "pool_b")
MODEL_OVERRIDES = {
    "embedding_model": "CTA_EMBEDDING_MODEL",
    "chat_model": "CTA_CHAT_MODEL",
    "judge_model": "CTA_JUDGE_MODEL",
}


def check_answer_model(cfg: dict) -> None:
    """answer.model must be null or a priced chat model (an unpriced one would make cost zero)."""
    name = cfg["answer"].get("model")
    if name is None:
        return
    entry = cfg["models"].get(name)
    if entry is None:
        raise ValueError(f"answer.model '{name}' has no price entry in models.yaml; add one first")
    if entry["kind"] != "chat":
        raise ValueError(f"answer.model '{name}' is a {entry['kind']} model, expected chat")


def answer_model(cfg: dict) -> str:
    """The model that writes retrieval-route answers: answer.model, else chat_model."""
    return cfg["answer"].get("model") or cfg["chat_model"]


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
    cfg["answer"].setdefault("model", None)
    if env.get("CTA_ANSWER_MODEL", "").strip():
        cfg["answer"]["model"] = env["CTA_ANSWER_MODEL"].strip()
    check_answer_model(cfg)
    cfg["answer"].setdefault("near_miss_margin", 0.0)
    if env.get("CTA_NEAR_MISS_MARGIN", "").strip():
        cfg["answer"]["near_miss_margin"] = env["CTA_NEAR_MISS_MARGIN"].strip()
    try:
        cfg["answer"]["near_miss_margin"] = float(cfg["answer"]["near_miss_margin"])
    except (TypeError, ValueError):
        raise ValueError("answer.near_miss_margin must be a number") from None
    if not 0 <= cfg["answer"]["near_miss_margin"] < cfg["answer"]["abstain_threshold"]:
        raise ValueError("answer.near_miss_margin must be at least 0 and below the cutoff")
    cfg["answer"].setdefault("quote_addenda", [])
    for rule in cfg["answer"]["quote_addenda"]:
        if not isinstance(rule, dict) or not all(
            isinstance(rule.get(k), str) and rule[k].strip() for k in ("chunk", "starts_with")
        ):
            raise ValueError("answer.quote_addenda entries need a chunk id and a starts_with text")
    cfg["answer"].setdefault("quote_addenda_question_words", [])
    words = cfg["answer"]["quote_addenda_question_words"]
    if not isinstance(words, list) or not all(isinstance(w, str) and w.strip() for w in words):
        raise ValueError("answer.quote_addenda_question_words must be a list of non-empty words")
    cfg["answer"].setdefault("rescue", "on")
    cfg["answer"].setdefault("rescue_similarity_floor", 0.45)
    cfg["answer"].setdefault("rescue_reranker_min", 8)
    if cfg["answer"]["rescue"] not in ("off", "on"):
        raise ValueError(f"answer.rescue must be off or on, not {cfg['answer']['rescue']!r}")
    floor, minimum = cfg["answer"]["rescue_similarity_floor"], cfg["answer"]["rescue_reranker_min"]
    if not 0 <= floor < cfg["answer"]["abstain_threshold"]:
        raise ValueError("answer.rescue_similarity_floor must be at least 0 and below the cutoff")
    if not 0 <= minimum <= 10:
        raise ValueError("answer.rescue_reranker_min must be between 0 and 10")
    cfg["answer"].setdefault("format_rule", "off")
    if env.get("CTA_ANSWER_FORMAT_RULE", "").strip():
        cfg["answer"]["format_rule"] = env["CTA_ANSWER_FORMAT_RULE"].strip()
    if cfg["answer"]["format_rule"] not in ("off", "on"):
        raise ValueError(
            f"answer.format_rule must be off or on, not {cfg['answer']['format_rule']!r}"
        )
    if env.get("CTA_RETRIEVAL_MODE", "").strip():
        cfg["retrieval"]["mode"] = env["CTA_RETRIEVAL_MODE"].strip()
    if env.get("CTA_DEPT_FILTER", "").strip():
        cfg["retrieval"]["dept_filter"] = env["CTA_DEPT_FILTER"].strip()
    if env.get("CTA_RERANK", "").strip():
        cfg["retrieval"]["rerank"] = env["CTA_RERANK"].strip()
    if cfg["retrieval"]["rerank"] not in RERANK_MODES:
        raise ValueError(
            f"retrieval.rerank must be one of {RERANK_MODES}, not {cfg['retrieval']['rerank']!r}"
        )
    if env.get("CTA_ROUTER_MODE", "").strip():
        cfg["router"]["mode"] = env["CTA_ROUTER_MODE"].strip()
    if env.get("CTA_ROUTER_CHAIN", "").strip():
        cfg["router"]["chain"] = env["CTA_ROUTER_CHAIN"].strip()
    cfg["router"].setdefault("chain", "off")
    if env.get("CTA_ROUTER_CHAIN_RENDER", "").strip():
        cfg["router"]["chain_render"] = env["CTA_ROUTER_CHAIN_RENDER"].strip()
    cfg["router"].setdefault("chain_render", "model")
    if cfg["router"]["chain_render"] not in ("model", "code"):
        raise ValueError(
            f"router.chain_render must be model or code, not {cfg['router']['chain_render']!r}"
        )
    if cfg["router"]["chain"] not in ("off", "on"):
        raise ValueError(f"router.chain must be off or on, not {cfg['router']['chain']!r}")
    if env.get("CTA_ROUTER_CONTACTS", "").strip():
        cfg["router"]["contacts"] = env["CTA_ROUTER_CONTACTS"].strip()
    cfg["router"].setdefault("contacts", "off")
    if cfg["router"]["contacts"] not in ("off", "on"):
        raise ValueError(f"router.contacts must be off or on, not {cfg['router']['contacts']!r}")
    if env.get("CTA_ROUTER_SELECTOR", "").strip():
        cfg["router"]["selector"] = env["CTA_ROUTER_SELECTOR"].strip()
    if str(cfg["router"]["selector"]) not in ("1", "2"):
        raise ValueError(f"router.selector must be 1 or 2, not {cfg['router']['selector']!r}")
    cfg["router"]["selector"] = int(cfg["router"]["selector"])
    if cfg["router"]["mode"] not in ("off", "on"):
        raise ValueError(f"router.mode must be off or on, not {cfg['router']['mode']!r}")
    if env.get("CTA_API_TODAY", "").strip():
        cfg["api"]["today"] = env["CTA_API_TODAY"].strip()
    if cfg["api"]["today"] is not None:
        try:
            cfg["api"]["today"] = date.fromisoformat(str(cfg["api"]["today"]))
        except ValueError:
            raise ValueError(f"api.today must be YYYY-MM-DD, not {cfg['api']['today']!r}") from None
    if cfg["retrieval"]["dept_filter"] not in ("off", "on"):
        raise ValueError(
            f"retrieval.dept_filter must be off or on, not {cfg['retrieval']['dept_filter']!r}"
        )
    if cfg["retrieval"]["mode"] not in RETRIEVAL_MODES:
        raise ValueError(
            f"retrieval.mode must be one of {RETRIEVAL_MODES}, not {cfg['retrieval']['mode']!r}"
        )
    cfg["guardrails"] = guardrail_settings(cfg.get("guardrails") or {}, env)
    cfg["tracing"] = {"enabled": bool((cfg.get("tracing") or {}).get("enabled", False))}
    # production switches tracing on through the environment only (the file default stays false)
    flag = env.get("CTA_TRACING_ENABLED", "").strip().lower()
    if flag:
        cfg["tracing"]["enabled"] = flag in ("1", "true", "yes", "on")
    return cfg


def config_version(cfg: dict) -> str:
    """A short fingerprint of the settings in force (the file plus environment overrides), shown
    in /health and on traces so a result can be tied to a configuration. Holds no secret: the
    secrets are never part of `cfg`."""
    text = json.dumps(cfg, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:10]


# (config key, environment variable, type, minimum allowed value)
GUARDRAIL_KEYS = (
    ("daily_spend_cap_usd", "CTA_DAILY_SPEND_CAP_USD", float, 0.0000001),
    ("monthly_spend_cap_usd", "CTA_MONTHLY_SPEND_CAP_USD", float, 0.0000001),
    ("rate_per_minute", "CTA_RATE_PER_MINUTE", int, 1),
    ("rate_per_day", "CTA_RATE_PER_DAY", int, 1),
    ("model_call_timeout_s", "CTA_MODEL_CALL_TIMEOUT_S", float, 0.1),
    ("model_retries", "CTA_MODEL_RETRIES", int, 0),
    ("request_timeout_s", "CTA_REQUEST_TIMEOUT_S", float, 0.1),
    ("failed_request_cost_usd", "", float, 0.0),
    ("spend_cache_s", "", float, 0.0),
    ("monthly_spend_cache_s", "", float, 0.0),
    ("rate_limit_max_keys", "", int, 1),
)  # fmt: skip


def guardrail_settings(block: dict, env: dict) -> dict:
    """The guardrails block with environment overrides, every number checked."""
    out = dict(block)
    for key, var, kind, minimum in GUARDRAIL_KEYS:
        raw = env.get(var, "").strip() if var else ""
        try:
            value = kind(raw if raw else out[key])
        except (KeyError, TypeError, ValueError):
            shown = raw or out.get(key)
            raise ValueError(f"guardrails.{key} must be a number, not {shown!r}") from None
        if value < minimum:
            raise ValueError(f"guardrails.{key} must be at least {minimum}, not {value}")
        out[key] = value
    flag = env.get("CTA_API_DISABLED", "").strip().lower()
    out["distress_reply"] = (
        env.get("CTA_DISTRESS_REPLY", "").strip() or out["distress_reply"]
    ).lower()
    if out["distress_reply"] not in ("988", "none"):
        raise ValueError(
            f"guardrails.distress_reply must be 988 or none, not {out['distress_reply']!r}"
        )
    out["personal_data"] = (
        env.get("CTA_PERSONAL_DATA", "").strip() or out["personal_data"]
    ).lower()
    if out["personal_data"] not in ("off", "redact", "redact_and_refuse"):
        shown = out["personal_data"]
        raise ValueError(
            f"guardrails.personal_data must be off, redact or redact_and_refuse, not {shown!r}"
        )
    screen_flag = env.get("CTA_INJECTION_SCREEN", "").strip().lower()
    out["non_english"] = (
        env.get("CTA_NON_ENGLISH", "").strip() or out.get("non_english", "english_only")
    ).lower()
    if out["non_english"] not in ("english_only", "translate"):
        raise ValueError(
            f"guardrails.non_english must be english_only or translate, not {out['non_english']!r}"
        )
    language_flag = env.get("CTA_LANGUAGE_STEP", "").strip().lower()
    out["language_step"] = (
        language_flag in ("1", "true", "yes", "on")
        if language_flag
        else bool(out.get("language_step", True))
    )
    out["injection_screen"] = (
        screen_flag in ("1", "true", "yes", "on") if screen_flag else bool(out["injection_screen"])
    )
    out["disabled"] = flag in ("1", "true", "yes", "on") if flag else bool(out.get("disabled"))
    return out


TRACING_VARIABLES = (
    "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING",
)  # fmt: skip


def enabled_tracing(env: dict | None = None) -> list[str]:
    """The LangSmith / LangChain tracing variables that are switched on (value true, 1 or yes).
    Tracing sends text to an outside service; nothing in this project enables it yet (Phase 3,
    step 6 will, with redacted text only)."""
    if env is None:
        load_dotenv(ROOT / ".env")
        env = dict(os.environ)
    return [k for k in TRACING_VARIABLES if env.get(k, "").strip().lower() in ("true", "1", "yes")]


def refuse_tracing(env: dict | None = None) -> None:
    """Raise at the start of an eval run if tracing is on, so a question or answer never leaves."""
    on = enabled_tracing(env)
    if on:
        raise RuntimeError(
            f"tracing is enabled ({', '.join(on)}); unset it: runs must not send text out"
        )


def cost_usd(cfg: dict, model: str, input_tokens: int, output_tokens: int = 0) -> float:
    """Dollar cost of a call from the price table; unknown models raise."""
    price = cfg["models"].get(model)
    if price is None:
        raise ValueError(f"no price entry for model '{model}'")
    return (input_tokens * price["input"] + output_tokens * price.get("output", 0.0)) / 1_000_000
