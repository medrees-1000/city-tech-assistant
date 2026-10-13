# Architecture: the router graph (Phase 3, step 4a)

The graph is built with LangGraph (`src/cta/graph/build.py`, `langgraph==1.2.14`, reason in `docs/decisions.md`). It is only used when `router.mode` is `"on"`;
with `"off"` (the default) `cta.answer.answer` runs directly, exactly as before. The diagram below is generated from the compiled graph
(`build_graph(...).get_graph().draw_mermaid()`) and a test checks that it is still the current one. Dotted arrows are conditional edges.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	classify(classify)
	calendar(calendar)
	chain(chain)
	retrieve(retrieve)
	__end__([<p>__end__</p>]):::last
	__start__ --> classify;
	calendar -.-> __end__;
	calendar -.-> retrieve;
	chain -.-> __end__;
	chain -.-> retrieve;
	classify -.-> calendar;
	classify -.-> chain;
	classify -.-> retrieve;
	retrieve --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

## What each node does

- **classify**: one model call (the answer model, temperature 0, JSON) returning `{"intent": "calendar" | "other", "term_mention": ...}`. A failed or unusable reply counts as `other` (the old pipeline must not be blocked by the router).
- **calendar** (conditional edge from `classify` when the intent is `calendar`):
  1. `terms.resolve_term` (plain code) turns the words the student used into a calendar: explicit term, season resolved against `eval.today`, no mention (the current term, stated in the answer), or an unsupported term (no calendar). An unsupported label is searched in the event text of every row (the q73 pattern); no match means abstain with the Registrar contact.
  2. `select.select_rows` (one model call) chooses row ids from the term's rows (link rows removed). Ids outside the pool are dropped and counted.
  3. `render.render_rows` (plain code, the only code that writes dates) writes the answer from the row fields and numbers the rows `[1]`, `[2]` ... as sources.
  - A valid empty selection for a supported term goes on to **retrieve** (Amendment 1). A failed or malformed selector call, an unsupported term with no usable row, or a selection whose ids are all outside the pool abstains (`ABSTAIN: ...` plus the Registrar contact).
- **chain** (step 4b; `router.chain` is `on` by default since step 4b-final, and `off` removes the third classifier intent so this node is unreachable; with it on the classifier has a third intent, `prerequisite`): `chain.extract_course` takes exactly one course code or one exact unique course title from the question (else the question falls through to **retrieve**, route `chain_fallthrough`); a code with no record in the four departments abstains; otherwise the `prerequisite_chain` LangChain `@tool` walks the catalog prerequisite text (plain, deterministic code: breadth-first, depth at most 4, at most 15 courses, exclusions not followed, UNPARSED text verbatim) and a chain answer step writes the answer from the numbered course records (route `chain`).
- **chain** (step 4b; `router.chain` is `on` by default since step 4b-final, and `off` removes the third classifier intent so this node is unreachable; with it on the classifier has a third intent, `prerequisite`): `chain.extract_course` takes exactly one course code or one exact unique course title from the question (else the question falls through to **retrieve**, route `chain_fallthrough`); a code with no record in the four departments abstains; otherwise the `prerequisite_chain` LangChain `@tool` walks the catalog prerequisite text (plain, deterministic code: breadth-first, depth at most 4, at most 15 courses, exclusions not followed, UNPARSED text verbatim) and a chain answer step writes the answer from the numbered course records (route `chain`).
- **retrieve**: the existing pipeline, unchanged (`cta.answer.answer`: vector top 20, rerank, top 5, abstain threshold, answer model).

## Routes written to `request_logs` (columns `route` and `router`)

`calendar`, `other`, `abstain` (the calendar node refused, or the chain node found no record), `calendar_fallthrough` (the calendar node found no row and retrieve answered), `chain`, `chain_fallthrough`. The `router` column holds the classifier and selector tokens, cost and latency, the invalid ids and the weekday mismatches.

Steps 4b (prerequisite chain) and 4c (contact lookup) add tool nodes next to `calendar`.

## Selector versions (step 4a-2)

The graph above is unchanged. The calendar node's selector has two versions (`router.selector`, default 2): version 1 chooses from the rows of the resolved term; version 2 (default) chooses from the rows of all three calendars, each line showing its term, with a stricter prompt, so a question like "register next spring" can use rows that sit in the Fall 2026 calendar. The unsupported-term path always uses version 1. The renderer names each row's own calendar in its source line.
