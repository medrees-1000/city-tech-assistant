import assert from "node:assert/strict";
import { test } from "node:test";

import { segments, telHref, withUrls } from "./segments.ts";

const cites = [{ n: 1 }, { n: 2 }];

test("plain text stays one text segment", () => {
  assert.deepEqual(segments("No markers here.", cites), [{ type: "text", text: "No markers here." }]);
});

test("a marker with a matching citation becomes a cite segment", () => {
  assert.deepEqual(segments("Due Friday [1].", cites), [
    { type: "text", text: "Due Friday " },
    { type: "cite", n: 1, label: "[1]" },
    { type: "text", text: "." },
  ]);
});

test("adjacent markers stay separate and keep their order", () => {
  assert.deepEqual(segments("Both [1][2]", cites), [
    { type: "text", text: "Both " },
    { type: "cite", n: 1, label: "[1]" },
    { type: "cite", n: 2, label: "[2]" },
  ]);
});

test("a marker with no matching citation is plain text and merges with its neighbours", () => {
  assert.deepEqual(segments("Odd [7] marker", cites), [{ type: "text", text: "Odd [7] marker" }]);
});

test("no citations means no links", () => {
  assert.deepEqual(segments("Abstained [1]", []), [{ type: "text", text: "Abstained [1]" }]);
});

test("a marker at the very start or end", () => {
  assert.deepEqual(segments("[2] first, last [1]", cites), [
    { type: "cite", n: 2, label: "[2]" },
    { type: "text", text: " first, last " },
    { type: "cite", n: 1, label: "[1]" },
  ]);
});

test("the pieces always add up to the original text", () => {
  const text = "A [1] b [3] c [2][2] d";
  const joined = segments(text, cites)
    .map((s) => (s.type === "text" ? s.text : s.label))
    .join("");
  assert.equal(joined, text);
});

test("empty text gives no segments", () => {
  assert.deepEqual(segments("", cites), []);
});

test("withUrls finds an address and leaves trailing punctuation outside", () => {
  assert.deepEqual(withUrls("see https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx."), [
    { type: "text", text: "see " },
    { type: "url", url: "https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx" },
    { type: "text", text: "." },
  ]);
  assert.deepEqual(withUrls("no address"), [{ type: "text", text: "no address" }]);
});

test("withUrls ignores http and other schemes", () => {
  assert.deepEqual(withUrls("http://x.org javascript:alert(1)"), [
    { type: "text", text: "http://x.org javascript:alert(1)" },
  ]);
});

test("telHref keeps digits only and adds the US country code", () => {
  assert.equal(telHref("718-260-5800"), "tel:+17182605800");
  assert.equal(telHref("(718) 260 5800"), "tel:+17182605800");
});
