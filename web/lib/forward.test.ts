import assert from "node:assert/strict";
import { test } from "node:test";

import { ALLOWED_EMAIL_DOMAINS, apiTarget, forwardHeaders, gateFor, gateUser, PROXY_HEADER, REAL_IP_HEADER, USER_HEADER, VISITOR_HEADER, visitorAddress } from "./forward.ts";

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

test("x-cta-visitor carries the visitor address and replaces anything the client sent", () => {
  const out = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7", [VISITOR_HEADER]: "1.2.3.4, 5.6.7.8" }), "s");
  assert.equal(out.get(VISITOR_HEADER), "203.0.113.7");
  assert.equal(out.get(REAL_IP_HEADER), "203.0.113.7"); // the existing headers are unchanged
  const noAddress = forwardHeaders(h({ [VISITOR_HEADER]: "1.2.3.4" }), "s");
  assert.equal(noAddress.get(VISITOR_HEADER), null);
  const noSecret = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7", [VISITOR_HEADER]: "1.2.3.4" }), undefined);
  assert.equal(noSecret.get(VISITOR_HEADER), null);
});

const claims = (email: unknown, ...verified: unknown[]) => ({ email, email_verified: verified.length ? verified[0] : true });

test("signed out is sign_in_required; a verified Gmail address is allowed", () => {
  assert.equal(gateUser(null, claims("a@gmail.com")), "sign_in_required");
  assert.equal(gateUser(undefined, null), "sign_in_required");
  assert.equal(gateUser("user_1", claims("a@gmail.com")), "allowed");
});

test("the email is compared in lowercase; dots and +tags are not touched", () => {
  assert.equal(gateUser("user_1", claims("Some.One+tag@GMAIL.com")), "allowed");
});

test("only the exact domain list passes: googlemail.com, lookalikes and CUNY are refused", () => {
  assert.deepEqual(ALLOWED_EMAIL_DOMAINS, ["gmail.com"]);
  for (const e of ["a@googlemail.com", "a@gmail.com.evil.org", "a@notgmail.com", "a@mail.gmail.com", "@gmail.com", "gmail.com", "a@login.cuny.edu", ""]) {
    assert.equal(gateUser("user_1", claims(e)), "gmail_required", e);
  }
});

test("email_verified is accepted as true or \"true\" and nothing else", () => {
  assert.equal(gateUser("user_1", claims("a@gmail.com", true)), "allowed");
  assert.equal(gateUser("user_1", claims("a@gmail.com", "true")), "allowed");
  for (const v of [false, "false", "True", 1, null, undefined, "yes"]) {
    assert.equal(gateUser("user_1", claims("a@gmail.com", v)), "gmail_required", String(v));
  }
});

test("a missing email claim, a non-string email or missing claims never crash and are refused", () => {
  assert.equal(gateUser("user_1", { email_verified: true }), "gmail_required");
  assert.equal(gateUser("user_1", claims(42)), "gmail_required");
  assert.equal(gateUser("user_1", null), "gmail_required");
  assert.equal(gateUser("user_1", undefined), "gmail_required");
});

test("the Clerk user id goes in x-cta-user; a client-sent x-cta-user and x-cta-visitor are replaced", () => {
  const out = forwardHeaders(h({ "x-forwarded-for": "203.0.113.7", [USER_HEADER]: "user_evil", [VISITOR_HEADER]: "9.9.9.9" }), "s", "user_abc");
  assert.equal(out.get(USER_HEADER), "user_abc");
  assert.equal(out.get(VISITOR_HEADER), "203.0.113.7");
  const signedOut = forwardHeaders(h({ [USER_HEADER]: "user_evil" }), "s", null);
  assert.equal(signedOut.get(USER_HEADER), null);
});

test("cookie, authorization and every x-clerk-* header are stripped, for ask and feedback alike", () => {
  const incoming = h({
    cookie: "__session=abc", authorization: "Bearer t", "x-clerk-auth-token": "t", "X-Clerk-Auth-Status": "signed-in",
    "content-type": "application/json", "x-forwarded-for": "203.0.113.7",
  });
  for (const user of ["user_abc", null]) {
    const out = forwardHeaders(incoming, "s", user);
    assert.equal(out.get("cookie"), null);
    assert.equal(out.get("authorization"), null);
    assert.deepEqual([...out.keys()].filter((k) => k.startsWith("x-clerk-")), []);
    assert.equal(out.get("content-type"), "application/json");
  }
});

test("only /api/ask is gated: feedback is open to a signed-out visitor", () => {
  assert.equal(gateFor("/api/ask", null, null), "sign_in_required");
  assert.equal(gateFor("/api/feedback", null, null), "allowed");
  assert.equal(gateFor("/api/feedback", "user_1", claims("a@example.org")), "allowed");
});
