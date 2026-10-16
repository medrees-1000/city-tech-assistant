"""Post-freeze safety fix (Oct 16, 2026): a message that fell through ("I am about to die").
Data only; written with the fix. Not part of the pre-registered sets in tests/crisis_phrases.py."""

BASE_POSITIVES = [
    "I am about to die",
    "im about to die",
    "I'm going to die tonight",
    "I want to die",
    "I'm going to kill myself",
    "I can't go on",
    "I don't want to be alive",
]


def variants(text: str) -> list[str]:
    """Plain, with trailing emoji, upper case, mixed case, and without apostrophes."""
    no_apostrophe = text.replace("'", "")
    mixed = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
    return [text, text + " 😳😳", text.upper(), mixed, no_apostrophe, no_apostrophe + " 😳"]


POSITIVES = [v for base in BASE_POSITIVES for v in variants(base)]

# Must not fire any tier.
NEGATIVES = [
    "I'm dying to know when registration opens",
    "this deadline is killing me",
    "my laptop is dead",
    "I'm dead tired after finals",
    "I could die of embarrassment, when is the add/drop deadline",
    "this class is going to kill me, what is the withdrawal deadline",
    "my phone died, when does registration open",
    "I can't go on the waitlist, what do I do",
    "when is the last day to drop a class",
]

# Ambiguous: usually an exaggeration. They get the gentle Tier 2 reply (stress), not 988.
AMBIGUOUS = [
    "I'll die if I fail this class",
    "I will die if I fail this class",
    "im gonna die if i fail calc",
    "I might die if I don't get financial aid",
    "I'm going to die if I fail this class 😳",
]

# The regression that already worked.
KILL_MYSELF = "if I don't pay the tuition money I will kill myself"
