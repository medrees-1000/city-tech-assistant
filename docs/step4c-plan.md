# Step 4c plan: the relevant office's contact on every abstention

Written 2026-10-13. Investigation only: no code, no config change, no paid call, test split not opened (only dev ids appear below; dev facts come from the stored runs `4b-run1..3`, the current default system, and from older dev runs where stated). Nothing here is pre-registered until the owner approves it; after approval this file is committed before any code.

CLAUDE.md requires: "Abstain, with the relevant office's contact". Today only the calendar abstains do it.

## 1. Every path that can say "I don't know"

"Dev hits" = dev questions that took the path in `4b-run1..3` (identical in all three runs unless said). A final column says whether a contact is attached today.

| # | Path | File and function | Exact message today | Dev hits | Contact today |
|---|---|---|---|---|---|
| A | Retrieval threshold (best vector cosine < 0.59, no chat call) | `src/cta/answer.py:26` `THRESHOLD_ABSTAIN`, set in `answer()` line 170-171, reason `below_threshold` | `ABSTAIN: I could not find this in the City Tech sources I have.` | q27, q44, q45, q47, q49 | none |
| B | The model writes the refusal (prompt rule 5, first line starts `ABSTAIN:`) | `INSTRUCTIONS` rule 5 in `answer.py:42`; `parse_reply` sets `abstained`; reason = the model's sentence | varies per run, e.g. `ABSTAIN: The sources do not list the Electrical Engineering Technology department's student hours.` (q15), `ABSTAIN: The sources do not identify who is teaching MAT 1475 this semester.` (q28). Rule 5 says to name an office "only if they appear in the sources"; neither answer names one | q15, q28 | none |
| C | Calendar: unsupported term, no row mentions it | `graph/build.py:93-101` (`calendar_unsupported_term`) | `ABSTAIN: There is no published calendar for <label>, and no calendar row mentions it. Contact the Registrar: <email>, <phone>.` | none on dev (its case is in the test split by design; not run) | Registrar (`render.abstain_text`) |
| D | Calendar: selector returned nothing for an unsupported term, or failed, or all ids were outside the pool | `build.py:118-124` (`calendar_no_row`, `calendar_selector_failed`) | `ABSTAIN: I could not find that in the <label> calendar. Contact the Registrar: ...` | q34 (Summer 2027, `calendar_no_row`) | Registrar |
| E | Calendar: TBA row (null date). Not an abstention flag, an answer "not announced yet" | `render.py:79-84` | `<event>: not announced yet ... Contact the Registrar: ...` | none on dev (q70 was dropped; q11 is test) | Registrar |
| F | Chain: the code has no record in the four departments | `graph/chain.py:337` `no_record_text`, used in `build.py:149-153` (`chain_no_record`) | `ABSTAIN: No record exists in the catalog data for <code> in the four departments (CST, Math, EET, Dental Hygiene).` | q83 (CST 4999) | none |
| G | Fall-throughs (not abstentions): calendar valid empty selection, chain cannot name one course, classifier failure | `build.py:119`, `:144`, `classify.py` | they go to retrieve, so they end in A, B or an answer | q13 (calendar_fallthrough, answered), q42 (chain_fallthrough, answered) | n/a |
| H | A refusal in prose that does not start with `ABSTAIN:` (partial answers, "the sources do not state X" inside an answer) | no code: `parse_reply` only tests the first characters | n/a | none among the dev abstain-like phrases I scanned in the 4b runs (the only phrase hit, q42, is a comparison, not a refusal). Older runs had it (q16 "the sources do not state the grade after Sept 17", `docs/decisions.md`) | none |

Other facts:
- Dev questions that abstained in older, non-routed runs and now do not: q12 q30 q31 q33 q36 q37 (calendar questions, now answered by the calendar node), q52 (rescued by the reranker; abstained in the reranker-off runs). So the current abstaining dev set is exactly 9: **q15 q27 q28 q34 q44 q45 q47 q49 q83**.
- q47 (gold NO ADVICE) and q49 (gold CLARIFY) abstain at the threshold although their gold is not ABSTAIN. That is a retrieval/answer-style matter (step 5), not 4c. They will get a contact line like any abstention.
- With `router.mode: off` (the frozen baseline path) only A and B exist, and no contact is attached anywhere.
- The eval recognises an abstention by the prefix `ABSTAIN:`. A contact line appended after the text keeps the prefix.
- Logs redact emails and phones (`[EMAIL]`, `[PHONE]`), so `request_logs` shows the calendar abstains as `Contact the Registrar: [EMAIL], [PHONE].` The contact is in the real answer.

## 2. Contact facts in the processed data

Source: `data/processed/contacts/<owner>.json` (the page's CONTACT US panel; `consistent: true` means every page of that owner prints the same block). `fetched_at` is the record's crawl time, 2026-10-11.

| Office | Email | Phone | Room | Hours | Source (first page, N pages) | fetched_at |
|---|---|---|---|---|---|---|
| Registrar | registrar@citytech.cuny.edu | 718-260-5800 | Namm Hall NG-15 | none printed | `/registrar/academic-calendar.aspx` (8) | 2026-10-11T16:49:37Z |
| Advisement | Advisement4u@citytech.cuny.edu (prospective & new students); transferadvisement@citytech.cuny.edu (transfer students); continuing students: "Visit departmental advisor" -> `/advisement/virtual-advisors.aspx` | **none in the data** | 300 Jay Street (no room) | none printed | `/advisement/six-steps.aspx` (9) | 2026-10-11T17:12:33Z |
| Bursar | bursar@citytech.cuny.edu | **none in the data** | Namm Hall NG-06 | Mon-Fri 9:30-4:00, weekend closed (service window and office) | `/bursar/payment-deadlines.aspx` (3) | 2026-10-11T16:49:46Z |
| Financial Aid | financialaid@citytech.cuny.edu | 718-260-5700 (the panel's `Phone:`); 718-254-8525 is printed as `Fax:` | Namm Hall NG-13 | long table (in person, Zoom, phone, web lab, work study); the phone-hours table prints Tuesday "9:00 PM - 5:00 PM" | `/financial-aid/financial-payment-calendar.aspx` (4) | 2026-10-11T16:49:50Z |
| Admissions | admissions@citytech.cuny.edu | 718-260-5500 (`Office Phone`); 718-682-7179 is "Call or chat 24/7 with our AI agent" | Namm Hall NG-17 | none printed | `/admissions/dates-deadlines.aspx` (3) | 2026-10-11T16:49:53Z |
| Special Circumstances | finaidspecialcircumstances@citytech.cuny.edu | 718-260-5714 | none | none | `data/pdfs/Special_Circumstances_Flyer_2025_2026_2026_2027.pdf`, last panel "Professional Judgment / Special Circumstances Coordinator, Ms. Pena" (a person's name; aid years 2025-26 and 2026-27); PDF created 2026-01-16 | file date only |
| CST | compsystech@citytech.cuny.edu | 718-260-5170 | Namm Hall 914 | Mon-Thu 9-7, Fri 9-5 | `/computer-systems/` (8) | 2026-10-11T16:50:01Z |
| Math | mathematics@citytech.cuny.edu | 718-260-5380 | Namm Hall 711 | none printed | `/mathematics/` (8) | 2026-10-11T16:50:09Z |
| EET | electricaltelecomm@citytech.cuny.edu | 718-260-5300 (`Phone:`); 718-254-8643 is printed as `Fax:` | Voorhees Hall 733 | none printed | `/electrical-telecomm/` (7) | 2026-10-11T16:50:16Z |
| Dental Hygiene | DentalHygiene@citytech.cuny.edu | 718-260-5070 | Academic Building 701 | none printed | `/dental/` (12) | 2026-10-11T16:50:28Z |

**Offices with no contact in the data:** none is entirely missing, but **Advisement and Bursar have no phone**, Advisement has two emails that depend on the student type, and there is no general help desk, no "Special Circumstances" page (only the flyer) and no student-account-data office. The chairs have separate contact records (`chairperson.aspx`); they are not the office contact and are not used.

**Finding that matters for 4c (a data bug, not fixed here):** the `phones` list in the EET and Financial Aid contact records contains the **fax** numbers (EET 718-254-8643, Financial Aid 718-254-8525), and `docs/manual-check-contacts.md` lists them in its Phone column (first). The panel text labels them `Fax:`. Today's `registrar_contact()` joins `phones`, which is harmless for the Registrar (one phone, no fax) but would print a fax as a phone for these two. A contacts table must take phones from the `Phone:` line only, and the validator must refuse a number that follows `Fax:`. The Admissions record likewise lists the AI-agent line as a phone; the table uses the office phone only.

## 3. Proposal

### (a) `config/contacts.yaml`, with a validator check

One entry per office and department (10 entries). Every entry carries: `name` (the phrase used in the sentence, e.g. "the Registrar"), `emails` (each with an optional `for:` note), `phones` (office phone only), `room` (stored, not printed), `source` (the contact record file and the first page URL) and `fetched_at` (copied from the record). Advisement carries one extra verbatim pointer (the virtual-advisors URL, which is in the panel). Special Circumstances is its own entry, with the role title and no person's name (decision 3).

Validator (`uv run python -m cta.validate`, new area `contacts`; fails on any of these):
1. every email and phone in the YAML appears in the owner's contact record (`emails`, `phones`) or, for Special Circumstances, in the flyer's processed text;
2. a phone must be the number after `Phone:` or `Office Phone:` in the panel text, never after `Fax:` and never the AI-agent line;
3. `source` page and `fetched_at` match the record;
4. every YAML email/phone is findable in `data/processed` (the check the owner asked for);
5. every department in `config/departments.yaml` has an entry and no entry is unreferenced.

### (b) A plain-code function that adds the line

New module `src/cta/graph/contact.py` (about 80 lines, no model call, no new dependency):

- `office_for(question, answer_state) -> str`: picks the entry key (rules in (c)).
- `contact_line(key) -> str`: formats the line from the YAML entry. The wording is fixed in code and tests, the model never writes contact details.
- `add_contact(ans, question)`: if `ans.abstained` is true and the text does not already end with that office's line, set `ans.text = ans.text + " " + line`. Non-abstaining answers are not touched. It runs once, in `Router.answer` after the graph, so it covers retrieve, calendar and chain abstains from one place. The calendar node's own contact (`render.abstain_text`, `Deps.contact`) is then replaced by the same function (the Registrar text stays byte-identical, see (d)). TBA rows still render their Registrar line, now read from the same table.
- Behind a switch `router.contacts: "off" | "on"` (default `off` until the rule passes), `CTA_ROUTER_CONTACTS`, `--contacts`. The router-off path (the frozen baseline) is not changed.
- Prompt rule 5 ("Name an office or give contact details only if they appear in the sources") is **left unchanged**: changing it would need its own paid measurement. A deterministic check (rule D5 below) fails if a model-written abstain sentence contains any email or phone that is not the table's.

### (c) Mapping from path or topic to office

First rule that applies wins. This is your starting suggestion, tested against the data, with two changes (rules 3 and 4 below).

1. **Calendar abstains** (C, D, and a TBA row): Registrar. Evidence: `registrar/academic-calendar.aspx` owns the calendar; unchanged from today.
2. **Chain no record** (F): the department whose course prefix is in `config/departments.yaml` (CST, MST, DPT -> CST; MAT, MEDU -> Math; EET, TCET -> EET; DEN -> Dental), else Advisement. (A prefix of the four with no such course, like CST 4999, goes to its department. A code outside the four, like ENG 1101, goes to Advisement.)
3. **Retrieve abstains (A, B), a department or course prefix in the question** (`detect_departments`, the function the step 2a filter already uses): exactly one department found -> that department. Several found -> skip to rule 5. This rule comes **before** the best-chunk rule because the best chunk can point elsewhere: q15's best chunk after reranking is `virtual-advisors#15` (Advisement), but the question names EET.
4. **Retrieve abstains, an account cue** (a small list of first-person words, written in `contacts.yaml` next to the office): `my gpa`, `my grade(s)`, `my transcript` -> Registrar (evidence: Registrar FAQ "Your official transcript must be requested from the Office of the Registrar"; grade policies are Registrar pages); `my balance`, `my bill`, `my tuition` -> Bursar; `my financial aid`, `my fafsa`, `my tap`, `my refund` -> Financial Aid. **Why this rule exists:** q44 ("What is my GPA this semester?") has best chunk `page/MATH-NYT/faqs#12` at 0.44, a Math FAQ that mentions GPA; the best-chunk rule would send a GPA question to the Math department. The cue list was written knowing q44, so q44 does not confirm it; the test split has to. "Holds" are left to rule 5 because the data names no single office: the Bursar page says unpaid tuition places a hold, the ePermit page speaks of holds on the academic record, the CUNYfirst guide shows "Tasks & Holds" for aid items.
5. **Retrieve abstains, otherwise: the office of the best-ranked chunk** (`results[0]`), by a map derived from the data, not hand-written per page: `page/<office>/...` and `contact:<office>` -> that office; `page/<DEPT>/...`, `dept/<DEPT>/...`, `contact:<DEPT>` and `catalog:...` (via its `department` field) -> that department; `pdf/financial-aid-refund-calendar-...` -> Financial Aid; `pdf/special-circumstances-flyer` -> Special Circumstances; `pdf/dropping-withdrawing-fall-2026` -> Registrar (a Fall 2026 policy about drops and W grades; the PDF itself names no office, so this is my judgement, decision 5); `pdf/cunyfirst-student-reference` (CUNY-wide aid guide) -> Financial Aid. Pages of the Admissions site map to Admissions because the contact record of that site lists them in `source_pages` (so `tuition-refund` and `tuition-penalty` go to Admissions, not the Bursar).
6. **Outside the four departments** (the best chunk is not from the four and no office rule fits, for example "How do I apply to Architectural Technology?"): Advisement, with its verbatim pointer to the virtual-advisors page. Evidence: that page lists a departmental advisor for about 20 departments, and the Advisement panel sends continuing students there. A code outside the four (ENG 1101) is already caught by rule 2.
7. **Fallback if nothing above fires:** Registrar (it has the largest set of policy chunks and the only course-scheduling, grades and ePermit pages). On the dev set this rule never fires; every one of the 9 abstentions is mapped by rules 1 to 5.

