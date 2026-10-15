"""Content guards of the API (Phase 4 step 7, Stage 2; docs/decisions.md): distress, bereavement,
personal data, prompt injection and an answer check. Plain code, no model call, API layer only.

The lists are fixed in docs/decisions.md ("Stage 2 ... keep rule") before this code was written.
Every fixed reply is a constant; none contains anything the student typed.
"""

import os
import re
from dataclasses import dataclass

from cta.graph.clarify import CODE as COURSE_CODE
from cta.graph.clarify import TERM_NAME, TOPIC_WORDS, WORD
from cta.index.departments import detect_departments
from cta.redact import redact

TEXTS = {
    "distress": (
        "I'm really sorry you're going through this. I can't help with this, but you don't have "
        "to face it alone. In the United States, you can call or text 988 (the 988 Suicide & "
        "Crisis Lifeline) at any time, day or night. If you or someone else is in immediate "
        "danger, call 911. Talking with someone you trust can help too."
    ),
    "bereavement": (
        "I'm so sorry for your loss. I can't help with this here, but please reach out to "
        "someone you trust. When you're ready, you can ask me about City Tech deadlines, "
        "Incompletes or other questions."
    ),
    "personal_data": (
        "Please don't type personal numbers such as a Social Security number. I don't need "
        "them to answer questions about City Tech."
    ),
    "injection": (
        "I can only help with City Tech registration, deadlines, advising, tuition and payment, "
        "financial aid, and four departments: Computer Systems Technology, Mathematics, "
        "Electrical and Telecommunications Engineering Technology, and Dental Hygiene. Could "
        "you ask about one of those?"
    ),
}
TEXTS["output"] = TEXTS["injection"]
# Tier 2 (tester round 1, item A): ordinary academic stress. No number, no contact, no claim.
TEXTS["stress"] = (
    "That sounds really stressful, and I'm sorry you're dealing with it. I can't give personal "
    "advice, but I can show you the rules and dates that apply. For example, I can look up "
    "withdrawing from a class, Incompletes, financial aid, or advising. Just ask about the one "
    "you need."
)
# distress_reply "none": the same kind reply without the 988 and 911 sentences (option B)
DISTRESS_NO_NUMBER = (
    "I'm really sorry you're going through this. I can't help with this, but you don't have to "
    "face it alone. Talking with someone you trust, or reaching local emergency services if you "
    "are in danger, can help."
)
REASONS = ("distress", "bereavement", "personal_data", "injection", "output", "stress")

DISTRESS = (
    "kill myself", "killing myself", "suicide", "suicidal", "end my life", "ending my life",
    "take my own life", "want to die", "wanna die", "wish i was dead", "wish i were dead",
    "hurt myself", "harm myself", "self-harm", "self harm", "cut myself", "don't want to live",
    "do not want to live", "no reason to live", "can't go on", "better off dead",
)  # fmt: skip

# Tier 1 additions (tester round 1, item A): first-person hopeless phrases. Each needs "i" (or im,
# i'm, i am) near the phrase, or is a flat statement of hopelessness; "can't ... anymore" needs the
# "anymore", and "don't want to be here" only counts at the end of the text.
_I = r"\b(?:i|im|i'm|i am)\b"
HOPELESS = tuple(
    re.compile(p)
    for p in (
        rf"{_I}[^.?!]{{0,25}}?\bgiv(?:e|ing) up on everything\b",
        rf"{_I}[^.?!]{{0,15}}?\b(?:can'?t|cannot|can not)\s+(?:do|take|handle)\s+(?:it|this)\s+"
        r"(?:any ?more|any longer)\b",
        r"\b(?:there'?s|there is)\s+no point\s+(?:in|to)\s+(?:anything|going on|living|life)\b",
        rf"{_I}[^.?!]{{0,40}}?\bno point\s+(?:in|to)\s+(?:anything|going on|living|life)\b",
        rf"{_I}[^.?!]{{0,20}}?\b(?:want(?:ed)? to|wanna)\s+disappear\b",
        rf"{_I}[^.?!]{{0,20}}?\b(?:don'?t|do not)\s+want to be here"
        r"(?:\s+(?:any ?more|any longer))?\s*[.!?,]*\s*$",
    )
)  # fmt: skip

