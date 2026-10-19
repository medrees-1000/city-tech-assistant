# Version 2, step 1: why the casual-wording questions are refused (diagnosis only)

Written 2026-10-16. Read only: no model call, no eval run, no code change. Dev questions only (the casual set q104 to q123, tag `casual`); the test split was not read.

**Where the numbers come from.**
- `eval/results/final-config-dev.json` (route, abstain flag, stored top-10 chunks with their similarity, first gold rank).
- Two free, read-only lookups on this machine, neither a model call: (1) a vector search of each casual question with `rerank off`, using the **cached** query embedding (a cache miss would have raised an error; there was none), to get the first-stage top 20 and the best vector similarity, which is the number the 0.59 cutoff is compared with (the stored top 10 is the reranked list and can hide the best chunk); (2) the reranker's own cached scores for the same pool (`data/cache/rerank-final-config-dev.json`, scores 0 to 10), read back with the run's cache, to see how the reranker judged the gold chunk.

## 1. The ten refused questions

All ten are `abstain below_threshold` (the best vector similarity is under 0.59, so the answer model is never called). The gold chunk is retrieved in every case.

| id | question | route | best similarity (cutoff 0.59) | gold rank in first-stage top 20 (similarity of the gold chunk) | reranker: gold rank / gold score (top score) | stage that failed |
|---|---|---|---|---|---|---|
| q104 | whats the tuition deadline | calendar fall-through | 0.576 | 1 (0.576) | 1 / 10 (10) | cutoff, 0.014 under |
| q105 | cst department chair name? | retrieve | 0.567 | 1 (0.567) | 1 / 10 (10) | cutoff, 0.023 under |
| q106 | name of the head of the computer systems tech department | retrieve | 0.558 | 7 (0.507) | 1 / 10 (10) | cutoff, 0.032 under |
| q107 | payment plan? | retrieve | 0.511 | 1 (0.511) | 1 / 10 (10) | cutoff, 0.079 under |
| q108 | i give up my seat in class, how do i drop | retrieve | 0.514 | 1 (0.514) | 3 / 5 (8) | cutoff, 0.076 under |
| q110 | that tuition bill almost gave me a heart attack lol when is it due | calendar fall-through | 0.526 | 1 (0.526) | 1 / 10 (10) | cutoff, 0.064 under |
| q111 | im drowning in paperwork, how do i apply for fafsa | retrieve | 0.497 | 4 (0.482) | 1 / 9 (9) | cutoff, 0.093 under |
| q113 | midterms r stressing me out so bad, whats the rule on withdrawing | retrieve | 0.508 | 1 (0.508) | 1 / 8 (8) | cutoff, 0.082 under |
| q120 | how do i apply for financial aid | retrieve | 0.589 | 1 (0.589) | 1 / 10 (10) | cutoff, 0.001 under |
| q123 | fafsa deadline | retrieve | 0.498 | 12 (0.404) | 1 / 10 (10) | cutoff, 0.092 under |

**Stage counts (10 refusals):**
- classifier route: 0 wrong. Eight went to retrieval; two (q104, q110, "tuition deadline") were read as calendar questions, the calendar selector found no row, and they fell through to retrieval, as designed. None was sent to clarify, advice or off-topic.
- retrieval: gold chunk in the first-stage top 20 in **10 of 10** (rank 1 in 7, ranks 4, 7 and 12 in the other three). Not a retrieval miss.
- reranker: gold chunk in the top 5 in **10 of 10** (rank 1 in 9, rank 3 in q108). Not a reranker loss.
- **similarity cutoff (0.59): 10 of 10.** The best vector similarity of the question to any chunk is 0.497 to 0.589. The answer step was never reached.

The one other casual failure, q118 ("deadline to appeal sap financial aid", partial), is not a refusal: it was answered by the calendar route with the Fall 2026 deadline only, where the gold also wants Spring 2027.

## 2. Causes, by what the casual wording does

| cause | questions | count | what in the wording triggers it |
|---|---|---|---|
| A. Very short keyword queries | q104, q105, q107, q123 | 4 | One to four words ("payment plan?", "fafsa deadline", "cst department chair name?"). A short query has few words to match the long chunk text, so cosine similarity is low even though the right chunk is ranked first (0.498 to 0.576). Missing words such as "how do I" or the office name make it worse. |
| B. Different vocabulary from the sources | q106, q108 | 2 | "head of the ... department" against the page word "chairperson"; "give up my seat in class" against "drop". The reranker finds the right chunk, the embedding does not rank it first (q106: seventh) or score it high (0.51). |
| C. Chatty filler around the real question | q110, q111, q113 | 3 | "almost gave me a heart attack lol", "im drowning in paperwork", "midterms r stressing me out so bad": a third to a half of the words carry feeling, not the topic, which dilutes the embedding (0.497 to 0.526). Text-speak ("r", "im", "whats") adds a little. |
| D. A plain question that scores just under the cutoff | q120 | 1 | "how do i apply for financial aid" is well formed and scores 0.5891, 0.001 under 0.59. The gold chunk is a generic FAQ section. |

Vague pronouns and two questions in one are not a cause here (those cases go to clarify or to the two-part known limit).

