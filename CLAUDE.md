# City Tech Assistant

A RAG assistant that answers City Tech (CUNY) students' questions about registration, deadlines,
advising, tuition/payment, financial aid, and four departments. Every answer must cite its source,
and the assistant must say "I don't know, contact X" when the sources don't cover the question.

This is a portfolio project. The owner reads and must be able to explain every line, so keep the
code simple, small, and well tested.

## Scope (pilot)

Central offices (about 24 pages, crawled as HTML):
- Registrar `/registrar/*`: academic-calendar, faqs, grade-policies, incomplete, readmission, epermit, applying-graduation, course-scheduling
- Advisement `/advisement/*`: six-steps, continuing-students, degree-checklist, gen-ed, planner, writing-intensive-fall26, required-core, flexible-core, virtual-advisors, interdisciplinary
- Bursar `/bursar/*`: payment-deadlines, payment-plan, refund-policy
- Financial aid `/financial-aid/*`: financial-payment-calendar, faqs, sap, tap-appeal
- Admissions: `dates-deadlines`, `tuition-refund`, `tuition-penalty`

Departments (catalog id): Computer Systems Technology `CST-NYT`, Mathematics `MATH-NYT`,
Electrical & Telecommunications Engineering Technology `EET-NYT` (the catalog calls it
"Electrical Engineering Technology"; handle both names), Dental Hygiene `DENT-NYT`.

Current term: Fall 2026. Calendars exist for Fall 2026, Winter 2027, Spring 2027. Any other term
is unknown: abstain.

Out of scope for now: anything behind a login (CUNYfirst, Brightspace), faculty bios, the faculty
directory (maybe later; its data loads by JavaScript, so it needs a DevTools check first), class
schedules/sections/seat availability, other departments, archived catalogs, any student data,
class meeting grid PDFs (optional later).

## Data sources (decided Oct 9, 2026)

| Content | Source | Method |
|---|---|---|
| Courses: code, title, description, credits, status, department | Catalog search API | script (POST, paged) |
| Prerequisite/corequisite text | Catalog rule lookup | script, one call per unique rule ID, cached |
| Programs, requirements, degree maps, department overview and chair | 4 department PDFs (downloaded by owner) | parse text, strip noise |
| Term calendars | `fall_2026.pdf`, `winter_2027.pdf`, `spring_2027.pdf` | extract to calendar table, owner verifies every row |
| Refund and aid dates | `Award_Year_2026_2027_Financial_Aid_Payment_Refund__Calendar.pdf` | parse, chunk by section, term metadata |
| Drop/withdraw rules and aid effects | `Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf` | parse, chunk by section |
| Special circumstances contact | `Special_Circumstances_Flyer_...pdf` (infographic) | type the few facts by hand |
| 24 office pages and about 35 department pages (incl. chair and contact blocks) | citytech.cuny.edu HTML | crawl, follow same-host redirects |
| How-to for viewing aid and holds in CUNYfirst | `cunyfirst_student_reference.pdf` (CUNY-wide) | parse, chunk by section, scope=cuny |

Skip `program-DSCI-BS-*.pdf`: it is a subset of the CST department PDF.

### Catalog API

- List: `POST https://app.coursedog.com/api/v1/cm/nyt01/courses/search/%24filters?catalogId=qPpQUgUy149umoKU2soi&skip=0&limit=20&orderBy=code&columns=code,name,description,departments,requirementGroup,credits,status,subjectCode,courseNumber,customFields.catalogAttributes,customFields.cuLibartsFlag&effectiveDatesRange=2026-08-28,2026-08-28&ignoreEffectiveDating=false`
  Body: filters `status is Active` and `catalogPrint is true` (see `scripts/test_catalog_api.py`).
  No login or token is needed. Headers: `Origin: https://citytech.catalog.cuny.edu`, `Referer`
  the same host, `x-requested-with: catalog`, identifying User-Agent. Opening the URL in a browser
  tab gives "Unauthenticated" because that is a GET with no body; that is expected.
- Total is 1,445 active courses. Keep only courses whose `departments[].id` is one of the four
  department ids (about 200). Page with `skip`; confirm the total before and after.
- Rule lookup: `GET https://app.coursedog.com/api/v1/nyt01/requirementGroups/<ID>?returnFields=code,catalogDisplayName,descriptionLong`.
  The `requirementGroup` field and every 6-digit value in degree-map notes is such an ID. Resolve
  them all with this lookup and cache the results. Never parse rule IDs by hand.
