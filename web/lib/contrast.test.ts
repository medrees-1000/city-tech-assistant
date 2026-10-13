import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { contrast } from "./contrast.ts";

// Reads the two token blocks of app/globals.css: the light :root and the dark one inside the media query.
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) out[m[1]] = m[2];
  return out;
}

const dark = css.match(/prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}/)?.[1] ?? "";
const light = tokens(css.match(/:root\s*\{([^}]*)\}/)?.[1] ?? "");
const both: Record<string, Record<string, string>> = { light, dark: { ...light, ...tokens(dark) } };

// [foreground, background, minimum ratio]: 4.5 for text; 3 for the orange border against the page.
const TEXT_PAIRS: [string, string][] = [
  ["text", "bg"],
  ["text", "surface"],
  ["muted", "bg"],
  ["muted", "surface"],
  ["link", "bg"],
  ["link", "surface"],
  ["on-blue", "blue"],
  ["text", "abstain-bg"],
  ["abstain-text", "abstain-bg"],
  ["on-orange", "orange"],
  ["error-text", "error-bg"],
  ["text", "error-bg"],
  ["link", "abstain-bg"],
  ["muted", "abstain-bg"],
];

for (const theme of ["light", "dark"] as const) {
  test(`${theme}: every text pair reaches WCAG AA (4.5:1)`, () => {
    const t = both[theme];
    for (const [fg, bg] of TEXT_PAIRS) {
      assert.ok(t[fg] && t[bg], `missing token ${fg} or ${bg}`);
      const ratio = contrast(t[fg], t[bg]);
      assert.ok(ratio >= 4.5, `${theme}: ${fg} ${t[fg]} on ${bg} ${t[bg]} is ${ratio.toFixed(2)}`);
    }
  });
}

test("the brand colors are the ones in the branding guide", () => {
  assert.equal(light["blue"], "#007fa3");
  assert.equal(light["orange"], "#e17800");
});

test("orange is never used as text color on a light ground (3.05:1 on white)", () => {
  assert.ok(contrast(light["orange"], "#ffffff") < 4.5);
  assert.doesNotMatch(css, /[^-]color:\s*var\(--orange\)/);
});

test("the focus ring is visible against both grounds (3:1)", () => {
  for (const theme of ["light", "dark"] as const) {
    const t = both[theme];
    assert.ok(contrast(t["focus"], t["bg"]) >= 3, `${theme} focus on bg`);
    assert.ok(contrast(t["focus"], t["surface"]) >= 3, `${theme} focus on surface`);
  }
});
