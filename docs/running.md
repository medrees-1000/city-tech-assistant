# Running it: full steps

The README has the short quickstart. This page has the full steps, including rebuilding the data, which is not in the repo (`data/raw`, `data/processed` and `data/pdfs` are git-ignored; only `data/calendar/calendar_events.json` is committed).

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, Node 22, an OpenAI API key.

## 1. Setup

```bash
uv sync
cp .env.example .env                        # set OPENAI_API_KEY, POSTGRES_PASSWORD, CTA_CONTACT_EMAIL
docker compose up -d                        # Postgres 17 with pgvector, on 127.0.0.1:5432
uv run python -m cta.index.db migrate       # create the tables
```

`CTA_CONTACT_EMAIL` goes into the crawler's User-Agent (`CityTechAssistantBot/0.1 (student portfolio project; contact: ...)`). Use your own address; it is never committed.

## 2. Rebuild the data

1. Download the 11 PDFs listed in `config/sources.yaml` by hand into `data/pdfs/` with those file names: the four department PDFs, the three term calendars, and four office PDFs (financial aid refund calendar, dropping and withdrawing, special circumstances flyer, CUNYfirst reference). The calendar PDFs are linked from the Registrar's academic calendar page.
2. Crawl (network, 1 request per second, robots.txt respected): `uv run python -m cta.crawl.catalog` and `uv run python -m cta.crawl.pages`. My fetch log has 409 requests, so at one per second a crawl takes at least about 7 minutes. I did not time a fresh crawl.
3. Parse: `uv run python -m cta.parse.pages`, `uv run python -m cta.parse.pdf_docs`, `uv run python -m cta.parse.departments`, `uv run python -m cta.parse.calendar_build` (it refuses to overwrite the hand-verified calendar table without `--force`).
4. Check: `uv run python -m cta.validate`. Nothing is indexed until it passes.
5. Index: `uv run python -m cta.index.load --dry-run`, then `uv run python -m cta.index.load --yes` (about 136,000 tokens, roughly $0.003 of embeddings), then `uv run python -m cta.index.load_calendar --yes`.

## 3. Run

```bash
uv run python -m cta.api                    # API on 127.0.0.1:8000 (see /health and /docs)
npm install --prefix web
npm run dev --prefix web                    # page on http://127.0.0.1:3000
```

## What I verified, and what I did not

Verified in a fresh clone of the repo (no data, no `.env`) on 16 Oct 2026: `uv sync`; `uv run pytest -q` (0 failed; tests that need the collected data or Postgres skip with a reason); `npm ci --prefix web`, `npm test --prefix web`, `npm run typecheck --prefix web` and `npm run build --prefix web`; `cta.index.db migrate` and `status` against a throwaway database (created and dropped for the check); `cta.index.load --dry-run`, `cta.index.load_calendar --dry-run` and `cta.validate` (the last one reports its areas as skipped without data). With the data on my machine I also ran `cta.validate`, both dry-runs, `cta.index.chunks --stats`, the API and the built web app (a smoke test of five questions).

Not verified end to end:
- the crawl and parse commands (they need network access and the downloaded PDFs; I only checked that the modules import);
- `cta.index.load --yes` and `cta.index.load_calendar --yes` on an empty database (they cost a few cents of embeddings);
- starting the API from a fresh clone (it needs the data, the database and a key).

## Running the built page (for demos)

The development server shows a small "N" badge in the bottom-left corner. The production build does not. For a demo or a recording, build the page and run the production server (bound to 127.0.0.1:3000; the API must be running on 127.0.0.1:8000):

```bash
npm run build --prefix web
npm run start --prefix web
```

Add `?details=1` to the page address to show the "How this was found" panel; it is hidden by default.
