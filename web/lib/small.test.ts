import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { showDetails } from "./details.ts";
import { hiddenCount, shouldCollapse, toggleLabel, VISIBLE_ITEMS } from "./lists.ts";
import { FOOTER_LINE, footerNotice, NOTICE_AFTER_FIRST } from "./notice.ts";

// ---- the ?details=1 switch (was details.test.ts) ----

test("details=1 turns the panel on, with or without the question mark", () => {
  assert.equal(showDetails("?details=1"), true);
  assert.equal(showDetails("details=1"), true);
  assert.equal(showDetails("?a=b&details=1"), true);
});

test("no parameter, an empty string or another value keeps it off", () => {
  assert.equal(showDetails(""), false);
  assert.equal(showDetails("?"), false);
  assert.equal(showDetails("?a=b"), false);
  assert.equal(showDetails("?details=0"), false);
  assert.equal(showDetails("?details=true"), false);
  assert.equal(showDetails("?details="), false);
  assert.equal(showDetails("?detail=1"), false);
});

// ---- collapsing long lists (was lists.test.ts) ----

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

test("every paragraph, heading and list item of an answer renders with dir=\"auto\", so an Arabic note line is displayed right to left (tester round 1b, language round)", () => {
  const code = readFileSync(new URL("../app/components/AnswerText.tsx", import.meta.url), "utf8");
  assert.match(code, /<p key=\{i\} dir="auto">/);
  assert.match(code, /<h3 key=\{i\} className="answer-heading" dir="auto">/);
  assert.match(code, /<h4 key=\{i\} className="answer-heading" dir="auto">/);
  assert.match(code, /<li key=\{j\} dir="auto"/);
  assert.equal((code.match(/dir="auto"/g) ?? []).length, 4);
});

// ---- the privacy notice (was notice.test.ts) ----

test("the full notice shows on the landing screen and the short one after the first question", () => {
  assert.equal(footerNotice(0), "full");
  assert.equal(footerNotice(1), "short");
  assert.equal(footerNotice(2), "short");
  assert.equal(footerNotice(40), "short");
});

test("the short notice says AI, mistakes and the independence line, and leaves the link to the page", () => {
  assert.match(NOTICE_AFTER_FIRST, /is AI and can make mistakes\./);
  assert.ok(NOTICE_AFTER_FIRST.includes(FOOTER_LINE));
  assert.doesNotMatch(NOTICE_AFTER_FIRST, /What is saved/);
});

test("the notice says names are removed only where they can be detected, and still asks for no personal information", async () => {
  const { NOTICE_SHORT, NOTICE_POINTS } = await import("./notice.ts");
  assert.equal(
    NOTICE_SHORT,
    "Your questions are saved to improve this assistant, with emails, phone numbers, ID numbers and names removed where we can detect them. Please don't type personal information.",
  );
  assert.ok(NOTICE_POINTS.some((p) => p.includes("A name written another way may be saved")));
  assert.ok(NOTICE_POINTS.every((p) => !p.includes("removed only when it follows")));
  assert.ok(NOTICE_POINTS.some((p) => p.includes("saved for 30 days")));
});

test("the short line after the first question is unchanged", () => {
  assert.equal(
    NOTICE_AFTER_FIRST,
    "City Tech Assistant is AI and can make mistakes. Independent student project, not affiliated with City Tech or CUNY.",
  );
});

test("the details say what goes to LangSmith, what does not, who else keeps logs, and that our records hold no address", async () => {
  const { NOTICE_POINTS } = await import("./notice.ts");
  const all = NOTICE_POINTS.join("\n");
  assert.match(all, /also sent to LangSmith, a third-party tracing service/);
  assert.match(all, /LangSmith keeps them for 14 days/);
  assert.match(all, /Messages that the safety checks handle .* are not sent/);
  assert.match(all, /hosted on Vercel .* Amazon Web Services\. They keep ordinary server logs that may include IP addresses, under their own policies/);
  assert.match(all, /scrambled \(hashed\) form of the network address/);
  assert.match(all, /Sign-in is by an emailed code through Clerk/);
  assert.match(all, /Clerk sets the cookies needed to keep you signed in/);
  assert.match(all, /We use only the domain of your email to allow Gmail/);
  assert.match(all, /The assistant's own request records hold no network address\. Our hosts and Clerk may keep their own standard server logs/);
  assert.match(all, /Ids and emails are not stored in our logs/);
  assert.doesNotMatch(all, /no accounts|no cookies are stored/);
  assert.doesNotMatch(all, /Optional developer tracing is off by default/);
});
