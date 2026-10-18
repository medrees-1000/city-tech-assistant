import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { FOOTER_LINE } from "./notice.ts";

// The pages are .tsx (no JSX loader in node:test), so these tests read the page source; the built pages
// were also rendered in a browser when this change was made (docs/decisions.md).
const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

test("the landing page no longer shows the orange 'independent student project' pill", () => {
  const landing = read("../app/page.tsx");
  assert.ok(!landing.includes("FOOTER_LINE"));
  assert.ok(!landing.includes("Independent student project"));
  assert.ok(!landing.includes('className="unofficial"'));
  assert.ok(!landing.includes("<footer"));
});

test("the one-line footer under the chat box still renders, with the same words", () => {
  const chat = read("../app/chat/page.tsx");
  assert.ok(chat.includes("{FOOTER_LINE}"));
  assert.equal(FOOTER_LINE, "Independent student project, not affiliated with City Tech or CUNY");
  assert.ok(chat.includes('<PrivacyNotice mode={notice} />'));
});
