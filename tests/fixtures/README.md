# Fixtures

- `catalog_page.json`: 10 real courses from the catalog search API (saved 2026-10-11, after the crawl that added `requirementDesignation`). Only the
  nested `departments` objects were trimmed to `id`, `name`, `displayName`, `status`.
  Includes the cross-listed trio EET 3672 / CET 3672 / MECH 3672, a shorthand rule (CST 4900),
  a course with no rule (CST 1101), and a liberal-arts + writing-intensive course (MAT 2540), and non-pilot courses for the department filter.
- `catalog_rules.json`: the real rule lookup answers (`returnFields=code,catalogDisplayName,descriptionLong`)
  for the pilot-department courses in that page, merged into one `data` object. CET 3672 and
  MECH 3672 have no rule here because the crawl only looked up rules for kept courses.
- `rule_shorthand_full.json`: the full, unrestricted rule response for 014763 (CST 4900).
- `page.html`, `robots_disallow.txt`: small hand-written crawler fixtures.

## pages/

Real pages from the 2026-10-11 crawl with only `<script>` and `<style>` blocks and blank lines
removed (the header, mega-menu, alert banner, sidebar and footer are kept, so the tests prove they
are left out): `bursar_refund_policy`, `admissions_tuition_refund`, `math_faqs`, `cst_chairperson`
(spaces inside the mailto link), `math_chairperson`, `writing_intensive_empty` (empty main div) and
`advisement_six_steps` (email link text split by a `<br>`, correct href) and
`bursar_payment_plan` (malformed table markup: a row whose cells sit outside any `<tr>`).
`placeholders_only.html` is hand-written: no real page is placeholder-only today.
Added for the page review: `advisement_gen_ed` (login links, a `<ul>` directly inside a `<ul>`),
`advisement_required_core` (tab panes, header row drawn with `<strong>`), `registrar_course_scheduling`
(a link whose fragment contains `login`) and `financial_aid_sap` (contact panels nested inside one
another, hours panels without a heading element, a `<table>` directly inside an `<ol>`).

## calendar/

`winter_2027.pdf` is the real Winter 2027 academic calendar (one page, saved 2026-10-11, "Last
updated: 7/27/26"). The Fall and Spring PDFs are not committed (`data/pdfs/` is ignored); tests that
need them are skipped when the files are missing.

## pdfs/

The real refund calendar and the real Dropping and Withdrawing PDF (saved 2026-10-11). The flyer
(1 MB) and the CUNYfirst guide (1.4 MB) are not committed; tests that need them are skipped when
`data/pdfs/` is missing.
