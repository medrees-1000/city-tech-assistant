# Phase 4 plan: a demo prototype (FastAPI service and one Next.js page)

Written 2026-10-13. Plan only: no code, nothing installed, no paid call, test split not opened. Facts below were read from the repository; version numbers were read from the package registries (`uv pip install --dry-run`, `npm view`, nothing installed). The prototype wraps the pipeline that milestone 1 measured and **changes none of it** (retrieval, router, prompts, thresholds, contact rules stay as they are), so no new evaluation is needed for it.

What the pipeline already gives the API (so nothing is copied):
- `cta.graph.build.Router(conn, cfg).answer(question, today)` runs classify -> calendar | chain | retrieve, and (with `router.contacts: on`, the default) calls `add_contact` itself. It returns a `RoutedAnswer`: text, `abstained`, `abstain_reason`, `sources` (numbered chunk dicts), `citations`, `route`, `router` (classifier/selector/chain numbers, `contact_office`), `search` (retrieval ms, rerank outcome with scores and ms, tokens, cost), token counts, cost, latency.
- `cta.graph.contact` knows the office table (`config/contacts.yaml`); `cta.settings.refuse_tracing` is the tracing guard; `cta.redact.redact` is the redactor; `request_logs` (migrations 001, 002, 004) already stores redacted question and answer, retrieved ids and scores, tokens, cost, latency, route and router numbers.

## 1. API

Module `src/cta/api/` (`app.py` the FastAPI app and routes, `schema.py` the response models, `convert.py` the one function that turns a `RoutedAnswer` into the response). `convert.py` only reads fields; the routing, abstaining, contact and rendering logic all stay in the existing graph.

### Endpoints

| | |
|---|---|
| `GET /health` | `{"status":"ok","db":"ok","version":"<git short hash>","router":"on"}`; 503 `{"status":"degraded","db":"down"}` if the database does not answer a `SELECT 1`. No model call, no secrets, no config values beyond those four. |
| `POST /ask` | the assistant. Body `{"question": "<1 to 500 characters>"}`. Questions are independent: **no conversation memory** (a follow-up such as "what about spring?" is not understood; clarifying questions are step 5). |
| `GET /docs` | FastAPI's generated OpenAPI page (free, useful for the demo and for my smoke test; can be switched off for a deployment). |

### `POST /ask` response (200; the example is illustrative, ids and text are not real rows)

```json
{
  "request_id": "b3c1...",
  "question": "When does Winter 2027 end?",
  "answer": "Monday, January 25, 2027: End of Winter 2027 session [1] (Winter 2027 calendar, winter_2027.pdf, last updated 2026-09-15; the calendar can change)",
  "answer_type": "answer",
  "abstained": false,
  "abstain_reason": null,
  "route": "calendar",
  "citations": [
    {"n": 1, "id": "winter-2027-0NN", "title": "Winter 2027: End of Winter 2027 session",
     "url": "https://www.citytech.cuny.edu/registrar/docs/winter_2027.pdf", "file": "winter_2027.pdf",
     "doc_type": "calendar", "term": "Winter 2027", "last_updated": "2026-09-15",
     "excerpt": "Monday, January 25, 2027: ...", "cited": true}
  ],
  "contact": null,
  "how_found": { "...": "see below" },
  "meta": {"today": "2026-10-13", "version": "a69d5cd", "model": "gpt-6-luna"}
}
```

