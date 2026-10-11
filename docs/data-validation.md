# Data validation

Nothing is chunked, embedded or indexed until these checks pass. Automatic checks run in code and
fail the build. Manual checks are done by the owner and recorded at the bottom.

## Automatic checks

Run them all with `uv run python -m cta.validate` (one pass/fail table per area: courses, pages,
PDFs, departments, calendar). A missing input is SKIPPED, never a pass.

### Courses (catalog API)
- Total from the API equals the number of records downloaded (1,445 before the department filter).
- After filtering, every course has: code, title, description, credits, department, status = Active.
- No course keeps a raw 6-digit rule ID as its prerequisite text; every rule ID resolves to text.
- Course codes mentioned inside prerequisite text exist in the catalog or are flagged for review.
- No duplicate codes within a department. Cross-listed courses (same description, different code)
  are kept separate.
- Count per department is stored and compared with the previous crawl; a change of more than a few
  courses is flagged.

### PDFs
- Every PDF has a term (or award year) and a "last updated" or file-generation date in its metadata.
- No replacement characters (`�`), no `{{...}}` placeholders, no repeated rule-dump blocks, no
  "Advisory Commission" or blank-page text left in the cleaned output.
- Each department PDF yields at least: overview, one program, requirements and one degree map.
- Department tables: no empty header, no column that is "-" or "No" in every row, no rule ID at the
  start of a rule notes cell (IDs are in `rule_ids` on the section), no semester heading ending in
  two bare numbers, and no two degree maps with the same label.
- "(Inactive)" courses do not appear in cleaned output. Legacy MST/DPT courses are flagged
  (`legacy_prefix`), not dropped.

### Web pages
- Every crawled page returns 200 and has non-empty main content after the mega-menu is stripped.
- No page is only template placeholders (those are logged as "not collected").
- Content hash is stored for every page, and the fetch log has no gaps.

- Redirects (e.g. `advisement/planner.aspx`) end at a 200 page on the same host.
- Refund pages show which terms they cover; no refund answer is given for a term the page does not list.
- Department chair name, office, phone and email are compared between the department PDF and
  `chairperson.aspx` (the web page wins). The PDF "Chair" block is the department office contact:
  it is compared with the root page contact block, stored `embed: false` and never indexed.
  No stray spaces inside emails.

### Metadata (before indexing)
- Every section with embed true carries `source_url` or `source_file`, `doc_type` (one of the allowed
  list in `config/sources.yaml`), `department` (null allowed for central offices and CUNY-wide
  documents), `scope`, `term` (null allowed where none is printed), `fetched_at` or a file date, and
  `last_updated` (null allowed). A missing key fails; a null where null is not allowed fails.
- Every page record has a `doc_type` from the `page_doc_types` rules; a page no rule covers is
  flagged. `docs/section-index.md` shows the null count per field and doc_type.

- Term tags: every section has `terms`, a list; each entry is a season name plus a year ("Fall 2026",
  "Summer I 2026"); a section whose heading path or table title names a term has it in `terms`; a term
  in no heading is allowed only with a stated source (the refund calendar rule, docs/decisions.md);
  `term` is the entry when there is exactly one, else null. Refund pages store `covered_terms`.

### Calendar
- Every row has event, date (or explicit TBA), term, source PDF and last-updated date.
- Dates fall inside the term's expected range, and the weekday matches the date for the right year.
- Terms with no calendar (Summer 2027, Fall 2027) produce no rows and cause an abstain.

## Manual checks (owner)

1. **Calendar:** check every row of every term against its PDF, then set `verified: true`.
2. **Courses:** pick 20 random courses and compare code, title, credits and prerequisite text with
   the live catalog page. At least 3 per department, plus 2 cross-listed courses.
3. **Pages:** open 10 random cleaned web pages and confirm no menu junk and no missing sections.
4. **Programs:** for each department, compare the credit total and required course list with the
   live catalog program page.
5. **Contacts:** confirm each office's phone/email in the data against the live page.

## Recording results

Save each run in `docs/validation-log.md` with the date, the counts, the checks that failed and
what was fixed. The README reports the final counts.