# Validation log

## 2026-10-11: first catalog crawl (courses)

- API total before and after: 1,445. Downloaded: 1,445. Kept (4 departments): 197.
- Per department: CST-NYT 93, MATH-NYT 49, EET-NYT 43, DENT-NYT 12.
- 161 unique rule IDs resolved (one call each). 14 courses have no rule (no prerequisite).
- robots.txt for `app.coursedog.com`: 404, so no rules.
- Automatic course checks: 0 failures, 25 flagged for review (all `prereq_codes`).
- Flags are not fixed yet. Causes seen: prerequisite text mentions codes that are not Active in the
  catalog (e.g. CST 1202, MAT 2070); words read as codes (`OR 3513`, `TWO 2000`); suffix letters
  (`MAT 1475H`). Separately, 40 CST courses have rule text that is shorthand (`PRE_CST3500_CST3600`),
  which passes the resolved-text check but is not readable prerequisite text.
- Manual checks: not done.

## 2026-10-11: re-run from saved raw data (no new crawl)

Same data as the first crawl (fetched 2026-10-11T14:59:40Z). Counts unchanged: 1,445 downloaded,
197 kept (CST-NYT 93, MATH-NYT 49, EET-NYT 43, DENT-NYT 12). Failures: 0.

Changes since the first entry:
- Code check tightened: SUBJ must be a subject used by the 1,445 catalog courses, suffix letters
  and codes without a space are normalized (`CST1201`, `MAT 1475H`), codes inside shorthand are
  checked too. `OR 3513` and `TWO 2000` are no longer flagged.
- Shorthand prerequisites: 3 rules were fetched in full (CST 4900 / 014763, CST 3519 / 014686,
  CST 2303 / 014420). The response is flat: the same text in `description`, `descriptionLong`,
  `catalogDisplayName` and `notes`, plus a short label (`descriptionShort`, e.g. `P:CS35/36`).
  No and/or or course-list fields, so nothing was converted. Records keep the raw text and carry
  `prereq_style`. Counts: shorthand 40 (all CST), text 143, none 14 (no rule), unresolved 0.

Warnings (28 findings, 0 failures). Each is a course code in prerequisite text that is not among
the 1,445 Active catalog courses. Not fixed; the owner decides:
  - CST 1202: referenced by CST 1205, CST 2302, CST 2303
  - CST 3500: referenced by CST 4900, CST 4905
  - CST 3600: referenced by CST 4801, CST 4816, CST 4900, CST 4905
  - EDU 4600: referenced by MEDU 4000
  - EMT 1111: referenced by CST 2403
  - EMT 1250: referenced by MAT 2899, MAT 2900
  - MAT 1205: referenced by CST 3510
  - MAT 1476: referenced by CST 2403
  - MAT 1476L: referenced by MAT 2630
  - MAT 2070: referenced by MAT 3021, MAT 3075
  - MAT 2071: referenced by MAT 3021
  - MAT 2672: referenced by MAT 4050, MAT 4672
  - MAT 3000: referenced by MAT 4800
  - MEDU 3020: referenced by MEDU 4000
  - TCET 2220: referenced by TCET 3222
  - TCET 2242: referenced by TCET 3122
  - TCET 3102: referenced by TCET 3222, TCET 4132
  - TCET 3202: referenced by TCET 4102

Other observations (no check covers these yet):
- (Decision 2026-10-11: kept and flagged `legacy_prefix: true`.) 8 Active records in CST-NYT have legacy prefixes: DPT 2309, MST 1101, MST 1204, MST 1205,
  MST 2050, MST 2304, MST 2307, MST 2405. CLAUDE.md says to drop MST/DPT from the PDFs. They were
  kept here because the catalog lists them as Active.
- The full catalog has one duplicated code, `AFR 2000` (outside the four departments).
- Course titles are the API `name` field, abbreviated by the catalog (for example
  "Software Development .NET Fram", "Prin Of Dh Care 4").
- Manual check sheet: `docs/manual-check-courses.md` (20 courses). Not done yet.

## 2026-10-11: extra course fields (rebuilt from saved raw data, no new crawl)

Fetch log unchanged (240 rows). 197 records, 0 failures, same 28 warnings.

- `description` is kept in all 197 records (it is present in all 1,445 raw courses).
- New fields, all taken from the raw JSON: `liberal_arts` (`customFields.cuLibartsFlag`: 40 true,
  157 false), `catalog_attributes` (`customFields.catalogAttributes`, raw strings; 38 records have
  some), `writing_intensive` (true when an attribute starts with `WRIC`: 24 records, MATH 12,
  CST 5, EET 5, DENT 2), `credit_hours` (`credits.creditHours`, `{min, max, operator}`) and
  `contact_hours` (`credits.contactHours`, `{value, operator}`).