Account-data, sections/professors/seat availability and outside-four questions, specifically:
- **Account data** ("my GPA", "do I have a hold"): rule 4 or 5 as above. The data supports no general student-services office, so there is no single answer for "hold" (see rule 4).
- **Sections, seats, instructors, meeting times of a named course**: the department of the course prefix (rule 3: q27 CST, q28 and q45 Math). Evidence is thin either way: `registrar/course-scheduling.aspx` says Course and Room Scheduling is under the Registrar, but the page is written for schedulers and says nothing about seats, instructors or students, while the department pages carry a contact block for exactly these departments. I propose the department and flag it for you (decision 1).
- **Outside the four departments**: Advisement (rule 6).

### (d) Wording

One sentence appended after the abstention text, fixed in code:

`Contact <name>: <email>[, <email>][, <phone>].`

This is byte-identical to today's calendar line (`Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800.`), so the existing calendar abstains do not change. Examples:
- `Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170.`
- `Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300.` (phone from the `Phone:` line, not the fax)
- Advisement, which has no phone and two emails: `Contact Advisement: Advisement4u@citytech.cuny.edu (prospective and new students), transferadvisement@citytech.cuny.edu (transfer students). Continuing students can find their department's advisor at https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx.`
- Bursar (no phone): `Contact the Bursar: bursar@citytech.cuny.edu.`