- Cross-listed courses (e.g. EET 3672, CET 3672, MECH 3672) share a description but have separate
  records and rules. Keep each under its own code and department. Never merge them.
- Course page for reference: `https://citytech.catalog.cuny.edu/courses/<courseGroupId>/<slug>`
  (server-rendered, but the prerequisite shows only the rule ID).
- This is the same public API the catalog website itself uses. The catalog has no robots.txt
  (404), so still be polite: 1 request/second, identifying User-Agent, save raw JSON.

## Findings about the sources

- `www.citytech.cuny.edu/robots.txt` only disallows `/academics/departments-html/`. Sitemap at
  `/sitemap.xml` has http URLs and junk entries; normalize and filter.
- Site pages carry a big mega-menu in `header`. The parser reads only the main content
  (`div.c-layout-sidebar-content`) and the sidebar contact panels, so the menu, alert banner, breadcrumbs
  and footer are never visited. As of Oct 11, 2026 there are no `{{...}}` placeholders outside the header
  alert banner on the 59 crawled pages (the directory and course-listing pages hold placeholders and
  stay out of scope). Still drop any `{{...}}` found, and treat
  a page with only placeholders as "not collected", never as content.
- Stray spaces inside email addresses (`EMilonas @citytech.cuny.edu`) are in the `mailto:` links on the
  CST, Math and Dental `chairperson.aspx` pages. Take the address from the `mailto:` link and remove
  whitespace; the repairs are listed in `docs/validation-log.md`.
- Department `directory.aspx` pages and the catalog `/faculty` pages are JS-loaded. Not collected.
- Department pages do give a contact block (email, phone, room, office hours); keep it.

### Page status (checked Oct 9, 2026 with a plain fetch)

- 21 of the 24 office pages return real body text (short to medium). The alert-banner placeholders
  sit outside the body and are ignored.
- `admissions/dates-deadlines.aspx` is thin; use the calendar PDFs for dates.
- `financial-aid/financial-payment-calendar.aspx` is a shell that only links to PDFs; the PDF is the content.
- `advisement/planner.aspx` answered with a 302 redirect to the `http://` URL on Oct 9, but returned 200
  directly on Oct 11. The crawler still follows same-host redirects and normalizes to https; don't
  assume a page is missing.
- `advisement/writing-intensive.aspx` (linked from gen-ed and six-steps) returns 404 (checked Oct 11); not collected.
- `advisement/required-core`, `flexible-core` and `virtual-advisors` return real body text; `interdisciplinary`
  does too, but most of it is class-section tables per term (days, rooms, instructors), which is out of scope
  (open decision). Tab panes are in the HTML, not JS-loaded; the parser labels each pane with its tab title.
- Login links (`ssologin.cuny.edu`, or "login" in the path or fragment) are removed from the cleaned text and
  `pdf_links`; the link text stays. Pages marked `index: false` (`no_index_pages` in sources.yaml) are kept as records.
- `advisement/writing-intensive-fall26.aspx` returns 200 with an empty main content div (checked Oct 11).
  It is recorded as `not_collected` ("main content empty in raw HTML") and fails the non-empty body check.
- `registrar/academic-calendar.aspx` links 12 PDFs under `/registrar/docs/` (winter, spring,
  summer, fall 2026 and winter, spring 2027, each with a `_meeting_grid.pdf`). Summer 2027 and
  Fall 2027 calendars are not published, so abstain on those terms.
- `admissions/tuition-refund.aspx` and `bursar/refund-policy.aspx` show tables only for Summer I,
  Summer II and Fall 2026. Spring/Winter 2027 refund answers must come from the calendar PDFs.
- Pages link many form PDFs (re-admission, ePermit, graduation application, TAP waiver). Record
  the links in the page record (`pdf_links`), not in the fetch log, and do not download or index forms for now.
- The financial aid FAQ links several 2025-26 guide PDFs. They are out of date; skip them.

### Department web pages

Real body text, crawl these (department root `https://www.citytech.cuny.edu/<dept>/`):
- CST `computer-systems`: root, advisement, degrees, chairperson, internship-scholarship,
  transfer-policies, student-resources, tutoring
- Math `mathematics`: root, advisement, degrees, accreditation, chairperson, student-resources,
  faqs, articulation-agreement
