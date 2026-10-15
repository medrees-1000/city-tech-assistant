"""The language step of the API (tester round 1b, Part 2; docs/language-plan.md, docs/decisions.md).

A question that does not look English gets ONE small model call that detects its language and
translates it to English; the rest of the pipeline (and every guardrail screen) then works on the
English text. English-looking questions never reach the model call and are never changed.

Plain code decides everything the model must not decide: whether to call at all (the prefilter),
whether the reply is usable, and whether the note line is safe to show. A failed or unusable call
falls back to today's behaviour with the original text.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cta.graph.llm import JsonCall, json_call

PROMPT = Path(__file__).resolve().parent / "prompts" / "language.txt"

# The prefilter list (docs/decisions.md): common English function words that are rare in Spanish,
# French, Portuguese and Italian. A question skips the language step when it is pure ASCII and holds
# at least two distinct words of this list.
ENGLISH_WORDS = frozenset(
    "the is what when how does can my for of are and i to you your this that with from about "
    "which who where why have there need should will".split()
)
WORD = re.compile(r"[a-z]+")
MIN_ENGLISH_WORDS = 2

FALLBACK_NOTE = "This answer is in English; the sources are in English."
NOTE_MAX_CHARS = 160
ENGLISH_MAX_CHARS = 1000
ECHOED_LABEL = re.compile(r"^\s*(?:question|translation|english)\s*:\s*", re.IGNORECASE)
CODE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")
UNSAFE_NOTE = re.compile(r"\d|@|https?:|www\.|[\r\n\[\]<>]", re.IGNORECASE)


def looks_english(text: str) -> bool:
    """Pure ASCII and at least two distinct English function words: skip the language step."""
    if not text.isascii():
        return False
    return len(set(WORD.findall(text.lower())) & ENGLISH_WORDS) >= MIN_ENGLISH_WORDS


@dataclass
class Language:
    code: str = "en"  # the detected language ("en" for English and for every fallback)
    english: str = ""  # the text every later step works on (the original when code is "en")
    note: str | None = None  # one short line in the student's language; None when code is "en"
    skipped: bool = True  # the prefilter skipped the model call
    failed: bool = False  # the call failed or its reply was unusable (then the original is used)
    call: JsonCall | None = None  # tokens, cost and time of the model call


def valid_note(raw) -> str:
    """The note when it is one short safe sentence; else the fixed English line."""
    if not isinstance(raw, str) or "\n" in raw or "\r" in raw:
        return FALLBACK_NOTE
    text = " ".join(raw.split())
    if not text or len(text) > NOTE_MAX_CHARS or UNSAFE_NOTE.search(text):
        return FALLBACK_NOTE
    return text


def is_english_code(code: str) -> bool:
    return code.lower() == "en" or code.lower().startswith("en-")


def detect(text: str, cfg: dict, client_factory: Callable) -> Language:
    """The language and the English text of `text` (already redacted). Never raises."""
    if looks_english(text):
        return Language(english=text)
    messages = [
        {"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
        {
            "role": "user",
            "content": text,
        },  # the bare text: a prefix such as "Question:" is echoed back
    ]
    try:
        call = json_call(client_factory(), cfg, messages, "language request")
    except Exception:  # noqa: BLE001 - e.g. no client: today's behaviour with the original
        return Language(english=text, skipped=False, failed=True)
    data = call.data or {}
    code, english = data.get("language"), data.get("english")
    usable = (
        isinstance(code, str)
        and CODE.fullmatch(code.strip())
        and isinstance(english, str)
        and 0 < len(english.strip()) <= ENGLISH_MAX_CHARS
    )
    if not usable:
        return Language(english=text, skipped=False, failed=True, call=call)
    code = code.strip()
    if is_english_code(code):
        return Language(
            code="en", english=text, skipped=False, call=call
        )  # the original, byte for byte
    return Language(
        code=code, english=" ".join(ECHOED_LABEL.sub("", english, count=1).split()),
        note=valid_note(data.get("note")),
        skipped=False, call=call,
    )  # fmt: skip


def add_to_response(response, lang: Language) -> None:
    """Record the step on an AskResponse: `how_found.language`, and the call's tokens, time and cost
    (so the daily spend cap counts them). Nothing is added when the prefilter skipped the step."""
    if lang.skipped:
        return
    hf = response.how_found
    english = lang.english if lang.code != "en" else None
    hf.language = {"code": lang.code, "english": english or None}
    call = lang.call
    if call is None:
        return
    hf.tokens["language_prompt"] = call.prompt_tokens
    hf.tokens["language_completion"] = call.completion_tokens
    hf.tokens["prompt"] = hf.tokens.get("prompt", 0) + call.prompt_tokens
    hf.tokens["completion"] = hf.tokens.get("completion", 0) + call.completion_tokens
    hf.cost_usd["language"] = call.cost
    hf.cost_usd["total"] = hf.cost_usd["total"] + call.cost
    hf.stages_ms["language"] = round(call.ms, 1)
    hf.stages_ms["total"] = (hf.stages_ms["total"] or 0.0) + round(call.ms, 1)
