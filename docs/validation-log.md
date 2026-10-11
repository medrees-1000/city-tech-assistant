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
- 8 Active records in CST-NYT have legacy prefixes: DPT 2309, MST 1101, MST 1204, MST 1205,
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
