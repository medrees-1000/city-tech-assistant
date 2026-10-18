import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ask, sendFeedback } from "./api.ts";
import { friendlyMessage } from "./errors.ts";

// ask() with a fake fetch: whatever the layers in front of the API answer, the visitor gets a plain
// sentence (never a blank, a status code, a stack trace or the raw body).
const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function fakeFetch(status: number, body: string, contentType = "text/html") {
  globalThis.fetch = (async () =>
    new Response(body, { status, headers: { "Content-Type": contentType } })) as typeof fetch;
}

async function shown(): Promise<string> {
  const result = await ask("when is the last day to drop?");
  assert.equal(result.ok, false);
  if (result.ok) throw new Error("unreachable");
  return friendlyMessage(result.error);
}

test("an HTML 502 or 504 from a proxy gets the unreachable or timeout sentence", async () => {
  fakeFetch(502, "<html><body>Bad Gateway</body></html>");
  assert.match(await shown(), /can't reach the assistant/);
  fakeFetch(504, "<html>Gateway Timeout</html>");
  assert.match(await shown(), /taking longer than expected/);
});

test("a 429 or 503 with any body gets the rate-limit or unavailable sentence", async () => {
  fakeFetch(429, "Too Many Requests");
  assert.match(await shown(), /asking quickly/);
  fakeFetch(503, "", "text/plain");
  assert.match(await shown(), /not available right now/);
  fakeFetch(503, JSON.stringify({ detail: "x" }), "application/json");
  assert.match(await shown(), /not available right now/);
});

test("the API's own error object still maps by its code", async () => {
  fakeFetch(502, JSON.stringify({ error: { code: "provider_error", message: "raw" }, request_id: "a" }), "application/json");
  assert.match(await shown(), /couldn't get an answer/);
});

test("a rejected request (403) and an unknown 4xx never show raw text", async () => {
  fakeFetch(403, "Forbidden");
  assert.match(await shown(), /could not be reached from here/);
  fakeFetch(418, "I am a teapot");
  const text = await shown();
  assert.doesNotMatch(text, /teapot|418/);
});

test("a network failure gets the unreachable sentence and a paused reply is an ordinary answer", async () => {
  globalThis.fetch = (async () => {
    throw new TypeError("Failed to fetch");
  }) as typeof fetch;
  assert.match(await shown(), /can't reach the assistant/);
  const paused = { answer: "The assistant is paused for the rest of this month ...", answer_type: "guardrail" };
  fakeFetch(200, JSON.stringify(paused), "application/json");
  const result = await ask("hello");
  assert.equal(result.ok, true);
});

test("feedback failures fall back to the fixed message", async () => {
  fakeFetch(502, "<html>bad</html>");
  const result = await sendFeedback("abc", "up");
  assert.equal(result.ok, false);
});
