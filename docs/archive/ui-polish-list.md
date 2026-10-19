# UI polish list (the owner's items, kept so nothing is lost between sessions)

Status: **round 1 done 2026-10-15** (items 1 to 6). Each item says what was done and where. The rule for the answer-text items and the evidence are in `docs/decisions.md` ("UI polish round"). New items from the owner are added below the list.

1. **The fixed input bar hid the last lines of a long answer.** DONE (`e659045`). Cause found by measuring: after a new answer the page scrolled by a fixed 13rem, but the bar is about 18.5rem tall at 390 px, so the last 63 px ("How this was found") sat under it. The chat page now measures the bar's real height (`--dock-h`, a `ResizeObserver`) and the scroll padding follows it, plus 1rem of air; a soft fade sits above the bar. After the fix the last line ends 42 px above the bar at 390 px (40 px at 1280 px). Tested in `web/lib/messages.test.ts`. Not a problem: at the very bottom of the page the last lines were always clear (the overlap in a full-page screenshot is a capture artifact).
2. **Group headings looked like the course headings.** DONE (commit "UI polish (b)"). "Prerequisites for CST 1204" is now larger (1.25rem) with a thin rule above (not on the first block of an answer); the course headings keep body size. Text unchanged.
3. **"No catalog record" was mentioned twice for the same course.** DONE (`8d95201`). The closing line goes only when every code in it is already marked "(no catalog record)" in a "Courses named" or "Must not have taken" line above; otherwise both stay. In the 197 single chains and 42 multi-course renders tested, the rule changes only the texts it should (see decisions).
4. **"Courses named: none" wording.** DONE (`8d95201`): "Courses named: none listed".
5. **Advice answers.** DONE for the two parts that were agreed: "Assuming the current term, Fall 2026." is now at the end of the provenance line (`8d95201`), and a list of more than five items shows the first five behind a keyboard-accessible "Show all N items" toggle (`8c94455`; the hidden items stay in the page, so no text changes). **Still open (deferred):** the drop or withdraw answer still holds 10 calendar rows when expanded, and the policy text and the rows repeat the refund dates; choosing "only the deadline rows" would change which rows are shown, which is an answer change and needs the owner's decision.
6. **Small `[n]` citation placement oddities.** DONE (`8c94455`): a marker is bound to the word before it (and consecutive markers to each other), so it never starts a line. Not changed: the order of the numbers inside a group (for example "[2][1]") is the model's order; sorting them would change answer text.

Not UI, kept here for the same reason:

7. **Known limit: the tuition due dates (q13) come out as one run-on sentence.** The optional fix is a small code-written route for the Bursar payment table; it needs rows the owner has verified by hand (like the calendar table). Deferred until the owner decides; see `docs/decisions.md`, "Step 5b closed".

## New items from the owner
(none yet)