Fields:
- `answer`: the answer text **without** the contact sentence (the sentence is the exact line `add_contact` appended; `convert.py` removes that exact suffix, so the web page shows the contact as a card and not twice). The eval runners keep the full text; the API changes nothing there.
- `answer_type`: `"answer"` | `"abstain"` | `"not_announced"` (a calendar row with no date yet; the Registrar line stays in the text) | `"clarify"` (reserved for step 5, never returned now).
- `route`: `"calendar"` | `"chain"` | `"retrieve"`. The internal route names map as: `calendar` -> calendar; `chain` -> chain; `other`, `calendar_fallthrough`, `chain_fallthrough` -> retrieve; `abstain` -> calendar or chain by which node refused. The internal name is in `how_found.route_detail`.
- `abstain_reason`: a short code (`below_threshold`, `model`, `calendar_no_row`, `calendar_unsupported_term`, `calendar_selector_failed`, `chain_no_record`), never the model's sentence.
- `citations`: the numbered sources the answerer was given, in order, so the `[n]` markers in the text map to them; `cited` is true for the numbers the answer actually used. Fields come from the chunk: `title` = `heading_path`, `doc_type`, `term`, `last_updated`, `excerpt` (first 300 characters of the chunk text; the data is public, text is not logged). **URLs are never invented**: a web page or contact chunk uses its own `source` URL; a calendar row or PDF chunk gets a public URL only if the page records contain that file as a `pdf_links` entry (e.g. `fall_2026.pdf` is linked from `registrar/academic-calendar.aspx`; a map file name -> URL is built at startup from the processed page records); otherwise `url` is null and `file` carries the file name. Course chunks have no URL in the data (the catalog page URL needs a slug that is not stored), so `url` is null and the title reads "City Tech course catalog: CST 1101 ..."; whether `https://citytech.catalog.cuny.edu/courses/<courseGroupId>` alone resolves is a free GET I can check in step 3 if you want it.
- `contact`: present when an office contact was attached (abstentions): `{"office": "registrar", "name": "the Registrar", "emails": [{"address": "...", "for": null}], "phones": ["..."], "note": null}` read from `contacts.yaml` through the same loader (Advisement carries its two labelled emails and the virtual-advisors pointer in `note`). Null otherwise.
- `how_found`, built once and also the object stored in the log (section 2): `route_detail`, `intent`, `top_vector_similarity` and `abstain_threshold`, `retrieved` (the 20-chunk pool with first-stage rank and similarity, rerank score and final rank, and which five went to the answerer; empty on the calendar and chain routes), `calendar` (term, how it was resolved, selected row ids) or `chain` (code, course count, truncated, courses not expanded), `stages_ms` (classify, select or search, rerank, answer, total), `tokens` (prompt, completion, embedding), `cost_usd` (total and by component), `cache_hits`.
- `meta`: today's date used, git short hash, model name.

### Errors
Always `{"error": {"code": "...", "message": "..."}, "request_id": "..."}`, never a traceback or a provider message: 422 invalid body (empty or over 500 characters); 413 body over 4 KB; 429 rate limit or daily cap reached (`Retry-After` where known); 503 kill switch, database down or startup check failed; 502 the model provider failed after the existing retries (`ApiError`); 500 anything else (logged, generic message).

### Reuse, configuration, date, guard
- One `Router` per request with its own database connection (`cta.index.db.connect()`), `answer(question, today)`. Router construction (graph compile, reading the calendar file) is per request; I will measure it in step 3 and cache it only if it costs more than about 50 ms. A connection pool is a deployment concern (section 7).
- Config is `load_models()` (same `config/models.yaml`, same `CTA_*` environment overrides). New `api:` section: `today` (null = server date; `CTA_API_TODAY=2026-10-11` overrides, used for demos and tests), `max_question_chars`, `max_body_bytes`, `rate_limit_per_minute`, `daily_cost_cap_usd`, `enabled`, `request_timeout_s`.
- Startup checks (the app refuses to start, with one clear message, if any fails): `refuse_tracing()` (any LangSmith variable on), `router.mode` and `router.contacts` are `on` (the contract promises routes and contacts), `OPENAI_API_KEY` set, database reachable and migrations applied, `config/contacts.yaml`, `data/calendar/calendar_events.json` and `data/processed/courses` present. The same `uv run python -m cta.validate` is not run at startup (too slow); it is part of the manual checklist.

## 2. Logging

Postgres, the existing `request_logs` table, extended by **migration 005** (a new numbered file; migrations are never edited): `request_id uuid`, `source text` (`api` or `eval`), `status text` (`ok` or an error code), `trace jsonb` (the `how_found` block: stage latencies, rerank order and scores, route detail, retrieved ids and similarities) and `contact_office text`. The eval runners keep writing the old columns. The API writes one row per request, including refused and failed ones (status set, answer null). It already stores per row: redacted question, redacted answer, `retrieved`, tokens, embedding tokens, cost, latency, route, router numbers. Why Postgres and not a JSONL file: the table exists, eval and API logs are queried together, and a JSONL file needs its own locking and rotation.

Stored: redacted question text, redacted answer text, chunk ids and scores (public data), numbers, route, office key, request id, timestamp, `today`. **Not stored:** IP address, user agent, cookies, headers, any identifier of the person. The rate limiter keeps client IPs in process memory only and never writes them down.

