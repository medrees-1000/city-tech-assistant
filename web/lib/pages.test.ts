import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { FOOTER_LINE } from "./notice.ts";

// The pages are .tsx (no JSX loader in node:test), so these tests read the page source, the
// stylesheet and the icon as text; the built pages were also fetched from `next start` when these
// were written (docs/decisions.md).
const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

// ---- the favicon (was favicon.test.ts) ----

test("the favicon is an original SVG in the site's own colours with no text or institutional logo", () => {
  const svg = read("../app/icon.svg");
  const css = read("../app/globals.css");
  const teal = css.match(/--blue:\s*(#[0-9a-f]{6})/i)?.[1];
  assert.ok(teal && svg.toLowerCase().includes(teal.toLowerCase()), "teal accent from globals.css");
  assert.ok(svg.includes("#ffb35c") && css.toLowerCase().includes("#ffb35c"));
  assert.ok(!/<text|<image|<font/i.test(svg), "letters are drawn as paths, no font or embedded image");
  assert.ok(!/cuny|city tech|seal/i.test(svg.replace(/<!--[\s\S]*?-->/g, "")));
});

// ---- the landing page and the footer line (was landing.test.ts) ----

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

// ---- the tab titles (was titles.test.ts) ----

test("the tab titles no longer say '(unofficial)'", () => {
  const root = read("../app/layout.tsx");
  const chat = read("../app/chat/layout.tsx");
  assert.match(root, /title: "City Tech Assistant",/);
  assert.match(chat, /title: "Chat · City Tech Assistant"/);
  for (const src of [root, chat]) {
    assert.ok(!/title:[^\n]*\(unofficial\)/i.test(src));
  }
});
