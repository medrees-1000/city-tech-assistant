# Selector v2 results (step 4a-2 part 2)

Calendar-only dev questions (13): q12, q31, q33, q36, q37, q61, q63, q64, q65, q67, q68, q71, q75

## (a) and (b): calendar-only questions per run

| run | correct | partial | incorrect | wrong dates stated | labels |
|---|---|---|---|---|---|
| router2-run1 | 12 | 1 | 0 | 0 | {'calendar missed': 1} |
| router2-run2 | 12 | 1 | 0 | 0 | {'calendar missed': 1} |
| router2-run3 | 13 | 0 | 0 | 0 | {} |
| before-new8 (current system, 8 new) | 0 | 0 | 8 | 0 | {'calendar missed': 8} |

Mean correct 12.33 of 13; lowest run 12. Rule (a): PASS. Rule (b) no wrong date stated: PASS.

- scored under v1: correct [12, 12, 13], partial [1, 1, 0], wrong rows stated [0, 0, 0]
- scored under v2 (decides the rule): correct [12, 12, 13], partial [1, 1, 0], wrong rows stated [0, 0, 0]
- acceptable extras in the gold: {'q33': ['spring-2027-006'], 'q63': ['winter-2027-005']}
- selector input and latency, 4a (selector v1): median prompt tokens [1649, 1649, 1649], median latency ms [969, 803, 929], p95 [1153, 1755, 1138]
- selector input and latency, this experiment: median prompt tokens [4412, 4412, 4412], median latency ms [1103, 937, 1036], p95 [1801, 1332, 1526]

| id | gold rows | router2-run1 | router2-run2 | router2-run3 |
|---|---|---|---|---|
| q12 | ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] |
| q31 | ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] |
| q33 | ['spring-2027-007'] | correct [calendar] ['spring-2027-007'] | correct [calendar] ['spring-2027-007'] | correct [calendar] ['spring-2027-007'] |
| q36 | ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] |
| q37 | ['fall-2026-039', 'fall-2026-038'] | correct [calendar] ['fall-2026-038', 'fall-2026-039'] | correct [calendar] ['fall-2026-038', 'fall-2026-039'] | correct [calendar] ['fall-2026-038', 'fall-2026-039'] |
| q61 | ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] |
| q63 | ['winter-2027-004'] | correct [calendar] ['winter-2027-004'] | correct [calendar] ['winter-2027-004'] | correct [calendar] ['winter-2027-004'] |
| q64 | ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] |
| q65 | ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] |
| q67 | ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] |
| q68 | ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] |
| q71 | ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] |
| q75 | ['fall-2026-046', 'fall-2026-045', 'fall-2026-047'] | partial [calendar] ['fall-2026-046'] | partial [calendar] ['fall-2026-046'] | correct [calendar] ['fall-2026-045', 'fall-2026-046', 'fall-2026-047'] |

## Routes, misroutes, classifier accuracy, fall-through

