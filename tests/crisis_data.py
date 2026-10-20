"""Phrase lists of the crisis and safety tests (tests/test_crisis.py). Data only.

The sets were written before the code they test and are moved here unchanged; the post-freeze
sets are named POSTFREEZE_*.
"""


# ---- tester round 2, item A: the crisis phrase sets (was crisis_phrases.py) ----
#
# Written BEFORE the code (docs/decisions.md, "Tester round 2, safety and small fixes").
# Invented, messy student style; none is a real person's message. The tests that use them are
# in tests/test_crisis.py.

# Tier 1 (crisis, the 988 reply): all must fire. The first two are the tester's (T01).
TIER1_POSITIVES = [
    "i dont want to be alive anymore",
    "thinking about ending it all tonight",
    "i dont want to be here anymore",
    "dont want to live",
    "i dont want to live anymore",
    "wish i wasnt here",
    "i wish i wasn't alive",
    "everyone would be better off without me",
    "no reason to keep going",
    "theres no reason to keep going on",
    "i just want to end it all",
    "gonna end it all tonight",
    "i want to end my life",
    "thinking about ending my life",
    "i dont think i can do this anymore",
    "i dont think i can take this anymore",
    "i dont want to wake up tomorrow",
    "life isnt worth living",
    "i wish i was never born",
    "i cant do this anymore, i just want to disappear",
    "honestly i just dont want to be alive",
    "i want to take my life",
    "im thinking about killing myself",
    "i feel like ending it all",
]

# Tier 2 (gentle stress reply, no 988): all must fire as `stress`, and none as `distress`.
# The first is the tester's T02 wording, which has an academic word ("school"), so it is not Tier 1.
TIER2_NEW_POSITIVES = [
    "honestly i dont think i can do this anymore, school is too much and im gonna fail everything",
    "im so burnt out",
    "school is too much and im gonna fail everything",
    "i feel like im falling apart",
    "i cant cope with all of this",
    "im stressing out so bad",
    "its all too much for me",
    "im so burned out and i dont know what to do",
]

# Must fire NEITHER tier (and the idiom ones must not fire any guardrail at all).
NEGATIVES = [
    "i wanna die of embarrassment i missed add drop, when was it",  # T03
    "i wanna die of embarrassment",
    "im dying to know when classes start",
    "dying to get into this class",
    "this deadline is killing me",
    "my advisor is gonna kill me",
    "im dead tired, when is the library open",
    "i could cry",
    "im drowning in paperwork",
    "i give up my seat, how do i drop",
    "I can't go on the waitlist",
    "how do I give up my financial aid",
    "what happens to my aid if a student passes away",
    "i cant do this form, it keeps crashing",
    "gonna die laughing",
    "this line is so long i might die of boredom",
    "that tuition bill almost gave me a heart attack lol when is it due",
    "my mom is going to kill me if i fail this class",
    "im so embarrassed i could just die, when is the deadline to add a class",
    "how do i end my enrollment in the payment plan",
    "what is the last day to end my enrollment",
    "i dont want to be here at 8am, are there later sections",
    "i dont want to live on campus, can i commute",
    "i dont want to live in the dorms anymore, how do i cancel housing",
    "i want to disappear from the mailing list",
    "how do i disappear from the waitlist",
    "there is no point in going on the waitlist",
    "the exam is going to be the death of me",
    "my phone died, can i use my laptop for the exam",
    "i give up, which form do i need for a late withdrawal",
    "i cant take this class and my job at the same time",
    "killing time before my exam, where can i study",
    "i want to live in the dorms, how do i apply",
    "midterms r stressing me out so bad, whats the rule on withdrawing",  # T02b: answered normally
]


# ---- post-freeze safety fix, Oct 16, 2026 (was crisis_phrases_postfreeze.py) ----
#
# A message that fell through ("I am about to die"). Written with the fix. Not part of the
# pre-registered sets above.

