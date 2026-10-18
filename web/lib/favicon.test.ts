import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

test("the favicon is an original SVG in the site's own colours with no text or institutional logo", () => {
  const svg = read("../app/icon.svg");
  const css = read("../app/globals.css");
  const teal = css.match(/--blue:\s*(#[0-9a-f]{6})/i)?.[1];
  assert.ok(teal && svg.toLowerCase().includes(teal.toLowerCase()), "teal accent from globals.css");
  assert.ok(svg.includes("#ffb35c") && css.toLowerCase().includes("#ffb35c"));
  assert.ok(!/<text|<image|<font/i.test(svg), "letters are drawn as paths, no font or embedded image");
  assert.ok(!/cuny|city tech|seal/i.test(svg.replace(/<!--[\s\S]*?-->/g, "")));
});
