"""Optional developer tracing with LangSmith (docs/decisions.md, "Near-miss floor and tracing").

OFF by default, and only inside the API process. Tracing is on only if all three hold: the config
flag `tracing.enabled`, the environment variable `CTA_TRACING=on`, and `LANGSMITH_API_KEY`.

It is switched on IN THE PROCESS (`langsmith.tracing_context(enabled=True, client=...)` around the
one call that runs the router), never by setting LANGSMITH_TRACING or any other tracing variable,
so the refusal guard of `cta.settings` keeps working for the API and for the eval runners. The eval
runners never import this module.

Privacy, defence in depth: (1) the tracing context is entered only after the personal-data scrub
and every guardrail, and only the scrubbed English text is passed in; (2) the langsmith client
scrubs every input, output and metadata payload with the existing redactor; (3) a request blocked
by a guardrail returns before the context is entered, so it makes no trace. No IP address, cookie,
header, rate-limit hash or visitor identifier is ever added.
"""

import dataclasses
import logging
import os
import re
from contextlib import contextmanager

from dotenv import load_dotenv

from cta.api import screen
from cta.settings import ROOT

log = logging.getLogger("cta.api")

KEY_SHAPE = re.compile(r"(?:sk-|lsv2_)[A-Za-z0-9_\-]{12,}")
MAX_STRING = 6000
MAX_ITEMS = 60
MAX_DEPTH = 8
ON = ("on", "true", "1", "yes")
DEFAULT_PROJECT = "city-tech-assistant"
TAG = "city-tech-assistant"
UPLOAD_WARNING = "tracing upload failed (details withheld)"  # fixed text: never any payload


# ---- scrubbing: every string of every payload goes through the existing redactor ----


def scrub_string(text: str) -> str:
    """Emails, phones, SSN-shaped and 8-digit numbers, a name after "my name is", key shapes."""
    text = screen.scrub(KEY_SHAPE.sub("[KEY]", text))
    return text if len(text) <= MAX_STRING else text[:MAX_STRING] + " [truncated]"


REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def keep_request_id(key, value, depth: int):
    """The request id is a random 32-hex string made by the API, never personal data; the 8-digit
    ID rule must not cut it when it happens to hold eight digits in a row (found as the cause of a
    flaky test). Any other value of any other key is scrubbed as before."""
    if key == "request_id" and isinstance(value, str) and REQUEST_ID.match(value):
        return value
    return scrub_value(value, depth + 1)


