# Step 4b results

CH (8): q22, q39, q40, q76, q77, q79, q81, q85; AB: q83; CTRL: 46 questions (q87 in it).

## M1 and M2

| run | M1 CH answered by the chain node | CH with intent prerequisite | M2 CTRL answered by the chain node | CTRL intent prerequisite but fell through |
|---|---|---|---|---|
| 4b-run1 | 8 of 8 (missed: []) | 8 | ['q21'] | ['q42'] |
| 4b-run2 | 8 of 8 (missed: []) | 8 | ['q21'] | ['q42'] |
| 4b-run3 | 8 of 8 (missed: []) | 8 | ['q21'] | ['q42'] |

## M3 chain coverage (CH questions with 2 or more gold catalog sources)

- 4b runs, all eligible CH questions: [0.8, 0.8, 0.8]
  - q39: NOT covered, NOT covered, NOT covered
  - q40: covered, covered, covered
  - q76: covered, covered, covered
  - q77: covered, covered, covered
  - q85: covered, covered, covered
- on the questions the router2 logs also contain (['q22', 'q39', 'q40']): 4b [0.5, 0.5, 0.5], router2 [0.0, 0.0, 0.0]

## M4 calendar-only dev questions under scoring v2

- correct per run: [13, 13, 13] of 13; wrong rows: [0, 0, 0]; new calendar misroutes beyond q09 q13 q30: [[], [], []]

## M5 judged questions on the 48 dev ids common to the router2 runs

| metric | router2 | 4b |
|---|---|---|
| correct share | 0.679 (0.654 to 0.692) | 0.744 (0.692 to 0.808) |
| faithfulness yes | 0.949 (0.923 to 0.962) | 0.974 (0.962 to 1.000) |
| abstention accuracy | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| wrongly abstained | 2.000 (2.000 to 2.000) | 2.000 (2.000 to 2.000) |
| citation rate | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| invalid citations | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) |

## M6 q83

- abstained: [True, True, True], route: ['abstain', 'abstain', 'abstain']

## Extras (no rule)

- calendar misroutes by classifier intent (all, including q09 q13 q30): [['q09', 'q13', 'q30'], ['q09', 'q13', 'q30'], ['q09', 'q13', 'q30']]
- 4b-run1 per route (n, p50 ms, p95 ms, mean answer-side cost per request): abstain: 2, 1821, 1821, $0.00006; calendar: 15, 1807, 2651, $0.00049; calendar_fallthrough: 1, 5333, 5333, $0.00122; chain: 9, 3273, 3893, $0.00032; chain_fallthrough: 1, 4102, 4102, $0.00087; other: 27, 3617, 5196, $0.00077
- 4b-run2 per route (n, p50 ms, p95 ms, mean answer-side cost per request): abstain: 2, 1483, 1483, $0.00006; calendar: 15, 1636, 2122, $0.00049; calendar_fallthrough: 1, 4291, 4291, $0.00121; chain: 9, 3255, 5124, $0.00033; chain_fallthrough: 1, 4102, 4102, $0.00087; other: 27, 3620, 5536, $0.00078
- 4b-run3 per route (n, p50 ms, p95 ms, mean answer-side cost per request): abstain: 2, 1603, 1603, $0.00006; calendar: 15, 1681, 3524, $0.00049; calendar_fallthrough: 1, 4564, 4564, $0.00121; chain: 9, 2762, 3479, $0.00032; chain_fallthrough: 1, 3723, 3723, $0.00086; other: 27, 3564, 5603, $0.00078
- classifier cost per request, router2: [3.1e-05, 3.1e-05, 3.1e-05]
- classifier cost per request, 4b: [4.1e-05, 4.1e-05, 4.1e-05]

## Every CH and AB question, per run

### q22: What do I need to take before Calculus III (MAT 2675)?
gold sources: ['catalog:MAT 2675']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:MAT 2675', 'catalog:MAT 1575', 'catalog:MAT 2580', 'catalog:MAT 1475', 'catalog:MAT 1375', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: - **Level 0 — MAT 2675 (Calculus III):** Its prerequisite text says, “Prerequisites of MAT 1575 AND MAT 2580.” [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:MAT 2675', 'catalog:MAT 1575', 'catalog:MAT 2580', 'catalog:MAT 1475', 'catalog:MAT 1375', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: ### Level 0
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:MAT 2675', 'catalog:MAT 1575', 'catalog:MAT 2580', 'catalog:MAT 1475', 'catalog:MAT 1375', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: - **MAT 2675 — Calculus III:** The catalog says, “Prerequisites of MAT 1575 AND MAT 2580.” [1]

