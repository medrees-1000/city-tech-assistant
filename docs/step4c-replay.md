| id | run | path | office | line appended |
|---|---|---|---|---|
| q15 | 4b-run1 | model | EET-NYT | Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300. |
| q15 | 4b-run2 | model | EET-NYT | Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300. |
| q15 | 4b-run3 | model | EET-NYT | Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300. |
| q27 | 4b-run1 | below_threshold | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q27 | 4b-run2 | below_threshold | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q27 | 4b-run3 | below_threshold | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q28 | 4b-run1 | model | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q28 | 4b-run2 | model | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q28 | 4b-run3 | model | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q34 | 4b-run1 | calendar_no_row | registrar | (already present, unchanged) |
| q34 | 4b-run2 | calendar_no_row | registrar | (already present, unchanged) |
| q34 | 4b-run3 | calendar_no_row | registrar | (already present, unchanged) |
| q44 | 4b-run1 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q44 | 4b-run2 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q44 | 4b-run3 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q45 | 4b-run1 | below_threshold | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q45 | 4b-run2 | below_threshold | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q45 | 4b-run3 | below_threshold | MATH-NYT | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q47 | 4b-run1 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q47 | 4b-run2 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q47 | 4b-run3 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run1 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run2 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | 4b-run3 | below_threshold | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q83 | 4b-run1 | chain_no_record | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q83 | 4b-run2 | chain_no_record | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q83 | 4b-run3 | chain_no_record | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |

| rule | verdict | detail |
|---|---|---|
| D1 | PASS | 27 abstentions end with exactly one table line |
| D2 | PASS | office = approved table; id differences [] |
| D3 | PASS | 138 non-abstaining answers byte-identical |
| D4 | PASS | text before the contact line unchanged |
| D5 | PASS | no email or phone outside the table or the original |
| D6 | PASS | validator PASS and a fax-only number is refused |
| D7 | PASS | idempotent; q34 byte-identical |
| D8 | PASS | ruff and pytest pass |
