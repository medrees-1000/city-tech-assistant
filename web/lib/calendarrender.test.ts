// The page shows the calendar text written by cta.graph.render. The fixtures are written by the
// Python renderer (tests/test_calendar_layout.py keeps them identical to its output).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Inline } from "./markdown.ts";
import { parseBlocks } from "./markdown.ts";

const fixture = (name: string): string =>
  readFileSync(new URL(`./testdata/${name}`, import.meta.url), "utf8").trimEnd();
const cites = (n: number) => Array.from({ length: n }, (_, i) => ({ n: i + 1 }));
const flat = (items: Inline[]): string =>
  items.map((x) => (x.type === "text" ? x.text : x.type === "cite" ? x.label : flat(x.children))).join("");

test("Winter start and end: a bullet list with the date in bold and a real [n] link, then the provenance paragraph", () => {
  const blocks = parseBlocks(fixture("calendar_winter_start_end.md"), cites(2));
  assert.deepEqual(blocks.map((b) => b.type), ["ul", "p"]);
  const list = blocks[0];
  assert.ok(list.type === "ul" && list.items.length === 2);
  list.items.forEach((item, i) => {
    assert.equal(item[0].type, "bold");
    assert.deepEqual(item[item.length - 1], { type: "cite", n: i + 1, label: `[${i + 1}]` });
  });
  assert.equal(flat([list.items[0][0]]), "Monday, January 4, 2027");
  assert.equal(
    flat((blocks[1] as { inlines: Inline[] }).inlines),
    "From the Winter 2027 calendar (winter_2027.pdf, last updated 2026-07-27). The calendar can change.",
  );
});

test("one row with an assumed term: three paragraphs, the date in bold in the middle one", () => {
  const blocks = parseBlocks(fixture("calendar_one_row.md"), cites(1));
  assert.deepEqual(blocks.map((b) => b.type), ["p", "p", "p"]);
  const row = (blocks[1] as { inlines: Inline[] }).inlines;
  assert.equal(row[0].type, "bold");
  assert.equal(flat(row), "Friday, November 6, 2026: Last day to withdraw from a course with a grade of W. [1]");
});

test("two calendars and a TBA row: two lists, each followed by its own provenance paragraph", () => {
  const blocks = parseBlocks(fixture("calendar_two_terms_tba.md"), cites(3));
  assert.deepEqual(blocks.map((b) => b.type), ["ul", "p", "ul", "p"]);
  const second = blocks[2];
  assert.ok(second.type === "ul" && second.items.length === 2);
  const tba = flat(second.items[1]);
  assert.ok(tba.startsWith("87th Commencement Ceremony: not announced yet [3] Contact the Registrar:"));
  assert.notEqual(second.items[1][0].type, "bold"); // no date, so no bold date
  assert.ok(flat((blocks[1] as { inlines: Inline[] }).inlines).startsWith("From the Fall 2026 calendar"));
  assert.ok(flat((blocks[3] as { inlines: Inline[] }).inlines).startsWith("From the Spring 2027 calendar"));
});