- New automatic check `extra_fields`: those fields exist and have the right type. 0 failures.
- `pathways_category` is null for all 197 records. It is NOT in the raw data: the list request
  asks for only two `customFields` columns (`cuLibartsFlag`, `catalogAttributes`), and neither holds
  a Pathways label. Waiting for the owner's OK before a new crawl to find the column.

## 2026-10-11: Pathways category found, full re-crawl

- 3 extra requests with no `columns` restriction (CST 2406, MAT 2540, CST 1101), logged in the
  fetch log. The full response has 100+ top-level keys. The Pathways label is the top-level
  `requirementDesignation`: CST 2406 = "Regular Non-Liberal Arts", CST 1101 = "Regular Liberal
  Arts", MAT 2540 = "RLA_FC_ScientificWorld" (a code; the readable text
  "Flexible Core - Scientific World" is in `customFields.catalogRequirementDesignation`).
- The list request now asks for `requirementDesignation` plus `customFields.cuPathwayFlag`,
  `cuPathwaysAttribute` and `catalogRequirementDesignation` (the last three are in the raw JSON
  only, not in the records). Full re-crawl at 2026-10-11T16:39:50Z: 1,445 downloaded, total before
  and after 1,445, 197 kept (CST 93, MATH 49, EET 43, DENT 12), 0 rule lookups (cache).
- `pathways_category` = `requirementDesignation` exactly as returned, never derived from the
  liberal arts flag. Present for all 1,445 raw courses and all 197 records. Values (197 records):
  Regular Non-Liberal Arts 149, Regular Liberal Arts 23, RLA_FC_ScientificWorld 8,
  Laboratory Non-Liberal Arts 8, RLA_RC_Mathtcl&QuantveReasng 5, RLA_CollegeOption 2,
  DLA_RC_Mathtcl&QuantveReasng 2.
- 17 records (the four coded values plus RLA_CollegeOption) carry a code, not a readable label.
  Open question for the owner: map codes to labels, or store `catalogRequirementDesignation` too.
- `extra_fields` check now also requires a non-empty `pathways_category`. Failures: 0.
  Warnings: the same 28. Fetch log: no gaps (4 robots.txt 404s, everything else 200).

## 2026-10-11: `pathways_label` added (rebuilt from saved raw data, no new requests)

Fetch log unchanged (319 rows). 197 records, 0 failures, 30 warnings (the same 28 `prereq_codes`
plus 2 new `pathways_labels`).

- `pathways_label` = `customFields.catalogRequirementDesignation`, exactly as in the raw JSON, else
  null. `pathways_category` is still the raw `requirementDesignation`. No code is mapped to a label.
- 15 of 197 records have a label: RLA_FC_ScientificWorld 8 ("Flexible Core - Scientific World"),
  RLA_RC_Mathtcl&QuantveReasng 5 and DLA_RC_Mathtcl&QuantveReasng 2 (both
  "Required Core - Mathematical&QuantitativeReasoning"). The 182 courses with a readable
  `pathways_category` (Regular/Laboratory ...) have no such key, so their label is null.
- Correction to the earlier entry: the 2 DLA_RC_Mathtcl&QuantveReasng courses (MAT 1190CO,
  MAT 1275CO) do have a label. Only 2 coded records lack one: CST 1102 and CST 1102ID, both
  `RLA_CollegeOption`. Their raw `customFields` hold only `catalogAttributes`, `cuLibartsFlag`
  and `cuPathwayFlag` (true); no `catalogRequirementDesignation` or `cuPathwaysAttribute`.
  Left null, not inferred.
- New warning check `pathways_labels`: a coded `pathways_category` (no spaces) with no label.
  It flags those 2 courses.

## 2026-10-11: `legacy_prefix` flag (rebuilt from saved raw data, no new requests)

Owner decision: the 8 Active MST/DPT courses (DPT 2309, MST 1101, 1204, 1205, 2050, 2304, 2307,
2405) are kept and flagged `legacy_prefix: true`; the catalog wins. CLAUDE.md updated. 197 records,
0 failures, 30 warnings, fetch log unchanged. Open: `docs/data-validation.md` (PDF checks) still says
legacy MST/DPT courses "do not appear in cleaned output"; not edited, owner to confirm wording.

## 2026-10-11: web pages, raw crawl (parser not built yet)

