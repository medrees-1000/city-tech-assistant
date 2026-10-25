"use client";

import { Show, UserButton, useClerk } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ask, MAX_QUESTION_CHARS } from "../../lib/api";
import { showDetails } from "../../lib/details";
import { FOOTER_LINE, footerNotice, SIGN_IN_LINE } from "../../lib/notice";
import { canSend, dropTurn, finishTurn, isEmpty, isLoading, startTurn } from "../../lib/messages";
import type { Message } from "../../lib/messages";
import { AssistantMessage } from "../components/AssistantMessage";
import { Composer } from "../components/Composer";
import { PrivacyNotice } from "../components/PrivacyNotice";

// Questions that exist in the current data: a calendar row, a prerequisite list, a payment
// deadline, a department rule.
const EXAMPLES = [
  "When is the last day to withdraw from a class in Fall 2026?",
  "What are the prerequisites for CST 3504?",
  "When is my tuition bill due this fall?",
  "Do the science prerequisites for the Dental Hygiene program expire?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]); // in memory only; Clerk keeps the sign-in cookies
  const [text, setText] = useState("");
  const [details, setDetails] = useState(false); // ?details=1 shows the technical panel; read after mount
  const { openSignIn } = useClerk();
  const nextId = useRef(1);
  const epoch = useRef(0); // bumped by "New chat" so a late answer is dropped
  const input = useRef<HTMLTextAreaElement | null>(null);
  const end = useRef<HTMLDivElement | null>(null);
  const dock = useRef<HTMLDivElement | null>(null);
  const empty = isEmpty(messages);
  const loading = isLoading(messages);
  const notice = footerNotice(messages.length);

  // The input bar is sticky and its height changes (small screens, the notice, a longer input):
  // keep its real height in a CSS variable so scrolling to the newest answer always clears it.
  useEffect(() => {
    const el = dock.current;
    if (!el) return;
    const root = document.documentElement;
    const update = () => root.style.setProperty("--dock-h", `${el.getBoundingClientRect().height}px`);
    update();
    const watcher = new ResizeObserver(update);
    watcher.observe(el);
    return () => {
      watcher.disconnect();
      root.style.removeProperty("--dock-h");
    };
  }, [empty]);

  useEffect(() => {
    setDetails(showDetails(window.location.search));
  }, []);

  useEffect(() => {
    if (!empty) end.current?.scrollIntoView({ block: "end" });
  }, [messages, empty]);

  async function send(raw: string) {
    if (!canSend(raw, loading, MAX_QUESTION_CHARS)) return;
    const id = nextId.current;
    nextId.current += 2;
    const mine = epoch.current;
    setMessages((m) => startTurn(m, id, raw.trim()));
    setText("");
    const result = await ask(raw.trim());
    if (epoch.current !== mine) return;
    if (!result.ok && result.error.code === "sign_in_required") {
      setMessages((m) => dropTurn(m, id)); // not answered: keep what was typed and ask for sign-in
      setText(raw);
      openSignIn();
      return;
    }
    setMessages((m) => finishTurn(m, id + 1, result));
  }

  function newChat() {
    epoch.current += 1;
    setMessages([]);
    setText("");
    input.current?.focus();
  }

  return (
    <div className={empty ? "chat is-empty" : "chat"}>
      <header className="topbar">
        <Link href="/" className="brand">
          City Tech Assistant
        </Link>
        <div className="topbar-end">
          <button type="button" className="ghost" onClick={newChat} disabled={empty}>
            New chat
          </button>
          <Show when="signed-in">
            <UserButton />
          </Show>
        </div>
      </header>

      <main className="body">
        {empty ? (
          <div className="greeting">
            <h1>Hi! What would you like to know?</h1>
            <p>Registration, deadlines, advising, tuition and aid, and four departments.</p>
          </div>
        ) : (
          <section className="thread" role="log" aria-live="polite" aria-label="Conversation">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="msg msg-user">
                  <p className="bubble">{m.text}</p>
                </div>
              ) : (
                <AssistantMessage key={m.id} id={m.id} turn={m.turn} details={details} />
              ),
            )}
            <div ref={end} />
          </section>
        )}

        <div className="dock" ref={dock}>
          <Composer
            value={text}
            max={MAX_QUESTION_CHARS}
            disabled={loading}
            canSend={canSend(text, loading, MAX_QUESTION_CHARS)}
            onChange={setText}
            onSend={() => void send(text)}
            inputRef={input}
          />
          <p className="fine">{SIGN_IN_LINE}</p>
          {empty ? (
            <ul className="chips" aria-label="Example questions">
              {EXAMPLES.map((q) => (
                <li key={q}>
                  <button type="button" className="chip" disabled={loading} onClick={() => void send(q)}>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {notice === "full" ? (
            <p id="fine-print" className="fine">
              Each question is answered on its own; earlier messages are not remembered.
              <br />
              <span className="unofficial">{FOOTER_LINE}</span>
            </p>
          ) : null}
          <PrivacyNotice mode={notice} />
        </div>
      </main>
    </div>
  );
}