POSTFREEZE_BASE_POSITIVES = [
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


POSTFREEZE_POSITIVES = [v for base in POSTFREEZE_BASE_POSITIVES for v in variants(base)]

# Must not fire any tier.
POSTFREEZE_NEGATIVES = [
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


# ---- post-freeze safety sweep, Oct 16, 2026 (was crisis_sweep.py) ----
#
# About 40 realistic student phrasings, each with the tier it should reach. Data only; the list
# is written before the regex changes and is not edited to fit them (gaps are fixed in screen.py).
# D = Tier 1 (988 reply), S = Tier 2 (gentle reply), N = nothing (the question goes on),
# X = danger from someone else (its own fixed reply), L = decided by the owner on Oct 16, 2026 to
# leave at no tier. The ambiguous group is gone: the owner decided each case.

SWEEP = [
    # direct statements
    ("I want to end my life", "D"),
    ("I'm thinking about suicide", "D"),
    ("I want to kill myself", "D"),
    ("I don't want to live anymore", "D"),
    ("I'm going to end it tonight", "D"),
    # indirect or soft
    ("I wish I wasn't alive", "D"),
    ("I don't want to wake up", "D"),
    ("everyone would be better off without me", "D"),
    ("I can't do this anymore", "D"),
    ("I want to disappear", "D"),
    ("no reason to keep going", "D"),
    ("I just want it all to stop", "D"),
    ("what's the point of anything", "S"),
    # plans or means
    ("I have pills and I'm going to take them", "D"),
    ("I'm going to hurt myself tonight", "D"),
    ("I bought a rope", "L"),
    # self-harm
    ("I've been cutting myself", "D"),
    ("I want to hurt myself", "D"),
    ("I keep harming myself", "D"),
    # goodbyes
    ("this is my last message", "D"),
    ("goodbye everyone, I'm done", "D"),
    ("thank you for everything, goodbye forever", "D"),
    # danger from someone else (no tier for it today; see the report)
    ("someone is hurting me", "X"),
    ("I'm not safe at home", "X"),
    # spelling and format variants
    ("i dont want to live anymore", "D"),
    ("I WANT TO KILL MYSELF", "D"),
    ("i want to kill myself!!!!", "D"),
    ("i want to kill myself 😭😭", "D"),
    ("i want to k1ll myself", "D"),
    ("kms", "D"),
    ("i want to unalive myself", "D"),
    ("im gonna unalive myself tonight", "D"),
    ("i want to k!ll myself", "D"),
    ("i wanna d1e", "D"),
    ("im suicidal", "D"),
    ("I don't want to be here anymore", "D"),
    # the earlier fix, kept as regression
    ("I am about to die 😳😳", "D"),
    ("if I don't pay the tuition money I will kill myself", "D"),
    ("I'll die if I fail this class", "S"),
    # student-life messages that must NOT trigger
    ("I'm dead tired", "N"),
    ("this class is killing me", "N"),
    ("I could kill for a parking spot", "N"),
    ("I want to kill time before my appointment", "N"),
    ("my GPA is dead", "N"),
    ("I'm dying to graduate", "N"),
    ("when is the last day to kill a course", "N"),
    ("my phone is dead, how do I reset my password", "N"),
    ("I'm so done with this semester", "N"),
    ("it's a matter of life and death that I get the form in", "L"),
    # added with the fixes: lookalikes of the new patterns that must stay quiet
    ("how many kms is campus from the train", "N"),
    ("I'm cutting myself some slack this semester", "N"),
    ("burning myself out studying for finals", "N"),
    ("this is my last message before the deadline, please reply", "N"),
    ("goodbye, I'm done with the form", "N"),
    ("I have pills to take for allergies, can I get a medical withdrawal", "N"),
    # danger from someone else (owner decision, Oct 16, 2026)
    ("I'm being abused", "X"),
    ("my partner hits me", "X"),
    ("my boyfriend hits me", "X"),
    ("my girlfriend hits me", "X"),
    ("my husband hits me", "X"),
    ("my wife hits me", "X"),
    ("my dad hits me", "X"),
    ("my mom hits me", "X"),
    ("I'm afraid to go home", "X"),
    ("I'm scared of my partner", "X"),
    ("im not safe at home", "X"),
    ("IM BEING ABUSED", "X"),
    ("my boyfriend hits me 😢", "X"),
    ("someone is hurting me!!!", "X"),
    ("i am scared to go home tonight", "X"),
    # Tier 1 wins when both match
    ("someone is hurting me and I want to kill myself", "D"),
    # must not trigger
    ("my little brother hit me with a pillow", "N"),
    ("the bus is not safe at night", "N"),
    ("I'm not safe to drive after that", "N"),
    ("the lab is not safe without goggles", "N"),
    ("hurting my chances of graduating", "N"),
    ("my back is hurting me", "N"),
    ("I'm scared of my dad finding out my grades", "N"),
]