- 59 pages crawled with the fetcher (24 office, 35 department), all returned 200, saved as received
  under `data/raw/www.citytech.cuny.edu/`, manifest in `data/processed/pages_manifest.json`.
  `advisement/planner.aspx` returned 200 directly (no redirect seen today; CLAUDE.md says 302).
- `advisement/writing-intensive-fall26.aspx` returns 200 with an empty main content div.
- Stray spaces inside emails (`EMilonas @citytech.cuny.edu`) appear on several pages, not one: the
  CST, MATH and DENT chair pages and five advisement pages (`transferadvisement @...`).

Pending manual items (not automated yet):
- Chair name, office, phone and email: compare the web page with the department PDF (needs the PDF
  parser, a later step).
- Refund pages show which terms they cover; no refund answer for a term the page does not list.

## 2026-10-11: web pages, parser and checks (first full run)

59 pages crawled and parsed (raw HTML untouched; parsing decodes in memory only). Selectors approved
by the owner: main `div.c-layout-sidebar-content`; contact panels `div.c-layout-sidebar-menu div.panel`
whose heading is "CONTACT US" or contains "HOURS"; `p.barTitle` read as a level-2 heading; tables
that contain headings are layout (their content becomes sections); `owner` comes from the manifest.

Pages per owner (collected / fetched, all HTTP 200): CST-NYT 8/8, MATH-NYT 8/8, EET-NYT 7/7,
DENT-NYT 12/12; admissions 3/3, advisement 5/6, bursar 3/3, financial-aid 4/4, registrar 8/8.
Total 58 collected of 59.

Failed checks (1, not fixed):
- `body_non_empty`: `advisement/writing-intensive-fall26.aspx` returns 200 with an empty main content
  div. Recorded as `not_collected`, reason "main content empty in raw HTML". Cause not investigated.

Email repairs (3 pages; the address is taken from the `mailto:` link and whitespace removed):
- `computer-systems/chairperson.aspx`: `EMilonas @citytech.cuny.edu` -> `EMilonas@citytech.cuny.edu`
- `dental/chairperson.aspx`: `AMatthews @citytech.cuny.edu` -> `AMatthews@citytech.cuny.edu`
- `mathematics/chairperson.aspx`: `JNatov @citytech.cuny.edu` -> `JNatov@citytech.cuny.edu`
  (the visible text is also split across elements; the link holds the whole address)

Correction to the earlier entry in this log: I wrote that stray spaces also appear on five
advisement pages (`transferadvisement @...`). That was wrong. It came from my own text search, which
joined text nodes with spaces. In the HTML the `mailto:` href is correct
(`transferadvisement@citytech.cuny.edu`); only the link text is split by a `<br>`. No repair is needed.
The EET chair email has no space either.

Parser problems found by comparing cleaned text with raw text, and fixed in code (not by editing data):
- `<p>` and `<table>` elements placed directly inside a `<ul>`/`<ol>` (registrar/faqs,
  financial-aid/sap) were dropped; they are now kept in order.