RELATIVES = (
    "mom|mother|mama|dad|father|papa|parent|parents|brother|sister|grandmother|grandfather|"
    "grandma|grandpa|grandparent|son|daughter|husband|wife|partner|friend|uncle|aunt|cousin|"
    "roommate|classmate"
)
BEREAVEMENT = (
    re.compile(rf"\bmy (?:{RELATIVES})\b[^.?!]{{0,40}}\b(?:died|passed away|was killed|is dead)\b"),
    re.compile(rf"\blost my (?:{RELATIVES})\b"),
    re.compile(rf"\b(?:death|funeral) of my (?:{RELATIVES})\b"),
    re.compile(rf"\bmy (?:{RELATIVES})['’]s (?:funeral|death)\b"),
)

SSN = re.compile(r"(?<!\d)\d{3}[- ]\d{2}[- ]\d{4}(?!\d)")
LONG_DIGITS = re.compile(r"\d{9,}")
NAME = re.compile(r"(?i:my name is|my name's)\s+([A-Z][a-z'’-]+(?:\s+[A-Z][a-z'’-]+){0,2})")

_GAP = r"(?:(?:all|any|your|the|my|previous|prior|above|earlier)\s+)+"
INJECTION = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\bignore\s+{_GAP}instructions?\b",
        r"\b(?:disregard|forget)\s+(?:all|any|your|the|previous)\s+(?:instructions|rules|prompt)\b",
        r"\boverride\s+(?:your|the)\s+(?:rules|instructions|safety)\b",
        r"\b(?:reveal|show|print|repeat|display|output|leak|tell me)\s+(?:me\s+)?(?:your|the)\s+"
        r"(?:system\s+)?(?:prompt|instructions)\b",
        r"\bwhat (?:is|are) your\s+(?:system\s+)?(?:prompt|instructions)\b",
        r"\bsystem prompt\b",
        r"\byou are now\s+(?:an?\s|the\s|my\s|no longer\b|free\b|unrestricted\b)",
        r"\bpretend\s+(?:to be|you are|that you)\b",
        r"\bact as\s+(?:if|though)\b",
        r"\bact as\s+an?\s+(?:unrestricted|different|new|evil|jailbroken|hacker|developer|admin)\b",
        r"\brole-?play\b",
        r"\bdeveloper mode\b",
        r"\bjailbreak\b",
        r"\bdo anything now\b",
        r"\bnew instructions:",
        r"</?\s*system\s*>",
        r"(?m)^\s*###\s*system\b",
    )
)  # fmt: skip
KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_-]{20,}")


# Said at the start of an answer when an e-mail, phone number, ID-shaped number or a name after
# "my name is" was removed from the question (tester round 1 item E; names added in round 1b).
# Not for an SSN-shaped number: that question is refused.
PERSONAL_NOTE = "I removed what looked like personal details from your question before answering."
NOTE_TAGS = ("EMAIL", "PHONE", "ID", "NAME")


@dataclass
class Screened:
    reason: str | None  # one of REASONS, or None when the question may go on
    question: str  # the question as it goes to the model and the log (scrubbed)
    scrubbed: bool = False  # something was replaced
    removed_details: bool = False  # an e-mail, phone, ID-shaped number or name was removed


def lowered(text: str) -> str:
    return text.lower().replace("’", "'")


# "can't go on" is also ordinary ("I can't go on the waitlist"): it counts as distress only at the
# end of a sentence or with "anymore", "any longer", "like this" or "living" (narrowed after the
# ordinary-question set found the false positive; docs/decisions.md).
NARROWED = {
    "can't go on": r"can't go on(?:\s+(?:anymore|any longer|like this|living)\b|\s*[.!?,]*\s*$)"
}


def is_distress(question: str) -> bool:
    text = lowered(question)
    if any(p.search(text) for p in HOPELESS):
        return True
    return any(re.search(NARROWED.get(p, rf"\b{re.escape(p)}"), text) for p in DISTRESS)


