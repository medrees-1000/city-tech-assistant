# Fixtures

- `catalog_page.json`: 8 real courses from the catalog search API (saved 2026-10-11). Only the
  nested `departments` objects were trimmed to `id`, `name`, `displayName`, `status`.
  Includes the cross-listed trio EET 3672 / CET 3672 / MECH 3672, a shorthand rule (CST 4900),
  a course with no rule (CST 1101), and non-pilot courses for the department filter.
- `catalog_rules.json`: the real rule lookup answers (`returnFields=code,catalogDisplayName,descriptionLong`)
  for the pilot-department courses in that page, merged into one `data` object. CET 3672 and
  MECH 3672 have no rule here because the crawl only looked up rules for kept courses.
- `rule_shorthand_full.json`: the full, unrestricted rule response for 014763 (CST 4900).
- `page.html`, `robots_disallow.txt`: small hand-written crawler fixtures.