**What the data says about the cutoff.** The reranker (which reads question and chunk together) scored the gold chunk 8 to 10 out of 10 for nine of the ten (q108: 5, with a different chunk at 8). So the system already holds a better signal than the cutoff uses: the cutoff looks only at the first-stage cosine similarity, and short or chatty wording lowers that number without making the answer any less available.

## 3. Proposed fixes (nothing implemented)

Ranked. "Cost to measure" is an estimate: a judged answer costs about $0.0055 (answer $0.0004, judge $0.005); the reranker scores are cached.

**Fix 1 (rank 1): let the reranker confirm a match that is under the cutoff** (fixes A, B, C and D together).
- What: when the best similarity is under 0.59 but at or above a floor, and the reranker's top score is at least a fixed minimum (for example floor 0.45, minimum score 8 or 9), go on to the answer model instead of refusing. The answer model can still abstain. Both numbers are fixed in advance and written in `docs/decisions.md` before any run.
- Files: `src/cta/answer.py` (the threshold decision; the reranker has already run by then), `src/cta/index/search.py` (expose the top rerank score), `config/models.yaml` (two new settings, default off), tests.
- What the dev data shows (cached scores): it would answer q104, q105, q106, q107, q108, q110, q111, q113, q120, q123 and q98 (a tester question with the same fault), and leave q44, q27, q45, q121 (top scores 0, 0, 0, 5) and q122 (7) as refusals. **One dev question would flip the wrong way: q49** "Can I take a class at another college?" (similarity 0.488, top score 10), the same question that sank the query-rewrite experiment E1 (it was answered with one case where the gold wants a clarifying question or both cases). The margin on q122 is one point (7 against a minimum of 8), and a floor of 0.49 would separate q49 (0.488) from q111 and q123 (0.497, 0.498) by 0.009, which is too thin to trust, so the owner would need to decide about q49 (drop it from the must-abstain list, or require the answer to cover both cases) before the rule is written.
- Risk to existing results: only questions that are refused today can change; questions answered today are untouched (their similarity is already over 0.59). The near-miss reply and the abstention accuracy on must-abstain questions are the exposed parts. No test-split run until the final milestone-style run is chosen again.
- Model calls: none to build. Measuring: the 11 flipped dev questions judged once is about $0.06; the must-abstain set three times (only flips cost anything) under $0.02; the 13-question casual held-out set (`docs/casual-holdout.md`) about $0.07. **About $0.15 in total**, ceiling $0.30.

**Fix 2 (rank 2): a fixed list of word equivalents added to the query before embedding** (fixes B, and a little of A).
- What: a small `config/query_aliases.yaml` (head or director -> chair; give up my seat -> drop; fafsa -> financial aid application; payment plan -> installment plan tuition) appended to the search text only (the answer step still sees the student's own words). Plain code, no model call.
- Files: `src/cta/graph/clean.py` or `src/cta/index/search.py`, the new yaml, tests.
- Risk: it is written knowing the failures, so it may fit the dev set rather than the next casual question; it changes the embedding of every question that contains a listed word. It raises similarity for questions that must still abstain (q45 sits at 0.567), so it should not be combined with a lower cutoff.
- Cost to measure: retrieval only, no answers: embeddings of about 120 changed queries, under $0.01.

**Fix 3 (rank 3): strip emotional filler with code** (fixes C: q110, q111, q113).
- What: remove a leading or trailing feeling clause (a clause with "lol", "so bad", "drowning", "stressing", and similar) before the search, keeping the clause that holds a question word or a topic word. Plain code with a short word list.
- Files: `src/cta/graph/clean.py`, tests.
- Risk: q110 has no comma, so a clause split does not work for it; a word list written from three questions may not generalize; a wrong cut loses the topic. It does not help A, B or D.
- Cost to measure: retrieval only, under $0.01.

Considered and not proposed again: the model-written query rewrite (E1) was rejected twice (`docs/decisions.md`, casual round); lowering the cutoff for everyone would let q45 (0.567) through; a short-query prefix on the embedding text would raise the similarity of out-of-scope questions too.

## 4. The five casual questions that pass by rule

| id | question | how it passes | hidden wording problem? |
|---|---|---|---|
| q109 | when is it due | the CLARIFY rule asks which deadline | None. The fixed question is the intended result. |
| q112 | what would you do, take a payment plan or pay all | the NO ADVICE route (advice cue "what would you do") gives rules and dates | One to note: this route builds its own fixed query, so it never meets the cutoff (the question's own best similarity is 0.457). It is correct because of the cue, not because of retrieval. Without the cue ("take a payment plan or pay it all?") it would be refused like q107. |
| q114 | whats the last day to drop a class fall 2026 | the calendar drop-family rule lists the three grade-related rows | None for wording; the known trade-off (refund rows left out, owner grade for q74) applies. |
| q121 | what is the email of my math professor | must abstain; refused at similarity 0.534, reranker top score 5 | The refusal rests on the cutoff, so any change that lowers it (Fix 1 included) must keep this one under its minimum score (5 against 8). |
| q122 | do i have a hold on my account and what is my balance | must abstain; account words route it to the personal-account reply; similarity 0.459 | Also rests on the cutoff plus the account cues; the reranker top score is 7, one point under the proposed minimum of 8. |

Summary: the passing five do not hide wording failures, but q121 and q122 are protected by the same cutoff that refuses the ten, so a fix for the ten has to be measured against them first.
