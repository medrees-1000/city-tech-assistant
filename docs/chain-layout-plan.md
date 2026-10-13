# Plan: chain layout, CLARIFY, NO ADVICE, two-course questions, date lists

Written 2026-10-13. Plan only: no code changed, no model call made, test split not read. I ran the existing deterministic chain walk (plain code, no model) on a few courses to build the mock-ups below.

**What this file contains (updated after the owner's review, 2026-10-13).** Five items in the order they are planned: **1 chain layout** (decisions below), **2 CLARIFY** (ambiguous questions), **3 NO ADVICE** (judgment questions), **4 two-course questions**, **5 date lists**; then eight drafted dev questions, one order of work with a cost per step, and the results of the manual checks that were run. Issue 6 (lowercase topics) is done and not in the plan. Everything here is a plan: no code, no eval change, no test-split use; the only model calls were the approved manual checks.

---

## Item 1: chain answers that are easy to read

### What is wrong now
For "What are the prerequisites for CST 3504?" the page shows a model-written answer: bullets "Level 0 / Level 1 / Level 2", with raw catalog strings such as `PRE: CST 1204 C OR HIGHER`. The model decides the wording, the order is by "level", and the reader has to work out which course names which.

### Proposal: the layout comes from plain code, not from a model
A new small module `src/cta/graph/chain_render.py` (same idea as the calendar renderer `render.py`) writes the whole chain answer from the data the walk already returns (`prerequisite_chain` result: per course `code`, `title`, verbatim `text`, `codes` named, `exclusions`, `unparsed`; plus `no_record`, `unexpanded`, `dropped`, `truncated`). **No model rewrites anything and nothing is parsed or paraphrased by hand:**
- the rule text is shown **verbatim in quotes** exactly as the catalog has it;
- "Courses named" lists the course codes the existing walk already extracted from that text (the same list the walk follows), with titles from the course records, joined by commas and **never "and" or "or"**: the quoted catalog text right below it decides that;
- the walk's own flags are shown with fixed sentences written once in the renderer.

The chain route then makes **no model call after the classifier** (the answer step and its prompt `chain_answer.txt` are not used when the switch is on).

### The layout (markdown that the page already renders)
```
Here is the prerequisite chain for <CODE>, from the catalog:

### <CODE> — <Title> [n]
**Courses named:** <CODE> (<Title>), <CODE> (<Title>)        <- or: none
**Catalog says:** "<verbatim catalog text>"                  <- or the sentence: No prerequisite listed in the catalog.
```
One block per course with a catalog record, in the walk's order (breadth-first, so a course comes before the courses it names). No "Level" wording anywhere. One `[n]` per block, in its heading (n is the course's position in the sources list, exactly as today). Fixed sentences, each written once in the code:

| situation (from the walk's data) | line |
|---|---|
| course has no prerequisite text | `No prerequisite listed in the catalog.` |
| the text names no course (placement, proficiency ...) | `**Courses named:** none` and the quoted text |
| a named course has no record | `<CODE> (no catalog record)` inside "Courses named" |
| the walk lists exclusions for the course | `**Must not have taken (as the catalog text says):** <CODE> (<Title>)` (the quoted text is still there) |
| the walk marked the text as shorthand or cut off (UNPARSED) | `**Courses named:** cannot be read from this text` and the quoted text |
| chain cut at the depth limit or the course cap | one closing sentence naming each course not followed and the courses it names: `The chain stops here: MAT 1475 names MAT 1375, which is not followed further (depth limit).` |
| codes with no catalog record anywhere in the chain | closing line `No catalog record in the four departments for: <CODE>, <CODE>.` |

Text with a line break (3 of the 197 course records) stays as written: the page shows paragraph line breaks as they are, so the quote keeps its two lines.

### Mock-up 1: "What are the prerequisites for CST 3504?" (real walk data, 4 courses)
Markdown the renderer would write:
```
Here is the prerequisite chain for CST 3504, from the catalog:

### CST 3504 — Database Design [1]
**Courses named:** CST 1204 (Database Systems Fundamentals)
**Catalog says:** "PRE: CST 1204 C OR HIGHER"

### CST 1204 — Database Systems Fundamentals [2]
**Courses named:** CST 1100 (Intro to Computer Systems), CST 1101 (Problem Solving Comp. Program)
**Catalog says:** "PRE: CST 1100 & 1101"

### CST 1100 — Intro to Computer Systems [3]
No prerequisite listed in the catalog.

### CST 1101 — Problem Solving Comp. Program [4]
No prerequisite listed in the catalog.
```
How the page shows it (small bold headings, bold labels, citation markers as the usual links):

> Here is the prerequisite chain for CST 3504, from the catalog:
>
> **CST 3504 — Database Design** [1]
> **Courses named:** CST 1204 (Database Systems Fundamentals)
> **Catalog says:** "PRE: CST 1204 C OR HIGHER"
>
> **CST 1204 — Database Systems Fundamentals** [2]
> **Courses named:** CST 1100 (Intro to Computer Systems), CST 1101 (Problem Solving Comp. Program)
> **Catalog says:** "PRE: CST 1100 & 1101"
>
> **CST 1100 — Intro to Computer Systems** [3]
> No prerequisite listed in the catalog.
>
> **CST 1101 — Problem Solving Comp. Program** [4]
> No prerequisite listed in the catalog.

(The `1101` in "CST 1100 & 1101" is read as CST 1101 by the walk's existing rule for a bare number after a code; the quoted text keeps the catalog's own `& 1101`.)

### Mock-up 2: a deeper chain, "What do I need to take before MAT 2440?" (real walk data, 10 courses, 3 codes without a record)
```
Here is the prerequisite chain for MAT 2440, from the catalog:

### MAT 2440 — Data Structures and Algorithms [1]
**Courses named:** MAT 1375 (Precalculus), CST 1201 (Programming Fundamentals), CST 2403 (Intro C++ Programming I), MAT 1630 (Intro to Computational Science), MTEC 1202 (no catalog record)
**Catalog says:** "Prerequisites of MAT 1375 or higher AND (CST 1201 or CST 2403 or MAT 1630 or MTEC 1202)."

### MAT 1375 — Precalculus [2]
**Courses named:** MAT 1275 (College Algebra/Trigonometry), MAT 1275CO (College Algebra & Trig w Coreq)
**Catalog says:** "PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375"

### CST 1201 — Programming Fundamentals [3]
**Courses named:** CST 1100 (Intro to Computer Systems), CST 1101 (Problem Solving Comp. Program)
**Catalog says:** "PRE: FOR CST MAJORS: CST 1100 & 1101, C GRADE
PRE: FOR NON-CST MAJORS: CST 1101"

### CST 2403 — Intro C++ Programming I [4]
**Courses named:** CST 1101 (Problem Solving Comp. Program), MAT 1275 (College Algebra/Trigonometry), MAT 1275CO (College Algebra & Trig w Coreq), MAT 1476 (no catalog record), EMT 1111 (no catalog record)
**Catalog says:** "Pre-requisite: (CST 1101 and MAT 1275 or MAT1275CO or higher) or MAT 1476 or (EMT 1111 and MAT 1275 or MAT 1275CO or higher)"

### MAT 1630 — Intro to Computational Science [5]
**Courses named:** MAT 1475 (Calculus I)
**Catalog says:** "Pre/Co-requisite of MAT 1475 is required."

[... blocks 6 to 10: MAT 1275 (courses named: none, its quoted proficiency text), MAT 1275CO, CST 1100 and CST 1101 (no prerequisite listed), MAT 1475 ...]

No catalog record in the four departments for: MTEC 1202, MAT 1476, EMT 1111.
```
What the owner sees: ten short blocks instead of nested bullets; each rule is quoted exactly once; "and"/"or" appear only inside the catalog's own quotation. A reader who skims "Courses named" could think every course is required, which is why the quoted catalog text sits on the very next line and why the lead sentence says "from the catalog".

### Deterministic checks (a test over **all 197 course chains**, plus the page)
Run for every course record, no model, no database:
1. every course the walk returns appears **exactly once** as a block heading, with its code, its title and `[n]` where n is its position in the walk result, and `sources_of(result)[n-1]` is that course (`catalog:<CODE>`), so the citations map to the same sources as today;
2. every verbatim rule string appears **unchanged** (character for character, including a line break) inside quotes in its own block; a course with empty text has the "No prerequisite listed" sentence and no "Catalog says" line;
3. "Courses named" equals the walk's `codes` for that course, in order, with the record's title (or "no catalog record"), joined by exactly `", "`: no "and", "or" or other word is added between codes; the exclusions line equals the walk's `exclusions`;
4. the set of `[n]` markers in the answer is exactly 1 to `course_count`, each marker sits in its own course's heading and nowhere else;
5. the word "Level" does not occur; the output is identical on a second run (deterministic);
6. the truncation sentence and the "no catalog record" line appear if and only if the walk reports them, naming exactly the walk's courses;
7. a UNPARSED course shows its verbatim string and the fixed "cannot be read" sentence;
8. page side (node test): `parseBlocks` of the rendered text gives one heading block per course and returns each verbatim string unchanged (a guard against a catalog text that looks like markdown: today **0 of 197** texts contain `#`, `- ` at a line start, `**`, `[n]`, `<` or a double quote, and the test fails loudly if a future catalog does);
9. chain route in the router test: after the switch only the classifier is called (`client.calls == ["classify"]`), the response has the same `route`, sources and `citations`.

### What would change in the chain evaluation (q78, q80, q86 and the others)
Chain questions in `eval/questions.jsonl`: dev q22, q39, q40, q76, q77, q79, q81, q85 (the CH set), plus q83 (no record) and q87 (control); test q20, q41, q78, q80, q82, q84 and q86. Effects:
- **What changes:** the chain route's answer text comes from code instead of the model: different wording and layout, quotes verbatim by construction, no sampling noise, no model call (about $0.0003 and about 2 s less per chain question; the 4b median for the chain route was about 3.3 s).
- **What does not change:** the classifier, the walk, the sources and the source order (so the "gold sources received" measure M3 is unchanged by construction), the route name `chain` (so the 4b measures M1, M2, M4, M6 and the router report are unchanged), the abstain paths (q83 no record, q84 outside the four departments, q43 two codes falls through), the failure-label rule (it depends on the tag and on whether it abstained, not on the wording), q87 (not a chain question).
- **What I cannot predict:** the judged correctness and faithfulness of chain answers, because the judge compares the new text with the gold. The golds are built from the same records and quote the catalog verbatim, so I expect no worse; I would still measure it. Known risks: the judge's faithfulness weakness on "the sources do not state X" sentences (q82, `docs/step4-judge-results.md`): the fixed sentences "No prerequisite listed in the catalog" and "cannot be read from this text" are of that kind; q39 and q41 keep their depth-limit truncation (the sentence replaces the model's mention of it, so they stay partial by design); q40 (partial in all 4b runs although every gold source was received) may change either way.
- **Milestone 1 stays as the record of the old route** (q78, q80, q86 were run with model-written chain answers). The test split is not used to design or tune this. The final milestone will measure the new route.

