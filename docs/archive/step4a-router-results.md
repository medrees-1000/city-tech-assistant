# Router results (step 4a)

Calendar-only dev questions (13): q12, q31, q33, q36, q37, q61, q63, q64, q65, q67, q68, q71, q75

## (a) and (b): calendar-only questions per run

| run | correct | partial | incorrect | wrong dates stated | labels |
|---|---|---|---|---|---|
| router-run1 | 10 | 1 | 2 | 2 | {'calendar missed': 1, 'calendar wrong row': 2} |
| router-run2 | 10 | 1 | 2 | 1 | {'calendar missed': 2, 'calendar wrong row': 1} |
| router-run3 | 10 | 1 | 2 | 1 | {'calendar missed': 2, 'calendar wrong row': 1} |
| before-new8 (current system, 8 new) | 0 | 0 | 8 | 0 | {'calendar missed': 8} |

Mean correct 10.00 of 13; lowest run 10. Rule (a): FAIL. Rule (b) no wrong date stated: FAIL.

| id | gold rows | router-run1 | router-run2 | router-run3 |
|---|---|---|---|---|
| q12 | ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] | correct [calendar] ['winter-2027-023'] |
| q31 | ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] |
| q33 | ['spring-2027-007', 'spring-2027-006'] | partial [calendar] ['spring-2027-007'] | partial [calendar] ['spring-2027-007'] | partial [calendar] ['spring-2027-007'] |
| q36 | ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] | correct [calendar] ['fall-2026-049'] |
| q37 | ['fall-2026-039', 'fall-2026-038'] | incorrect [calendar] ['spring-2027-033'] | incorrect [calendar_fallthrough] [] | incorrect [calendar_fallthrough] [] |
| q61 | ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] | correct [calendar] ['fall-2026-007'] |
| q63 | ['winter-2027-004'] | incorrect [calendar] ['winter-2027-004', 'winter-2027-005'] | incorrect [calendar] ['winter-2027-004', 'winter-2027-005'] | incorrect [calendar] ['winter-2027-004', 'winter-2027-005'] |
| q64 | ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] | correct [calendar] ['winter-2027-001'] |
| q65 | ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] | correct [calendar] ['spring-2027-017'] |
| q67 | ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] | correct [calendar] ['spring-2027-050'] |
| q68 | ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] | correct [calendar] ['fall-2026-035'] |
| q71 | ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] | correct [calendar] ['fall-2026-040'] |
| q75 | ['fall-2026-046', 'fall-2026-045', 'fall-2026-047'] | correct [calendar] ['fall-2026-045', 'fall-2026-046', 'fall-2026-047'] | correct [calendar] ['fall-2026-045', 'fall-2026-046', 'fall-2026-047'] | correct [calendar] ['fall-2026-045', 'fall-2026-046', 'fall-2026-047'] |

## Routes, misroutes, classifier accuracy, fall-through

