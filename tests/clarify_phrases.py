"""Tester round 2, item C (T08): the vague-question sets for the CLARIFY detector, written
BEFORE the code (docs/decisions.md, "Tester round 2, safety and small fixes"). Data only."""

# Short, vague, no topic noun, no course code, no department: must get the clarify template.
POSITIVES = [
    "when is it due",  # T08
    "when is it",
    "whens it due",
    "when is that due",
    "when is this due",
    "when is it due?",
    "when are they due",
    "when's it due",
]

# Must NOT clarify.
NEGATIVES = [
    "when is it due for tuition",
    "when is the add drop deadline",
    "when does fall 2026 start",
    "when is it due for CST 1101",
    "when is the tuition due",
    "when is my bill due",
    "when is it open",
    "when is it due for financial aid",
    "when is the library open",
    "when is graduation",
    "when is it due, the fafsa",
    "what time is it",
    "when is it due for the thing my professor told me about in class last week",  # long
]