### How I would introduce it (pre-registered before any run)
One change behind a switch: `router.chain_render: "model" | "code"` (default `"model"`; `CTA_ROUTER_CHAIN_RENDER`, `--chain-render`). Keep rule, measured on **dev only** with the chain questions (CH set), judged under the current rubric, repeated judge twice because the answers themselves are deterministic: (K1) checks 1 to 9 pass; (K2) judged correctness on the CH set not lower than the 4b mean by more than one question, faithfulness not lower by more than one (with the usual caveat); (K3) M1 to M6 of the 4b report unchanged; (K4) cost per chain question lower. If kept, the default flips in its own commit. Expected cost: judge only, about $0.04 for 8 dev chain questions twice, plus the classifier calls. The prompt `chain_answer.txt` stays in the repository, unused with the switch on, as the fallback.

### Option considered and not planned (owner decision): an indented tree for deep chains
Same data, but each course sits under the course that named it (`named_by` is already in the walk result), indented one step per depth, so the structure of a 10-course chain is visible at a glance.
What it would cost:
- **A new page feature:** the markdown helper has no nested lists today; I would add them (about the size of the headings step, with its own tests), or the renderer could emit the structure as a small data block that the page draws. No new dependency either way.
- **A modelling problem:** the walk records each course once (visited set), so a course named by two parents (CST 1101 is named by CST 1201 and by CST 2403) would appear under the first one only; the tree needs an "also named by CST 2403" note, and a check that every `named_by` link is shown. A tree is therefore a simplification of what the catalog says; the flat blocks are not.
- **Space and phones:** a 15-course chain with indentation is taller and narrower on a 390px screen; verbatim quotes with line breaks nest awkwardly.
- **More checks:** each course once, under its `named_by` parent, in a stable order.
- **Effort:** one step with tests, no change to the evaluation beyond the layout.
My recommendation: ship the flat blocks first. Chains are median 5 courses (max 15; 56 of the 197 are cut at the depth limit), and the flat layout loses nothing the catalog says. Decide on the tree after seeing real deep chains on the page.

