import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

test("the tab titles no longer say '(unofficial)'", () => {
  const root = read("../app/layout.tsx");
  const chat = read("../app/chat/layout.tsx");
  assert.match(root, /title: "City Tech Assistant",/);
  assert.match(chat, /title: "Chat · City Tech Assistant"/);
  for (const src of [root, chat]) {
    assert.ok(!/title:[^\n]*\(unofficial\)/i.test(src));
  }
});
