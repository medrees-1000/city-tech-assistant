| id | run | old office and rule (v1) | new result (v2) |
|---|---|---|---|
| q15 | 4b-run1 | EET-NYT (department) | same line (EET-NYT) |
| q15 | 4b-run2 | EET-NYT (department) | same line (EET-NYT) |
| q15 | 4b-run3 | EET-NYT (department) | same line (EET-NYT) |
| q27 | 4b-run1 | CST-NYT (department) | same line (CST-NYT) |
| q27 | 4b-run2 | CST-NYT (department) | same line (CST-NYT) |
| q27 | 4b-run3 | CST-NYT (department) | same line (CST-NYT) |
| q28 | 4b-run1 | MATH-NYT (department) | same line (MATH-NYT) |
| q28 | 4b-run2 | MATH-NYT (department) | same line (MATH-NYT) |
| q28 | 4b-run3 | MATH-NYT (department) | same line (MATH-NYT) |
| q34 | 4b-run1 | registrar (calendar) | same line (registrar) |
| q34 | 4b-run2 | registrar (calendar) | same line (registrar) |
| q34 | 4b-run3 | registrar (calendar) | same line (registrar) |
| q44 | 4b-run1 | registrar (account cue) | same line (registrar) |
| q44 | 4b-run2 | registrar (account cue) | same line (registrar) |
| q44 | 4b-run3 | registrar (account cue) | same line (registrar) |
| q45 | 4b-run1 | MATH-NYT (department) | same line (MATH-NYT) |
| q45 | 4b-run2 | MATH-NYT (department) | same line (MATH-NYT) |
| q45 | 4b-run3 | MATH-NYT (department) | same line (MATH-NYT) |
| q47 | 4b-run1 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q47 | 4b-run2 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q47 | 4b-run3 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run1 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run2 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run3 | registrar (chunk map) | **line removed**; old line: Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q83 | 4b-run1 | CST-NYT (chain (department prefix)) | same line (CST-NYT) |
| q83 | 4b-run2 | CST-NYT (chain (department prefix)) | same line (CST-NYT) |
| q83 | 4b-run3 | CST-NYT (chain (department prefix)) | same line (CST-NYT) |

| rule | verdict | detail |
|---|---|---|
| V1 | PASS | 21 abstentions from the rules that stay keep the identical line |
| V2 | PASS | lost the line: ['q47', 'q49'] (predicted ['q47', 'q49']), the same in each of the three runs |
| V3 | PASS | 138 non-abstaining answers byte-identical; no double lines; idempotent |
| V4 | PASS | contacts validator passes |
| V5 | PASS | ruff and pytest pass |
