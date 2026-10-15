import assert from "node:assert/strict";
import { test } from "node:test";

import type { Citation } from "./api.ts";
import {
  abstainWhy,
  calendarLines,
  chainLines,
  consideredLines,
  describe,
  formatCents,
  formatMs,
  ordinal,
  routeWords,
  shownSources,
  stepLines,
  usageLines,
  weakNote,
  WEAK_MARGIN,
} from "./howfound.ts";
import { chunk, howFound, response } from "./testdata.ts";

const cite = (n: number, title: string): Citation => ({
  n, id: `c${n}`, title, url: null, file: null, doc_type: null, term: null, last_updated: null, excerpt: "", cited: true,
});

test("the route is said in words", () => {
  assert.equal(routeWords(response({ route: "calendar" })), "Looked up in the verified calendar");
  assert.equal(routeWords(response({ route: "calendar", abstained: true })), "Checked the verified calendar");
  assert.equal(routeWords(response({ route: "chain" })), "Looked up the prerequisites in the catalog");
  assert.equal(routeWords(response({ route: "chain", abstained: true })), "Looked for the course in the prerequisite data");
  assert.equal(routeWords(response({ route: "retrieve" })), "Searched City Tech pages and documents");
});

test("each abstain reason has its own sentence; an answer has none", () => {
  assert.equal(abstainWhy(response()), null);
  const why = (code: string, hf = howFound()) => abstainWhy(response({ abstained: true, abstain_reason: code, how_found: hf }));
  assert.match(why("below_threshold", howFound({ top_vector_similarity: 0.5403 })) ?? "", /below the confidence cutoff.*0\.54 against a confidence cutoff of 0\.59/);
  assert.match(why("model") ?? "", /found pages, but .* nothing in them/);
  assert.match(why("personal_account") ?? "", /personal account/);
  assert.match(why("calendar_no_row") ?? "", /No row of the calendar/);
  assert.match(why("calendar_unsupported_term") ?? "", /no calendar for that term/);
  assert.match(why("chain_no_record") ?? "", /no record of that course/);
  assert.match(why("calendar_selector_failed") ?? "", /did not return a usable result/);
  assert.match(why("something_new") ?? "", /did not answer/);
});

test("the threshold sentence is left out of the numbers when there is no similarity", () => {
  const w = abstainWhy(response({ abstained: true, abstain_reason: "below_threshold", how_found: howFound({ top_vector_similarity: null }) }));
  assert.equal(w, "The best match was below the confidence cutoff, so no answer was written.");
});

test("ordinals", () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 112].map(ordinal), ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "112th"]);
});

test("times: milliseconds under a second, seconds above", () => {
  assert.equal(formatMs(45.4), "45 ms");
  assert.equal(formatMs(999.4), "999 ms");
  assert.equal(formatMs(1000), "1.0 s");
  assert.equal(formatMs(3914), "3.9 s");
});

test("cost in cents", () => {
  assert.equal(formatCents(0), "0 cents");
  assert.equal(formatCents(0.00000001), "under 0.01 cents");
  assert.equal(formatCents(0.0004934), "0.05 cents");
  assert.equal(formatCents(0.0123), "1.2 cents");
  assert.equal(formatCents(0.25), "25 cents");
});

test("sources are listed in the order shown to the model (final rank), not the search order", () => {
  const hf = howFound({
    retrieved: [
      chunk({ id: "a", title: "A", first_stage_rank: 1, final_rank: 3, rerank_score: 0 }),
      chunk({ id: "b", title: "B", first_stage_rank: 2, final_rank: 2, rerank_score: 5 }),
      chunk({ id: "c", title: "C", first_stage_rank: 15, final_rank: 1, rerank_score: 10, similarity: 0.58 }),
      chunk({ id: "d", title: "D", first_stage_rank: 4, final_rank: 6, sent_to_answerer: false }),
    ],
  });
  assert.deepEqual(shownSources(hf).map((c) => c.id), ["c", "b", "a"]);
  const lines = consideredLines(response({ how_found: hf }));
  assert.equal(lines[0], "[1] C (search rank 15, similarity 0.58, re-check score 10 of 10)");
  assert.ok(lines[1].startsWith("[2] B (") && lines[2].startsWith("[3] A ("));
  assert.ok(lines.includes("1 more candidates were considered but not used."));
  assert.ok(lines.some((l) => l.includes("reordered")));
});