Room and office hours are stored in the YAML but **not printed** (hours change by term, and the Financial Aid hours table has a printed typo). Decision 4.

## 4. Pre-registered rule for dev (deterministic, no paid call needed)

**Replay.** The function is run offline on the 55 dev questions from the stored `4b-run1..3` (question, answer text, `abstained`, `route`, `abstain_reason`, retrieved ids and similarities, as logged and in `eval/results/4b-run*.json`). No model call, no embedding call, cost $0. Threshold abstains (A) are deterministic, so the replay is exact for q27 q44 q45 q47 q49; route-based ones (q34, q83) are exact; the model-written ones (q15, q28) are replayed on the three stored texts.

**Keep rule (all must hold; otherwise `router.contacts` stays `off`):**
- D1. Every dev answer with `abstained: true` ends with exactly one contact line, and it equals the `contacts.yaml` line of the office in the table below (the one you approve).
- D2. The mapped office for each of the 9 dev abstentions equals your approved table. (On the replay of all three runs.)
- D3. Every non-abstaining answer is byte-identical to the original (no contact line added anywhere).
- D4. For abstaining answers, the text before the contact line is identical to the original.
- D5. After the change, every email and phone-like string in any dev answer is in the contacts table, or was already in the original answer.
- D6. `uv run python -m cta.validate` passes with the new `contacts` area; the fax and AI-agent numbers are refused by a test.
- D7. Applying the function twice adds the line once (idempotent); the calendar abstains (q34) are unchanged byte for byte.
- D8. `ruff` and `pytest` pass; with `router.contacts: "off"` the outputs are identical to today.

