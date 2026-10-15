// The page shows the chain text written by cta.graph.chain_render. The fixtures are written by the
// Python renderer (tests/test_chain_render.py keeps them identical to its output).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Block, Inline } from "./markdown.ts";
import { inlines, parseBlocks } from "./markdown.ts";

const fixture = (name: string): string =>
  readFileSync(new URL(`./testdata/${name}`, import.meta.url), "utf8").trimEnd();
const cites = (n: number) => Array.from({ length: n }, (_, i) => ({ n: i + 1 }));

const flat = (items: Inline[]): string =>
  items.map((x) => (x.type === "text" ? x.text : x.type === "cite" ? x.label : flat(x.children))).join("");

test("CST 3504: a lead paragraph, then one small heading per course with its [n] link", () => {
  const blocks = parseBlocks(fixture("chain_cst3504.md"), cites(4));
  assert.equal(blocks[0].type, "p");
  const headings = blocks.filter((b): b is Extract<Block, { type: "h" }> => b.type === "h");
  assert.deepEqual(
    headings.map((h) => [h.level, flat(h.inlines)]),
    [
      [4, "CST 3504 — Database Design [1]"],
      [4, "CST 1204 — Database Systems Fundamentals [2]"],
      [4, "CST 1100 — Intro to Computer Systems [3]"],
      [4, "CST 1101 — Problem Solving Comp. Program [4]"],
    ],
  );
  // each heading ends with a real citation link, not plain text
  for (const [i, h] of headings.entries()) {
    const last = h.inlines[h.inlines.length - 1];
    assert.deepEqual(last, { type: "cite", n: i + 1, label: `[${i + 1}]` });
  }
});

test("CST 3504: bold labels, the courses named, and the catalog text exactly as written in quotes", () => {
  const blocks = parseBlocks(fixture("chain_cst3504.md"), cites(4));
  const paragraphs = blocks.filter((b): b is Extract<Block, { type: "p" }> => b.type === "p");
  const second = paragraphs[1].inlines;
  assert.equal(second[0].type, "bold");
  assert.equal(flat([second[0]]), "Courses named:");
  assert.equal(
    flat(second),
    'Courses named: CST 1204 (Database Systems Fundamentals)\nCatalog says: "PRE: CST 1204 C OR HIGHER"',
  );
  assert.ok(flat(paragraphs[2].inlines).includes('"PRE: CST 1100 & 1101"')); // the & is not touched
  assert.equal(flat(paragraphs[3].inlines), "No prerequisite listed in the catalog.");
});

test("MAT 2440: ten blocks and text with two spaces survive as written; a code without a record is marked once, in its Courses named line (UI polish 3a)", () => {
  const text = fixture("chain_mat2440.md");
  const blocks = parseBlocks(text, cites(10));
  assert.equal(blocks.filter((b) => b.type === "h").length, 10);
  const all = blocks.map((b) => (b.type === "p" ? flat(b.inlines) : b.type === "h" ? flat(b.inlines) : "")).join("\n");
  assert.ok(all.includes('"CUNY proficiency in mathematics.  High School Math GPA 70'));
  assert.ok(all.includes("MAT 1476 (no catalog record)"));
  assert.ok(!all.includes("No catalog record in the four departments")); // every code is marked above, so the closing line is left out
  assert.ok(!/level/i.test(text));
});

test("the whole fixture is shown as written: nothing is dropped or added except the ** and ### marks", () => {
  const text = fixture("chain_mat2440.md");
  const shown = parseBlocks(text, cites(10))
    .map((b) => (b.type === "ul" ? "" : flat(b.inlines)))
    .join("\n\n");
  const squeeze = (t: string) => t.replace(/\n+/g, "\n"); // block breaks may differ, the words may not
  assert.equal(squeeze(shown), squeeze(text.replace(/\*\*/g, "").replace(/^### /gm, "")));
});

test("catalog text holding markup characters WOULD be changed by the page (so the renderer refuses it)", () => {
  // bold: the ** marks vanish
  assert.deepEqual(inlines('"PRE: **MAT 1275**"', cites(2)).map((x) => x.type), ["text", "bold", "text"]);
  // a [1] in a catalog text becomes a citation link
  assert.ok(inlines('"see [1] first"', cites(2)).some((x) => x.type === "cite"));
  // a line starting with "- " becomes a list, a line starting with "#" becomes a heading
  assert.equal(parseBlocks('Catalog says: "a\n- item"', cites(1))[1].type, "ul");
  assert.equal(parseBlocks('Catalog says: "a\n# heading"', cites(1))[1].type, "h");
});

test("two courses: a section heading per asked course, then the course headings with numbers running on", () => {
  const blocks = parseBlocks(fixture("chain_cst1204_cst2403.md"), cites(6));
  const headings = blocks.filter((b): b is Extract<Block, { type: "h" }> => b.type === "h");
  assert.deepEqual(
    headings.map((h) => [h.level, flat(h.inlines)]),
    [
      [3, "Prerequisites for CST 1204"],
      [4, "CST 1204 — Database Systems Fundamentals [1]"],
      [4, "CST 1100 — Intro to Computer Systems [2]"],
      [4, "CST 1101 — Problem Solving Comp. Program [3]"],
      [3, "Prerequisites for CST 2403"],
      [4, "CST 2403 — Intro C++ Programming I [4]"],
      [4, "MAT 1275 — College Algebra/Trigonometry [5]"],
      [4, "MAT 1275CO — College Algebra & Trig w Coreq [6]"],
    ],
  );
  const course = headings.filter((h) => h.level === 4);
  for (const [i, h] of course.entries()) {
    assert.deepEqual(h.inlines[h.inlines.length - 1], { type: "cite", n: i + 1, label: `[${i + 1}]` });
  }
});

test("two courses: the shared course sentence is a plain paragraph and the no-record codes are marked in their lines (UI polish 3a)", () => {
  const text = fixture("chain_cst1204_cst2403.md");
  const paragraphs = parseBlocks(text, cites(6))
    .filter((b): b is Extract<Block, { type: "p" }> => b.type === "p")
    .map((p) => flat(p.inlines));
  assert.ok(paragraphs.includes("CST 1101 is already shown above."));
  assert.ok(!paragraphs.some((p) => p.startsWith("No catalog record in the four departments")));
  assert.ok(text.includes("MAT 1476 (no catalog record), EMT 1111 (outside the four departments I cover)")); // tester round 1b, 1a
  assert.ok(paragraphs[0].startsWith("Here are the prerequisites for CST 1204 and CST 2403, from the catalog:"));
  assert.ok(!/chain|level/i.test(text.replace(/"[^"]*"/g, "")));
});