- router2-run1: routes {'calendar': 15, 'other': 31, 'calendar_fallthrough': 1, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13']
- router2-run2: routes {'calendar': 15, 'other': 31, 'calendar_fallthrough': 1, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13']
- router2-run3: routes {'calendar': 15, 'other': 31, 'calendar_fallthrough': 1, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13']

## (c): the 40 common questions, router runs against the stored 3b arm-ON runs (on-run1, on-run2, on-run3)

- PASS  a: correct share: -0.013 (limit -0.038)
- PASS  b: faithfulness yes share: +0.026 (must not fall)
- PASS  c: abstention: accuracy +0.000, wrongly abstained -1.00 per run
- PASS  d: citation validity: citation rate +0.000, invalid citations +0.00 per run

| metric | before (3b ON) | router |
|---|---|---|
| correct share | 0.692 (0.654 to 0.731) | 0.679 (0.654 to 0.692) |
| faithfulness yes | 0.923 (0.885 to 0.962) | 0.949 (0.923 to 0.962) |
| abstention accuracy | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| wrongly abstained | 3.000 (3.000 to 3.000) | 2.000 (2.000 to 2.000) |
| citation rate | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| invalid citations | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) |

Questions whose verdict changed or is unstable (judged questions):
- q01 correctness ['correct', 'partial', 'partial'] -> ['partial', 'partial', 'partial']: unstable; faithfulness ['yes', 'yes', 'partly'] -> ['no', 'no', 'yes']: unstable (leaning worse)
- q06 correctness ['partial', 'correct', 'partial'] -> ['correct', 'correct', 'correct']: unstable (leaning better); faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same
- q15 correctness ['incorrect', 'incorrect', 'incorrect'] -> ['incorrect', 'incorrect', 'incorrect']: same; faithfulness ['no', 'no', 'no'] -> ['yes', 'yes', 'yes']: real better
- q18 correctness ['correct', 'partial', 'correct'] -> ['correct', 'partial', 'correct']: unstable; faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same
- q22 correctness ['partial', 'partial', 'partial'] -> ['partial', 'partial', 'partial']: same; faithfulness ['yes', 'no', 'no'] -> ['yes', 'yes', 'no']: unstable
- q40 correctness ['partial', 'partial', 'partial'] -> ['partial', 'partial', 'partial']: same; faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'no']: unstable
- q54 correctness ['correct', 'partial', 'correct'] -> ['partial', 'partial', 'partial']: unstable (leaning worse); faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same

## (d): abstain questions for unsupported terms and sections

- q27: abstained [other], abstained [other], abstained [other]
- q28: abstained [other], abstained [other], abstained [other]
- q34: abstained [abstain], abstained [abstain], abstained [abstain]

Rule (d): PASS.

## Latency per route, median / p95 ms

- router2-run1 calendar (n=15): classify 1078 / 1811, select 1103 / 1801, render 0 / 0, total 2136 / 2975
- router2-run1 other (n=31): classify 977 / 1917, total 4063 / 5826
- router2-run1 calendar_fallthrough (n=1): classify 1245 / 1245, select 1385 / 1385, total 5276 / 5276
- router2-run1 abstain (n=1): classify 1098 / 1098, select 989 / 989, total 2091 / 2091
- router2-run2 calendar (n=15): classify 977 / 1583, select 1002 / 1332, render 0 / 1, total 1947 / 2717
- router2-run2 other (n=31): classify 948 / 1382, total 3817 / 5526
- router2-run2 calendar_fallthrough (n=1): classify 884 / 884, select 801 / 801, total 4323 / 4323
- router2-run2 abstain (n=1): classify 1018 / 1018, select 793 / 793, total 1816 / 1816
- router2-run3 calendar (n=15): classify 960 / 1688, select 1049 / 1526, render 0 / 0, total 2011 / 2622
- router2-run3 other (n=31): classify 939 / 1466, total 3907 / 5264
- router2-run3 calendar_fallthrough (n=1): classify 1055 / 1055, select 832 / 832, total 4439 / 4439
- router2-run3 abstain (n=1): classify 839 / 839, select 849 / 849, total 1692 / 1692

## Cost per request (USD)

| run | classify | select | rerank | answer | judge | total run |
|---|---|---|---|---|---|---|
| router2-run1 | 0.00003 | 0.00015 | 0.00035 | 0.00013 | 0.00288 | 0.1700 |
| router2-run2 | 0.00003 | 0.00015 | 0.00035 | 0.00013 | 0.00292 | 0.1722 |
| router2-run3 | 0.00003 | 0.00015 | 0.00035 | 0.00013 | 0.00292 | 0.1724 |

## Verdict by the pre-registered rule: (a) True, (b) True, (c) True, (d) True => KEEP router on


## Example calendar answers in full (stored in `request_logs`; the Registrar contact would show as [EMAIL], [PHONE] in the log)

**q37 "When can I register for classes next spring?"** (run 1; rows come from the Fall 2026 calendar although the question resolved to Spring 2027; each row names its own calendar)

```
- Thursday, October 29, 2026: Early online registration for Spring 2027 begins for ASAP, BMI, CSTEP, Honors, SEEK, Seniors & Veteran student populations. Registration by appointment only. [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change) (applies to: ASAP, BMI, CSTEP, Honors, SEEK, Seniors & Veteran student populations)
- Monday, November 2, 2026: Online registration for Spring 2027 begins for all students. [2] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change) (applies to: all students)
```

**q75 "What days are off for Thanksgiving break?"** (run 3, all three rows; runs 1 and 2 returned only the Thanksgiving row, scored partial)

```
Assuming the current term, Fall 2026.
- Wednesday, November 25, 2026: No classes scheduled [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
- November 26-27, 2026 (Thursday-Friday): Thanksgiving Holiday. College Closed [2] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
- Saturday, November 28, 2026: No classes scheduled [3] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
```

**q61 "What is the last day to add a course in Fall 2026?"**

```
Thursday, September 3, 2026: Last day to add a course. [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
```

## Other things the runs showed

- **The q37 pattern is fixed:** all three runs returned `fall-2026-038` and `-039` (registration for Spring 2027, which sit in the Fall 2026 calendar), correct under both scoring versions. In 4a the Spring-only pool led to a wrong Plan Week row or a fall-through.
- **q75 is the one calendar-only question that varies:** runs 1 and 2 returned only `fall-2026-046` (partial), run 3 all three rows. By the fixed rule that is partial, not wrong.
- **q33 and q63** are correct in every run: the selector returned exactly the required row (the acceptable extras were not needed). The refined gold made v1 and v2 give the same numbers here.
- **Fall-through:** only q13, in all 3 runs (answered correctly by retrieval); q37 no longer falls through. q14 was classified `other`. Misroutes and classifier accuracy as in 4a: 45/48 and q09, q13, q30 sent to the calendar node, none sent away.
- **Selector input and latency:** median prompt 4,412 tokens (4a: 1,649), median selector latency about 0.9 to 1.1 s (4a: 0.8 to 1.0 s); calendar-route total median 1.9 to 2.1 s (4a: 1.8 to 1.9 s). Selector cost $0.00015 per request averaged over all requests (4a: $0.00005); total per request about $0.0036 with the judge.
- **A limit of the stability rule, seen here:** q15 shows a "real better" faithfulness change (no to yes in all three runs against all three 3b runs) although its route (`other`) and its retrieval are identical to the 3b arm; the classifier call does not touch the answer path. It is judge/answer noise that happened to be stable in both arms, not an effect of the router.
- **Old pipeline on the 8 new questions (`before-new8`):** 0 of 8 (it abstains on all of them).
- **Spend:** about $0.51 of the $2.00 allowance.
