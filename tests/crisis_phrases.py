"""Tester round 2, item A: the crisis phrase sets, written BEFORE the code (docs/decisions.md,
"Tester round 2, safety and small fixes"). Data only: invented, messy student style; none is a real
person's message. The tests that use them are in tests/test_crisis.py."""

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
