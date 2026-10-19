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

# The two numbers of the crisis replies live here once. The distress reply and the one sentence
# added to every fixed "paused" reply (CRISIS_LINE, used by cta.api.guard) are built from them, so
# the launch-day re-check of 988 and 911 covers both.
LIFELINE = "988"
EMERGENCY = "911"
CRISIS_LINE = (
    f"If you are in crisis, you can call or text {LIFELINE} (the {LIFELINE} Suicide & Crisis "
    f"Lifeline) at any time; in an emergency, call {EMERGENCY}."
)  # holds nothing a student typed

TEXTS = {
    "distress": (
        "I'm really sorry you're going through this. I can't help with this, but you don't have "
        f"to face it alone. In the United States, you can call or text {LIFELINE} (the {LIFELINE} "
        "Suicide & Crisis Lifeline) at any time, day or night. If you or someone else is in "
        f"immediate danger, call {EMERGENCY}. Talking with someone you trust can help too."
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
# Danger from someone else (post-freeze, owner decision of Oct 16, 2026): fixed text supplied by the
# owner. Sources and the date they were checked: docs/decisions.md. The Public Safety line is kept
# here and not in config/contacts.yaml, because that file is checked against collected data
# (`cta.validate`) and this contact is not in it. Re-check every number before a public launch.
TEXTS["danger"] = (
    "I'm really sorry this is happening to you. If you are in immediate danger, call 911. If it "
    "is happening on campus, City Tech Public Safety is available 24 hours a day at "
    "(718) 260-5550 (from a campus phone, dial 5550, or 5555 in an emergency). For support with "
    "abuse or domestic violence, you can call the National Domestic Violence Hotline any time at "
    "1-800-799-7233 (SAFE) or text START to 88788. In New York City, the 24-hour NYC hotline is "
    "1-800-621-4673 (HOPE)."
)
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
REASONS = ("distress", "danger", "bereavement", "personal_data", "injection", "output", "stress")

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
# "going on" is also ordinary ("no point in going on the waitlist"): not followed by these words
GOING_ON = r"going on(?!\s+(?:the|a|this|that|my|to|with|in)\b)"
_ANYMORE = r"(?:any ?more|any longer)"
HOPELESS = tuple(
    re.compile(p)
    for p in (
        rf"{_I}[^.?!]{{0,25}}?\bgiv(?:e|ing) up on everything\b",
        rf"{_I}[^.?!]{{0,15}}?\b(?:can'?t|cannot|can not)\s+(?:do|take|handle)\s+(?:it|this)\s+"
        r"(?:any ?more|any longer)\b",
        rf"\b(?:there'?s|there is)\s+no point\s+(?:in|to)\s+(?:anything|{GOING_ON}|living|life)\b",
        rf"{_I}[^.?!]{{0,40}}?\bno point\s+(?:in|to)\s+(?:anything|{GOING_ON}|living|life)\b",
        rf"{_I}[^.?!]{{0,20}}?\b(?:want(?:ed)? to|wanna)\s+disappear(?!\s+(?:from|off|out)\b)",
        # tester round 2, item A: passive ideation, first person, narrow
        r"\b(?:don'?t|do not)\s+want to be (?:alive|dead)\b",
        rf"\b(?:don'?t|do not)\s+want to be here\s+{_ANYMORE}\b",
        r"\b(?:don'?t|do not)\s+want to wake up\s+(?:tomorrow|again|any ?more)\b",
        r"\bwish\s+(?:that\s+)?(?:i|we)\s+(?:was|were)(?:n'?t| not)\s+(?:here|alive|around)\b",
        r"\bwish\s+(?:that\s+)?i\s+(?:was|were)\s+never\s+born\b",
        r"\bwish\s+i\s+hadn'?t\s+been born\b",
        r"\bbetter off without me\b",
        r"\bno reason to (?:keep going|keep living|go on)(?!\s+(?:to|the|a|with|in|for|my)\b)",
        r"\bend(?:ing)? it all\b",
        r"\btake my (?:own )?life\b",
        # post-freeze sweep (Oct 16, 2026): plans, means, self-harm, goodbyes, text-speak
        rf"{_I}\s+(?:am\s+)?(?:about to|going to|gonna)\s+end it"
        r"(?:\s+(?:tonight|today|now|soon|tomorrow|right now))?\s*[.!?,]*\s*$",
        r"\b(?:don'?t|do not)\s+want to wake up\s*[.!?,]*\s*$",
        r"\b(?:pills|a gun|a rope|a knife|a razor)\b[^.?!]{0,50}"
        r"\b(?:going to|gonna|about to|will|want to|wanna)\s+"
        r"(?:take|swallow|use|hang|shoot|end|do it)\b",
        r"\b(?:cutting|harming|hurting|burning)\s+myself\b(?!\s+(?:some|a|off|loose|short|out|up)\b)",
        r"\b(?:this is|it'?s) my last (?:message|text|post|goodbye)\s*[.!?,]*\s*$",
        r"\bgoodbye\b[^.?!]{0,25}\b(?:i'?m|i am) done\s*[.!?,]*\s*$",
        r"^\s*kms\s*[.!?]*\s*$|\b(?:gonna|going to|wanna|want to|just|ima|i'll)\s+kms\b",
        r"\bunaliv(?:e|ing)\s+(?:myself|me)\b",
        # owner decisions on the ambiguous list (Oct 16, 2026)
        rf"{_I}[^.?!]{{0,12}}?\bwant (?:it|this|everything) (?:all )?to (?:just )?(?:stop|end)\b",
        r"\bgoodbye forever\b|\bthank you for everything[,.!]?\s*goodbye\b",
        # post-freeze safety fix: "i am about to die", "im going to die tonight" (a bare statement
        # or a time word at the end; "going to die if i fail" is the ambiguous case below)
        rf"{_I}\s+(?:am\s+)?(?:about to|going to|gonna|ready to|planning to|will|'ll)\s+die"
        r"(?:\s+(?:tonight|today|now|soon|tomorrow|right now|this (?:week|weekend)|here))?"
        r"\s*[.!?,]*\s*$",
        r"\b(?:isn'?t|is not|not) worth living\b",
        rf"\b(?:don'?t|do not) think (?:i|that i) can (?:do|take|handle)\s+(?:it|this)\s+{_ANYMORE}"
        r"\s*[.!?,]*\s*$",
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
    "don't want to live": r"don'?t want to live(?!\s+(?:on|in|with|at|near|off|by|where|there)\b)",
    "do not want to live": r"do not want to live(?!\s+(?:on|in|with|at|near|off|by|where|there)\b)",
    "can't go on": r"can'?t go on(?:\s+(?:anymore|any longer|like this|living)\b|\s*[.!?,]*\s*$)",
}


# Idioms removed BEFORE matching (tester round 2, T03: "i wanna die of embarrassment" is not a
# crisis). Only the idiom's own words go; anything else in the question is still matched.
_FEELING = r"(?:embarrass\w*|shame|laughter|laughing|boredom|bored|cringe|hunger|thirst|curiosity)"
IDIOMS = tuple(
    re.compile(p)
    for p in (
        rf"\b(?:die|dying|dead|death)\s+(?:of|from)\s+{_FEELING}\b",
        r"\b(?:die|dying|dead)\s+laughing\b",
        r"\bdying to\s+\w+",
        r"\bdead tired\b",
        r"\bkilling me\b",
        r"\b(?:gonna|going to|will|would|'ll)\s+kill me\b",
    )
)  # fmt: skip


def without_idioms(text: str) -> str:
    for idiom in IDIOMS:
        text = idiom.sub(" ", text)
    return text


LEET = (  # "k1ll myself", "k!ll", "d1e", "su1c1de": digits and ! standing for i inside a few words
    (re.compile(r"\bk[1!]ll"), "kill"),
    (re.compile(r"\bd[1!]e\b"), "die"),
    (re.compile(r"\bsu[1!]c[1!]d"), "suicid"),
    (re.compile(r"\bd[1!]ed\b"), "died"),
)


def plain_text(question: str) -> str:
    """Lower case, with emoji and other symbols turned into spaces so that "i cant go on 😳"
    still ends at "go on", and with the lightest leetspeak undone. Letters, digits, apostrophes
    and ordinary punctuation stay."""
    text = re.sub(r"[^\w\s'.,!?;:\"()\[\]-]", " ", lowered(question))
    for pattern, plain in LEET:
        text = pattern.sub(plain, text)
    return text


def is_distress(question: str) -> bool:
    text = without_idioms(plain_text(question))
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
# tester round 2 (T02): stress said without a stress word, still first person or a fixed phrase
STRESS_PHRASES = re.compile(
    rf"{_I}[^.?!]{{0,15}}?\b(?:burnt|burned) out\b|{_I}[^.?!]{{0,15}}?\bfalling apart\b"
    rf"|{_I}[^.?!]{{0,15}}?\bstressing out\b|\b(?:can'?t|cannot) cope\b"
    r"|\btoo much for me\b|\b(?:all|everything|school|life|work|it|this) (?:is|its|it's) "
    r"(?:just |all )?too much\b|\b(?:its|it's) all too much\b"
    r"|\b(?:gonna|going to|will) fail everything\b"
    r"|\bwhat'?s the point of (?:anything|it all|all this|any of this)\b"
    rf"|\b(?:don'?t|do not) think (?:i|that i) can (?:do|take|handle)\s+(?:it|this)\s+{_ANYMORE}"
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


# Ambiguous first-person "die" statements ("i'll die if i fail this class"): usually an
# exaggeration, but not always. They get the gentle Tier 2 reply (no number, no claim), never a
# silent pass (post-freeze safety fix; the owner can move them to Tier 1).
DIE_AMBIGUOUS = re.compile(
    rf"{_I}[^.?!]{{0,20}}?\b(?:will|'ll|would|gonna|going to|might|could|about to)\s+die\b"
)


def is_ambiguous_die(question: str) -> bool:
    return bool(DIE_AMBIGUOUS.search(without_idioms(plain_text(question))))


def is_stress(question: str) -> bool:
    """A first-person stress word, no topic noun, course code or department, at most 20 words."""
    text = lowered(question)
    words = WORD.findall(text)
    if not words or len(words) > STRESS_MAX_WORDS:
        return False
    if not (STRESS_FRAMED.search(text) or STRESS_PHRASES.search(text)):
        return False
    if names_stress_topic(words) or detect_departments(question):
        return False
    return not COURSE_CODE.search(TERM_NAME.sub(" ", question))


# Defence in depth (tester round 2, T01): the model-written topic sentence of an abstain must never
# name suicide or self-harm; if it does, the whole reply becomes the Tier 1 crisis reply.
SELF_HARM_TOPIC = re.compile(
    r"suicid|desire to die|want(?:s|ed|ing)? to die|self[- ]harm"
    r"|end(?:ing)? (?:my|his|her|their) life"
    r"|kill(?:ing)? (?:my|him|her|them)self|ending it all|thoughts? of dying"
    # post-freeze safety fix: a topic that restates the student's own dying or death
    r"|\b(?:your|my|own|imminent) death\b|\bdying\b|\b(?:about|going) to die\b",
    re.IGNORECASE,
)


def names_self_harm(answer: str) -> bool:
    return bool(SELF_HARM_TOPIC.search(answer.replace("’", "'")))


# Danger from someone else (first person, about being harmed or unsafe). A place alone ("the bus is
# not safe at night"), an injury or object ("my back is hurting me") and a joke ("my little brother
# hit me with a pillow") do not match: the pattern needs a named person or "at home".
_PEOPLE = (
    "partner|boyfriend|girlfriend|husband|wife|dad|mom|mother|father|stepdad|stepmom|ex|"
    "fiance|fiancee|parent|parents|uncle|aunt|brother|sister|roommate|landlord|boss"
)
_HARM = (
    r"(?:hits|hit|hitting|beats|beating|hurts|hurting|abuses|abusing|chokes|choking|punches|"
    r"slaps|kicks|threatens|threatening|attacks|stalks)"
)
_SELF = r"\b(?:i|im|i'm|i am)\s+(?:am\s+)?"
_AFRAID = r"(?:afraid|scared|terrified|frightened)"
DANGER = tuple(
    re.compile(p)
    for p in (
        rf"\b(?:someone|somebody)\s+(?:is|keeps|has been|was)?\s*{_HARM}\s+me\b",
        rf"\bmy\s+(?:{_PEOPLE})\s+(?:is |has been |keeps )?{_HARM}\s+me\b",
        rf"{_SELF}not safe\s+(?:at (?:my )?home|in my (?:home|house|apartment)|"
        r"with (?:him|her|them))\b",
        rf"{_SELF}being\s+(?:abused|beaten|hit|hurt|threatened|stalked|assaulted)\b",
        rf"{_SELF}{_AFRAID}\s+(?:to go (?:back )?home|of going (?:back )?home)\b",
        rf"{_SELF}{_AFRAID}\s+of\s+my\s+(?:{_PEOPLE})\b"
        r"(?!\s+(?:finding|seeing|knowing|when|if|learning|reading|hearing|getting)\b)",
    )
)  # fmt: skip


def is_danger(question: str) -> bool:
    text = plain_text(question)
    return any(p.search(text) for p in DANGER)


def is_bereavement(question: str) -> bool:
    text = lowered(question)
    return any(p.search(text) for p in BEREAVEMENT)


def is_personal_refusal(question: str) -> bool:
    return bool(SSN.search(question) or LONG_DIGITS.search(question))


def is_injection(question: str) -> bool:
    return any(p.search(question) for p in INJECTION)


# Batch 1, item 2 (docs/archive/polish-triage.md G1-3): more ways a student may type their own name.
# Plain patterns, no name list and no library; they run on the QUESTION only. For the cues
# "i'm", "i am", "this is", "name is", "name:" and "call me" the next word must start with a
# capital letter, be more than an acronym (a capital followed by lowercase letters) and not be a
# common word (NOT_NAMES). After "my name is" a lowercase name is also removed, up to three
# words, stopping at the first word that is not a name.
CAPITAL = r"[A-Z][a-z'’-]+"
NAME_CUES = re.compile(
    rf"(?i:\bi'?m|\bi am|\bthis is|\bname is|\bname:|\bcall me)"
    rf"\s+({CAPITAL}(?:\s+{CAPITAL}){{0,2}})"
)
LOWER_WORD = r"[a-z][a-z'’-]*"
LOWER_NAME = re.compile(rf"(?i:my name is|my name's)\s+({LOWER_WORD}(?:\s+{LOWER_WORD}){{0,2}})\b")
NOT_NAMES = frozenset(
    """a an the and or but so if as at by of on in to for with from about not no yes sure
    ok okay fine confused lost sorry stressed worried happy new transfer freshman
    sophomore junior senior student currently also just still really very too trying
    looking wondering asking having getting taking interested eligible registered
    enrolled late early here there what when where why how who which can could do does
    did is are was were will would should may might please thanks thank hi hello hey
    january february march april may june july august september october november
    december monday tuesday wednesday thursday friday saturday sunday fall spring summer
    winter city tech cuny cunyfirst brightspace pathways computer systems technology
    mathematics math electrical telecommunications engineering dental hygiene registrar
    bursar financial advisement admissions advisor office department college school
    semester term class course degree major wrong missing misspelled spelled listed showing
    shown incorrect different changed written printed appearing appears off""".split()
)  # fmt: skip


def _is_name_word(word: str) -> bool:
    return word.lower().strip("'’-") not in NOT_NAMES and not any(
        word.lower().startswith(t) for t in TOPIC_WORDS if len(t) >= 4
    )


def _name_span(match: re.Match) -> str:
    """The words of the match that are a name: stop at the first word that is not one."""
    words = match.group(1).split()
    keep: list[str] = []
    for w in words:
        if not _is_name_word(w):
            break
        keep.append(w)
    return " ".join(keep)


def scrub_names(text: str) -> str:
    """[NAME] for a name typed after "my name is" (any case) or after one of NAME_CUES."""
    text = NAME.sub(lambda m: m.group(0).replace(m.group(1), "[NAME]"), text)

    def mask(match: re.Match) -> str:
        span = _name_span(match)
        return match.group(0).replace(span, "[NAME]", 1) if span else match.group(0)

    return NAME_CUES.sub(mask, LOWER_NAME.sub(mask, text))


def scrub(question: str) -> str:
    """Emails, phones, SSN-shaped and 8-digit numbers (cta.redact), and a name typed after "my name
    is", "my name's", "i'm", "i am", "this is", "name is", "name:" or "call me"."""
    return scrub_names(redact(question))


def removed_personal_details(original: str, clean: str) -> bool:
    """True when `clean` holds an [EMAIL], [PHONE], [ID] or [NAME] tag `original` did not have."""
    pattern = re.compile(r"\[(?:" + "|".join(NOTE_TAGS) + r")\]")
    return len(pattern.findall(clean)) > len(pattern.findall(original))


def screen(question: str, g: dict) -> Screened:
    """The first guardrail that applies, in the order of the plan: distress, bereavement,
    personal data, injection; else the scrubbed question."""
    if is_distress(question):
        return Screened("distress", question)
    if is_danger(question):  # after Tier 1: a message that matches both gets the 988 reply
        return Screened("danger", question)
    if is_bereavement(question):
        return Screened("bereavement", question)
    if g["personal_data"] == "redact_and_refuse" and is_personal_refusal(question):
        return Screened("personal_data", question)
    if g["injection_screen"] and is_injection(question):
        return Screened("injection", question)
    if is_stress(question) or is_ambiguous_die(question):
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
