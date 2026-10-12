"""The classifier: calendar question or not, and the words the student used for a term (step 4a).

The prompt is written once and committed before any paid call; it is not edited after results (a
second prompt would be a new experiment).
"""

from dataclasses import dataclass

from cta.graph.llm import JsonCall, json_call

INSTRUCTIONS = """\
You route a question from a City Tech (CUNY) student. Reply with one JSON object:
{"intent": "calendar" or "other", "term_mention": a string or null}

intent "calendar": the student asks for a date, a deadline, when a period starts or ends, or a
closure or break, of the kind printed on the academic calendar (for example the last day to add a
course, when classes begin, when final exams are, whether the college is closed, when registration
opens).
intent "other": everything else: explanations of policies, how-to steps, amounts and fees,
programs, courses, contacts, requirements.

term_mention: the exact words the student used to name a term or semester (for example "Fall 2026",
"this spring", "next fall", "winter session", "Summer 2027"), copied as written. null if the
question names no term.

Return only the JSON object.
"""


@dataclass
class Classification:
    intent: str  # "calendar" | "other"
    term_mention: str | None
    call: JsonCall
    failed: bool = (
        False  # the call or its reply was unusable; the question then takes the "other" route
    )


def parse_classification(data: dict | None) -> tuple[str, str | None] | None:
    """(intent, term_mention) from the model's JSON, or None if it does not fit."""
    if not data or data.get("intent") not in ("calendar", "other"):
        return None
    mention = data.get("term_mention")
    if mention is not None and not isinstance(mention, str):
        return None
    return data["intent"], (mention.strip() or None) if mention else None


def classify(client, cfg: dict, question: str) -> Classification:
    messages = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": f"Question: {question}"},
    ]
    call = json_call(client, cfg, messages, "classifier request")
    parsed = parse_classification(call.data)
    if parsed is None:  # a failed classifier must not block the old pipeline
        return Classification("other", None, call, failed=True)
    return Classification(parsed[0], parsed[1], call)
