"""Term resolution for the calendar route: plain code, no model (step 4a).

The supported terms are the ones in the calendar file ("Fall 2026", "Winter 2027", "Spring 2027").
A mention such as "Fall 2027" or "Summer" names a term without a calendar: it is unsupported, and
the only help the table can give is a row whose event text mentions that label (the q73 pattern:
"Online registration for Fall 2027 begins" sits in the Spring 2027 calendar).
"""

import re
from dataclasses import dataclass, field
from datetime import date

SEASONS = ("winter", "spring", "summer", "fall")
SEASON_YEAR = re.compile(
    r"\b(winter|spring|summer|fall|autumn)\s*(?:semester|term|session)?\s*,?\s*(\d{4})\b", re.I
)
SEASON_ONLY = re.compile(r"\b(winter|spring|summer|fall|autumn)\b", re.I)
YEAR_ONLY = re.compile(r"\b(20\d\d)\b")
LINK_ROW = re.compile(r"^\s*for more info\b.*(https?://|www\.)\S+\s*$", re.I)


@dataclass
class Resolution:
    status: str  # explicit | season | assumed | unsupported
    term: str | None = None  # the calendar to use (explicit, season, assumed)
    label: str | None = None  # the unsupported label, as searched, e.g. "Fall 2027"
    pool: list[dict] = field(default_factory=list)  # rows for an unsupported label (maybe empty)


def supported_terms(events: list[dict]) -> list[str]:
    """Terms that have a calendar, in file order."""
    return list(dict.fromkeys(e["term"] for e in events))


def term_span(events: list[dict], term: str) -> tuple[date, date]:
    """(start, end) of a term: its 'Start of ...' and 'End of ...' rows, else its first and last
    dated rows."""
    rows = [e for e in events if e["term"] == term and e["date_start"]]
    starts = [e["date_start"] for e in rows if e["event"].lower().startswith("start of")]
    ends = [e["date_start"] for e in rows if e["event"].lower().startswith("end of")]
    every = [e["date_start"] for e in rows] + [e["date_end"] for e in rows if e["date_end"]]
    return date.fromisoformat(min(starts or every)), date.fromisoformat(max(ends or every))


def current_term(events: list[dict], today: date) -> str:
    """The term in session today; else the next one to start; else the one that ended last."""
    spans = {t: term_span(events, t) for t in supported_terms(events)}
    inside = [t for t, (a, b) in spans.items() if a <= today <= b]
    if inside:
        return max(inside, key=lambda t: spans[t][0])
    upcoming = [t for t, (a, _) in spans.items() if a > today]
    if upcoming:
        return min(upcoming, key=lambda t: spans[t][0])
    return max(spans, key=lambda t: spans[t][1])


def season_term(events: list[dict], season: str, today: date) -> str | None:
    """The term of that season that is running or still to come (the earliest such), else None."""
    spans = {t: term_span(events, t) for t in supported_terms(events)}
    options = [t for t in spans if t.lower().startswith(season) and spans[t][1] >= today]
    return min(options, key=lambda t: spans[t][0]) if options else None


def link_row(event: dict) -> bool:
    """A row whose text is only a 'For more info' web address."""
    return bool(LINK_ROW.match(event["event"]))


def term_pool(events: list[dict], term: str) -> list[dict]:
    """The rows of one term, minus the link rows."""
    return [e for e in events if e["term"] == term and not link_row(e)]


def all_rows_pool(events: list[dict]) -> list[dict]:
    """The rows of every calendar, minus the link rows (the selector v2 pool)."""
    return [e for e in events if not link_row(e)]


def label_pool(events: list[dict], label: str) -> list[dict]:
    """Rows of any calendar whose event text mentions the label (case-insensitive)."""
    needle = label.lower()
    return [e for e in events if needle in e["event"].lower() and not link_row(e)]


def resolve_term(mention: str | None, today: date, events: list[dict]) -> Resolution:
    """Which calendar a question is about, from the words the student used for the term."""
    terms = supported_terms(events)
    text = (mention or "").strip()
    if not text:
        return Resolution("assumed", term=current_term(events, today))
    lowered = text.lower()
    for term in terms:
        if re.search(rf"\b{re.escape(term.lower())}\b", lowered):
            return Resolution("explicit", term=term)
    named = SEASON_YEAR.search(text)
    if named:  # a season and a year that is not a supported term
        label = f"{normalise_season(named.group(1))} {named.group(2)}"
        if label in terms:  # "spring semester 2027"
            return Resolution("explicit", term=label)
        return Resolution("unsupported", label=label, pool=label_pool(events, label))
    season = SEASON_ONLY.search(text)
    if season:
        name = normalise_season(season.group(1))
        term = season_term(events, name.lower(), today)
        if term:
            return Resolution("season", term=term)
        return Resolution("unsupported", label=name, pool=label_pool(events, name))
    year = YEAR_ONLY.search(text)
    if year and not any(year.group(1) in t for t in terms):  # "2028": no calendar for that year
        return Resolution(
            "unsupported", label=year.group(1), pool=label_pool(events, year.group(1))
        )
    return Resolution("assumed", term=current_term(events, today))


def normalise_season(word: str) -> str:
    word = word.capitalize()
    return "Fall" if word == "Autumn" else word
