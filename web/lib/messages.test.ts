import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { AskResponse } from "./api.ts";
import { response } from "./testdata.ts";
import {
  answerView,
  canSend,
  finishTurn,
  fitTextarea,
  isEmpty,
  isLoading,
  MAX_HEIGHT,
  MIN_HEIGHT,
  PERSONAL_ACCOUNT_TEXT,
  PERSONAL_ACCOUNT_TEXT_NO_CARD,
  showContact,
  sourceDomId,
  startTurn,
} from "./messages.ts";

const data = (over: Partial<AskResponse> = {}): AskResponse => response(over);

test("a new conversation is empty; a turn adds the question and a loading placeholder", () => {
  assert.equal(isEmpty([]), true);
  const list = startTurn([], 1, "When?");
  assert.equal(isEmpty(list), false);
  assert.deepEqual(list.map((m) => [m.id, m.role]), [[1, "user"], [2, "assistant"]]);
  assert.equal(isLoading(list), true);
});

test("finishing a turn fills the placeholder and leaves the other messages alone", () => {
  const first = finishTurn(startTurn([], 1, "a"), 2, { ok: true, data: data() });
  const second = startTurn(first, 3, "b");
  const done = finishTurn(second, 4, {
    ok: false,
    error: { code: "x", message: "Nope", request_id: "r2" },
  });
  const a = done.find((m) => m.id === 2);
  const b = done.find((m) => m.id === 4);
  assert.ok(a && a.role === "assistant" && a.turn.status === "done");
  assert.ok(b && b.role === "assistant" && b.turn.status === "error");
  assert.equal(isLoading(done), false);
});

test("finishing an unknown id changes nothing; the input list is not mutated", () => {
  const list = startTurn([], 1, "a");
  const out = finishTurn(list, 99, { ok: true, data: data() });
  assert.deepEqual(out, list);
  assert.equal(isLoading(list), true);
});

test("canSend needs text, no more than the limit and no request in flight", () => {
  assert.equal(canSend("hi", false, 500), true);
  assert.equal(canSend("   ", false, 500), false);
  assert.equal(canSend("hi", true, 500), false);
  assert.equal(canSend("x".repeat(501), false, 500), false);
  assert.equal(canSend("x".repeat(500), false, 500), true);
});

test("source ids are unique per answer", () => {
  assert.notEqual(sourceDomId(2, 1), sourceDomId(4, 1));
  assert.equal(sourceDomId(2, 3), "source-2-3");
});

test("the textarea is one line high when empty or short", () => {
  assert.deepEqual(fitTextarea(0), { height: MIN_HEIGHT, scroll: false });
  assert.deepEqual(fitTextarea(40), { height: MIN_HEIGHT, scroll: false });
  assert.equal(MIN_HEIGHT, 52);
});

test("the textarea grows with its content up to six lines, then scrolls", () => {
  assert.deepEqual(fitTextarea(100), { height: 100, scroll: false });
  assert.deepEqual(fitTextarea(MAX_HEIGHT), { height: MAX_HEIGHT, scroll: false });
  assert.deepEqual(fitTextarea(MAX_HEIGHT + 1), { height: MAX_HEIGHT, scroll: true });
  assert.deepEqual(fitTextarea(900), { height: MAX_HEIGHT, scroll: true });
  assert.equal(MAX_HEIGHT, 172);
});

test("a normal answer is its own text", () => {
  assert.deepEqual(answerView(data()), { kind: "answer", text: "Because. [1]" });
});

test("a normal abstention shows the API text as a plain message (no label, no box)", () => {
  const v = answerView(data({ abstained: true, answer_type: "abstain", abstain_reason: "below_threshold", answer: "I could not find this." }));
  assert.deepEqual(v, { kind: "abstain", text: "I could not find this." });
});

test("a personal-account abstention shows the fixed sentence, not the API text", () => {
  const v = answerView(data({ abstained: true, answer_type: "abstain", abstain_reason: "personal_account", answer: "model words", contact: card }));
  assert.equal(v.kind, "personal_account");
  assert.equal(v.text, PERSONAL_ACCOUNT_TEXT);
  assert.ok(v.text.startsWith("I can't answer questions about your personal account"));
  assert.ok(v.text.endsWith("Here is who can help:"));
});

test("a personal_account code on an answer that did not abstain is ignored", () => {
  const v = answerView(data({ abstain_reason: "personal_account" }));
  assert.equal(v.kind, "answer");
});

test("not announced and clarify keep their kind and their text, with no label", () => {
  const v = answerView(data({ answer_type: "not_announced", answer: "Not yet [1]" }));
  assert.deepEqual(v, { kind: "not_announced", text: "Not yet [1]" });
  assert.equal(answerView(data({ answer_type: "clarify" })).kind, "clarify");
});

const card = { office: "registrar", name: "the Registrar", emails: [], phones: [], note: null };

test("the contact card is shown only when the API sent a contact", () => {
  assert.equal(showContact(data({ contact: card })), true);
  assert.equal(showContact(data({ contact: null })), false);
});

test("an abstention with no contact is a plain abstain box: its own text, no card", () => {
  const d = data({ abstained: true, answer_type: "abstain", abstain_reason: "below_threshold", answer: "I could not find this.", contact: null });
  assert.equal(showContact(d), false);
  assert.deepEqual(answerView(d), { kind: "abstain", text: "I could not find this." });
});

test("a personal-account abstention with a card says who can help; without a card it does not point at one", () => {
  const base = { abstained: true, answer_type: "abstain" as const, abstain_reason: "personal_account" };
  assert.equal(answerView(data({ ...base, contact: card })).text, PERSONAL_ACCOUNT_TEXT);
  const without = answerView(data({ ...base, contact: null }));
  assert.equal(without.text, PERSONAL_ACCOUNT_TEXT_NO_CARD);
  assert.ok(!without.text.includes("Here is who can help"));
});

test("the stylesheet leaves no bottom margin under the last block of an answer (no gap without a card) and has no abstain or teal box", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.answer-text > :last-child\s*\{\s*margin-bottom:\s*0;/);
  assert.doesNotMatch(css, /answer-card|answer-abstain|answer-not_announced|answer-personal_account/);
});

test("the conversation area and the page leave room under the last line for the sticky input bar", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const thread = css.match(/\.thread\s*\{[^}]*padding:\s*[\d.]+(?:rem)?\s+[\d.]+(?:rem)?\s+([\d.]+)rem/);
  assert.ok(thread && Number(thread[1]) >= 2.5, "the bottom padding of .thread must be at least 2.5rem");
  const scroll = css.match(/scroll-padding-bottom:\s*([\d.]+)rem/);
  assert.ok(scroll && Number(scroll[1]) >= 12, "scroll-padding-bottom must clear the input bar");
});
