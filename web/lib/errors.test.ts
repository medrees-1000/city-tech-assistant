import assert from "node:assert/strict";
import { test } from "node:test";

import { friendlyMessage, GENERIC, isTimeout } from "./errors.ts";

const err = (code: string, message = "raw text from the server") => ({ code, message, request_id: "abc123" });

test("every code the API or the page can produce has its own plain sentence", () => {
  for (const code of ["unreachable", "timeout", "unavailable", "provider_error", "too_large", "invalid_request", "invalid_question", "rate_limited", "daily_cap", "kill_switch"]) {
    const text = friendlyMessage(err(code));
    assert.notEqual(text, GENERIC, code);
    assert.doesNotMatch(text, /raw text|abc123|\b[45]\d\d\b|error|exception|traceback/i, code);
  }
});

test("an unknown code or a server error gets the generic sentence, never the server's text", () => {
  assert.equal(friendlyMessage(err("weird_code")), GENERIC);
  assert.equal(friendlyMessage(err("internal_error")), GENERIC);
});

test("the rate-limit, daily-cap and switched-off sentences match the API's own wording", () => {
  assert.equal(friendlyMessage(err("rate_limited")), "You're asking quickly. Please wait a moment and try again.");
  assert.equal(friendlyMessage(err("daily_cap")), "The assistant has reached its limit for today. Please try again tomorrow.");
  assert.equal(friendlyMessage(err("kill_switch")), "The assistant is switched off for now. Please check back later.");
});

test("isTimeout recognises a fetch timeout or abort and nothing else", () => {
  assert.equal(isTimeout(new DOMException("t", "TimeoutError")), true);
  assert.equal(isTimeout(new DOMException("a", "AbortError")), true);
  assert.equal(isTimeout(new TypeError("Failed to fetch")), false);
  assert.equal(isTimeout("nope"), false);
});
