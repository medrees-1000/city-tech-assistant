import assert from "node:assert/strict";
import { test } from "node:test";

import { apiTarget, forwardHeaders, PROXY_HEADER, REAL_IP_HEADER, visitorAddress } from "./forward.ts";

const h = (o: Record<string, string>) => new Headers(o);

test("the secret and the visitor address are added when a secret is configured", () => {
  const out = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7", "content-type": "application/json" }), "s3cret-value");
  assert.equal(out.get(PROXY_HEADER), "s3cret-value");
  assert.equal(out.get(REAL_IP_HEADER), "203.0.113.7");
  assert.equal(out.get("content-type"), "application/json");
});

test("x-forwarded-for (overwritten by Vercel) wins over x-real-ip; only its first entry counts", () => {
  assert.equal(visitorAddress(h({ "x-real-ip": "198.51.100.1", "x-forwarded-for": "203.0.113.7" })), "203.0.113.7");
  assert.equal(visitorAddress(h({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" })), "203.0.113.7");
  assert.equal(visitorAddress(h({ "x-real-ip": "198.51.100.1" })), "198.51.100.1");
  assert.equal(visitorAddress(h({})), null);
});

test("a visitor who sends their own x-real-ip cannot choose the address the API sees", () => {
  const out = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7", "x-real-ip": "1.2.3.4" }), "s");
  assert.equal(out.get(REAL_IP_HEADER), "203.0.113.7");
});

test("a header the visitor sends to forge the secret is replaced, never passed on", () => {
  const out = forwardHeaders(h({ [PROXY_HEADER]: "guess", "x-forwarded-for": "203.0.113.7" }), "real-secret");
  assert.equal(out.get(PROXY_HEADER), "real-secret");
  const none = forwardHeaders(h({ [PROXY_HEADER]: "guess", [REAL_IP_HEADER]: "1.1.1.1" }), undefined);
  assert.equal(none.get(PROXY_HEADER), null);
  assert.equal(none.get(REAL_IP_HEADER), null);
});

test("with no secret configured (local development) nothing is added", () => {
  const out = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7" }), undefined);
  assert.equal(out.get(PROXY_HEADER), null);
  assert.equal(out.get(REAL_IP_HEADER), null);
});

test("the target drops the /api prefix and keeps the query; the default is the local API", () => {
  assert.equal(apiTarget("/api/ask", "", "https://x.duckdns.org").href, "https://x.duckdns.org/ask");
  assert.equal(apiTarget("/api/feedback", "?a=1", undefined).href, "http://127.0.0.1:8000/feedback?a=1");
});