test("a source with no title shows its id; no score or similarity leaves those parts out", () => {
  const hf = howFound({ retrieved: [chunk({ id: "page/x#9", title: null, similarity: null, rerank_score: null, first_stage_rank: 1, final_rank: 1 })] });
  assert.deepEqual(consideredLines(response({ how_found: hf })), ["[1] page/x#9 (search rank 1)"]);
});

test("no candidates means no source lines", () => {
  assert.deepEqual(consideredLines(response()), []);
});

test("a weak best match is noted only when it is within the margin above the cutoff", () => {
  assert.equal(WEAK_MARGIN, 0.05);
  assert.match(weakNote(howFound({ top_vector_similarity: 0.61 })) ?? "", /weak \(similarity 0\.61, close to the cutoff of 0\.59\)/);
  assert.equal(weakNote(howFound({ top_vector_similarity: 0.64 })), null);
  assert.equal(weakNote(howFound({ top_vector_similarity: 0.8 })), null);
  assert.equal(weakNote(howFound({ top_vector_similarity: null })), null);
});

test("calendar: the term and how it was found, the pool size and the row used", () => {
  const data = response({
    route: "calendar",
    citations: [cite(1, "Fall 2026: Last day to withdraw")],
    how_found: howFound({ calendar: { term: "Fall 2026", term_status: "explicit", pool_size: 131, selected: ["fall-2026-040"] } }),
  });
  assert.deepEqual(calendarLines(data), [
    "Term: Fall 2026 (named in your question)",
    "Chosen from 131 calendar rows.",
    "Row used: Fall 2026: Last day to withdraw",
  ]);
  const assumed = response({ route: "calendar", how_found: howFound({ calendar: { term: "Fall 2026", term_status: "assumed" } }) });
  assert.match(calendarLines(assumed)[0], /assumed to be the current term/);
  assert.deepEqual(calendarLines(response()), []); // not a calendar answer
});

test("chain: the course, the courses followed with their numbers, no-record ones and the depth limit", () => {
  const data = response({
    route: "chain",
    citations: [cite(1, "City Tech course catalog: CST 3504 - Database Design"), cite(2, "City Tech course catalog: CST 1201 - Programming")],
    how_found: howFound({
      chain: { code: "CST 3504", course_count: 2, no_record_codes: ["ENG 1101"], truncated: true, unexpanded: [{ code: "MAT 1475", level: 4, names: ["MAT 1375"], reason: "depth limit" }] },
    }),
  });
  assert.deepEqual(chainLines(data), [
    "Course asked about: CST 3504",
    "Courses followed (2), in the order found:",
    "1. CST 3504 - Database Design",
    "2. CST 1201 - Programming",
    "No catalog record for: ENG 1101.",
    "The walk stopped at its depth limit.",
    "Not followed: MAT 1475 (level 4) names MAT 1375.",
  ]);
});

test("chain with no record at all", () => {
  const data = response({ route: "chain", abstained: true, abstain_reason: "chain_no_record", how_found: howFound({ chain: { code: "CST 4999", no_record: true } }) });
  assert.deepEqual(chainLines(data), ["Course asked about: CST 4999", "No catalog record for CST 4999."]);
});

test("times: steps in a fixed order, steps that did not run are left out, then the total", () => {
  const lines = stepLines(howFound({ stages_ms: { total: 3914, classify: 2122.2, select: 1769.9, retrieval: null, rerank: null, walk: null, answer: null, topic: null } }));
  assert.deepEqual(lines, ["Understanding the question: 2.1 s", "Choosing calendar rows: 1.8 s", "Total: 3.9 s"]);
  assert.ok(stepLines(howFound({ cache_hits: { embedding: true, rerank: true } })).at(-1)?.includes("reused"));
});