Personal data. `cta.redact` removes emails, SSN-like numbers, phone numbers and 8-digit CUNY EMPLIDs from the question and the answer before the insert. It cannot remove a name or a free-text circumstance ("I am Maria and my GPA is 2.1"). My proposal, and why:
1. keep storing the redacted question text, because without it failures cannot be analysed (the eval loop depends on it);
2. a **retention limit**: `uv run python -m cta.api.purge --days 30` deletes API rows older than 30 days (config `logs.retention_days`; run by hand in the prototype);
3. a **notice on the page** under the chat box: "Questions are logged, with emails, phone numbers and ID numbers removed, to improve the assistant. Do not type personal information.";
4. the assistant itself does not look up any student data, and questions that need account data abstain; nothing in the logs links to a person.
The alternative (store only a hash and the route, no text) loses all failure analysis; I do not recommend it for a demo that is meant to improve, but it is a one-line switch (`logs.store_text: false`) if you prefer it. Stronger detection of names or of personal circumstances waits for step 6.

## 3. Web page

- `web/`, Next.js **16.4.0** (App Router, TypeScript; registry latest on 2026-10-13, needs Node >= 20.9, this machine has Node 22.23.2 and npm 10.9.8), React 19.3.0. Versions are pinned exactly in `package.json` after I check the peer ranges at install time. No UI library, no CSS framework: one CSS file.
- One page (`web/app/page.tsx`) and a few small components: `Chat` (question box and submit, keeps the questions and answers of this visit in memory only; each question is sent alone), `AnswerCard` (answer text with `[n]` turned into links to the source list), `Sources` (title, doc type, term, last updated, link when `url` is present, file name otherwise, excerpt on expand), `ContactCard` (office name, mailto and tel links, shown when `contact` is present), `HowFound` (a collapsible `<details>`: route, retrieved chunks with scores and rerank order, stage latency, tokens, cost), `Notice` (the logging notice).
- States: loading (disabled button, "Looking this up..."), abstain (a visibly different card: "I couldn't find this in the City Tech sources I have" plus the contact card, no source list), `not_announced` (answer plus Registrar line), error (human message by error code, retry button; 429 shows the wait), empty/too-long input blocked client side at 500 characters.
- Mobile first: single column, 16 px input font (no iOS zoom), tap targets 44 px, `viewport` meta, `aria-live="polite"` on the answer, labelled input, keyboard submit.
- Calls the API with plain `fetch("/api/ask")`. **Same-origin proxy**: `next.config` `rewrites` sends `/api/*` to `http://127.0.0.1:8000/*`, so the browser never talks to the API host, there is no CORS configuration and the API can stay bound to localhost. (Deployment can use the same rewrite with an environment variable for the API URL.)
- Needs locally: Node >= 20.9, `npm install` in `web/`, the API running on port 8000. No keys in the web app.

## 4. Dependencies (nothing is installed until you say yes)

