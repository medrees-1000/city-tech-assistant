"use client";

import { useState } from "react";

import { NOTICE_AFTER_FIRST, NOTICE_POINTS, NOTICE_SHORT, NOTICE_TITLE } from "../../lib/notice";
import type { FooterNotice } from "../../lib/notice";

/** The text lives in lib/notice.ts. "full" (landing screen): one short line and an expandable
 * list. "short" (after the first question): one small line with the same "What is saved?" link,
 * which opens the same list. */
export function PrivacyNotice({ mode }: { mode: FooterNotice }) {
  const [open, setOpen] = useState(false);
  if (mode === "full") {
    return (
      <div className="privacy">
        <p>{NOTICE_SHORT}</p>
        <details>
          <summary>{NOTICE_TITLE}</summary>
          <ul>
            {NOTICE_POINTS.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </details>
      </div>
    );
  }
  return (
    <div className="privacy privacy-short">
      <p id="fine-print">
        {NOTICE_AFTER_FIRST}{" "}
        <button type="button" className="notice-link" aria-expanded={open} onClick={() => setOpen(!open)}>
          {NOTICE_TITLE}
        </button>
      </p>
      {open ? (
        <ul>
          {NOTICE_POINTS.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