test("tokens and cost: totals, then the steps that cost something", () => {
  const lines = usageLines(howFound());
  assert.equal(lines[0], "Tokens: 2400 read by the model, 60 written.");
  assert.equal(lines[1], "Cost: 0.07 cents.");
  assert.equal(lines[2], "By step: understanding the question under 0.01 cents, re-checking 0.05 cents, writing 0.02 cents.");
});

test("a request with a single cost step has no 'By step' line", () => {
  const lines = usageLines(howFound({ cost_usd: { classify: 0.00004, total: 0.00004 } }));
  assert.equal(lines.length, 2);
});

test("describe: an answer from a search has route, sources, confidence, time and cost", () => {
  const data = response({ how_found: howFound({ top_vector_similarity: 0.61, retrieved: [chunk()] }) });
  const view = describe(data);
  assert.equal(view.summary, "Searched City Tech pages and documents");
  assert.deepEqual(view.sections.map((s) => s.title), [
    "What the assistant did",
    "Sources shown to the model, in the order it saw them",
    "Confidence",
    "Time",
    "Tokens and cost",
  ]);
});

test("describe: a threshold abstention says why and calls the matches 'not sent to the model'", () => {
  const data = response({ abstained: true, abstain_reason: "below_threshold", how_found: howFound({ top_vector_similarity: 0.54, retrieved: [chunk()] }) });
  const titles = describe(data).sections.map((s) => s.title);
  assert.ok(titles.includes("Why there is no answer"));
  assert.ok(titles.includes("Closest matches (below the cutoff, so not sent to the model)"));
  assert.ok(!titles.includes("Confidence"));
});

test("describe: calendar and chain answers have their own section and no source list", () => {
  const cal = describe(response({ route: "calendar", how_found: howFound({ calendar: { term: "Fall 2026", term_status: "explicit" } }) }));
  assert.ok(cal.sections.some((s) => s.title === "Calendar") && !cal.sections.some((s) => s.title.startsWith("Sources")));
  const ch = describe(response({ route: "chain", how_found: howFound({ chain: { code: "CST 3504" } }) }));
  assert.ok(ch.sections.some((s) => s.title === "Prerequisites"));
});

test("describe never invents data: with an empty how_found it shows only route, time and cost", () => {
  const view = describe(response({ how_found: howFound({ stages_ms: {}, tokens: {}, cost_usd: {} }) }));
  assert.deepEqual(view.sections.map((s) => s.title), ["What the assistant did", "Tokens and cost"]);
});

test("a step with no time did not happen and is not listed", () => {
  const lines = stepLines(howFound({ stages_ms: { classify: 900, answer: 0, rerank: 0.2, total: 900 } }));
  assert.deepEqual(lines, ["Understanding the question: 900 ms", "Total: 900 ms"]);
});

test("several courses asked: the panel lists all of them", () => {
  const data = response({
    route: "chain",
    how_found: howFound({ chain: { code: "CST 1204", extraction: "codes", detail: ["CST 1204", "CST 2403"] } }),
  });
  assert.equal(chainLines(data)[0], "Courses asked about: CST 1204, CST 2403");
  const one = response({ route: "chain", how_found: howFound({ chain: { code: "CST 3504", extraction: "code", detail: [] } }) });
  assert.equal(chainLines(one)[0], "Course asked about: CST 3504");
});

test("a clarify reply says it asked for more detail and shows no sources, prerequisites or calendar", () => {
  const data = response({
    answer_type: "clarify",
    route: "clarify",
    how_found: howFound({ route_detail: "clarify", intent: "calendar", top_vector_similarity: null }),
  });
  assert.equal(routeWords(data), "Asked for more detail");
  const view = describe(data);
  assert.equal(view.summary, "Asked for more detail");
  const titles = view.sections.map((s) => s.title);
  assert.deepEqual(titles, ["What the assistant did", "Time", "Tokens and cost"]);
});

test("a guardrail reply says it is a fixed message and shows no steps, times or costs", () => {
  const data = response({
    answer_type: "guardrail",
    route: "guardrail",
    how_found: howFound({ route_detail: "daily_cap", intent: null, top_vector_similarity: null }),
  });
  const view = describe(data);
  assert.equal(view.summary, "Replied with a fixed message");
  assert.deepEqual(view.sections.map((s) => s.title), ["What the assistant did"]);
});
