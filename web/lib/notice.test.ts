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
