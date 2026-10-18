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

test("the details say what goes to LangSmith, what does not, who else keeps logs, and that our records hold no address", async () => {
  const { NOTICE_POINTS } = await import("./notice.ts");
  const all = NOTICE_POINTS.join("\n");
  assert.match(all, /also sent to LangSmith, a third-party tracing service/);
  assert.match(all, /LangSmith keeps them for 14 days/);
  assert.match(all, /Messages that the safety checks handle .* are not sent/);
  assert.match(all, /hosted on Vercel .* Amazon Web Services\. They keep ordinary server logs that may include IP addresses, under their own policies/);
  assert.match(all, /scrambled \(hashed\) form of the network address/);
  assert.match(all, /no accounts/);
  assert.match(all, /No IP address and no cookies are stored/);
  assert.doesNotMatch(all, /Optional developer tracing is off by default/);
});
