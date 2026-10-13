import assert from "node:assert/strict";
import { test } from "node:test";

import { inlines, parseBlocks } from "./markdown.ts";
import type { Block, Inline } from "./markdown.ts";

const cites = [{ n: 1 }, { n: 2 }];
const t = (text: string): Inline => ({ type: "text", text });
const cite = (n: number): Inline => ({ type: "cite", n, label: `[${n}]` });
const bold = (...children: Inline[]): Inline => ({ type: "bold", children });

test("plain text is one text node", () => {
  assert.deepEqual(inlines("Just words.", cites), [t("Just words.")]);
});

test("bold becomes a bold node between text", () => {
  assert.deepEqual(inlines("a **b** c", cites), [t("a "), bold(t("b")), t(" c")]);
});

test("two bold pairs in one line", () => {
  assert.deepEqual(inlines("**a** and **b**", cites), [bold(t("a")), t(" and "), bold(t("b"))]);
});

test("a citation inside bold and next to bold keeps its link", () => {
  assert.deepEqual(inlines("**due [1]** then [2]", cites), [bold(t("due "), cite(1)), t(" then "), cite(2)]);
});

test("an unmatched ** stays as text", () => {
  assert.deepEqual(inlines("**oops no close", cites), [t("**oops no close")]);
  assert.deepEqual(inlines("a ** b", cites), [t("a ** b")]);
  assert.deepEqual(inlines("**a** and **b", cites), [bold(t("a")), t(" and **b")]);
});

test("empty bold is text, not an empty bold node", () => {
  assert.deepEqual(inlines("a **** b", cites), [t("a **** b")]);
  assert.deepEqual(inlines("** ** x", cites), [t("** ** x")]);
});

test("HTML-looking input stays text (it is never turned into markup)", () => {
  const html = "<b>x</b> <script>alert(1)</script> <img src=x onerror=alert(1)>";
  assert.deepEqual(inlines(html, cites), [t(html)]);
  assert.deepEqual(inlines("**<i>x</i>**", cites), [bold(t("<i>x</i>"))]);
  const blocks = parseBlocks("- <a href=\"javascript:alert(1)\">x</a>", cites);
  assert.deepEqual(blocks, [{ type: "ul", items: [[t('<a href="javascript:alert(1)">x</a>')]] }]);
});

test("a marker with no matching citation is plain text inside bold too", () => {
  assert.deepEqual(inlines("**see [9]**", cites), [bold(t("see [9]"))]);
});

test("paragraphs are split at blank lines and keep their own line breaks", () => {
  const blocks = parseBlocks("one\ntwo\n\nthree", cites);
  assert.deepEqual(blocks, [
    { type: "p", inlines: [t("one\ntwo")] },
    { type: "p", inlines: [t("three")] },
  ]);
});

test("bullet lines form a list; text before and after stays in paragraphs", () => {
  const blocks = parseBlocks("Dates:\n- March 19 [1]\n- **July 20** to August 7\nDone.", cites);
  const expected: Block[] = [
    { type: "p", inlines: [t("Dates:")] },
    { type: "ul", items: [[t("March 19 "), cite(1)], [bold(t("July 20")), t(" to August 7")]] },
    { type: "p", inlines: [t("Done.")] },
  ];
  assert.deepEqual(blocks, expected);
});

test("a list ends at a blank line and a new one starts after it", () => {
  const blocks = parseBlocks("- a\n\n- b", cites);
  assert.deepEqual(blocks, [
    { type: "ul", items: [[t("a")]] },
    { type: "ul", items: [[t("b")]] },
  ]);
});

test("a dash without a space, an empty bullet and numbered lines are ordinary text", () => {
  assert.deepEqual(parseBlocks("-no space", cites), [{ type: "p", inlines: [t("-no space")] }]);
  assert.deepEqual(parseBlocks("- ", cites), [{ type: "p", inlines: [t("- ")] }]);
  assert.deepEqual(parseBlocks("1. first", cites), [{ type: "p", inlines: [t("1. first")] }]);
});

test("Windows line breaks work and empty text gives no blocks", () => {
  assert.deepEqual(parseBlocks("a\r\n- b\r\n", cites), [
    { type: "p", inlines: [t("a")] },
    { type: "ul", items: [[t("b")]] },
  ]);
  assert.deepEqual(parseBlocks("", cites), []);
  assert.deepEqual(parseBlocks("\n\n", cites), []);
});

test("the text of all nodes adds up to the input without the ** marks", () => {
  const flat = (xs: Inline[]): string =>
    xs.map((x) => (x.type === "text" ? x.text : x.type === "cite" ? x.label : flat(x.children))).join("");
  const text = "**a [1]** b ** c";
  assert.equal(flat(inlines(text, cites)), "a [1] b ** c");
});
