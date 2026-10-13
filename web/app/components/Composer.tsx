"use client";

import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";

import { fitTextarea } from "../../lib/messages";

type Props = {
  value: string;
  max: number;
  disabled: boolean; // a request is in flight
  canSend: boolean;
  onChange: (text: string) => void;
  onSend: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
};

/** One-line input that grows with its text (up to about six lines, then scrolls). Enter sends,
 * Shift+Enter adds a line; the send button sits inside the input. */
export function Composer({ value, max, disabled, canSend, onChange, onSend, inputRef }: Props) {
  const own = useRef<HTMLTextAreaElement | null>(null);
  const ref = inputRef ?? own;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const { height, scroll } = fitTextarea(el.scrollHeight);
    el.style.height = `${height}px`;
    el.style.overflowY = scroll ? "auto" : "hidden";
  }, [value, ref]);

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSend();
      }}
    >
      <label htmlFor="question" className="sr-only">
        Your question
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={1}
        maxLength={max}
        value={value}
        placeholder="Ask about City Tech…"
        aria-describedby="fine-print"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSend();
          }
        }}
      />
      <button type="submit" className="send" disabled={!canSend} aria-label={disabled ? "Sending" : "Send question"}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 19V5" />
          <path d="M5 12l7-7 7 7" />
        </svg>
      </button>
      {value.length >= max - 100 ? (
        <p className="counter muted small" aria-live="polite">
          {value.length} / {max}
        </p>
      ) : null}
    </form>
  );
}
