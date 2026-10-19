"""The chain answer written by plain code (chain layout, docs/archive/chain-layout-plan.md, item 1).

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

from cta.graph.chain import MAX_COURSES, known_prefixes, outside_sentence

RISKY = re.compile(r'(^|\n)\s*(#{1,3} |- )|\*\*|\[\d+\]|<|"')  # markdown, a link marker or a quote
NO_PREREQUISITE = "No prerequisite listed in the catalog."
UNREADABLE = "cannot be read from this text"
NO_RECORD = "no catalog record"
# a named course whose subject prefix is in no record we hold
OUTSIDE = "outside the four departments I cover"
NO_RECORD_ASKED = (
    "There is no catalog record for {code} "
    "in the four departments (CST, Math, EET, Dental Hygiene)."
)
ALREADY_SHOWN = "{code} is already shown above."


class ChainRenderError(ValueError):
    """A verbatim catalog text cannot be shown safely in the page's markdown."""


def named(code: str, titles: dict[str, str]) -> str:
    """ "CODE (Title)"; for a code with no record "CODE (no catalog record)", or, when its subject
    prefix is in no record we hold, "CODE (outside the four departments I cover)"."""
    if titles.get(code):
        return f"{code} ({titles[code]})"
    outside = code.split()[0] not in known_prefixes(titles)  # the prefixes of the records
    return f"{code} ({OUTSIDE if outside else NO_RECORD})"


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
        lines.append("**Courses named:** none listed")
    if course["exclusions"]:
        excluded = ", ".join(named(c, titles) for c in course["exclusions"])
        lines.append(f"**Must not have taken (as the catalog text says):** {excluded}")
    lines.append(f'**Catalog says:** "{text}"')
    return "\n".join(lines)


def marked_codes(courses: list[dict], titles: dict[str, str]) -> set[str]:
    """Codes that a rendered block already marks "(no catalog record)": the codes of a "Courses
    named" or "Must not have taken" line that has no title. A block whose text is empty or
    unreadable has no such line, so it marks nothing."""
    marked: set[str] = set()
    for course in courses:
        if not course["text"] or course["unparsed"]:
            continue
        marked |= {c for c in [*course["codes"], *course["exclusions"]] if not titles.get(c)}
    return marked


def closing(result: dict, skip: set[str] = frozenset(), marked: set[str] = frozenset()) -> str:
    """The sentences after the blocks: codes without a record (except the asked ones in `skip`,
    which have their own section), a chain cut at the depth limit, courses left out by the cap.
    The "No catalog record" sentence is left out only when every code in it is already marked in a
    block above (`marked`); otherwise it stays whole (UI polish 3a, docs/decisions.md)."""
    lines = []
    missing = [c for c in result["no_record"] if c not in skip]
    if missing and not all(c in marked for c in missing):
        lines.append(f"No catalog record in the four departments for: {', '.join(missing)}.")
    for u in result["unexpanded"]:
        lines.append(
            f"The list stops at {u['code']}, which names {', '.join(u['names'])}; "
            "prerequisites of the last courses are not shown."
        )
    for d in result["dropped"]:
        lines.append(
            f"{d['code']}, named by {d['named_by']}, is not shown because the list is limited "
            f"to {MAX_COURSES} courses."
        )
    return "\n".join(lines)


def codes_phrase(codes: list[str]) -> str:
    """ "A", "A and B" or "A, B and C"."""
    return codes[0] if len(codes) == 1 else f"{', '.join(codes[:-1])} and {codes[-1]}"


def render(result: dict, records: dict[str, dict]) -> str:
    """The answer for a found chain (the dict `prerequisite_chain` returns), or for several asked
    courses (`combined_chain`: the result has `sections`)."""
    titles = {code: r["title"].strip() for code, r in records.items()}
    if "sections" in result:
        return render_sections(result, titles)
    parts = [f"Here are the prerequisites for {result['root']}, from the catalog:"]
    parts += [block(n, c, titles) for n, c in enumerate(result["courses"], 1)]
    if text := closing(result, marked=marked_codes(result["courses"], titles)):
        parts.append(text)
    return "\n\n".join(parts)


def render_sections(result: dict, titles: dict[str, str]) -> str:
    """One section per asked course in the order asked; a course is shown once, in the first section
    that reaches it, and a later section says so. Numbers run on across the sections."""
    number = {c["code"]: n for n, c in enumerate(result["courses"], 1)}
    by_code = {c["code"]: c for c in result["courses"]}
    parts = [f"Here are the prerequisites for {codes_phrase(result['asked'])}, from the catalog:"]
    for s in result["sections"]:
        parts.append(f"## Prerequisites for {s['root']}")
        if not s["found"]:
            if s["root"].split()[0] not in known_prefixes(titles):
                # the same sentence as the single-course answer (item D)
                parts.append(outside_sentence(s["root"]))
            else:
                parts.append(NO_RECORD_ASKED.format(code=s["root"]))
        elif s["already_shown"]:
            parts.append(ALREADY_SHOWN.format(code=s["root"]))
        else:
            parts += [block(number[c], by_code[c], titles) for c in s["courses"]]
        if s["shared"]:
            parts.append("\n".join(ALREADY_SHOWN.format(code=c) for c in s["shared"]))
    unknown = {s["root"] for s in result["sections"] if not s["found"]}
    shown = {c for s in result["sections"] if s["found"] for c in s["courses"]}
    marked = marked_codes([by_code[c] for c in shown], titles)
    if text := closing(result, unknown, marked):
        parts.append(text)
    return "\n\n".join(parts)
