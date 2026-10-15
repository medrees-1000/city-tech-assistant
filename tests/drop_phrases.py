"""Casual round, item 2 (T04): the question sets for the drop-family calendar rule, written BEFORE
the code (docs/decisions.md, "Casual round"). Data only."""

# Unqualified drop/withdraw date questions: the rule applies (all three grade-related rows).
POSITIVES = [
    "whats the last day to drop a class fall 2026",
    "last day to drop a class",
    "when can i withdraw from a class in spring 2027",
    "deadline to drop classes this fall",
    "last day to withdraw from a course",
    "when is the last day for dropping a course winter 2027",
    "call me at [PHONE] whats the last day to drop a class fall 2026",
    "last day for withdrawal spring 2027",
    "until when can i drop my class",
    "i wanna drop a class, what's the last day",
]

# Qualified, or not a drop/withdraw date question: the rule does not apply.
NEGATIVES = [
    "What is the last day to withdraw from a course with a grade of W in Fall 2026?",  # q31
    "What is the last day to withdraw from a course with a W?",  # q71
    "What is the last day to drop for a 50% tuition refund in Spring 2027?",  # q65
    "last day to drop a class fall 2026 without a W",
    "last day to add or drop",
    "how do i drop a class",
    "what is the tuition refund if i drop a class",
    "last day to drop after the first week",
    "last day to drop with a WD grade in Fall 2026",
    "when is the last day to add a class fall 2026",
    "when does the fall 2026 semester end",
    "can i drop a class before the semester starts",
]
