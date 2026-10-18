import assert from "node:assert/strict";
import { test } from "node:test";

import { CRISIS_LINE, codeForStatus, friendlyMessage, GENERIC, isTimeout } from "./errors.ts";

const err = (code: string, message = "raw text from the server") => ({ code, message, request_id: "abc123" });

test("every code the API or the page can produce has its own plain sentence", () => {
  for (const code of ["unreachable", "timeout", "unavailable", "provider_error", "too_large", "invalid_request", "invalid_question", "rate_limited", "daily_cap", "kill_switch", "monthly_cap", "forbidden"]) {
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
  assert.equal(friendlyMessage(err("daily_cap")), "The assistant has reached its limit for today. Please try again tomorrow. " + CRISIS_LINE);
  assert.equal(friendlyMessage(err("kill_switch")), "The assistant is temporarily paused. Please check back later. " + CRISIS_LINE);
});

test("isTimeout recognises a fetch timeout or abort and nothing else", () => {
  assert.equal(isTimeout(new DOMException("t", "TimeoutError")), true);
  assert.equal(isTimeout(new DOMException("a", "AbortError")), true);
  assert.equal(isTimeout(new TypeError("Failed to fetch")), false);
  assert.equal(isTimeout("nope"), false);
});

test("a status with no API error body maps to a friendly code: 429, 502, 503, 504 and 403", () => {
  assert.equal(codeForStatus(429), "rate_limited");
  assert.equal(codeForStatus(503), "unavailable");
  assert.equal(codeForStatus(504), "timeout");
  assert.equal(codeForStatus(502), "unreachable");
  assert.equal(codeForStatus(500), "unreachable");
  assert.equal(codeForStatus(403), "forbidden");
  assert.equal(codeForStatus(404), null);
});

test("every paused message carries the crisis line (988 and 911)", () => {
  for (const code of ["kill_switch", "daily_cap", "monthly_cap"]) {
    const text = friendlyMessage(err(code));
    assert.ok(text.endsWith(CRISIS_LINE), code);
    assert.match(text, /988/);
    assert.match(text, /911/);
  }
  for (const code of ["rate_limited", "timeout", "unreachable"]) {
    assert.ok(!friendlyMessage(err(code)).includes("988"), code);
  }
});