### q39: What is the full prerequisite chain for CST 3602 Data Visualization?
gold sources: ['catalog:CST 3602', 'catalog:CST 3512', 'catalog:CST 2312', 'catalog:CST 1101', 'catalog:MAT 2572', 'catalog:MAT 1575', 'catalog:MAT 1475', 'catalog:MAT 1375', 'catalog:MAT 1275', 'catalog:MAT 1275CO']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3602', 'catalog:CST 3512', 'catalog:MAT 2572', 'catalog:CST 2312', 'catalog:MAT 1575', 'catalog:CST 1101', 'catalog:MAT 1475', 'catalog:MAT 1375']; verdict partial / yes; first line: - **Level 0 — CST 3602: Data Visualization:** “PRE: CST 3512 & MAT 2572” [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3602', 'catalog:CST 3512', 'catalog:MAT 2572', 'catalog:CST 2312', 'catalog:MAT 1575', 'catalog:CST 1101', 'catalog:MAT 1475', 'catalog:MAT 1375']; verdict partial / yes; first line: - **Level 0 — CST 3602, Data Visualization:** “PRE: CST 3512 & MAT 2572” [1]
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3602', 'catalog:CST 3512', 'catalog:MAT 2572', 'catalog:CST 2312', 'catalog:MAT 1575', 'catalog:CST 1101', 'catalog:MAT 1475', 'catalog:MAT 1375']; verdict partial / yes; first line: - **Level 0 — CST 3602 Data Visualization:** “PRE: CST 3512 & MAT 2572” [1]

### q40: Starting from CST 3613 (Application Development with Database), which courses do I have to take first, and what do those courses require?
gold sources: ['catalog:CST 3613', 'catalog:CST 1201', 'catalog:CST 1100', 'catalog:CST 1101', 'catalog:CST 1204']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3613', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict partial / yes; first line: - **Level 0 — CST 3613:** The catalog says: “PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER.” [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3613', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict partial / yes; first line: ### Level 0
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3613', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict partial / yes; first line: - **Level 0 — CST 3613:** The catalog says: “PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER.” [1]

### q76: What are all the courses I have to take before CST 2412, step by step?
gold sources: ['catalog:CST 2412', 'catalog:CST 2402', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:MAT 1375', 'catalog:CST 1100', 'catalog:CST 1101', 'catalog:MAT 1275', 'catalog:MAT 1275CO']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2412', 'catalog:CST 2402', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:MAT 1375', 'catalog:CST 1100', 'catalog:CST 1101', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: **Level 0**
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2412', 'catalog:CST 2402', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:MAT 1375', 'catalog:CST 1100', 'catalog:CST 1101', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: **Level 0**
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2412', 'catalog:CST 2402', 'catalog:CST 1201', 'catalog:CST 1204', 'catalog:MAT 1375', 'catalog:CST 1100', 'catalog:CST 1101', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: **Level 0**

### q77: What do I need to take before EET 2150?
gold sources: ['catalog:EET 2150', 'catalog:EET 1222', 'catalog:EET 1122', 'catalog:MAT 1375', 'catalog:EET 1102', 'catalog:MAT 1275', 'catalog:MAT 1275CO']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 2150', 'catalog:EET 1222', 'catalog:EET 1122', 'catalog:MAT 1375', 'catalog:EET 1102', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: **Level 0**
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 2150', 'catalog:EET 1222', 'catalog:EET 1122', 'catalog:MAT 1375', 'catalog:EET 1102', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: **Level 0**
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 2150', 'catalog:EET 1222', 'catalog:EET 1122', 'catalog:MAT 1375', 'catalog:EET 1102', 'catalog:MAT 1275', 'catalog:MAT 1275CO']; verdict correct / yes; first line: - **Level 0 — EET 2150:** The catalog lists: “PRE: EET 1222, PHYS 1433” [1]

### q79: What are the prerequisites for EET 3572?
gold sources: ['catalog:EET 3572']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 3572']; verdict correct / yes; first line: No prerequisite is listed for EET 3572 in the catalog. [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 3572']; verdict correct / yes; first line: EET 3572: No prerequisite is listed for it in the catalog. [1]
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:EET 3572']; verdict correct / yes; first line: EET 3572: No prerequisite is listed for it in the catalog. [1]

