# UI polish list (the owner's items, kept so nothing is lost between sessions)

Status: **not started**. This is a list, not a plan; each item would be its own small change with its own check. Last updated 2026-10-15.

1. **The fixed input bar hides the last lines of a long answer while scrolling.** Idea: a fade above the bar, or more bottom padding on the thread. (Some padding exists today: `.thread` bottom padding and `scroll-padding-bottom`, both checked by a node test; long answers still end up under the bar.)
2. **Group headings such as "Prerequisites for CST 1204" look like the course headings**, so the hierarchy is unclear (which line is a group, which is a course).
3. **"No catalog record" is mentioned twice for the same course**: once in "Courses named" and again at the bottom of the answer.
4. **"Courses named: none" wording** (in "How this was found").
5. **Advice answers** (step 5):
   - "Assuming the current term, Fall 2026." sits oddly in the middle of the answer, between the rules and the dates.
   - The drop or withdraw answer lists **10 calendar rows** (about 2,700 px tall at 390 px). Consider fewer rows or collapsed rows (for example a "Show all dates" toggle, or only the rows that are deadlines).
6. **Small `[n]` citation placement oddities** (for example "[2][1]" in a different order than the text, or a number after a colon).

Not UI, kept here for the same reason:

7. **Known limit: the tuition due dates (q13) come out as one run-on sentence.** The optional fix is a small code-written route for the Bursar payment table; it needs rows the owner has verified by hand (like the calendar table). Deferred until after the guardrails; see `docs/decisions.md`, "Step 5b closed".
