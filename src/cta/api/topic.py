"""Topic-aware wording of a generic abstention (docs/decisions.md, "Chat polish").

One small model call returns {topic, in_scope}; the CODE writes the sentence from two fixed
templates, the model never does. Any failure or unusable reply leaves the generic sentence.
"""

import re
import unicodedata
from pathlib import Path

from cta.graph.llm import json_call
from cta.redact import redact

PROMPT = Path(__file__).resolve().parent / "prompts" / "topic.txt"
GENERIC_CODES = ("below_threshold", "model")  # the abstain codes whose text is a generic sentence
OUT_OF_SCOPE = (
    "I can only help with City Tech questions (registration, deadlines, advising, tuition and aid, "
    "and four departments), so I can't help with {topic}."
)
NOT_FOUND = "I couldn't find anything about {topic} in the City Tech pages and documents I use."
MAX_WORDS, MAX_CHARS = 8, 60

LINK = re.compile(r"https?://\S+|www\.\S+|\S+@\S+", re.IGNORECASE)
MARKDOWN = re.compile(r"[\[\]()*_`#>~|\\{}<>\"“”‘’']")


def sanitize_topic(raw) -> str | None:
    """A topic that is safe to put in a sentence, or None (then the generic sentence stays)."""
    if not isinstance(raw, str):
        return None
    text = "".join(" " if unicodedata.category(c).startswith("C") else c for c in raw)
    text = MARKDOWN.sub(" ", LINK.sub(" ", text))
    words = text.split()[:MAX_WORDS]
    text = " ".join(words).strip(" .,;:!?-")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0].strip(" .,;:!?-")
    if not text or redact(text) != text or not re.search(r"[A-Za-z]", text):
        return None  # empty, or an email, phone, SSN or ID pattern: do not use
    return text


def sentence(topic: str, in_scope: bool) -> str:
    return (NOT_FOUND if in_scope else OUT_OF_SCOPE).format(topic=topic)


def rewrite(question: str, response, cfg: dict, client_factory) -> None:
    """Replace the generic abstain sentence of `response` (an AskResponse) when the topic call
    gives a usable topic. Adds the call's tokens, cost and time to the response in every case."""
    if not (response.abstained and response.abstain_reason in GENERIC_CODES):
        return
    messages = [
        {"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
        {"role": "user", "content": f"Question: {question}"},
    ]
    try:
        call = json_call(client_factory(), cfg, messages, "topic request")
    except Exception:  # noqa: BLE001 - e.g. no client: the generic sentence stays
        response.how_found.abstain_wording = "generic"
        return
    hf = response.how_found
    hf.stages_ms["topic"] = round(call.ms, 1)
    hf.stages_ms["total"] = (hf.stages_ms["total"] or 0.0) + round(call.ms, 1)
    hf.tokens["topic_prompt"] += call.prompt_tokens
    hf.tokens["topic_completion"] += call.completion_tokens
    hf.tokens["prompt"] += call.prompt_tokens
    hf.tokens["completion"] += call.completion_tokens
    hf.cost_usd["topic"] = call.cost
    hf.cost_usd["total"] = hf.cost_usd["total"] + call.cost
    data = call.data or {}
    topic, in_scope = sanitize_topic(data.get("topic")), data.get("in_scope")
    if topic and isinstance(in_scope, bool):
        response.answer = sentence(topic, in_scope)
        hf.abstain_wording, hf.topic_in_scope = "topic", in_scope
    else:
        hf.abstain_wording = "generic"