### Decisions for item 1 (owner, 2026-10-13: all six accepted as proposed)
1. **Exclusions line: yes**, from the walk's own `exclusions` data, with the fixed label `**Must not have taken (as the catalog text says):** <CODE> (<Title>)`.
2. **One `[n]` per block, in the heading only.**
3. `router.chain_render` stays **`"model"` by default** until the dev keep rule (K1 to K4) passes.
4. **The model fallback stays until the final cleanup**, then it is removed.
5. **Flat blocks now; the tree is not planned.**
6. **Em dash** in "CODE — Title".

One disclosure: I first ran the walk on EET 4202 for a "deeper chain", then switched the mock-up to MAT 2440, because EET 4202 is a test-split question and I do not want to design on it. Only the walk's catalog data was used, no test labels or results.

---

## Item 2: CLARIFY (an ambiguous question gets a short clarifying reply)

**Today.** "When is the deadline?" has no term, office or course. The classifier may send it to the calendar node, which finds no row and falls through to retrieval, which abstains at the cutoff; the topic call then calls it out of scope or "nothing found". Nothing tells the student what is missing.

**Proposal (zero extra model calls).** A plain-code check after the classifier and before retrieval, `needs_clarification(question)`, true only if **all** hold: (a) the question is short (at most 8 words); (b) it contains a generic date cue from a small list ("deadline", "due date", "last day", "when is the ... due"); (c) it contains **no topic noun** from a closed list taken from the data (register, registration, add, drop, withdraw, tuition, payment, pay, bill, refund, aid, FAFSA, TAP, graduate, graduation, ePermit, readmission, incomplete, commencement, exam, grades, SAP, appeal, ...); (d) no course code or department (`detect_departments` is empty); (e) the classifier did not say "prerequisite". A term is not needed to fire: "deadline for Fall 2026?" is still missing the topic. A question that names a topic but no term never fires (the calendar node already assumes the current term and says so).
**Reply: a fixed template written by the code**, using the options present in the data: "I can help with that, but I need a little more detail. Which deadline do you mean: registration, tuition payment, dropping or withdrawing from a class, applying to graduate, or financial aid? And for which term (Fall 2026, Winter 2027 or Spring 2027)?" The terms are read from `config/calendar_terms.yaml`. API: `answer_type: "clarify"` (already reserved in the contract), no citations, no contact card, no model call after the classifier. The route value would need a new member (`"clarify"`) in the contract and in the page's types; `how_found` says "Asked for more detail" (new sentence in the panel). **Optional extra:** the reply carries a `suggestions` list and the page shows them as buttons that send a clear question each ("When is the registration deadline?"); cost: one contract field and one small component, no model use.

**Options not chosen.** (B) a fourth classifier intent "unclear": more general but it changes the pipeline's classifier prompt and re-opens the calendar and chain evaluations (4a/4b). (C) extend the existing topic call (it already runs on abstentions) to return `needs_detail`: no extra call, but it fires only after retrieval and abstention, and a model decides when to ask, which is harder to bound than a rule.

**Cost.** Code and tests free. Dev check about $0.01 (the new questions q88 to q90 and q24, q49 through the API). The CLARIFY scoring rule (see "what could change in eval") needs a small, separately pre-registered change in the eval runner.

