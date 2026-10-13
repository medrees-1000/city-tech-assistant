"""The chain answer written by plain code (chain layout, docs/chain-layout-plan.md, item 1).

No model writes anything. One block per course with a catalog record, in the walk's order:

    ### CODE — Title [n]
    **Courses named:** CODE (Title), CODE (Title)
    **Catalog says:** "the catalog text, verbatim"

The rule text is never parsed or paraphrased here. "Courses named" is the list the walk already
extracted (same codes, same order), joined by commas only: the quoted catalog text decides "and" and
"or". Fixed sentences are written once below. A catalog text that holds a character the page would
read as markup raises ChainRenderError (the router then uses the model path), so it fails loudly in
tests and safely in production.
"""

import re

from cta.graph.chain import MAX_COURSES

RISKY = re.compile(r'(^|\n)\s*(#{1,3} |- )|\*\*|\[\d+\]|<|"')  # markdown, a link marker or a quote
NO_PREREQUISITE = "No prerequisite listed in the catalog."
UNREADABLE = "cannot be read from this text"
NO_RECORD = "no catalog record"


class ChainRenderError(ValueError):
    """A verbatim catalog text cannot be shown safely in the page's markdown."""


def named(code: str, titles: dict[str, str]) -> str:
    """ "CODE (Title)", or "CODE (no catalog record)" for a code that has no record."""
    return f"{code} ({titles.get(code) or NO_RECORD})"


def block(number: int, course: dict, titles: dict[str, str]) -> str:
    text = course["text"]
    if RISKY.search(text):
        raise ChainRenderError(f"{course['code']}: the catalog text holds markup characters")
    lines = [f"### {course['code']} — {course['title']} [{number}]"]
    if not text:
        lines.append(NO_PREREQUISITE)
        return "\n".join(lines)
    if course["unparsed"]:
        lines.append(f"**Courses named:** {UNREADABLE}")
    elif course["codes"]:
        lines.append("**Courses named:** " + ", ".join(named(c, titles) for c in course["codes"]))
    else:
        lines.append("**Courses named:** none")
    if course["exclusions"]:
        excluded = ", ".join(named(c, titles) for c in course["exclusions"])
        lines.append(f"**Must not have taken (as the catalog text says):** {excluded}")
    lines.append(f'**Catalog says:** "{text}"')
    return "\n".join(lines)


def render(result: dict, records: dict[str, dict]) -> str:
    """The answer for a found chain (the dict `prerequisite_chain` returns)."""
    titles = {code: r["title"].strip() for code, r in records.items()}
    parts = [f"Here is the prerequisite chain for {result['root']}, from the catalog:"]
    parts += [block(n, c, titles) for n, c in enumerate(result["courses"], 1)]
    closing = []
    if result["no_record"]:
        closing.append(
            f"No catalog record in the four departments for: {', '.join(result['no_record'])}."
        )
    for u in result["unexpanded"]:
        closing.append(
            f"The chain stops here: {u['code']} names {', '.join(u['names'])}, "
            f"which is not followed further ({u['reason']})."
        )
    for d in result["dropped"]:
        closing.append(
            f"{d['code']}, named by {d['named_by']}, is not shown because the chain is limited "
            f"to {MAX_COURSES} courses."
        )
    if closing:
        parts.append("\n".join(closing))
    return "\n\n".join(parts)
