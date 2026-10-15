"""Casual round, item 3: the question sets for the extended NO ADVICE cues, written BEFORE the
code (docs/decisions.md, "Casual round"). Data only."""

# Advice cue plus an action word: must be detected as an advice question.
POSITIVES = [
    "what would you do, take a payment plan or pay all at once",  # cq14
    "what do you suggest, drop the class or withdraw",
    "which is better, withdrawing or taking an incomplete",
    "what's your advice, audit the course or take it for credit",
    "what would you do in my place about changing my major",
    "what do you suggest for transferring from another college",
    "which is better, a payment plan or paying in full",
    "do you think i should sign up for the winter session",
]

# Plain rule questions or a cue with no action word: must NOT be detected.
NEGATIVES = [
    "what would my payment be on the payment plan",
    "which is better known, FAFSA or TAP",
    "what would the refund be if i drop a class",
    "what would a W do to my gpa",
    "what do i do if i want to withdraw from a class",
    "how do i sign up for the payment plan",
    "which is the last day to withdraw in fall 2026",
    "which is better, the degree checklist or the planner",
    "what do you suggest for finding the registrar office",
    "what is the advice policy for transfer credits",
    "what would you need to bring to the advisement office to change my major",
    "which is better for tuition, the bursar page or the financial aid page",
]
