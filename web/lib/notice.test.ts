import assert from "node:assert/strict";
import { test } from "node:test";

import { FOOTER_LINE, footerNotice, NOTICE_AFTER_FIRST } from "./notice.ts";

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