### q81: What are the prerequisites for CST 2304?
gold sources: ['catalog:CST 2304']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2304']; verdict correct / yes; first line: CST 2304 has no prerequisite listed in the catalog. [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2304']; verdict correct / yes; first line: CST 2304 has no prerequisite listed in the catalog. [1]
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 2304']; verdict correct / yes; first line: CST 2304 has no prerequisite listed in the catalog. [1]

### q85: What do I need to take before Database Design?
gold sources: ['catalog:CST 3504', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']
- 4b-run1: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3504', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict correct / yes; first line: - **Level 0 — CST 3504, Database Design:** The catalog says: “PRE: CST 1204 C OR HIGHER” [1]
- 4b-run2: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3504', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict correct / yes; first line: - **Level 0 — CST 3504, Database Design:** The catalog says: “PRE: CST 1204 C OR HIGHER” [1]
- 4b-run3: route chain, intent prerequisite, answered by chain True; sources received ['catalog:CST 3504', 'catalog:CST 1204', 'catalog:CST 1100', 'catalog:CST 1101']; verdict correct / yes; first line: - **Level 0 — CST 3504, Database Design:** The catalog says: “PRE: CST 1204 C OR HIGHER” [1]

### q83: What are the prerequisites for CST 4999?
gold sources: (none)
- 4b-run1: route abstain, intent prerequisite, answered by chain True; sources received []; verdict correct / None; first line: ABSTAIN: No record exists in the catalog data for CST 4999 in the four departments (CST, Math, EET, Dental Hygiene).
- 4b-run2: route abstain, intent prerequisite, answered by chain True; sources received []; verdict correct / None; first line: ABSTAIN: No record exists in the catalog data for CST 4999 in the four departments (CST, Math, EET, Dental Hygiene).
- 4b-run3: route abstain, intent prerequisite, answered by chain True; sources received []; verdict correct / None; first line: ABSTAIN: No record exists in the catalog data for CST 4999 in the four departments (CST, Math, EET, Dental Hygiene).

CTRL questions with classifier intent prerequisite: 4b-run1: ['q21', 'q42']; 4b-run2: ['q21', 'q42']; 4b-run3: ['q21', 'q42']

## Keep rule

| rule | pass |
|---|---|
| R1 | pass |
| R2 | pass |
| R3 | pass |
| R4 | pass |
| R5 | pass |
| R6 | pass |

**Verdict by the pre-registered rule: KEEP**


## Measurement note (disclosed)

The first run of this report counted q83 as a calendar misroute: `chain_report` reused a helper that treats the route name `abstain` as a calendar route, but `abstain` is also the route of the chain node's no-record abstain. q83's classifier intent was `prerequisite` in all three runs and the calendar node never saw it, so it is not a "question sent to the calendar node". That first computation therefore showed R4 as FAIL and the verdict as REJECT. I corrected the helper to use the classifier's intent (as the plan defines the misroute) after seeing the numbers, and the output above is the corrected one: R4 passes and the verdict is KEEP. Because this correction was made after seeing results, the router default was **not** switched; that decision is left to the owner (see `docs/experiments.md`).

## Also noted

- **q39** is not covered in any run, as predicted in the plan: its gold has MAT 1275 and MAT 1275CO at level 5, beyond the depth limit of 4. The walk truncated there and the chain answer says so; the judge graded q39 partial in all three runs.
- **q40** is graded partial in all three runs although every gold source was received; the gold is long and the chain answer lists the courses level by level (the judge's reasons are in the results files).
- **q21** (EET 3672, an untagged prerequisite question) was answered by the chain node in all three runs: the one id R1 allows. **q42** (two codes) fell through to retrieve in all three runs.
- Interpretation fixed in the plan: M1 and M2 count questions answered by the chain node; the classifier-intent counts are printed beside them (q42 is the only CTRL question with intent prerequisite that fell through).
- Cost of the three runs: $0.6092 of the $2.00 allowance (the estimate was about $0.63).