- EET `electrical-telecomm`: root, advisement, degrees, articulation-agreement, chairperson,
  student-resources, student-hours
- Dental `dental`: root, profession, advisement, apply, accreditation, transfer-students,
  dh-progression, faq, chairperson, student-resources, degrees-after-aas, clinic

Skip: `course-listing.aspx` (only `{{course.Subject}}` placeholders; the catalog API covers
courses), `directory.aspx` (placeholders), news-events, advisory-committee, research, CUNY 2x Tech.
Chair name, office, phone and email appear on both the department PDF and `chairperson.aspx`. If
they differ, prefer the web page and flag the mismatch in the validation log (one page has a
stray space inside an email address; fix it).

### PDF parsing hazards (department PDFs)

- Two-column card layout; the same degree map repeats per track.
- Huge generic rule-text dumps (Flexible Core, Liberal Arts, Required Common Core). Strip them and
  keep only the program-specific requirements and the course lists.
- Drop the Advisory Commission tables (outside people, only noise) and blank "Programs" pages.
- Drop anything tagged "(Inactive)"; drop trailing
  "Total ... Credits 0" lines.
- EET starts with an empty stray program ("Accelerator Science and Technology"); ignore it.
- Broken characters appear (e.g. `O�ers`, `O�ce` for "Offers", "Office"; a lost "ff" ligature).
  Repair them before indexing and add a validation check for the replacement character.
- Shorthand like `PRE_CST1215` and truncated text (CST 3619 "Prerequisite: CST") appear in notes.
  Don't guess; defer to the rule lookup or flag it.
- Term labels disagree ("2027" in the PDF vs "2026 Fall Term" on the web). Store both and don't
  invent a term.
- The file name carries the generation date; keep it in metadata.
- Catalog wins for course facts (API over PDF if they disagree); the registrar calendar wins for dates.
- Legacy courses (MST/DPT prefixes): the catalog wins. The 8 that the catalog lists as Active (7 MST,
  1 DPT, all CST) stay in the course records, flagged `legacy_prefix: true`, not dropped.

### Calendar PDFs

- Rows have no year ("January 04"). The term gives the year; Winter 2027 starts December 2026 and
  ends January 2027, so resolve each row's year carefully and have the owner verify it.
- Some rows are TBA (e.g. commencement). Store the date as null and answer "not announced".
- Each PDF has a "Last updated" date and says the calendar can change; show it in the answer.
- Each row (`data/calendar/calendar_events.json`, built by `uv run python -m cta.parse.calendar_build`):
  `id`, `term`, `event`, `date_start`, `date_end`, `date_raw`, `weekday_raw`, `applies_to`, `bold`,
  `source_pdf`, `source_page`, `pdf_last_updated`, `verified`, `verified_by`, `verified_on`, `notes`.
  All 136 events are verified (owner, 2026-10-11). `calendar_build` refuses to overwrite a file that has
  verified rows unless `--force` is given, and loading the file for indexing fails if any row is unverified. The PDFs are Excel tables; rows are rebuilt from character
  positions (the text stream is not in reading order). One event per printed line of the event cell; a line
  that wraps onto a second line is joined and noted. `pdf_last_updated` is the printed "Last updated" date.

## Architecture

```
config/sources.yaml   -> crawler/API client -> data/raw/ (untouched HTML/PDF/JSON + fetch log)
                                            -> parse/clean -> data/processed/ (one JSON record per section/course)
                                            -> validate (docs/data-validation.md) -> chunk + embed -> Postgres (pgvector + full-text)
calendar PDFs -> hand-verified data/calendar/calendar_events.json -> Postgres table
question -> LangGraph router -> [calendar lookup | hybrid retrieval | abstain] -> answer + citations
every request -> logs (chunks, latency, tokens, cost) -> eval + dashboard
```

Stack: Python 3.12, uv, FastAPI, LangGraph/LangChain, OpenAI API, Postgres + pgvector (Docker),
pytest, ruff, GitHub Actions. Frontend (later): Next.js + Vercel AI SDK.

## Folder layout