**Pre-registered deterministic checks.**
1. **Never on a clear question:** `needs_clarification` is false for every dev question (all 55), the four example chips, the manual-check questions, every question text in the calendar gold set and the six drafted controls; the test runs the function over them and fails on a single hit. (The test split is not read to build this list: I check the function against dev only; the final milestone will show whether it fires on test.)
2. **Property test:** any question that contains a topic noun, a course code or a department name never fires, whatever else it says.
3. It fires on the drafted ambiguous questions q88 and q89 and on "When is the deadline?".
4. The reply is exactly the template with data-derived terms; every option named in it is backed by data (calendar rows or an office page), tested.
5. The chain, calendar and retrieve routes are byte-identical for all dev questions that do not fire (replay of stored routes, $0).
6. No model call after the classifier, no contact, no citations; `answer_type` is `clarify`; the request is logged with that type.

**What could change in eval.** Only questions whose text matches the rule: among the existing ones, **q23** (test, "When is the deadline?", gold CLARIFY) would get a clarifying reply instead of an abstention. q24 and q49 (dev, CLARIFY gold) and q50, q74 (test) are *not* matched (they name a topic), so they stay as they are. The decisions file says the CLARIFY scoring rule (passes if it asks the question or answers every branch) is "implemented in step 5"; it is not implemented yet, so today such questions are reported as "not supported yet". Scoring them needs that rule in `run_answers` (a deterministic pass for `answer_type == clarify`, the judge otherwise): an eval-path change, pre-registered and measured on dev before it is used on test. Milestone 1 stays the record of the old behaviour.

## Item 3: NO ADVICE (judgment questions get the rules, not a verdict)

**Today.** "Should I drop my calculus class?" abstains at the cutoff (and gets no card, since no contact rule applies). CLAUDE.md says: never give advice, state the rules and the deadline. In the eval, a NO ADVICE gold passes when the answer abstains (a known scoring limit), so abstaining hides the gap; q48 (test) failed in milestone 1 only because the contact line was read as advice.

**Proposal.** A plain-code detector in the router after the classifier: an advice cue ("should I", "is it a good idea", "would you recommend", "is it better to", "do you think I should") **and** an action noun from a closed list (drop, withdraw, incomplete, ...). The answer is built from three parts: (1) **dates**: the calendar rows for that action in the current term, rendered by the existing calendar renderer (Fall 2026: last day to drop without a WD `fall-2026-011`, drop with WD `fall-2026-021`, W period from `fall-2026-024`, last day to withdraw `fall-2026-040`); (2) **rules**: the policy sections, retrieved with a fixed code-written question ("What are the rules and deadlines for dropping or withdrawing from a class?"), through the existing retrieve-and-answer path with its existing "no advice" prompt, citing them (`pdf/dropping-withdrawing-fall-2026#4`, `#5`, `#7`, the grade policy page); (3) **a fixed line from the code**: "I can't tell you whether you should; that is your decision. These are the rules and dates the sources give." The advisement contact is **not** attached: contact policy v2 has no rule that matches (no department, cue or calendar abstention). If you want advice questions to point to Advisement, that is a new confident rule and needs evidence from the data first (the same kind of search as for holds); I would not add it unseen.

**Options.** (A, proposed) code-detected, retrieval with a fixed rule query, existing answer model, fixed lines and checks around it; about $0.0007 per question. (B) fully code-built: the calendar rows plus the verbatim first paragraph of each policy section; no model, but the policy sections are long and picking sentences by code is the kind of hand-parsing we avoided. (C) keep abstaining: free, honest, and the owner has said it is not enough.

**Pre-registered deterministic checks** (run over every dev answer of this route, no judge): (1) the fixed line appears exactly once; (2) none of a closed list of advice phrases occurs ("you should", "I recommend", "I suggest", "it is best", "it would be better", "consider dropping", ...); (3) every date in the answer (month-day-year pattern) is a date of a cited calendar row or occurs in a cited source; (4) every `[n]` maps to a retrieved or calendar source; (5) no contact line unless a contact rule matches; (6) the detector fires on the advice questions (q30, q47, q91, q92) and on none of the other 51 dev questions; a question with an action noun but no advice cue ("When is the last day to drop?") never fires.

**Cost.** Free tests; evidence check free; dev run on q30, q47, q91, q92 judged twice about $0.04.

