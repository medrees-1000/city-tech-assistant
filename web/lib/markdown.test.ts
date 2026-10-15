import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { bindCitations, inlines, parseBlocks } from "./markdown.ts";
import type { Block, Inline } from "./markdown.ts";

const cites = [{ n: 1 }, { n: 2 }, { n: 3 }, { n: 7 }];
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

const h = (level: 3 | 4, ...inl: Inline[]): Block => ({ type: "h", level, inlines: inl });

test("# and ## are small level-3 headings, ### is level 4 (never a page title)", () => {
  assert.deepEqual(parseBlocks("# One", cites), [h(3, t("One"))]);
  assert.deepEqual(parseBlocks("## Two", cites), [h(3, t("Two"))]);
  assert.deepEqual(parseBlocks("### Level 0", cites), [h(4, t("Level 0"))]);
});

test("a heading followed by a list, then a paragraph", () => {
  assert.deepEqual(parseBlocks("### Level 1\n- MAT 1375 [1]\n- CST 1201\nDone", cites), [
    h(4, t("Level 1")),
    { type: "ul", items: [[t("MAT 1375 "), cite(1)], [t("CST 1201")]] },
    { type: "p", inlines: [t("Done")] },
  ]);
});

test("a heading ends the paragraph above it and needs no blank line", () => {
  assert.deepEqual(parseBlocks("text line\n## Next\nmore", cites), [
    { type: "p", inlines: [t("text line")] },
    h(3, t("Next")),
    { type: "p", inlines: [t("more")] },
  ]);
});

test("a # in the middle of a line, four hashes, and a # with no space stay text", () => {
  assert.deepEqual(parseBlocks("Room # 5 and C# code", cites), [{ type: "p", inlines: [t("Room # 5 and C# code")] }]);
  assert.deepEqual(parseBlocks("#### too deep", cites), [{ type: "p", inlines: [t("#### too deep")] }]);
  assert.deepEqual(parseBlocks("#nospace", cites), [{ type: "p", inlines: [t("#nospace")] }]);
  assert.deepEqual(parseBlocks("a\n# b", cites)[1], h(3, t("b"))); // but at the start of its own line it is one
  assert.deepEqual(parseBlocks("see - # x", cites), [{ type: "p", inlines: [t("see - # x")] }]);
});

test("a heading can hold a citation and bold text", () => {
  assert.deepEqual(parseBlocks("## Due **soon** [2]", cites), [h(3, t("Due "), bold(t("soon")), t(" "), cite(2))]);
  assert.deepEqual(parseBlocks("### **Level 0** [1]", cites), [h(4, bold(t("Level 0")), t(" "), cite(1))]);
});

test("HTML in a heading is text", () => {
  assert.deepEqual(parseBlocks("# <script>alert(1)</script>", cites), [h(3, t("<script>alert(1)</script>"))]);
});

test("the stylesheet gives headings small sizes", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const size = css.match(/\.answer-text \.answer-heading\s*\{[^}]*font-size:\s*([\d.]+)rem/);
  assert.ok(size && Number(size[1]) <= 1.25, "headings must not be page-title sized");
});

test("course-name headings use the body colour, bold, at body size", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const rule = css.match(/\.answer-text h4\.answer-heading\s*\{([^}]*)\}/);
  assert.ok(rule, "the h4 rule exists");
  assert.match(rule[1], /color:\s*var\(--text\)/);
  assert.match(rule[1], /font-weight:\s*(700|bold)/);
  const body = css.match(/\.answer-text\s*\{[^}]*font-size:\s*([\d.]+)rem/);
  const size = rule[1].match(/font-size:\s*([\d.]+)rem/);
  assert.ok(body && size && body[1] === size[1], "same size as the body text");
});

test("UI polish (b): a group heading (h3) is larger than a course heading (h4) and has a thin rule above, except as the first block", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const group = css.match(/\.answer-text h3\.answer-heading\s*\{([^}]*)\}/);
  const course = css.match(/\.answer-text h4\.answer-heading\s*\{([^}]*)\}/);
  assert.ok(group && course);
  const size = (rule: string) => Number(rule.match(/font-size:\s*([\d.]+)rem/)?.[1]);
  assert.ok(size(group[1]) > size(course[1]), "the group heading is larger than the course heading");
  assert.ok(size(group[1]) <= 1.25, "and still not page-title sized");
  assert.match(group[1], /border-top:\s*1px solid var\(--line\)/);
  assert.match(css, /\.answer-text > h3\.answer-heading:first-child\s*\{[^}]*border-top:\s*0/);
});

// ---- UI polish (d): a [n] marker never starts a line ----

const flat = (items: Inline[]): string =>
  items.map((i) => (i.type === "text" ? i.text : i.type === "cite" ? i.label : flat(i.children))).join("");

test("a marker is bound to the last word before it; the characters are unchanged", () => {
  const items = inlines("Last day to drop for 75% tuition refund. [7] Next", cites);
  const bound = bindCitations(items);
  assert.equal(flat(bound), flat(items));
  const group = bound.find((i) => i.type === "nowrap");
  assert.ok(group && group.type === "nowrap");
  assert.equal(flat(group.children), "refund. [7]");
  assert.deepEqual(bound[0], { type: "text", text: "Last day to drop for 75% tuition " });
});

test("consecutive markers and a bolded phrase stay together", () => {
  for (const text of ["A W is non-punitive. [3][1]", "A W is non-punitive. [3] [1]", "the **W grade** [2] applies"]) {
    const bound = bindCitations(inlines(text, cites));
    assert.equal(flat(bound), text.replaceAll("**", ""));
    for (const [i, item] of bound.entries()) {
      if (item.type === "cite") assert.fail(`a loose marker at ${i} in "${text}"`);
    }
  }
  const two = bindCitations(inlines("done. [3][1]", cites)).find((i) => i.type === "nowrap");
  assert.ok(two && two.type === "nowrap" && two.children.filter((c) => c.type === "cite").length === 2);
});

test("a marker with nothing before it, and an input without markers, are returned as they are", () => {
  assert.deepEqual(bindCitations(inlines("no markers here", cites)), inlines("no markers here", cites));
  assert.equal(flat(bindCitations(inlines("[1] first", cites))), "[1] first");
});

test("the input is not modified", () => {
  const items = inlines("word [1]", cites);
  const copy = JSON.stringify(items);
  bindCitations(items);
  assert.equal(JSON.stringify(items), copy);
});

test("the stylesheet makes the group nowrap", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.nowrap\s*\{\s*white-space:\s*nowrap;/);
});
