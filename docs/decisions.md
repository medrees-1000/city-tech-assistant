# Decisions

Short notes on choices that are not obvious from the code. Newest last.

## Term tags on sections (Oct 11, 2026)

- Every section has `terms`, a list that may be empty. An entry is an explicit term name: Summer I,
  Summer II, Summer, Fall, Winter or Spring followed by a 4-digit year ("Fall 2026"; "Summer Session I
  2026" is stored as "Summer I 2026"). `term` is the single entry when `terms` has exactly one, else null.
- Terms are read only from the section's heading path (its parents' headings and its own heading) and the
  header row of its tables (a table title such as "Summer 2026 Advisement Schedule"). Never from body text
  and never from dates: "Summer 2026 refunds begin July 17, 2026" in a paragraph tags nothing.
- A season with no year ("Fall Refund Date", "Year 1 Fall", "Fall and Spring") is not a term.
- **Refund calendar rule (the only exception).** The refund calendar PDF has the heading "Summer 2026, Fall
  2026, and Spring 2027 Refund Schedule", which names three terms. For that document only, a heading that
  starts with a season and no year takes the one term of that season named in that heading:
  - "Fall Book Advance Refund Dates" and "Fall Refund Date" -> Fall 2026
  - "Spring Book Advance Refund Dates" and "Spring Refund Date" -> Spring 2027
  - the main schedule table section (the heading itself) -> Summer 2026, Fall 2026, Spring 2027
  Such sections carry `terms_source` saying so. If the schedule heading named no term (or two) for a season,
  the section gets none. Nothing else is resolved this way.
- Refund pages (`refund_pages` in `config/sources.yaml`) also store `covered_terms`, every term their
  headings and tables name, and `seasons_without_year`, the season names they use without a year. The
  coverage is what the page prints; it is not assumed from the page's purpose.

## Phase 3 answer rule: terms on retrieved sections

If none of the terms tagged on a retrieved section matches the term the question is about (or the current
term when none is named), the answer states the term printed on the source (for example "this page lists
Fall 2024 hours") or abstains with the office contact. Term filtering is soft: a section with no terms is
never excluded.
