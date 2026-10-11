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
