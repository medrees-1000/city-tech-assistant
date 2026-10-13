import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canVote,
  feedbackMessage,
  finishVote,
  initialFeedback,
  isDisabled,
  isPressed,
  LABELS,
  startVote,
} from "./feedback.ts";
import type { FeedbackState } from "./feedback.ts";

const saved = (vote: "up" | "down"): FeedbackState => ({ vote, pending: null, status: "saved" });

test("nothing is chosen at first and there is no message", () => {
  assert.equal(isPressed(initialFeedback, "up"), false);
  assert.equal(isPressed(initialFeedback, "down"), false);
  assert.equal(feedbackMessage(initialFeedback), null);
  assert.equal(isDisabled(initialFeedback), false);
});

test("voting up: sending, then saved with the thanks", () => {
  const sending = startVote(initialFeedback, "up");
  assert.deepEqual(sending, { vote: null, pending: "up", status: "sending" });
  assert.equal(isPressed(sending, "up"), true); // shows at once
  assert.equal(isDisabled(sending), true);
  assert.equal(feedbackMessage(sending), "Saving…");
  const done = finishVote(sending, true);
  assert.deepEqual(done, saved("up"));
  assert.equal(isDisabled(done), false);
  assert.equal(feedbackMessage(done), "Thanks, noted");
});

test("changing the vote from up to down", () => {
  const sending = startVote(saved("up"), "down");
  assert.equal(isPressed(sending, "down"), true);
  assert.equal(isPressed(sending, "up"), false);
  assert.deepEqual(finishVote(sending, true), saved("down"));
});

test("choosing the same vote again sends nothing and changes nothing", () => {
  assert.equal(canVote(saved("up"), "up"), false);
  assert.deepEqual(startVote(saved("up"), "up"), saved("up"));
  assert.equal(canVote(saved("up"), "down"), true);
});

test("while a vote is in flight no other vote can start", () => {
  const sending = startVote(initialFeedback, "up");
  assert.equal(canVote(sending, "down"), false);
  assert.equal(startVote(sending, "down"), sending);
});

test("a failed vote goes back to the old vote and shows a plain error", () => {
  const failedFirst = finishVote(startVote(initialFeedback, "down"), false);
  assert.deepEqual(failedFirst, { vote: null, pending: null, status: "error" });
  assert.equal(isPressed(failedFirst, "down"), false);
  assert.match(feedbackMessage(failedFirst) ?? "", /could not be saved/);
  const failedChange = finishVote(startVote(saved("up"), "down"), false);
  assert.equal(failedChange.vote, "up");
  assert.equal(isPressed(failedChange, "up"), true);
  assert.equal(canVote(failedChange, "down"), true); // it can be tried again
});

test("finishing with nothing in flight changes nothing", () => {
  assert.equal(finishVote(initialFeedback, true), initialFeedback);
  assert.deepEqual(finishVote(saved("down"), false), saved("down"));
});

test("the button labels are the plain ones", () => {
  assert.deepEqual(LABELS, { up: "Good answer", down: "Wrong or unhelpful" });
});