**What could change in eval.** NO ADVICE golds: q30 (dev; answered today by the calendar node with one date), q47 (dev; abstains at the cutoff today and passes only because abstaining passes), q48 (test; "Should I sign up for the Nelnet payment plan?" has no action noun in the list, so it would still abstain unless the list gets "sign up", "payment plan"), plus new q91 and q92. The judge checks only "gives advice yes/no", so q47 becomes a real test of the rule instead of a free pass: the risk is that the answer model adds a recommendation, which check 2 and the judge would catch. q30 is already answered by calendar rows; under the new route it would get the rules as well (a change in a dev answer that is now judged correct). Milestone 1 stays the record of the old behaviour.

## Item 4: two-course questions

**Today.** "What are the prerequisites for EET 2171 and EET 2162?" gives `extraction: many`, the chain node hands over to retrieve, retrieve has neither course, the model abstains (q43, test). The 4b design takes exactly one course per question.

**Proposal.** `extract_course` accepts up to **3** codes (in the order written, duplicates removed; titles are not mixed in); with more than 3 the question still falls through (the reply asks to name up to three courses). One **combined walk**: the same walk with a shared visited set and one cap of 15 courses with records across all roots (the cap and the depth limit are recorded exactly as today). The renderer from item 1 writes **one chain section per asked course**, a heading "Chain for EET 2171", then its blocks; **a course reached from both roots is shown once**, in the first root's section, and the second section says in a fixed sentence "CODE is already shown above." If one asked course is inside the chain of another (CST 3504 and CST 1204), it gets no second block, only that sentence. The question "are they the same?" is not answered by code: both quoted texts stand next to each other, the reader compares them.

**Options.** (A, proposed) as above, after item 1 (it needs the renderer). (B) with the model writing the answer: the model would again decide the wording and could merge the chains wrongly; not recommended. (C) keep one course per question and ask the student to pick: free, but q43-type questions stay unanswered.

**Pre-registered deterministic checks** (test over pairs and triples drawn from the 197 records, including pairs with shared courses and a pair where one contains the other): (1) every course of the union appears exactly once; (2) the roots appear in the order asked, each with its heading; (3) a shared course is in the first root's section only, the later section has the fixed sentence; (4) the combined number of courses with records is at most 15, and anything cut is named in the closing sentence exactly as in the walk; (5) every verbatim string unchanged (the item-1 checks 2 to 7 apply to the combined result); (6) the single-course output is byte-identical to item 1's (no regression); (7) four codes fall through, titles alone do not trigger two-course handling; (8) cross-listed codes (EET 3672 / CET 3672) stay separate, never merged.

**Cost.** Free tests; dev run on q42, q93, q94 judged twice about $0.03.

**What could change in eval.** **q43** (test; two EET codes, gold from the records) becomes a chain answer instead of an abstention. **q42** (dev, "MAT 1190CO ... how are they different from MAT 1190?") **changes route**: today it falls through to retrieve and is answered correctly there; with two codes it goes to the chain node. That alters two 4b definitions (M2 treated q21 and q42 as "prerequisite-looking questions the chain node must not take"; R1 allowed at most one such id): they must be re-stated before any run, and q42's judged result compared before and after (the combined chain shows both texts verbatim, which should satisfy its gold, but it is a measured claim, not a given). Single-course questions (q20, q22, q39, q40, q41, q76 ...) are unaffected by construction (check 6).

## Item 5: date lists

