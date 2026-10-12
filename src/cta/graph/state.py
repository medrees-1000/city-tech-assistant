"""The router's state and result types (step 4a)."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, TypedDict

from cta.answer import Answer


class RouterState(TypedDict, total=False):
    """What flows through the graph. `total=False`: each node adds its own keys."""

    question: str
    today: date
    run_id: int | None
    intent: str  # "calendar" | "other" (the classifier's answer; "other" if the call failed)
    term_mention: str | None
    classify: dict  # tokens, cost and time of the classifier call
    calendar: dict  # what the calendar node did (term, status, selector numbers, row ids ...)
    fallthrough: bool  # the calendar node found no row and hands over to retrieve
    answer: Answer  # the final answer (from the calendar renderer or the existing pipeline)
    route: str  # "calendar" | "other" | "abstain" | "calendar_fallthrough"


@dataclass
class RoutedAnswer(Answer):
    """An Answer that also says which route made it. Everything the eval runner reads from an
    Answer is unchanged; `router` holds the router's own numbers and `row_ids` the calendar rows
    the answer states (empty for the retrieval route)."""

    route: str = "other"
    router: dict[str, Any] = field(default_factory=dict)
    row_ids: list[str] = field(default_factory=list)
    today: date | None = None