- router-run1: routes {'calendar': 15, 'other': 31, 'calendar_fallthrough': 1, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13']
- router-run2: routes {'calendar': 14, 'other': 31, 'calendar_fallthrough': 2, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13', 'q37']
- router-run3: routes {'calendar': 14, 'other': 31, 'calendar_fallthrough': 2, 'abstain': 1}; classifier accuracy 45/48; other sent to calendar ['q09', 'q13', 'q30']; calendar sent away []; fell through ['q13', 'q37']

## (c): the 40 common questions, router runs against the stored 3b arm-ON runs (on-run1, on-run2, on-run3)

- PASS  a: correct share: -0.026 (limit -0.038)
- PASS  b: faithfulness yes share: +0.026 (must not fall)
- PASS  c: abstention: accuracy +0.000, wrongly abstained -1.00 per run
- PASS  d: citation validity: citation rate +0.000, invalid citations +0.00 per run

| metric | before (3b ON) | router |
|---|---|---|
| correct share | 0.692 (0.654 to 0.731) | 0.667 (0.654 to 0.692) |
| faithfulness yes | 0.923 (0.885 to 0.962) | 0.949 (0.923 to 0.962) |
| abstention accuracy | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| wrongly abstained | 3.000 (3.000 to 3.000) | 2.000 (2.000 to 2.000) |
| citation rate | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| invalid citations | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) |

Questions whose verdict changed or is unstable (judged questions):
- q01 correctness ['correct', 'partial', 'partial'] -> ['partial', 'partial', 'partial']: unstable; faithfulness ['yes', 'yes', 'partly'] -> ['no', 'yes', 'yes']: unstable
- q06 correctness ['partial', 'correct', 'partial'] -> ['correct', 'correct', 'correct']: unstable (leaning better); faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same
- q15 correctness ['incorrect', 'incorrect', 'incorrect'] -> ['incorrect', 'incorrect', 'incorrect']: same; faithfulness ['no', 'no', 'no'] -> ['no', 'yes', 'yes']: unstable (leaning better)
- q18 correctness ['correct', 'partial', 'correct'] -> ['partial', 'partial', 'correct']: unstable; faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same
- q22 correctness ['partial', 'partial', 'partial'] -> ['partial', 'partial', 'partial']: same; faithfulness ['yes', 'no', 'no'] -> ['yes', 'no', 'no']: unstable
- q54 correctness ['correct', 'partial', 'correct'] -> ['partial', 'partial', 'partial']: unstable (leaning worse); faithfulness ['yes', 'yes', 'yes'] -> ['yes', 'yes', 'yes']: same

## (d): abstain questions for unsupported terms and sections

- q27: abstained [other], abstained [other], abstained [other]
- q28: abstained [other], abstained [other], abstained [other]
- q34: abstained [abstain], abstained [abstain], abstained [abstain]

Rule (d): PASS.

## Latency per route, median / p95 ms

- router-run1 calendar (n=15): classify 909 / 1298, select 969 / 1153, render 0 / 0, total 1894 / 2458
- router-run1 other (n=31): classify 867 / 1223, total 3824 / 6684
- router-run1 calendar_fallthrough (n=1): classify 930 / 930, select 1005 / 1005, total 5620 / 5620
- router-run1 abstain (n=1): classify 1202 / 1202, select 909 / 909, total 2115 / 2115
- router-run2 calendar (n=14): classify 861 / 2062, select 856 / 1755, render 0 / 0, total 1784 / 2748
- router-run2 other (n=31): classify 842 / 1264, total 4010 / 5843
- router-run2 calendar_fallthrough (n=2): classify 1011 / 1011, select 1044 / 1044, total 5031 / 5031
- router-run2 abstain (n=1): classify 1193 / 1193, select 765 / 765, total 1964 / 1964
- router-run3 calendar (n=14): classify 892 / 1094, select 957 / 1138, render 0 / 0, total 1911 / 2236
- router-run3 other (n=31): classify 864 / 1358, total 3963 / 5879
- router-run3 calendar_fallthrough (n=2): classify 840 / 840, select 789 / 789, total 4899 / 4899
- router-run3 abstain (n=1): classify 833 / 833, select 929 / 929, total 1767 / 1767

## Cost per request (USD)

| run | classify | select | rerank | answer | judge | total run |
|---|---|---|---|---|---|---|
| router-run1 | 0.00003 | 0.00005 | 0.00035 | 0.00013 | 0.00294 | 0.1683 |
| router-run2 | 0.00003 | 0.00005 | 0.00036 | 0.00013 | 0.00287 | 0.1657 |
| router-run3 | 0.00003 | 0.00005 | 0.00036 | 0.00013 | 0.00286 | 0.1648 |

## Verdict by the pre-registered rule: (a) False, (b) False, (c) True, (d) True => REJECT: the default stays off


## Example calendar answers in full (stored in `request_logs` for `router-run1`; the Registrar contact is shown as [EMAIL], [PHONE] there because the log is redacted)

**q75 "What days are off for Thanksgiving break?"** (three rows, term assumed)

```
Assuming the current term, Fall 2026.
- Wednesday, November 25, 2026: No classes scheduled [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
- November 26-27, 2026 (Thursday-Friday): Thanksgiving Holiday. College Closed [2] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
- Saturday, November 28, 2026: No classes scheduled [3] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)
```

**q67 "When are final exams in Spring 2027?"** (a range)

```
May 21-27, 2027 (Friday-Thursday): Final Examinations [1] (Spring 2027 calendar, spring_2027.pdf, last updated 2026-07-27; the calendar can change)
```

**q63 "When does the Winter 2027 session start?"** (scored incorrect only because the gold names one of two rows with the same date)

```
- Monday, January 4, 2027: Start of Winter 2027 session. [1] (Winter 2027 calendar, winter_2027.pdf, last updated 2026-07-27; the calendar can change)
- Monday, January 4, 2027: Classes begin [2] (Winter 2027 calendar, winter_2027.pdf, last updated 2026-07-27; the calendar can change)
```

## Other things the runs showed

- **q37 "When can I register for classes next spring?"** is the one real wrong date: run 1 stated Plan Week of Spring 2027 (`spring-2027-033`, March 8-12, 2027) because "next spring" resolved to the Spring 2027 calendar, but the registration rows for Spring 2027 sit in the **Fall 2026** calendar (gold `fall-2026-038/-039`). Runs 2 and 3 selected nothing and fell through to retrieval. The design cannot see rows of another term.
- **q63 and q33** are gold-granularity cases: q63's gold is `winter-2027-004` only, the router also returned `winter-2027-005` ("Classes begin", the same date); q33's gold has both `spring-2027-006` and `-007`, the router returned only `-007` (partial in all 3 runs). The scoring rule is fixed (an id outside the gold set counts as a wrong date stated), so q63 counts against rule (b) although the date it states, January 4, 2027, is the same.
- **Fall-through (expected q13 and q14):** q13 fell through in all 3 runs (and was answered correctly by retrieval in all 3); q14 was classified `other` and never reached the calendar node (correct). q37 fell through in runs 2 and 3.
- **q30** ("Should I drop my class before September 3?", NO ADVICE gold) was sent to the calendar node and answered with the three drop rows and no advice, judged correct. **q09** (SAP appeal deadline, a normal question with a calendar row) went to the calendar route and was correct in all 3 runs.
- **Old pipeline on the 8 new questions (`before-new8`):** abstained on all 8, so it scores 0 of 8 under the exact rule (it also states no dates).
- **Spend:** about $0.50 of the $2.00 allowance (three runs about $0.165 each, `before-new8` $0.005).