Python (checked with `uv pip install --dry-run fastapi uvicorn`; the project's `pydantic`, `anyio`, `httpx` are already installed):

| package | version | reason | built-in alternative |
|---|---|---|---|
| fastapi | 0.143.0 | routing, request validation, response models, OpenAPI page, `TestClient` | `http.server` / hand-written WSGI: I would reimplement validation and error handling; not recommended |
| uvicorn | 0.54.0 | the ASGI server that runs the app (`python -m cta.api`); plain, without the `[standard]` extras | none in the standard library for ASGI |
| starlette | 1.8.0 | FastAPI's base (transitive) | n/a |
| click | 8.5.0 | uvicorn's CLI (transitive) | n/a |
| annotated-doc | 0.0.5 | FastAPI documentation helper (transitive) | n/a |
| opentelemetry-api | 1.45.1 | **a transitive dependency of this FastAPI version that I did not expect**; the API package only (no exporter, no network) | n/a |

Rate limiting, the daily cap and the kill switch are written by hand (about 60 lines, standard library); no `slowapi`. Pydantic is already present. Tests use Starlette's `TestClient`, which needs `httpx` (installed).

Node (all in `web/`): `next`, `react`, `react-dom` (the framework; the page needs a server for the proxy rewrite and for a later Vercel deployment), `typescript`, `@types/react`, `@types/node` (so the response contract is typed; checked with `tsc --noEmit`). No ESLint, no Tailwind, no testing library in the prototype. **Not added: the Vercel AI SDK.** CLAUDE.md anticipated it, but it buys streaming and chat-state helpers, and this API returns one JSON object per question (the answer is built from sources and checked as a whole; streaming tokens would show text before the route, abstain state and contact are known). A `fetch` call and `useState` are about 40 lines and easier for you to explain. If streaming is wanted later, that is a separate decision.

## 5. Tests (no paid calls)

`tests/test_api.py` with `fastapi.testclient.TestClient`. The model and the database are stubbed the way `tests/test_router.py` does it: a scripted chat client (the existing `Script`), `build.answer` replaced by a stub `Answer`, `Router(None, cfg, client_factory, events=...)`, and the log writer injected so no connection is opened. `create_app(...)` takes its dependencies (router factory, log writer, clock, config) as arguments, so the tests never touch the real ones.

Tested: every contract field and type (also against the pydantic model); a retrieve answer with citations and `cited` flags; a threshold abstain (contact present, contact sentence removed from `answer`, `answer_type: abstain`); a model-written abstain; a calendar answer (rows as citations, public PDF URL only when mapped, else null); a TBA row (`not_announced`); a calendar abstain (single contact, no double); a chain answer and the no-record abstain; URL rules (no invented URL for course and unmapped PDF chunks); `how_found` fields present; the tracing guard (any of the four variables on -> the app refuses to start); startup refusals (router off, contacts off, missing key); errors (422 empty and too long, 413, provider failure -> 502 with no provider text, database down -> 503, unexpected exception -> 500 generic); rate limit, daily cap and kill switch (429, 429, 503); `/health` with the database stub up and down; redaction applied before the log row is built; migration 005 and the log insert against the Docker database in a throwaway schema (`integration` marker, skipped when Postgres is not running); the date override.

Manual smoke test, real calls, under $0.01: start the API and send three questions with `curl` or `/docs`: a lookup ("What is the refund policy for withdrawing in Fall 2026?", about $0.001: classify $0.00003, embedding, rerank $0.0005, answer $0.0001 to $0.0003), a calendar question ("When does Winter 2027 end?", about $0.0002) and a threshold abstain ("What is my GPA this semester?", about $0.00005). The response's own `cost_usd` is checked against these figures; total expected under $0.005, hard stop at $0.01.

## 6. Guardrails

In the prototype (small, standard library, each with a config value and a test):
- **Request size:** question 1 to 500 characters (422), body at most 4 KB (413).
- **Rate limit:** in-memory token bucket per client address, 10 requests per minute and 100 per day (429 with `Retry-After`); single process, resets on restart, addresses never stored.
- **Daily cost cap:** the day's cost is summed from today's `request_logs` rows with `source = 'api'` at startup and kept in memory; at `api.daily_cost_cap_usd` (default $1.00) `/ask` answers 429 "the daily budget is used up". This also bounds a runaway loop.
- **Kill switch:** `api.enabled` (or `CTA_API_ENABLED=false`), plus a file flag `data/api_disabled` checked on every request so it can be switched off without a restart; `/ask` answers 503, `/health` still answers.
- **Timeout:** one overall request timeout (default 30 s) so a slow provider cannot hold workers.

Wait for step 6: input scope checks and prompt-injection screening of the question, stronger personal-data detection, enforcing (not only reporting) the citation check, authentication or API keys, per-user limits and a shared rate-limit store for more than one process, CORS and abuse controls for a public host, LangSmith tracing (redacted), response cache, the HNSW index decision.

## 7. Running it, and what deployment needs later

Prerequisites (once): `docker compose up -d` (Postgres with the loaded chunks), `.env` with the keys, `uv sync`, `npm install --prefix web`. Then two commands, in two terminals:

```
uv run python -m cta.api            # API on 127.0.0.1:8000  (open /docs)
npm run dev --prefix web            # page on http://localhost:3000
```

Deployment (not done now; only a list): an API host that can run the Python app and reach Postgres with pgvector; **the data problem: `data/processed/` is git-ignored, and the chain walk, the contact loader and the calendar renderer read files from it and from `data/calendar/`** (the calendar file and `contacts.yaml` are committed, the processed course records are not), so the image must ship them or the chain tool must read them from the database; a connection pool (`psycopg_pool`, a new dependency to be justified then) instead of a connection per request; secrets in the host's secret store; HTTPS; the web app on Vercel or the same host with the API URL as an environment variable; log retention job; monitoring of cost and errors; step 6 guardrails; a privacy notice; `.env.example` kept current (it currently lacks `CTA_ROUTER_CONTACTS`; I will add that and the new `CTA_API_*` names in step 2).

## 8. Steps, one commit each (order changed by the owner on 2026-10-13)

1. **Dependencies:** `fastapi`, `uvicorn` and the transitive packages, exact pins in `pyproject.toml` and `uv.lock`; Node versions pinned exactly when `web/` is created (step 4). *(Nothing to see yet.)*
2. **API skeleton:** `create_app`, `GET /health`, startup checks including the tracing guard, `api:` config block, `python -m cta.api`, `.env.example`, tests. **First thing visible in a browser:** `http://127.0.0.1:8000/health` and `/docs`.
3. **`POST /ask`:** response models, `convert.py`, error handling, URL map, tests with stubs; then two real questions through the endpoint (one calendar, one retrieval; under $0.005).
4. **Web page, first version:** Next.js scaffold, proxy rewrite, chat box, answer, abstain, loading and error states. **First chat visible in a browser.**
5. **Logging:** migration 005, the log writer, redaction, 30-day purge command, tests (one integration test).
6. **Web page, full:** clickable sources and `[n]` links, contact card, collapsible "how this was found", mobile layout, the logging notice ("Do not type personal information"), `tsc --noEmit` clean.
7. **Guardrails:** size limits, rate limit, daily cap, kill switch, timeout, tests.
8. **Docs and demo check:** README "run it", `docs/architecture.md`, `docs/decisions.md`, the three-question smoke test (under $0.01), tag `phase4-prototype`.

**The API stays local-only (bound to 127.0.0.1, no one else can reach it) until logging (step 5) and guardrails (step 7) are in.** In steps 3 and 4 the endpoint writes no log row (the router is called with `log=False`); that is acceptable only because it is the owner's own machine.

Each step ends with ruff, pytest and `python -m cta.validate`; the pipeline code is not edited (the only touches outside `src/cta/api/`, `web/`, `docs/` are `pyproject.toml`/`uv.lock`, `config/models.yaml` for the `api:` block, `.env.example`, one migration, and tests).

## Node pins (decided at step 1, installed at step 4)
Node 22.23.2 and npm 10.9.8 are what this machine has (Next 16.4.0 needs Node >= 20.9). Exact versions for `web/package.json`: `next` 16.4.0, `react` 19.3.0, `react-dom` 19.3.0, `typescript` **5.9.3**, `@types/react` 19.3.0, `@types/node` **22.20.5**. Two deliberate departures from the registry's latest: `typescript` 5.9.3 instead of 7.0.2 (Next 16.4.0 does not name TypeScript in its peer ranges and I have no evidence that it works with the 7.x line; 5.9.3 is the last 5.x), and `@types/node` 22.x to match the Node 22 runtime instead of 26.6.5. `package-lock.json` is committed.

## Owner decisions (2026-10-13)
1. Yes to `fastapi` and `uvicorn` with the listed transitive packages, including `opentelemetry-api` (to be confirmed as the API package only: no exporter, no network call, and the tracing-variable guard must still work with it installed).
2. Yes to Next.js 16.4.0 + React 19.3.0 + TypeScript with plain `fetch`; no Vercel AI SDK. Exact pins: npm exact versions in `package.json`, lockfile committed; Python exact pins and `uv.lock`.
3. Logging: redacted question and answer text kept 30 days, with a purge command and a notice under the chat box saying not to type personal information.
4. The contact is shown as a card and removed from the API answer text.
5. Course citations without a link are fine for the demo; never invent a URL.
6. Order as in section 8 above (logging after the first web page).

## Owner decisions (2026-10-13, after steps 1 to 3)
1. `typescript` 5.9.3 and `@types/node` 22.20.5 are accepted.
2. The API answer text drops the `ABSTAIN:` marker; `citations` is empty on an abstention.
3. `scope` is dropped from the API contract (the search result columns do not carry it). `last_updated` stays null for web pages.
4. The contact card belongs in step 4: the API strips the contact sentence, so the page must show the card.
5. The page says "Unofficial student project, not affiliated with City Tech".
6. No third-party requests: system fonts, no analytics, no cookies, no localStorage; the conversation is kept in memory only.
7. Step 4 builds `web/` with exact npm pins and a committed lockfile and nothing else; any extra package: stop and ask. The "how this was found" panel and the logging notice are step 6 (a marked empty place is left for them).

## Running it locally (two terminals)
```
uv run python -m cta.api              # terminal 1: API on 127.0.0.1:8000 (needs docker compose up -d, .env)
npm run dev --prefix web              # terminal 2: page on http://127.0.0.1:3000
```
The dev server is bound to 127.0.0.1 (`next dev -H 127.0.0.1`), so the proxy is not reachable from the network. WSL2: opening `http://localhost:3000` in the Windows browser normally works, because WSL2 forwards localhost ports to Windows. If it does not: restart WSL (`wsl --shutdown` from PowerShell) and start both commands again; check that `curl http://127.0.0.1:3000/` works inside WSL; or set `localhostForwarding=true` under `[wsl2]` in `%UserProfile%\.wslconfig`; as a last resort start the dev server with `-H 0.0.0.0` for that one session (this makes the page and the `/api` proxy reachable from your network; go back to the default afterwards).

## Owner direction, step 4b (2026-10-13): redesign of the web page (landing + chat) and a personal-account message
- **Two pages.** `/` is a welcome page: the title; the sentence "Ask about registration, deadlines, advising, tuition and aid, and four departments. Every answer shows its source; when I don't know, I say so and point you to the right office."; four small cards of example topics (registration and deadlines; prerequisites and degrees; tuition and financial aid; the four departments); one clear "Start chatting" button to `/chat`; the "Unofficial student project, not affiliated with City Tech" note.
- **`/chat`** works like a modern chat app. Empty state: a short greeting and one small single-line input in the middle of the page, example questions as chips below it. The input is an auto-growing textarea (one line high, grows to about 6 lines, then scrolls); Enter sends, Shift+Enter adds a line; the send button sits inside the input. After the first message the input docks at the bottom and the conversation scrolls above it in a centered column (max about 760px). The question is a bubble aligned right; the answer is aligned left (light, no heavy bubble) with `[n]` links, a collapsed "Sources (n)" toggle, the contact card and the abstain and "not announced yet" states. Loading is an assistant placeholder with a gentle CSS animation. Auto-scroll to the newest message, `aria-live` for new answers. A "New chat" control clears the conversation. The conversation is in memory only. Under the input: "Each question is answered on its own; earlier messages are not remembered." and the unofficial note. A marked empty place is reserved for the per-answer "How this was found" toggle and for the logging notice (step 6; not built).
- **Colors.** City Tech blue `#007FA3` (primary accent) and orange `#E17800` (secondary: abstain state, small highlights), from the City Tech branding guide, https://www.citytech.cuny.edu/communications/branding-guide.aspx (the values come from the owner; the page was not fetched). Contrast checked against WCAG AA in light and dark (a test reads the stylesheet); orange only for fills, borders and large text; lighter tints of the same hues on the dark theme. System fonts only.
- **No** City Tech logo, wordmark, crest or campus photo (the branding guide forbids recreating or altering logos); no layout, text or branding copied from other projects. Plain CSS, CSS-only animation, `prefers-reduced-motion` honoured, mobile first (390px and desktop), 44px tap targets, visible focus, labelled controls.
- **Personal-account message (contract only).** When the system abstains on the retrieval route (`below_threshold` or a model-written abstention) and the question contains one of the account-word cues the contact mapping already uses (`config/contacts.yaml` `cues`), the API returns `abstain_reason: "personal_account"` (a code, never the model's sentence). The chat then shows "I can't answer questions about your personal account (holds, balances, grades, aid status). Here is who can help:" followed by the contact card the mapping already chose. Other abstentions keep "No answer found". Implemented in `convert.py` from the question and the abstain reason the pipeline already returns; no change to the pipeline, the eval path, prompts, thresholds or the contact table. Known limit: the cues are first-person phrases ("my gpa", "my balance", "my financial aid" ...); a question such as "Do I have a hold on my account?" has no cue and keeps the normal wording.


## Contact policy v2 (2026-10-13)
The contact card is shown only when the office clearly applies (named department or course prefix, account-word cue, calendar abstention, chain no-record for one of the four departments). Otherwise `contact` is null, the answer has no contact line, and the chat page shows the abstain box alone, with no card and no empty gap. See `docs/decisions.md` ("Contact policy v2") and `docs/step4c-plan.md` ("v2").
