import assert from "node:assert/strict";
import { test } from "node:test";

import { showDetails } from "./details.ts";

test("details=1 turns the panel on, with or without the question mark", () => {
  assert.equal(showDetails("?details=1"), true);
  assert.equal(showDetails("details=1"), true);
  assert.equal(showDetails("?a=b&details=1"), true);
});

test("no parameter, an empty string or another value keeps it off", () => {
  assert.equal(showDetails(""), false);
  assert.equal(showDetails("?"), false);
  assert.equal(showDetails("?a=b"), false);
  assert.equal(showDetails("?details=0"), false);
  assert.equal(showDetails("?details=true"), false);
  assert.equal(showDetails("?details="), false);
  assert.equal(showDetails("?detail=1"), false);
});