- Footnote markers glued onto words (`Psychology<sup>1</sup>` read as "Psychology1"); now `Psychology^1`.
- `<button>` text inside a link was dropped (computer-systems root, "Advisement and Tutoring
  Information"); now kept as link text.
- Broken markup on `bursar/payment-plan.aspx` (`<tr><tr>...</tr></tr><td>...`) hid the last row of the
  Fall 2026 table (Aug 25 - Sept 04, 2 payments, Oct - Nov); table cells outside a `<tr>` are now kept.
- Commented-out HTML is ignored on purpose (for example a stale "Fall 2025 Payment Plan" table on the
  payment-plan page, and a phone number in the bursar contact panel).
After these fixes every word in the raw main content (outside comments) appears in the cleaned text.

Pending manual items (not automated):
- Chair name, office, phone and email: compare the web page with the department PDF (needs the PDF
  parser, a later step). The web-side check only requires the chair block to be complete and
  well formed; the department root pages carry the department office contact, not the chair.
- Refund pages show which terms they cover; no refund answer for a term the page does not list.
- Manual check 3 (open 10 random cleaned pages and look for menu junk or missing sections).

## 2026-10-11: page review (rebuilt from saved raw HTML; 5 new fetches)

Pages: 63 in the manifest (28 office + 35 department), 62 collected, 59 `index: true`. Checks: 1 failure
(the empty writing-intensive-fall26 page, unchanged), 4 warnings (`long_urls`), 0 other findings.
Pages per owner (collected / fetched): CST-NYT 8/8, MATH-NYT 8/8, EET-NYT 7/7, DENT-NYT 12/12,
admissions 3/3, advisement 9/10, bursar 3/3, financial-aid 4/4, registrar 8/8.

1. Login links removed (link text kept) from markdown and `pdf_links`: 7 links on 6 pages
   (`ssologin.cuny.edu` on degree-checklist, gen-ed (2), planner, six-steps, registrar/faqs; one
   `cuny.coursedog.com/#/login` link on registrar/course-scheduling). No `pdf_links` entry was a login
   link. New checks: `login_links` (fail) and `long_urls` (warning, query string over 100 characters).
   URLs with a query over 100 characters that remain (4 distinct, not removed, owner to decide): a
   Teams meeting link on electrical-telecomm/student-hours (125 chars, 3 times on the page) and three job
   listing links with tracking parameters on electrical-telecomm/student-resources (careerbuilder.com
   119, careerrookie.com 164 twice). The 348- and 122-character `ssologin.cuny.edu` URLs are gone.
2. Contacts: `data/processed/contacts/<owner>.json`, one per owner (9). Panels are identical on every
   collected page of each owner (`consistent: true` everywhere). The only different page,
   writing-intensive-fall26, has no sidebar and is not collected. Per-page `contact.embed` is false.
   Parser fixes found on the way: panels nested inside another panel are no longer processed twice, and
   panels whose title is plain text (no heading element) are read by their first line. The financial-aid
   hours (in-person, zoom, phone, web-lab, work-study) were being dropped and are now in the contact
   record, inside the CONTACT US panel body. `check_contacts` warns if panels differ.
3. Empty sections dropped (check `empty_sections`, 0 found). Added `parents` to each section (the
   headings above it, for example the FAQ category above a question) so dropping empty headings does not
   lose context; `render_markdown` prints them. Headings with no text under them and no child sections
   disappear completely (5 `h` headings: registrar/applying-graduation "Congratulations! You are almost
   at the finish line!", financial-aid/sap "Financial Aid Suspension and SAP Appeal Process",
   mathematics/student-resources "Academic Resources", electrical-telecomm/ "Annual Enrollment and
   Graduation Data", dental/advisement "How to Apply for the Dental Hygiene Program"; plus a few labels:
   computer-systems/tutoring "Areas of Expertise", electrical-telecomm/student-resources tab titles
   "Industry Partners" and "Links", dental/profession "Overview"). Their content, if any, was not text.
   Nested lists: a `<ul>` placed directly inside a `<ul>` is now the children of the previous item
   (advisement/gen-ed, College Option). Also fixed: an unclosed `<p class="barTitle">` on financial-aid/sap
   swallowed the paragraphs after it into one heading; that would have been dropped as an empty section
   (132 words), now only its leading text is the heading. Tab panes (6 pages) get their tab title as a
   heading, and a header row drawn with `<strong>` is the table header.
4. `index` and `index_reason` on every record. `index: false`: registrar/course-scheduling,
   electrical-telecomm/articulation-agreement, mathematics/articulation-agreement (reasons are in
   sources.yaml `no_index_pages`, written by me from what the pages contain: owner to confirm), and the
   not-collected page ("not collected: main content empty in raw HTML"). Records are kept.
5. Five fetches (advisement/*.aspx), all in the fetch log:
   - required-core: 200, real text (3 tab panes, one table each). Added.
   - flexible-core: 200, real text (5 tab panes, one table each). Added.
   - virtual-advisors: 200, real text (advisement by department, 10 PDF links). Added. It lists advisor
     names and email addresses (staff, not students).
   - interdisciplinary: 200, real text, but about 11,700 words, mostly class-section tables per term
     (section numbers, days/times, rooms, instructors). Added as asked; class schedules and sections are
     out of scope in CLAUDE.md, so this needs an owner decision (for example `index: false`).
   - writing-intensive: 404. Not added. The URL is linked from advisement/gen-ed and advisement/six-steps.
     Cause not investigated.

## 2026-10-11: owner decisions on the page review (rebuilt from saved raw data, no new crawl)

Pages: 63, 62 collected, 58 `index: true`. Page checks: **0 unexpected failures, 2 accepted, 0 warnings**.

Decisions applied:
1. advisement/interdisciplinary: `index: false`, `index_reason` "class-section tables per term, out of
   scope". The record is kept.
2. advisement/virtual-advisors: `index: true`, `doc_type: "advisement_contacts"`, `note: "lists staff
   emails"` (set from `page_metadata` in sources.yaml; every record now has `doc_type` and `note`, null
   by default).
3. `index_reason` for course-scheduling and the two articulation pages unchanged; `parents` kept.
4. Query strings over 100 characters are stripped from links (link text kept; also in `pdf_links`) and
   the stripped URLs are listed in each record's `stripped_urls`. 8 links on 2 pages (5 distinct URLs):
   electrical-telecomm/student-hours: Teams meeting link (query 125 characters, 3 times);
   electrical-telecomm/student-resources: careerbuilder.com (119), careerrookie.com (164, twice) and
   jobs.volt.com (271, a link the earlier check did not list). The `long_urls` warning is gone; the check
   now fails if any such query is kept (it found none).
5. Known and accepted (reported every run, with the reason, in `ACCEPTED` in `cta/validate/pages.py`):
   - `advisement/writing-intensive-fall26.aspx`: not_collected, 200 with an empty main content div
     (check `body_non_empty`). Cause not investigated.
   - `advisement/writing-intensive.aspx`: known 404, linked from gen-ed and six-steps; not in
     sources.yaml. Check `known_404` reads the latest fetch-log row; if it ever stops being a 404 the check
     `known_404_changed` fails. Cause not investigated.
   The same failure on any other page is still an unexpected failure.
6. Chunking rule for tables added to CLAUDE.md "Data rules": a table stays in the same chunk as the intro
   text above it. `merge_tables_into_parents` (`src/cta/parse/sections.py`) merges a section that contains a
   table into its parent section. On financial-aid/sap the 13 sections become 11 units: the intro ("the
   following table...") plus the Associate and Baccalaureate tables form one unit. Both SAP tables were
   checked by the owner against the live page.

Source typo, left as printed (not changed): financial-aid "PHONE HOURS" table says
"Tuesday | 9:00 PM - 5:00 PM"; it should presumably be AM. It is in the financial-aid contact record and in
the contact panel of each of the 4 financial-aid pages.

## 2026-10-11: calendar table (Fall 2026, Winter 2027, Spring 2027)

Built by `uv run python -m cta.parse.calendar_build` from `data/pdfs/{fall_2026,winter_2027,spring_2027}.pdf`
into `data/calendar/calendar_events.json`; the owner's review sheet is `docs/calendar-verification.md`.
All 136 rows are `verified: false`. Checks: **0 failures**, 0 weekday mismatches, 0 lines that could not
be parsed.

- Text layer: all three PDFs have one (readable text-drawing operators; one image each, a logo).
  Checked first with the standard library, then with pdfplumber (new dependency). No OCR.
- Events per term: Fall 2026 55 (page 1: 45, page 2: 10), Winter 2027 26 (page 1), Spring 2027 55
  (page 1: 44, page 2: 11). Summer 2027 and Fall 2027: no rows, status "abstain".
- `pdf_last_updated` from the printed text: Fall "9/15/26" (2026-09-15), Winter and Spring "7/27/26"
  (2026-07-27). The PDF metadata ModDate is 2026-09-15 for Fall (same as printed) and 2026-08-28 for
  Winter and Spring (later than the printed date); the printed text is used, as agreed.
- Rows are rebuilt from character positions: the cell borders are thin rectangles and each character
  belongs to the cell holding its center (the stream order is not reading order, and a few words such as
  "Friday" change font mid-word).
- Bold: the font name says it (`TimesNewRomanPS-BoldMT` vs `TimesNewRomanPSMT`). Spot-checked on a
  rendering of the Winter page: the 9 bold events match the printed bold lines. No event line mixes bold
  and regular text, so `bold` is never null here (50 true, 86 false).
- Year: Winter 2027 starts in December 2026 (first row December 28, 2026); the year moves to the next
  one when the table goes from December to January. Fall 2026 prints "January 01, 2027" for its last
  row, which agrees. No printed year disagreed with the table position. A date was never changed.
- Weekday check: all 135 dated rows match (including ranges such as "Tuesday-Monday" for Dec 15-21,
  2026). The TBA row has no date to check.
- Wrapped lines (8 rows, joined and noted "printed on 2 lines; joined as wrapped text"): a printed line
  continues the one above it when it starts with a lowercase letter or digit, or when its first word would
  not have fitted on the line above. Rows: Fall 35 (Plan Week), 38 (early registration), 41 (appeals
  deadline); Winter 17 (appeals deadline); Spring 1 (appeals), 33 (Plan Week), 38 (early registration),
  46 (appeals). Winter row 17 was checked against the rendered page. This rule is mine, not the PDF's:
  the owner should check these 8 rows in particular.
- TBA: Spring 2027 "87th Commencement Ceremony", date_raw "TBA", weekday_raw "TBA", dates null.
- `applies_to` is filled only when the text names who it is for (11 rows: "all students" for the
  online-registration rows, the ASAP/CSTEP/Honors/SEEK list for early registration, and the
  "students dismissed ..." qualifier of the appeals deadline). Otherwise null.
- Date windows (`config/calendar_terms.yaml`): Winter 2027 2026-12-20..2027-02-10 (owner's description).
  Fall 2026 2026-06-29..2027-01-21 and Spring 2027 2026-11-29..2027-06-27 are my choice from the dates
  printed in their own PDFs (60 days before the printed start-of-term event to 31 days after the
  end-of-term event). Owner to confirm.
- Text in each PDF outside the table, not turned into events: the title, the line "*The Academic Calendar
  is subject to change at any time by official action of the University", "CUNY Policy on Religious
  Accommodations" and "All Religions and Ethnic Holidays Calendar".
- Automatic checks (tested, including with deliberately damaged data): required fields and unique ids; dates
  inside the term window; printed weekday matches the date; no duplicate rows; every character the PDF has
  inside the table (minus the header row) is in the table and nothing else is, and the event texts equal
  the printed event lines in order; each term has one start and one end event; the title matches the file;
  no-calendar terms have no rows and abstain.
- The completeness check compares the table with all characters inside the table outline, found without
  using the rows or cells, so a dropped, duplicated or invented line is caught. It cannot catch a wrong
  grouping of lines into events (for example a line wrongly joined or split): that is what the manual row
  check is for.

Pending (owner): check every row of `docs/calendar-verification.md` against its PDF, then set `verified: true`.

## 2026-10-11: calendar verified by the owner

The owner checked every row of `docs/calendar-verification.md` against the PDFs; all 136 rows are correct.
`data/calendar/calendar_events.json`: `verified: true`, `verified_by: "owner"`, `verified_on: "2026-10-11"` on
all 136 events (55 Fall 2026, 26 Winter 2027, 55 Spring 2027). Nothing else in the file changed except the
`notes` entry below (the old and new data were compared field by field).

- New check `check_verified` and loader `load_events_for_indexing`: loading the file for indexing raises
  `UnverifiedCalendarError` if any event is not `verified: true`, or has no `verified_by` or a valid
  `verified_on`. Tested, including that the committed file loads.
- `calendar_build` no longer overwrites a file that has verified rows (it prints a message and stops
  unless `--force` is given), so re-running it cannot reset the verification by accident.
- `docs/calendar-verification.md` still says the rows are unverified: it is written by the build and was
  not regenerated.

### Open cross-source conflict: Spring 2027 SAP appeals deadline

| Source | Value |
|---|---|
| Calendar PDF https://www.citytech.cuny.edu/registrar/docs/spring_2027.pdf (local copy `data/pdfs/spring_2027.pdf`, "Last updated: 7/27/26", row `spring-2027-043`, page 1) | "Deadline to submit Satisfactory Academic Progress (SAP) Appeals for Title IV for Spring 2027": **March 31, Wednesday** (2027-03-31) |
| Financial Aid SAP page https://www.citytech.cuny.edu/financial-aid/sap.aspx (fetched 2026-10-11, section "SAP Appeal Deadlines") | "Spring 2027: **Tuesday, March 30th, 2027**" |

Both weekdays agree with their own dates (March 30, 2027 is a Tuesday and March 31 a Wednesday), so this is a
real difference of one day, not a typo in one weekday. The Fall 2026 deadline agrees in both sources
(Friday, November 13, 2026). Handling: the calendar PDF is the source for dates (CLAUDE.md: the registrar
calendar wins for dates); the calendar row carries this in its `notes`. The SAP page text is kept as it is.
Status: open, nobody has asked either office which date is right.

## 2026-10-11: the four smaller PDFs

Records in `data/processed/pdfs/<slug>.json` (not committed), built by `uv run python -m cta.parse.pdf_docs`
(checks in `cta/validate/pdfs.py`). All four have `index: true`, `text_source: "text layer"`. Findings: 0
failures, no line that could not be placed. The four files are in `known_data` in `config/sources.yaml`.

| Record | doc_type / scope | term / aid year | pdf_last_updated | file_modified | Sections |
|---|---|---|---|---|---|
| financial-aid-refund-calendar-2026-2027 | aid / city_tech | aid year 2026-2027 | 2026-06-08 ("Updated 06/08/2026") | 2026-07-27T09:22:20-04:00 | 7 (title + 7 headings; 3 tables) |
| dropping-withdrawing-fall-2026 | policy / city_tech | term Fall 2026 | none printed | 2026-09-01T09:23:13-04:00 | 9 (title + 8 headings) |
| special-circumstances-flyer | aid / city_tech | aid year "2025-2026 & 2026-2027" | none printed | none (created 2026-01-16T15:31:41) | 5 |
| cunyfirst-student-reference | howto / cuny | none printed | none printed | 2022-12-28T12:06:31-05:00 | 10 |

- Refund calendar: all three date tables and every date are as printed (the main table is 5 columns, its
  last row has 3 dates and keeps its blank cells; the two book-advance lists are one column each). The
  printed "Updated 06/08/2026" (a footer) differs from the metadata date (2026-07-27); both are kept. The
  footer lines and the page number are in `excluded`, not in a section.
- Dropping and Withdrawing: the PDF has one heading style, so all headings are level 2 under the title
  (the three "Dropping a Class ..." headings are not nested under "Dropping Classes": nothing in the PDF says
  so). No "last updated" is printed, so `pdf_last_updated` is null. Bold dates and terms are kept as `**`.
- Special circumstances flyer: the owner asked for a transcription from a rendered image, but the PDF has a
  text layer, so the text is read from it, panel by panel (intro, STEP 1-3, contact). The record says so in
  `note` and is NOT flagged as transcribed from an image. The rendered page was compared with the text by
  eye. The `ﬁ` and `ﬂ` ligatures are replaced by `fi` and `fl` (13 times, listed in `repairs`; this also
  makes the email address `finaidspecialcircumstances@citytech.cuny.edu` correct). The line-by-line check
  cannot be used (the lines of different panels share a baseline); the character check is.
- CUNYfirst guide: written steps only. 22 lines of 7 pt callout text laid over the screenshots (for example
  "Click here to choose your college of enrollment and financial aid year") are in `excluded` with that
  reason. `note` says its examples show Hunter and LaGuardia and the 2022-23 aid year; that is the owner's
  reading of the screenshots, which are images and are not in the record. The guide's last section is the
  W-2 form (the cover also says "paycheck"); there is a section on accepting/reducing/declining offers that is
  not in the owner's list. Its heading "VIEW YOUR FEDERAL WORK- STUDY W-2 FORM" is kept as printed.
- Parser decisions (documented, applied to all four): a bold-only line without final `. ! ? , ;` and with
  space above it is a heading; a line that ends early starts a new paragraph, a line whose next word would not
  have fitted continues it; lines ending in a hyphen are joined without a space ("three-quarter-time", a URL;
  listed in `repairs`); superscript ordinals ("21st", "5th") are joined, other superscripts get a `^`.
- Checks (tested, including with damaged records): no U+FFFD; every character the PDF prints is in the record
  and nothing else (each record is compared with all characters of the PDF); every line pdfplumber finds is
  in the record, in order (not for the flyer); the term, aid year and "Updated" date the PDF prints in its
  title area or text are in the record and none is invented; every table has all its cells and equal row
  widths (refund calendar only; the other PDFs have none that count, and the frames and cover grid in the
  CUNYfirst guide are skipped).
- Not committed: the flyer (1 MB) and CUNYfirst (1.4 MB) PDFs, so their tests are skipped when `data/pdfs`
  is missing. The refund calendar and Dropping PDFs are committed as test fixtures.

## Phase 1, step 5: department PDFs (CST, EET, DENT, MATH) — 2026-10-11

Part A (follow-ups on step 4, nothing changed):

- a) CUNYfirst guide, 22 excluded lines (all "screenshot annotation (7 pt callout text laid over a
  screenshot)"). Read like a step instruction (7 places, 11 of the lines): p3 "Click here to access
  additional information"; p4 and p6 "Click here to choose your college of enrollment and financial aid
  year" (2 lines each); p7 "You can click on the filter icon to choose whether to view aid by type ... You
  can also search by the status of the award ..." (2 lines) and "Use the dropdown menu to view information by
  term or for the entire academic year" (5 lines); p8 "Use the drop-down menu to view information by term"
  (2 lines); p14 "Choose the term you wish to view then click the go button to view." (2 lines). Plain
  labels, not instructions (5 lines): p3 "You can filter your to do list by type and by college"; p6 "This
  option will only show when your aid has been packaged at the college for the indicated academic year". Kept excluded
  until the owner decides.
- b) Dropping and Withdrawing vs `calendar_events.json` (Fall 2026): Sept 3 certification date = fall-2026-010
  (and 011 "last day to drop without a grade of WD"): match. WD window Sept 4-17 = fall-2026-013 (Sept 4, WD
  assigned) to fall-2026-021 (Sept 17, last day to drop with WD): match. 21st day = Sept 17: same row (021):
  match. The W period starting after Sept 17 = fall-2026-024/025 (Sept 18): match. No mismatches.

Part B: records in `data/processed/departments/<dept>/` (git-ignored, like the other outputs).

| Dept | Records | Sections | Stripped (type: count) |
|---|---|---|---|
| CST-NYT | overview + 4 programs | 124 | advisory 1, blank Programs page 1, zero total lines 20, rule-dump sentences 19, inactive 1 |
| DENT-NYT | overview + 1 | 26 | advisory 1, blank Programs page 1, zero total lines 2, rule-dump 4 |
| EET-NYT | overview + 2 | 38 | advisory 1, "Programs" heading 1, stray program 1, zero total lines 4, rule-dump 9 |
| MATH-NYT | overview + 4 | 64 | advisory 3, blank Programs page 1, zero total lines 6, rule-dump 14, inactive 1 |

- Checks (code in `cta.validate.departments`, run by `uv run python -m cta.parse.departments`, tested): no
  U+FFFD, no unrepaired U+2BD1, no ligature characters, no generic rule text left, no "Advisory Commission",
  "(Inactive)", "Total ... Credits" or stray program, each department has an overview with Description, at
  least one program, a Requirements section and one degree map, no term invented, every rule ID resolved,
  and a character-level completeness check (every printed character is kept, stripped, repaired or counted).
  All four departments: 0 findings. 138 rule IDs, all in the cache (the 23 missing ones were fetched at 1
  request/second in an earlier run).
- Repairs: `O⯑ers`→`Offers` and `O⯑ce`→`Office` (U+2BD1 is a lost "ff"), each with its count in `repairs`;
  ﬁ/ﬂ ligatures normalized. Only these two words are repaired; any other use of the glyph fails the check.
- Terms: `term` is null. `term_label_pdf` comes from the degree map effective years as printed;
  `term_label_web` is "2026 Fall Term", taken from CLAUDE.md (no collected page prints it).
- Chair vs chairperson.aspx (web wins). The PDF block holds department-office contact data and prints no
  email. Name matches everywhere. Mismatches: CST office (PDF N-914, web N-1000) and phone (5170 vs 5038);
  DENT office (A-701 vs A-702) and phone (5070 vs 5907); EET office (V-733 vs V-734) and phone (5300 vs
  5305); MATH phone (5380 vs 5928; office N-711 matches).
- Legacy MST/DPT codes: no requirement list or degree map option names one. The only mention is the shorthand
  `PRE_CST2307_MST2307` in rule 014435 (CST Networking and Security, IT Operations and Cybersecurity maps),
  left as printed and flagged with the other shorthand.
- Course links: `programs` filled on 134 of 197 course records (170 program codes). Codes in a program that
  are not in the catalog data: none. 36 codes are in the catalog but outside the four departments, so they
  have no course record (ENG, BIO, PHYS, COM, ...); listed in `course_links.json`.
- Flags for the owner: (1) 57 `PRE_...` shorthand rule texts left as printed; (2) Cybersecurity BS has two
  different degree maps with the same name and the same 114-118 total, and the requirements say "Earn at least
  120-124": credit totals disagree; (3) MATH Applied Mathematics: map 117-119 vs "Earn at least 120"; (4) the
  MATH minor's title is printed incomplete ("Computer Science -"); (5) no degree map is repeated per track, so
  no "applies to tracks" note exists (CST Computer Systems has 4 distinct maps); (6) the Courses section is
  stripped (it duplicates the catalog data); (7) the stray EET program "Accelerator Science and Technology"
  is stripped.
- Credit totals for manual check: CIS AAS 60-63 / 63-66 / 63-65 (earn 60); Computer Systems BTECH 120-124 x3,
  120-123 (earn 120); Cybersecurity 114-118 (earn 120-124); Data Science 121-123 (earn 120-124); Dental
  Hygiene 66-67 (earn 66-67); EET AAS 67-69 (earn 67-69); EET BTECH 131-133 (earn 129-134); Applied
  Mathematics 117-119 (earn 120); Computer Science AS 59-65 (earn 60); Mathematics Education 119-121 (earn
  120); the CS minor prints no total.
- Not committed: the CST, EET and MATH PDFs (large); their tests are skipped when `data/pdfs` is missing. The
  DENT PDF and its 20 rule texts are fixtures (`tests/fixtures/pdfs/`).
