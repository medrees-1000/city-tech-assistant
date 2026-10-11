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
