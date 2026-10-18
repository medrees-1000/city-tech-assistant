import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { FOOTER_LINE } from "./notice.ts";

// The pages are .tsx (no JSX loader in node:test), so these tests read the page source; the built pages
// were also fetched from `next start` when this change was made (docs/decisions.md).
const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

test("the landing page shows the orange 'independent student project' pill under the four cards", () => {
  const landing = read("../app/page.tsx");
  assert.ok(landing.includes('<p className="unofficial">{FOOTER_LINE}</p>'));
  assert.ok(landing.indexOf('className="topics"') < landing.indexOf('className="unofficial"'));
  assert.equal(FOOTER_LINE, "Independent student project, not affiliated with City Tech or CUNY");
});

test("the one-line footer under the chat box still renders, with the same words", () => {
  const chat = read("../app/chat/page.tsx");
  assert.ok(chat.includes('<span className="unofficial">{FOOTER_LINE}</span>'));
  assert.ok(chat.includes("<PrivacyNotice mode={notice} />"));
});

test("the pill's style is still the orange-outlined rounded one", () => {
  const css = read("../app/globals.css");
  const rule = css.match(/\.unofficial \{[^}]*\}/)?.[0] ?? "";
  assert.match(rule, /border: 1px solid var\(--orange\)/);
  assert.match(rule, /border-radius: 999px/);
});
