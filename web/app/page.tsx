"use client";

import { useRef, useState } from "react";

import { ask, MAX_QUESTION_CHARS } from "../lib/api";
import type { ApiError, AskResponse } from "../lib/api";
import { AnswerView } from "./components/AnswerView";
import { ErrorView } from "./components/ErrorView";

// Questions that exist in the current data (a calendar row, a prerequisite chain, a payment
// deadline, a department rule).
const EXAMPLES = [
  "When is the last day to withdraw from a class in Fall 2026?",
  "What are the prerequisites for CST 3504?",
  "When is my tuition bill due this fall?",
  "Do the science prerequisites for the Dental Hygiene program expire?",
];

type View =
  | { state: "idle" }
  | { state: "loading"; question: string }
  | { state: "done"; data: AskResponse }
  | { state: "error"; error: ApiError };

export default function Page() {
  const [question, setQuestion] = useState("");
  const [view, setView] = useState<View>({ state: "idle" });
  const input = useRef<HTMLTextAreaElement>(null);
  const trimmed = question.trim();
  const loading = view.state === "loading";
  const canSubmit = trimmed.length > 0 && question.length <= MAX_QUESTION_CHARS && !loading;

  async function submit(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setView({ state: "loading", question: q });
    const result = await ask(q);
    setView(result.ok ? { state: "done", data: result.data } : { state: "error", error: result.error });
    input.current?.focus();
  }

  return (
    <main className="page">
      <header className="masthead">
        <h1>City Tech Assistant</h1>
        <p className="unofficial">Unofficial student project, not affiliated with City Tech.</p>
        <p className="lede">
          Ask about registration, deadlines, advising, tuition and aid, or the Computer Systems,
          Mathematics, Electrical and Telecommunications, and Dental Hygiene departments. Answers
          come only from City Tech pages and documents, with their sources.
        </p>
      </header>

      <form
        className="ask"
        onSubmit={(e) => {
          e.preventDefault();
          void submit(question);
        }}
      >
        <label htmlFor="question" className="label">
          Your question
        </label>
        <textarea
          id="question"
          ref={input}
          rows={3}
          maxLength={MAX_QUESTION_CHARS}
          value={question}
          placeholder="For example: When is the last day to withdraw in Fall 2026?"
          aria-describedby="counter"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit(question);
            }
          }}
        />
        <div className="ask-row">
          <span id="counter" className="muted small">
            {question.length} / {MAX_QUESTION_CHARS} · Enter to send, Shift+Enter for a new line
          </span>
          <button type="submit" disabled={!canSubmit}>
            {loading ? "Looking this up…" : "Ask"}
          </button>
        </div>
      </form>

      <div className="examples">
        <p className="muted small">Try an example:</p>
        <ul>
          {EXAMPLES.map((q) => (
            <li key={q}>
              <button
                type="button"
                className="example"
                disabled={loading}
                onClick={() => {
                  setQuestion(q);
                  void submit(q);
                }}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="result" aria-live="polite" aria-busy={loading}>
        {view.state === "loading" ? (
          <p className="loading muted">Looking this up in the City Tech sources…</p>
        ) : null}
        {view.state === "done" ? <AnswerView data={view.data} /> : null}
        {view.state === "error" ? <ErrorView error={view.error} /> : null}
      </div>

      {/* STEP 6: the logging notice ("Do not type personal information") goes here. Not built yet. */}
      <div id="log-notice-slot" hidden />
    </main>
  );
}
