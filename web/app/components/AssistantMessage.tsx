"use client";

import { useState } from "react";

import { answerView, showContact, sourceDomId } from "../../lib/messages";
import type { Turn } from "../../lib/messages";
import { AnswerText } from "./AnswerText";
import { ContactCard } from "./ContactCard";
import { ErrorView } from "./ErrorView";
import { Feedback } from "./Feedback";
import { HowFound } from "./HowFound";
import { SourceList } from "./SourceList";

export function AssistantMessage({ id, turn }: { id: number; turn: Turn }) {
  const [open, setOpen] = useState(false);

  function showSource(n: number) {
    setOpen(true);
    requestAnimationFrame(() => {
      const el = document.getElementById(sourceDomId(id, n));
      el?.scrollIntoView({ block: "nearest" });
      el?.focus();
    });
  }

  return (
    <div className="msg msg-assistant">
      <p className="who">Assistant</p>
      {turn.status === "loading" ? (
        <div role="status">
          <span className="sr-only">Looking this up in the City Tech sources…</span>
          <span className="dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </div>
      ) : null}
      {turn.status === "error" ? <ErrorView error={turn.error} /> : null}
      {turn.status === "done" ? <Done data={turn.data} id={id} open={open} setOpen={setOpen} onCite={showSource} /> : null}
    </div>
  );
}

function Done({
  data,
  id,
  open,
  setOpen,
  onCite,
}: {
  data: Extract<Turn, { status: "done" }>["data"];
  id: number;
  open: boolean;
  setOpen: (open: boolean) => void;
  onCite: (n: number) => void;
}) {
  const view = answerView(data);
  return (
    <>
      <AnswerText text={view.text} citations={data.citations} onCite={onCite} />
      {data.contact && showContact(data) ? <ContactCard contact={data.contact} /> : null}
      <Feedback requestId={data.request_id} />
      <SourceList assistantId={id} citations={data.citations} open={open} onToggle={setOpen} />
      <HowFound data={data} />
    </>
  );
}