```
config/            sources.yaml, settings
scripts/           test_catalog_api.py and one-off helpers
src/cta/crawl/     fetching, URL normalization, robots, change detection, catalog API client
src/cta/parse/     html/pdf/json -> clean text + sections
src/cta/index/     chunking, embeddings, pgvector schema
src/cta/graph/     LangGraph nodes (router, calendar, retrieve, abstain, answer)
src/cta/api/       FastAPI app
src/cta/validate/  data checks
src/cta/eval/      metrics + runner
data/raw/          NOT committed
data/processed/    NOT committed (commit small samples under tests/fixtures/)
data/calendar/     calendar_events.json (committed, hand-verified)
data/pdfs/         the 9 PDFs the owner downloaded (not committed if large; list in docs/)
eval/              questions.jsonl (committed), results/ (committed summaries)
docs/              data-validation.md, decisions.md
tests/
```

## Crawling rules (non-negotiable)

- Respect robots.txt where it exists. Max 1 request/second. User-agent:
  `CityTechAssistantBot/0.1 (student portfolio project; contact: <owner email>)`.
- Save raw responses untouched with URL, timestamp, status, and content hash in a fetch log.
- Only crawl hosts and paths allowed in `config/sources.yaml` (citytech.cuny.edu,
  citytech.catalog.cuny.edu, app.coursedog.com for the two catalog endpoints above). Never follow
  login links. Never send cookies or tokens.
- Never collect or store personal student data.
- Re-crawl detects changes by content hash and re-embeds only changed items.

## Data rules

- Every chunk carries: `source_url` (or `source_file`), `doc_type`
  (policy|calendar|catalog_course|program|department|faq|aid), `department`, `scope`
  (cuny|city_tech|department), `term` (when relevant), `fetched_at` (or file date), `last_updated`.
- Chunk by heading/section, not fixed size. Keep tables as markdown.
- A table stays in the same chunk as the intro text above it (for example "see the following table:").
  When chunking, merge a section's tables with their parent section's text (`merge_tables_into_parents`
  in `src/cta/parse/sections.py`), keeping the table's own heading.
- A course record is one chunk: code, title, credits, description, resolved prerequisite text,
  department, and the program(s) that list it.
- Calendar questions are answered from the calendar table, not vector search.
- Nothing is indexed until the validation checks in `docs/data-validation.md` pass.

## Answer behavior

- Cite the source URL or file for every factual claim. Pass today's date to the model so
  "this fall" resolves to the right term.
- Abstain, with the relevant office's contact, when retrieval confidence is low, the term has no
  calendar (anything other than Fall 2026, Winter 2027, Spring 2027), the question needs account
  data ("do I have a hold?"), or it asks for sections/professors/seat availability or a department
  outside the four.
- Never give advice or judgment ("should I drop this class?"); state the rules and the deadline.
- Low temperature and low top_p for answers.

## Evaluation

- Labels are document/section level (source URL + heading), never chunk IDs.
- `eval/questions.jsonl` fields: `id`, `question`, `gold_answer`, `gold_sources`, `type`
  (lookup|multi_chunk|time_sensitive|ambiguous|unanswerable), `department`, `split` (dev|test).
- Metrics: recall@k, precision@k, hit rate, MRR, answer correctness, faithfulness, abstention
  accuracy, cost per request, latency. Report each retrieval change against the baseline.
- Do not tune on `test`. Change one thing at a time. CI fails on a recall regression.
- The owner writes or reviews every eval question. Do not invent gold answers; mark unknowns `TODO`.
- Include cases for: date questions needing the right term, chained prerequisites, cross-listed
  courses, and each abstain category above.

## Phases

0. Done: catalog access decided (public API above) and every office page and department page
   checked (see Page status).
1. Collect: catalog API client, rule cache, Tier 1 crawl, PDF parsers, calendar table; run
   validation; write 30 starter eval questions.
2. Baseline: chunk, embed, vector-only RAG; record metrics.
3. Improve: hybrid search, reranker, term filtering, LangGraph router + calendar tool. Compare to baseline.
4. Product: FastAPI + Next.js UI, logging dashboard, CI eval, deployment, README with results and failure analysis.

## Working rules for Claude Code

- Do one phase at a time. Propose a short plan before large changes. Make small commits.
- Add or update tests with every change. Run `ruff` and `pytest` before finishing.
- Never invent URLs, dates, policies, or course data. If a fact is not in the data, say so.
- Do not add dependencies without saying why. Prefer the standard library and boring choices.
- Secrets live in `.env` (never committed). Keep `.env.example` current.
- Keep functions small and typed. Explain non-obvious decisions in a short comment or `docs/decisions.md`.