**Today.** What the page renders: paragraphs, "- " bullet lists, headings (# to ###), bold and `[n]` links. **No tables, no numbered lists, no nested lists, no italics, no inline links.** Several-date answers come from two places: (a) the calendar renderer (plain code): each row is a bullet that repeats a long provenance clause, for example "- Thursday, September 3, 2026: Last day to add a course. [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)" four times in a four-row answer; (b) retrieval answers (tuition and payment deadlines, aid refund dates) are written by the model from table chunks, so their layout is the model's.

**Options.** (A, proposed, no page change) **code-written layout for calendar rows**: one line per row, date in bold, then the event and `[n]`; **one provenance line per calendar** at the end ("From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change."), a separate group when rows come from two terms; the TBA row keeps its Registrar line. (B) **table support in the page's markdown subset** (pipe tables: header, separator, rows; text, bold and `[n]` in cells; real `<table>` with header cells; a scroll container on narrow screens; pure parser with tests): about the size of the headings step; a calendar answer could then be a two-column "Date | Event" table, and any table the model quotes would render. A table costs more on a phone (390px) than a list: wide event texts wrap in narrow cells; I would still keep lists for 1 to 4 rows and use a table only above that. (C) a **deterministic payment-deadline route** that returns the bursar table verbatim, like the calendar route: needs a classifier intent or selector and a table parser; larger, not recommended now. (D) a line in the **answer prompt** ("put each date on its own bullet"): a pipeline prompt change, needs a full dev run (3 runs of 55 questions judged, about $0.2) and touches retrieval answers only; not recommended before A.

**Cost.** A: free tests; dev check on the calendar-only questions (13) and q95 under both scorings about $0.01 (classifier and selector calls, no judge needed). B: free tests plus screenshots.

**Pre-registered deterministic checks (A).** (1) every returned row's weekday-and-date text is exactly the one the current renderer writes (`date_in_words`), same rows, same order (by date, then id); (2) each row's `[n]` unique and mapped to its row source; (3) the provenance line appears once per calendar (term and PDF name and last-updated date equal the rows' fields) and the "calendar can change" warning is present; (4) TBA rows say "not announced yet" and keep the Registrar line; (5) a one-row answer keeps its provenance inline or in the line below, never lost; (6) the calendar-only scoring (row ids, v2) gives identical verdicts on all stored dev runs when re-scored from the returned row ids, which do not change.

**What could change in eval.** Calendar-only scoring compares row ids, which A does not change, so those verdicts are unchanged by construction. Calendar-route answers that are *judged* by text (calendar questions with a normal gold, for example q09, q10, q30 ...) get different wording and could be judged differently; the dev run covers them. Milestone 1 stays the record of the old layout.

## Eight drafted dev questions (drafts only; nothing goes into `eval/questions.jsonl` until you approve)
Built only from facts in the collected data; ids continue from q88 (the file ends at q87); all would be `dev`; I checked by text search that none repeats an existing question (counts only). Golds that need your words are `TODO`.

| id | question | type / tag | purpose | gold sources | gold |
|---|---|---|---|---|---|
| q88 | When is the due date? | ambiguous | CLARIFY fires | none | `CLARIFY: ask which deadline (registration, tuition payment, dropping or withdrawing, applying to graduate, financial aid) and which term (Fall 2026, Winter 2027, Spring 2027); do not guess.` |
| q89 | What is the last day? | ambiguous | CLARIFY fires | none | same as q88 |
| q90 | When is the filing period for February 2027 graduation? | time_sensitive, calendar | CLARIFY must **not** fire on a clear question | `winter-2027-024`, `winter-2027-026` | Monday, January 25, 2027 to Monday, February 1, 2027 (rows `winter-2027-024` "Filing period for February 2027 graduation begins", `-026` "ends"; weekdays TODO, owner to check) |
| q91 | Should I withdraw from my biology class? | unanswerable-by-advice, NO ADVICE | rules and dates, no verdict | `fall-2026-011`, `fall-2026-021`, `fall-2026-040`, `pdf/dropping-withdrawing-fall-2026#4`, `#5`, `#7` | `NO ADVICE: state the rules and dates (last day to drop without a WD grade Sept 3, 2026; WD through Sept 17; W from Sept 18 to Nov 6, 2026; financial aid effects per the PDF) without recommending a choice.` details TODO (owner reviews against the PDF) |
| q92 | Is it a good idea to take an Incomplete? | lookup, NO ADVICE | rules, no verdict | `page/registrar/incomplete#1` | `NO ADVICE: state what an Incomplete is and its conditions from the Registrar page, without recommending.` details TODO |
| q93 | What do I need before CST 1204 and CST 2403? | multi_chunk, chain | two-course chain | `catalog:CST 1204`, `catalog:CST 2403` | CST 1204: "PRE: CST 1100 & 1101"; CST 2403: "Pre-requisite: (CST 1101 and MAT 1275 or MAT1275CO or higher) or MAT 1476 or (EMT 1111 and MAT 1275 or MAT 1275CO or higher)" (verbatim from the records; `MAT 1476` and `EMT 1111` have no record) |
| q94 | What are the prerequisites for MAT 1275 and MAT 1375? | multi_chunk, chain | two-course chain where one course is named by the other | `catalog:MAT 1275`, `catalog:MAT 1375` | verbatim records: MAT 1375 "PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375"; MAT 1275 text as in the record (long; TODO paste) |
| q95 | When does the Winter 2027 session start and end? | time_sensitive, calendar | date list of two rows | `winter-2027-004` (acceptable extra `winter-2027-005` "Classes begin", same date), `winter-2027-023` | Monday, January 4, 2027 and Monday, January 25, 2027 |

q90 and q95 are `calendar`-tagged (scored by row ids under scoring v2); q93 and q94 carry the `chain` tag.

## Order of work, with a cost estimate per step
One commit per step, each pre-registered in this file before its first paid call; free tests first, dev measurement only; the test split only at the next milestone.
1. **Chain layout (item 1)**: `chain_render.py`, the nine checks over all 197 chains, the switch (default `"model"`), router tests; dev run on the 8 CH questions judged twice, about **$0.07**; flip the default if K1 to K4 hold.
2. **Two-course questions (item 4)**: extraction up to 3 codes, combined walk, per-root sections, checks; re-state the 4b definitions that mention q42; dev run on q42, q93, q94 judged twice about **$0.03**.
3. **Date lists (item 5, option A)**: calendar rows layout and checks; dev run on the calendar-only questions plus q90 and q95, about **$0.01**; table support (B) only if you ask for it (screenshots, no model cost).
4. **CLARIFY (item 2)**: rule, template, `answer_type clarify`, the "never on a clear question" test over all dev questions; the CLARIFY scoring rule in the eval runner pre-registered separately; dev run on q88, q89, q90, q24, q49 about **$0.01**.
5. **NO ADVICE (item 3)**: evidence check for an Advisement rule first (free); detector, fixed line, checks; dev run on q30, q47, q91, q92 judged twice about **$0.04**.
6. **Next milestone** (not part of this plan): one test run with everything on, about $0.15 to $0.2 for old and new.
Estimated dev spend for steps 1 to 5: about **$0.16**. Order reasons: 1 before 2 (the renderer is shared); 3 and 4 are independent of 1 and 2; 5 is last (it touches the most: a new route, a prompt-free check set, and the judge's NO ADVICE rule).

## Manual checks (run 2026-10-13, with the approved budget; servers stopped afterwards)
1. **"Do I have a hold on my account?" through the real API.** `route: retrieve`, `answer_type: abstain`, `abstained: true`, **`abstain_reason: "personal_account"`**, **`contact: null`**, no citations. The `answer` field is the pipeline's generic sentence "I could not find this in the City Tech sources I have." and the topic call did not run (`abstain_wording: null`); the page replaces it with its own fixed text without "Here is who can help:". Cost $0.00004.
2. **CST 3504 on the real page** (real chat typed in headless Chrome, real API, real answer): the model-written route today shows one bullet per course, "**Level 0 — CST 3504:** The catalog prerequisite text is “PRE: CST 1204 C OR HIGHER.” [1]", "Level 1 — CST 1204: ... “PRE: CST 1100 & 1101.” [2]", "Level 2 — CST 1100: No prerequisite is listed for it in the catalog. [3]", "Level 2 — CST 1101: ... [4]", then the thumbs, "Sources (4)" and "How this was found". The panel says "Walked the prerequisite chain", "Courses followed (4), in the order found", times (1.2 s understanding, 1 ms following, 2.0 s writing, 3.3 s total), "Tokens: 1787 read by the model, 130 written", "Cost: 0.02 cents". Screenshots at 390px and 1280px, light and dark, panel closed and open (the saved real response replayed for all eight views, plus one live pass): everything renders; the bullets, bold "Level N — CODE", quotes and `[n]` links are as the text above; the layout is what item 1 replaces (the word "Level", the sentence "The catalog prerequisite text is" repeated on every line). Cost of the real requests for both checks: $0.0008 in total.
