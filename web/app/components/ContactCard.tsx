import { useId } from "react";

import type { Contact } from "../../lib/api";
import { telHref, withUrls } from "../../lib/segments";

export function ContactCard({ contact }: { contact: Contact }) {
  const titleId = useId();
  return (
    <section className="card contact" aria-labelledby={titleId}>
      <h3 id={titleId} className="card-title">
        Contact {contact.name}
      </h3>
      <ul className="contact-list">
        {contact.emails.map((e) => (
          <li key={e.address}>
            <a href={`mailto:${e.address}`}>{e.address}</a>
            {e.for ? <span className="muted"> ({e.for})</span> : null}
          </li>
        ))}
        {contact.phones.map((p) => (
          <li key={p}>
            <a href={telHref(p)}>{p}</a>
          </li>
        ))}
      </ul>
      {contact.note ? (
        <p className="muted small">
          {withUrls(contact.note).map((piece, i) =>
            piece.type === "url" ? (
              <a key={i} href={piece.url} target="_blank" rel="noopener noreferrer">
                {piece.url}
              </a>
            ) : (
              <span key={i}>{piece.text}</span>
            ),
          )}
        </p>
      ) : null}
    </section>
  );
}
