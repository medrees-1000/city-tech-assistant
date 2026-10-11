# City Tech Assistant

A RAG assistant that answers City Tech (CUNY) students' questions about registration, deadlines,
advising, tuition, financial aid and four departments, with a citation for every answer.
See [CLAUDE.md](CLAUDE.md) for scope and rules, and [docs/data-validation.md](docs/data-validation.md)
for the data checks.

Status: Phase 1 (data collection). Nothing is embedded or indexed yet.

## Setup

```bash
uv sync
cp .env.example .env     # then set CTA_CONTACT_EMAIL (used in the crawler User-Agent)
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

## Data

`data/raw/` and `data/processed/` are not committed. Final counts will be reported here after the
validation checks pass.