**Paid run: not needed for the rule.** The function acts on the final answer, so replay plus unit tests (stub router, as `tests/test_router.py` does) cover the wiring. If you want one end-to-end confirmation anyway: all 55 dev questions, **answers only, no judge**, `router.contacts on`, estimated **about $0.05** (the 4b runs cost $0.61 for 3 x 55 questions including the judge at about $0.003 per question; classify, select, rerank and answer are about $0.0008 per question), hard cap $0.10. I would not judge it: the judge would see an extra sentence on abstentions and its verdicts there (q15, q47, q49) would change for reasons unrelated to answer quality, so a judged run would measure wording, not the rule. Say if you want it; I recommend skipping it and doing the replay.

### Per-question table for your review (the 9 current dev abstentions)

| id | Question | Path | Rule | Proposed office | Contact line that would be appended |
|---|---|---|---|---|---|
| q15 | student hours for the Electrical Engineering Technology department | B (model) | 3 (EET named; best chunk would give Advisement) | EET | Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300. |
| q27 | open seats in CST 1101 this fall | A (0.540) | 3 (CST prefix; best chunk `CST-NYT/tutoring#2` agrees) | CST | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q28 | who is teaching MAT 1475 this semester | B (model) | 3 (MAT prefix; best chunk `catalog:MAT 1475` agrees) | Math | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q34 | last day to drop for a 100% refund in Summer 2027 | D (`calendar_no_row`) | 1 | Registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. (unchanged from today) |
| q44 | what is my GPA this semester | A (0.441) | 4 (cue "my gpa"; best chunk `MATH-NYT/faqs#12` would give Math, wrong) | Registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q45 | what days and times does MAT 1475 meet this fall | A (0.568) | 3 (MAT prefix; best chunk `catalog:MAT 1475` agrees) | Math | Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380. |
| q47 | should I take an Incomplete or withdraw | A (0.542) | 5 (best chunk `registrar/incomplete#1`) | Registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q49 | can I take a class at another college | A (top cosine 0.462) | 5 (best chunk `registrar/epermit#1`) | Registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q83 | prerequisites for CST 4999 | F | 2 (CST prefix) | CST | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |

Mapping check against the data: 4 of the 5 threshold abstentions have a best chunk from the right office (q27, q45, q47, q49); the fifth (q44) is wrong at 0.44, which is why rule 4 exists. The best chunk is not a reliable signal at low similarity: its similarity on these five ranges 0.44 to 0.57.

Also on dev, not abstaining now: all other 46 questions must come out byte-identical (D3). The controls that matter: q13 and q42 (fall-throughs that answer), q30 (calendar answer with a "Should I" question), q52 (rescued by the reranker, would abstain with the reranker off).

## Owner decisions (2026-10-13) — these replace the open questions

1. Seats, instructors, meeting times of a named course: the department of the course prefix (when it is one of the four).
2. Fallback office when no rule maps: Registrar.
3. Special Circumstances line: role only, no personal name.
4. Printed fields: email and phone only; room and hours are stored in `contacts.yaml`, not printed.
5. `pdf/dropping-withdrawing-fall-2026` maps to the Registrar.
6. The account-word cues (rule 4) stay. **They were written knowing dev question q44, so dev cannot validate them; the test split at the final milestone is their real check.** The same holds for the office table and the best-chunk map: they were derived with the dev abstentions in view, so the nine dev results are a consistency check, not independent evidence.
7. **Fax bug: the parser is not touched in this step.** The contacts table takes only the `Phone:` or `Office Phone:` line, and the validator refuses any number that is only a fax. The bug (EET and Financial Aid phone lists include fax numbers; the Admissions record lists the 24/7 AI-agent line as a phone) is logged in `docs/phase3-plan.md` under known issues; the fix is the next small step and needs a re-embed of the affected contact chunks.
8. q47 and q49: 4c only adds the contact line; their behaviour is for step 5.