# Tier 2: ordinary academic stress, no crisis words (tester round 1, item A; docs/decisions.md).
_STRESS = r"(?:stressed|overwhelmed|anxious|panicking|panicked|freaking out|failing out|so worried)"
# The stress word must follow a first-person word closely (at most three words between, none of
# them "for", "of", "to", "with", "about", "help" or "find"), so "how do I find help for stressed
# students" does not count: found by the near-miss set and narrowed (docs/decisions.md).
STRESS_FRAMED = re.compile(
    r"\b(?:i|im|i'm|i am|i've|ive|me|myself)\b"
    r"(?:\s+(?!(?:for|of|to|with|about|help|find)\b)[a-z']+){0,3}?"
    rf"\s+{_STRESS}\b|\b(?:i|im|i'm|i am|i've|ive)\s+{_STRESS}\b"
)
STRESS_MAX_WORDS = 20
STRESS_TOPIC_EXTRA = ("requirement", "pathway", "elective")  # for this tier only
STEMS = (*TOPIC_WORDS, *STRESS_TOPIC_EXTRA)


def names_stress_topic(words: list[str]) -> bool:
    """The CLARIFY topic list, with whole-word matching for stems of four letters or fewer ("fee"
    and "fees" count, "feel" and "lately" do not)."""
    for w in words:
        for stem in STEMS:
            if len(stem) >= 5:
                hit = w.startswith(stem)
            else:
                hit = w in (stem, stem + "s", stem + "ed", stem + "ing")
            if hit:
                return True
    return False


def is_stress(question: str) -> bool:
    """A first-person stress word, no topic noun, course code or department, at most 20 words."""
    text = lowered(question)
    words = WORD.findall(text)
    if not words or len(words) > STRESS_MAX_WORDS:
        return False
    if not STRESS_FRAMED.search(text):
        return False
    if names_stress_topic(words) or detect_departments(question):
        return False
    return not COURSE_CODE.search(TERM_NAME.sub(" ", question))


def is_bereavement(question: str) -> bool:
    text = lowered(question)
    return any(p.search(text) for p in BEREAVEMENT)


def is_personal_refusal(question: str) -> bool:
    return bool(SSN.search(question) or LONG_DIGITS.search(question))


def is_injection(question: str) -> bool:
    return any(p.search(question) for p in INJECTION)


def scrub(question: str) -> str:
    """Emails, phones, SSN-shaped and 8-digit numbers (cta.redact), and a name after "my name is"
    or "my name's"."""
    return NAME.sub(lambda m: m.group(0).replace(m.group(1), "[NAME]"), redact(question))


def removed_personal_details(original: str, clean: str) -> bool:
    """True when `clean` holds an [EMAIL], [PHONE], [ID] or [NAME] tag `original` did not have."""
    pattern = re.compile(r"\[(?:" + "|".join(NOTE_TAGS) + r")\]")
    return len(pattern.findall(clean)) > len(pattern.findall(original))


def screen(question: str, g: dict) -> Screened:
    """The first guardrail that applies, in the order of the plan: distress, bereavement,
    personal data, injection; else the scrubbed question."""
    if is_distress(question):
        return Screened("distress", question)
    if is_bereavement(question):
        return Screened("bereavement", question)
    if g["personal_data"] == "redact_and_refuse" and is_personal_refusal(question):
        return Screened("personal_data", question)
    if g["injection_screen"] and is_injection(question):
        return Screened("injection", question)
    if is_stress(question):
        return Screened("stress", question)
    clean = scrub(question) if g["personal_data"] != "off" else question
    return Screened(None, clean, clean != question, removed_personal_details(question, clean))


def reply(reason: str, g: dict) -> str:
    if reason == "distress" and g["distress_reply"] == "none":
        return DISTRESS_NO_NUMBER
    return TEXTS[reason]


def leaks_key(answer: str, env: dict | None = None) -> bool:
    """True when the answer holds the API key or a key-shaped string."""
    key = (env if env is not None else os.environ).get("OPENAI_API_KEY", "")
    return bool(KEY_SHAPE.search(answer) or (len(key) >= 8 and key in answer))
