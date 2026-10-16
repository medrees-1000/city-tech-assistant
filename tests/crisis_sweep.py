"""Post-freeze safety sweep (Oct 16, 2026): about 40 realistic student phrasings, each with the tier
it should reach. Data only; the list is written before the regex changes and is not edited to fit
them (gaps are fixed in screen.py). D = Tier 1 (988 reply), S = Tier 2 (gentle reply), N = nothing
(the question goes on), A = ambiguous: no automatic decision, see docs/decisions.md.
"""

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
    ("I just want it all to stop", "A"),
    ("what's the point of anything", "A"),
    # plans or means
    ("I have pills and I'm going to take them", "D"),
    ("I'm going to hurt myself tonight", "D"),
    ("I bought a rope", "A"),
    # self-harm
    ("I've been cutting myself", "D"),
    ("I want to hurt myself", "D"),
    ("I keep harming myself", "D"),
    # goodbyes
    ("this is my last message", "D"),
    ("goodbye everyone, I'm done", "D"),
    ("thank you for everything, goodbye forever", "A"),
    # danger from someone else (no tier for it today; see the report)
    ("someone is hurting me", "A"),
    ("I'm not safe at home", "A"),
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
    ("it's a matter of life and death that I get the form in", "A"),
    # added with the fixes: lookalikes of the new patterns that must stay quiet
    ("how many kms is campus from the train", "N"),
    ("I'm cutting myself some slack this semester", "N"),
    ("burning myself out studying for finals", "N"),
    ("this is my last message before the deadline, please reply", "N"),
    ("goodbye, I'm done with the form", "N"),
    ("I have pills to take for allergies, can I get a medical withdrawal", "N"),
]
