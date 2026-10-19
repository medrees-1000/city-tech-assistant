# Casual-question draft set (proposal only)

Drafted Oct 15, 2026 from the second outside tester's results (`~/city-tech-tester2/findings.md`, items T04, T06, T07, T08, T09, plus the answered controls). **For the owner's review.** Nothing here is in `eval/questions.jsonl`; no gold answer is written (all `TODO`); no model was called. Gold sources below are **proposals** found by plain-text search of `data/processed/chunks.jsonl` (source + heading, as the eval labels are document/section level); where the search found no clear section the row says `TODO`.

Row ids are placeholders (`cq01` ...); the real ids come after your review. Types use the existing set (`lookup`, `multi_chunk`, `time_sensitive`, `ambiguous`, `unanswerable`). "Tester ids" are the first 8 characters of the `request_logs` ids in findings.md.

## A. Casual wording that fell under the line or got "couldn't find" (17)

| id | question (exact tester text) | type | department | proposed gold source (URL or file + heading) | matching text (excerpt) | tester ids / what happened |
|---|---|---|---|---|---|---|
| cq01 | whats the tuition deadline | lookup | none | https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx — "Bill Payment Deadlines" | "Your payment due date corresponds to your initial registration date. Failure to pay tuition and fees by the due date could result in cancellation of course enrollment." | 914d1559; closest page listed, no answer (sim 0.576) |
| cq02 | cst department chair name? | lookup | CST | https://www.citytech.cuny.edu/computer-systems/chairperson.aspx — "Meet the Chair" | "Prof. Elizabeth Milonas Chair Namm Hall 1000 (N-1000) 718-260-5038" | 6b28f230; only "Meet the Chair" listed |
| cq03 | name of the head of the computer systems tech department | lookup | CST | same as cq02 | same as cq02 | 1e81d358; listed "Mission" instead |
| cq04 | how to register for classes | lookup | none | TODO — no section found that states the registration steps. Candidates to check by eye: https://www.citytech.cuny.edu/advisement/six-steps.aspx ("Six Steps to Prepare for Academic Advisement ...") and https://www.citytech.cuny.edu/advisement/continuing-students.aspx | six-steps is advising preparation, not CUNYfirst enrollment steps | 0da4ee2e; "couldn't find" |
| cq05 | fafsa deadline | lookup | none | TODO — the search found no FAFSA deadline date in the collected text. Related only: https://www.citytech.cuny.edu/financial-aid/faqs.aspx ("Frequently Asked Questions > Applying for Financial Aid") | "How do I apply for FAFSA and TAP? To apply for both FAFSA and TAP, follow the [instructions] ..." (no date) | 858de1fc. **May be genuinely unanswerable**: owner to decide `lookup` or `unanswerable` |
| cq06 | payment plan? | lookup | none | https://www.citytech.cuny.edu/bursar/payment-plan.aspx — "Nelnet Tuition Payment Plan" | "Payment plan options are available for Fall, Spring and Summer terms prior to the start of the semester. Students interested in this monthly payment plan can enroll by: ..." | 470fddc1; "couldn't find" |
| cq07 | how do i pay my tuition bill | lookup | none | https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx — "Bill Payment Deadlines"; maybe also https://www.citytech.cuny.edu/bursar/payment-plan.aspx | same text as cq01; no section on how to pay was found | ac2124b2; closest page was "Penalty Fees > Outstanding Balances" (not helpful) |
| cq08 | i give up my seat in class, how do i drop | lookup | none | data/pdfs/Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf — "Dropping Classes" (and "Dropping a Class On or Before September 3, 2026") | "... between the date you register and the **21st day of the semester.**" / "If you drop a class on or before **September 3, 2026,** the course will not be included when determining your enrollment status ..." | dfe8dae3; "couldn't find". The "give up my seat" wording is the T03/T07 near-miss idiom |
| cq09 | i could cry the line was so long, where do i pay | lookup | none | TODO — no section on *where* to pay was found. Candidate: https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx ("Contact: Bursar office") | contact block only | 3d22db37; answered "outside what I can answer" (wrong: paying is in scope) |
| cq10 | when is it due | ambiguous | none | none — the right answer is the clarify question (no gold source) | — | 90fd0316; fixed in this round (CLARIFY) |
| cq11 | is it worth it to major in cst, how many credits is the degree | multi_chunk | CST | data/pdfs/CST-NYT-2026-09-10-19-16-13.pdf — the degree map headings, e.g. "Computer Systems - BTECH ... > Degree Maps > Degree map: Computer Systems: Database" ("Total degree map credits: 120 - 124"). TODO: which program the student means is not stated, so the gold may be several maps | "Total degree map credits: 120 - 124" (BTECH Database), "114 - 118" (Cybersecurity BS), "121 - 123" (Data Science BS) | 1e81d358-family (T06); the "is it worth it" half is advice; expected: rules/credits, no verdict |
| cq12 | that tuition bill almost gave me a heart attack lol when is it due | lookup | none | same as cq01 | same as cq01 | 744c8fd2; "couldn't find" |
| cq13 | im drowning in paperwork, how do i apply for fafsa | lookup | none | https://www.citytech.cuny.edu/financial-aid/faqs.aspx — "Frequently Asked Questions > Applying for Financial Aid" | "How do I apply for FAFSA and TAP? To apply for both FAFSA and TAP, follow the [instructions] ..." | b0891291; "couldn't find" |
| cq14 | what would you do, take a payment plan or pay all at once | ambiguous | none | https://www.citytech.cuny.edu/bursar/payment-plan.aspx — "Nelnet Tuition Payment Plan" for the rules; the expected behaviour is the no-advice frame (rules, no verdict) | as cq06 | tester 7 (T07 list); opinion question |
| cq15 | midterms r stressing me out so bad, whats the rule on withdrawing | time_sensitive | none | data/pdfs/Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf — "Withdrawal (W Grade)"; calendar row fall-2026-040 (last day to withdraw, Nov 6 2026) | "A **W grade** is assigned when you withdraw from a course **after the 21st day of the semester** (after **September 17, 2026,** for Fall 2026)." | 59e0383c; "couldn't find ... the rule on withdrawing" (T02b, retrieval, out of this round's scope) |
| cq16 | when is tuition due and what is the last day to withdraw | multi_chunk | none | https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx — "Bill Payment Deadlines" **and** calendar row fall-2026-040 | as cq01 + the Nov 6 withdraw row | 4f74d972; answered only the withdraw half (T05, known limit) |
| cq17 | whats the last day to drop a class fall 2026 | time_sensitive | none | `data/calendar/calendar_events.json` rows fall-2026-011 (last day to drop without a grade of WD, Sep 3), fall-2026-021 (drop with WD, Sep 17), fall-2026-040 (withdraw with W, Nov 6) | the three "drop/withdraw" rows of Fall 2026 | a73ca7ac / this round's live replay: the plain wording gets only the Nov 6 row (T04) |

## B. Controls: already answer well (6)

| id | question | type | department | proposed gold source | note |
|---|---|---|---|---|---|
| cq18 | how do i drop a class | lookup | none | data/pdfs/Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf — "Dropping Classes"; https://www.citytech.cuny.edu/bursar/refund-policy.aspx — "Refund Policy > Refund Policy and Deadlines for Dropping Classes" | answered with 5 citations in the tester run |
| cq19 | when do pell grant refunds go out | time_sensitive | none | data/pdfs/Award_Year_2026_2027_Financial_Aid_Payment_Refund _Calendar.pdf — "Financial Aid (Federal Pell, SEOG, Direct Loans) Refund Dates" | answered in the tester run |
| cq20 | who is the chair of the math department | lookup | MATH | https://www.citytech.cuny.edu/mathematics/chairperson.aspx — "Meet the Chair" | "Jonathan Natov Chair Namm Hall 711 (N-711) 718-260-5928" |
| cq21 | deadline to appeal sap financial aid | lookup | none | https://www.citytech.cuny.edu/financial-aid/sap.aspx — "How to Submit a SAP Appeal" (TODO: check the deadline sentence) | answered (7.3 s) in the tester run |
| cq22 | what degrees does the math dept offer | lookup | MATH | TODO — a department PDF/degrees page section; not searched | answered in the tester run |
| cq23 | how do i apply for financial aid | lookup | none | https://www.citytech.cuny.edu/financial-aid/faqs.aspx — "Frequently Asked Questions > Applying for Financial Aid" | got "closest pages" in the tester run, so it is a borderline control |

## C. Must keep abstaining (4)

| id | question | type | department | proposed gold source | expected |
|---|---|---|---|---|---|
| cq24 | how many seats are left in MAT 1475 section 3 | unanswerable | MATH | none | abstain: seat availability is out of scope |
| cq25 | what is the email of my math professor | unanswerable | MATH | none | abstain: faculty directory/individual instructors are out of scope |
| cq26 | what time does section 2 of CST 1101 meet | unanswerable | CST | none | abstain: class schedules/sections are out of scope |
| cq27 | do i have a hold on my account and what is my balance | unanswerable | none | none | abstain: personal account data (`personal_account`, with the contact card) |

## Notes for the review

- `cq05` (FAFSA deadline), `cq09` (where to pay) and `cq04` (how to register) found **no clear source section**; they may be gaps in the collected data rather than retrieval faults. Deciding that is the owner's call.
- `cq01`, `cq07`, `cq12` and `cq16` share one source: if all four are added, they test the same section from four wordings.
- The texts above are the testers' own words; the idiom questions (`cq08`, `cq09`, `cq12`) were the ones that nearly tripped the crisis screen and are kept for that reason too.