Rule order is as written in section 3(c): calendar and chain rules, then a named department or course prefix, then account-word cues, then the chunk-source map, then the Registrar fallback. The rules D1 to D8 and the per-question table above are the pre-registration; they are not adjusted after the replay. If any D fails, `router.contacts` stays `off` and the failure is reported.


## v2: a contact only when the office clearly applies (written 2026-10-13, before any v2 code)

**Why.** See `docs/decisions.md`, "Contact policy v2": manual chat tests showed wrong cards on low-similarity abstentions. Rules that add a contact, with the v1 precedence kept for the existing tests: calendar abstention -> Registrar; chain no-record for a code with a prefix of the four departments -> that department; the question names one of the four departments (alias or course prefix) -> that department; an account-word cue -> the office of the table. **Removed:** the chunk-source map, the Registrar fallback, the Advisement default for a chain no-record outside the four departments. No match: no contact, no line in the text.

**Predicted replay (stored dev answers `4b-run1..3`, $0).** Under v1 the nine dev abstentions got: q15 EET (department), q27 CST (department), q28 Math (department), q34 Registrar (calendar), q44 Registrar (account cue), q45 Math (department), q83 CST (chain), q47 Registrar (chunk map), q49 Registrar (chunk map). **Prediction: q47 and q49 lose their line** (their only match was the chunk map); the other seven keep the identical line.

**Rule (all must hold, otherwise v2 stays off and I report):**
- V1. Every abstention whose v1 office came from a rule that stays (calendar, chain with a department prefix, department, cue) keeps the identical line (same office, same text).
- V2. Every abstention whose office came only from the chunk map or the fallback loses the line (text unchanged apart from the removed sentence, `contact_office` null); they are listed by id with the old line. Predicted: exactly q47 and q49, in each of the three runs.
- V3. Non-abstaining answers stay byte-identical; no abstention ends with two contact lines.
- V4. `uv run python -m cta.validate` passes (contacts area unchanged).
- V5. Ruff, pytest, typecheck and `next build` pass.
The per-question table (id, old office and rule, new result) is printed by `cta.eval.contact_replay`.
