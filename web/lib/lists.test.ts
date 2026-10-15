import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { hiddenCount, shouldCollapse, toggleLabel, VISIBLE_ITEMS } from "./lists.ts";

test("only lists of more than five items collapse; the first five stay visible", () => {
  assert.equal(VISIBLE_ITEMS, 5);
  assert.deepEqual([0, 1, 5].map(shouldCollapse), [false, false, false]);
  assert.deepEqual([6, 10].map(shouldCollapse), [true, true]);
  assert.equal(hiddenCount(10), 5);
  assert.equal(hiddenCount(6), 1);
  assert.equal(hiddenCount(3), 0);
});

test("the toggle says how many items there are", () => {
  assert.equal(toggleLabel(10, false), "Show all 10 items");
  assert.equal(toggleLabel(10, true), "Show fewer");
});

test("the component keeps every item in the page text, hides the rest with the hidden attribute, and the toggle is a real button with aria-expanded and aria-controls", () => {
  const code = readFileSync(new URL("../app/components/AnswerText.tsx", import.meta.url), "utf8");
  assert.match(code, /<button[^>]*type="button"/);
  assert.match(code, /aria-expanded=\{open\}/);
  assert.match(code, /aria-controls=/);
  assert.match(code, /hidden=\{/); // collapsed items are hidden, not removed: the text is unchanged
  assert.match(code, /VISIBLE_ITEMS/);
});

test("the toggle has a visible keyboard focus style", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.list-toggle:focus-visible/);
});