def scrub_value(value, depth: int = 0):
    """A JSON-friendly copy of `value` with every string scrubbed. Long lists of numbers (embedding
    vectors) are summarised; other long lists are cut; other objects become scrubbed text."""
    if depth > MAX_DEPTH:
        return "[too deep]"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return scrub_string(value)
    if isinstance(value, bytes):
        return "[bytes]"
    if isinstance(value, dict):
        return {scrub_string(str(k)): keep_request_id(k, v, depth) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        items = list(value)
        if len(items) > 20 and all(isinstance(x, int | float) for x in items):
            return f"[{len(items)} numbers]"
        shown = [scrub_value(x, depth + 1) for x in items[:MAX_ITEMS]]
        return shown + [f"[{len(items) - MAX_ITEMS} more]"] if len(items) > MAX_ITEMS else shown
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        try:
            return scrub_value(dataclasses.asdict(value), depth + 1)
        except Exception:  # noqa: BLE001 - not copyable: fall back to its text
            return scrub_string(repr(value))
    dump = getattr(value, "model_dump", None)  # a pydantic model
    if callable(dump):
        try:
            return scrub_value(dump(), depth + 1)
        except Exception:  # noqa: BLE001
            return scrub_string(repr(value))
    return scrub_string(str(value))


def scrub_payload(payload):
    """The hide_inputs, hide_outputs and hide_metadata function of the langsmith client."""
    clean = scrub_value(payload)
    return clean if isinstance(clean, dict) else {"value": clean}


def embeddings_summary(response) -> dict:
    """What an embedding call records: how many vectors and how long, never the vectors."""
    data = getattr(response, "data", None) or []
    usage = getattr(response, "usage", None)
    return {"vectors": len(data), "dimensions": len(data[0].embedding) if data else 0,
            "total_tokens": getattr(usage, "total_tokens", None)}  # fmt: skip


# ---- the tracer ----


class NullRecorder:
    """What a request holds when tracing is off: nothing happens."""

    def finish(self, response) -> None:
        return None


class Recorder:
    def __init__(self, run):
        self.run = run

    def finish(self, response) -> None:
        """Add the outcome (route, abstained, ...) and the reply text to the root run. A failure
        here is logged without any text and never reaches the student."""
        try:
            self.run.add_metadata({
                "route": response.route, "answer_type": response.answer_type,
                "abstained": response.abstained, "abstain_reason": response.abstain_reason,
                "near_miss": response.how_found.near_miss,
            })  # fmt: skip
            self.run.end(outputs={"answer": response.answer})
        except Exception:  # noqa: BLE001
            log.warning("tracing could not record the outcome (details withheld)")


class Tracing:
    def __init__(self, client, project: str = DEFAULT_PROJECT):
        self.client, self.project = client, project

    @classmethod
    def build_client(cls, env: dict):
        """A langsmith client that scrubs every payload and omits runtime information."""
        from langsmith import Client

        def on_error(error) -> None:
            log.warning(UPLOAD_WARNING)

        return Client(
            api_key=env["LANGSMITH_API_KEY"], api_url=env.get("LANGSMITH_ENDPOINT") or None,
            hide_inputs=scrub_payload, hide_outputs=scrub_payload, hide_metadata=scrub_payload,
            omit_traced_runtime_info=True, tracing_error_callback=on_error,
        )  # fmt: skip

    @classmethod
    def from_settings(cls, cfg: dict, env: dict | None = None) -> "Tracing | None":
        """The tracer, or None: on only with the config flag, CTA_TRACING=on and the key."""
        if env is None:
            load_dotenv(ROOT / ".env")
            env = dict(os.environ)
        requested = env.get("CTA_TRACING", "").strip().lower() in ON
        flag = bool(cfg.get("tracing", {}).get("enabled", False))
        if not (requested and flag):
            if requested:
                log.warning("CTA_TRACING is on but tracing.enabled is false: tracing stays off")
            return None
        if not env.get("LANGSMITH_API_KEY", "").strip():
            log.warning("CTA_TRACING is on but LANGSMITH_API_KEY is not set: tracing stays off")
            return None
        project = env.get("LANGSMITH_PROJECT", "").strip() or DEFAULT_PROJECT
        return cls(cls.build_client(env), project)

    def flush(self) -> None:
        """Send what is still queued (called when the API stops, so no trace is lost)."""
        try:
            self.client.flush()
        except Exception:  # noqa: BLE001
            log.warning(UPLOAD_WARNING)

    def wrap(self, openai_client):
        """The OpenAI client with its chat calls traced, and its embedding call traced as a small
        run that records only the number of vectors. Outside a request nothing is recorded."""
        from langsmith import traceable
        from langsmith.wrappers import wrap_openai

        wrapped = wrap_openai(openai_client, tracing_extra={"client": self.client})
        original = wrapped.embeddings.create

        @traceable(name="embeddings", run_type="embedding", client=self.client,
                   process_outputs=embeddings_summary)  # fmt: skip
        def create(**kwargs):
            return original(**kwargs)

        wrapped.embeddings.create = create
        return wrapped

    @contextmanager
    def request(self, text: str, request_id: str):
        """One trace for one request. `text` must already be scrubbed (the API passes the text the
        router gets); the client scrubs every payload again."""
        import langsmith as ls

        with ls.tracing_context(enabled=True, client=self.client, project_name=self.project,
                                tags=[TAG]):  # fmt: skip
            with ls.trace(name="ask", run_type="chain", inputs={"question": text},
                          metadata={"request_id": request_id}, client=self.client,
                          project_name=self.project) as run:  # fmt: skip
                yield Recorder(run)
