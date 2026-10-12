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

## Database setup (Oct 12, 2026)

- Image `pgvector/pgvector:0.8.7-pg17`: Postgres 17 (current major with long support left) and the newest
  pgvector tag listed on Docker Hub on this date. The tag is pinned so a pull never changes the database
  version. Moving to a newer tag is a deliberate edit of `docker-compose.yml`.
- The container publishes `127.0.0.1:5432` only. A host Postgres was already using 5432; the owner stopped it.
- `schema_migrations` is created by `cta.index.db migrate`, not by a migration file (a migration could not
  record itself before its own table exists). Each migration runs in one transaction with its record, so a
  failed one leaves nothing half-applied. Migration files are applied in file-name order and never edited after
  they have run; a schema change is a new numbered file.
- The vector column is `vector(1536)`. Changing the embedding model to one with other dimensions needs a new
  migration and a full re-embed.
- Connection errors print a fixed message, because the driver message can contain connection details.

## Chunk builder (Oct 12, 2026)

- Counts match the plan: 619 chunks (413 section, 197 course, 9 contact), 121 sections merged into a parent.
  Exact tokens (cl100k_base, the encoding of text-embedding-3-small): 136,297 in total, max 2,138 per chunk,
  so nothing needs splitting and the one-time embedding cost is about $0.0027.
- A merged chunk takes the id of the parent section; the table sections are listed in `merged_section_ids`, so
  eval labels at section level still resolve. Section ids count all sections of the record, including
  `embed: false` ones, so they match `docs/section-index.md`.
- A merged chunk's `terms` is the union of the parent's and the merged tables' terms (a table titled "Fall 2026
  Payment Due Dates" under a general heading makes the chunk a Fall 2026 chunk); `term` is the single entry,
  else null. Terms still come only from headings and table titles.
- Course prerequisites: `text` rules are embedded as printed. A shorthand rule (40 courses, e.g.
  `PRE_CST1100`) is embedded as printed with the note "shorthand as printed in the catalog, not expanded":
  never guessed. A course with no rule says "none listed in the catalog".
- Contact chunks use every panel of the owner record (address, email, hours) and cite the first source page of
  that owner. Departments are named from the course records (`department_name`); offices as "<Name> office".
- `content_hash` = sha256(text + embedding model + dimensions); `meta_hash` = sha256 of the id and the
  metadata fields in sorted-key JSON. Tokens are counted with tiktoken; the encoding file is cached in
  `.cache/tiktoken` (git-ignored).

## Embedding loader (Oct 12, 2026)

- The loader needs `--yes` for any write, not only for embedding: without it, metadata-only updates and stale
  deletions are previewed too. A run with nothing to change prints the report and needs no flag.
- The OpenAI client is created with `max_retries=0`; `cta.index.embed` retries itself (3 retries, waits of 1, 2
  and 4 seconds, only for 429, 5xx and connection errors) so the rule is in our code and tested. Error messages
  never contain the key.
- The cost shown before a run is the tiktoken estimate; the cost printed after is from the API's reported
  usage. On the first load they were equal (136,297 tokens).
- `openai` 3.x depends on `httpx2` (the pydantic-org successor of httpx, openai requires it since 3.0.0 of
  2026-08-12). It is a transitive dependency and not named in `pyproject.toml`.
- Loader tests run in a throwaway schema (created and dropped per test), because the loader really commits.

## Calendar loader (Oct 12, 2026)

- Same rules as the chunk loader: `--yes` for any write, nothing written in a dry run, one transaction, rows no
  longer in the file are deleted. The integrity checks run after the load and only report; a mismatch is listed
  and the exit code is 1, nothing is corrected silently.
- Weekday check: the first name in `weekday_raw` must be the weekday of `date_start`, and for a range such as
  "Friday-Sunday" the second must be the weekday of `date_end`.
- Year check: the term decides the year (Winter 2027: December is 2026, January is 2027), **unless the PDF
  printed a year in `date_raw`, which decides.** The first version of the check had no such exception and
  flagged `fall-2026-055` ("College Closed", `date_raw` "January 01, 2027", a Friday): a Fall 2026 row that is
  correctly in 2027 because the Fall calendar runs to January 1. The data was right; the check was too blunt.
- Tests that used to assume the real `chunks` table was empty now compare its row count and latest
  `updated_at` before and after.
