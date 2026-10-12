# Independent check of the chain candidates (step 4b-1, 2026-10-12)

Output of `uv run python scripts/verify_chain_candidates.py` run on the raw saved catalog JSON (`data/raw/app.coursedog.com`), the rule cache and the contact chunks. Checks: a records equal raw; b codes in texts are in the chain, exclusions or no record, no extra chain courses; c gold sources; d no lost prerequisite field (q79, q81); e CST 4999 absent from the full raw list (q83); f ENG 1101 in the full list? (q84); g title uniqueness (q85); h contact lines equal the contact chunks (q82, q83, q84). `-` = not applicable. q87 is a single-record lookup (no chain tag), so b does not apply to it.

| id | a | b | c | d | e | f | g | h | notes |
|---|---|---|---|---|---|---|---|---|---|
| q76 | pass | pass | pass | - | - | - | - | - |  |
| q77 | pass | pass | pass | - | - | - | - | - |  |
| q78 | pass | pass | pass | - | - | - | - | - |  |
| q79 | pass | pass | pass | pass | - | - | - | - | d: fields checked for EET 3572: _id, alternativeCode, code, courseGroupId, courseNumber, credits, customFields, departmentOwnership, departments, description, effectiveEndDate, effectiveStartDate, globalCourseTitle, id, name, orderByKeyForCode, requirementDesignation, requirementGroup, status, subjectCode; requirementGroup = '' |
| q80 | pass | pass | pass | - | - | - | - | - |  |
| q81 | pass | pass | pass | pass | - | - | - | - | d: fields checked for CST 2304: _id, alternativeCode, code, courseGroupId, courseNumber, credits, customFields, departmentOwnership, departments, deprecatedCourseGroupId, description, effectiveEndDate, effectiveStartDate, globalCourseTitle, id, name, orderByKeyForCode, requirementGroup, status, subjectCode; requirementGroup = '' |
| q82 | pass | pass | pass | - | - | - | - | pass | h: contact:CST-NYT: compsystech@citytech.cuny.edu, 718-260-5170 |
| q83 | - | - | pass | - | pass | - | - | pass | e: 1445 distinct records (1444 distinct codes; codes with two records: ['AFR 2000']) in the saved raw pages (the search reported 1445 courses), statuses ['Active']; no inactive or legacy forms are saved; searched every field of every record and the raw files as text for CST 4999; h: contact:CST-NYT: compsystech@citytech.cuny.edu, 718-260-5170 |
| q84 | - | - | pass | - | - | pass | - | pass | f: ENG 1101 exists in the full raw list (English Composition I; departments ['ENGL-NYT']), outside the four departments; h: contact:registrar: registrar@citytech.cuny.edu, 718-260-5800 |
| q85 | pass | pass | pass | - | - | - | pass | - | g: 197 records in the four departments; exact title ['CST 3504']; other titles containing the phrase: none |
| q86 | pass | pass | pass | - | - | - | - | - |  |
| q87 | pass | - | pass | - | - | - | - | - | b: not a chain question (no chain tag); only the single record is checked |

12 candidates checked; failed: none
